"""Host-neutral value model for ephemeral source-adapter candidate plans.

This module models candidate data and deterministic output only.  It does not
discover or execute adapters, retain a plan, interpret human decisions, or
define a durable decision-cache format.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import PurePosixPath
import re
from typing import Any

from .annotations import (
    annotation_companion,
    validate_annotation_companion,
    validate_stored_record,
)
from .canonical import canonical_json_bytes, canonical_yaml_bytes
from .errors import ConfigurationError


RECORD_ROOT = PurePosixPath("metadata/records")
ANNOTATION_ROOT = PurePosixPath("metadata/overlays/annotations")
RECORD_SUFFIXES = frozenset({".yaml", ".yml"})
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


class CandidateOperation(StrEnum):
    """The visible record operation represented by one candidate."""

    ADD = "add"
    MODIFY = "modify"
    DELETE = "delete"


class _ReadOnlyJsonMapping(Mapping[str, object]):
    """Expose detached values from one immutable canonical JSON mapping."""

    def __init__(self, value: Mapping[str, object]) -> None:
        self._encoded = canonical_json_bytes(value)
        decoded = json.loads(self._encoded)
        if not isinstance(decoded, dict):  # pragma: no cover - guarded by type
            raise AssertionError("canonical mapping did not decode to a mapping")
        self._keys = tuple(decoded)

    def __getitem__(self, key: str) -> object:
        decoded = json.loads(self._encoded)
        return decoded[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return False
        try:
            return self.to_dict() == json.loads(canonical_json_bytes(other))
        except (TypeError, ValueError):
            return False

    def __repr__(self) -> str:
        return repr(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return a detached ordinary mapping."""

        decoded = json.loads(self._encoded)
        if not isinstance(decoded, dict):  # pragma: no cover - constructor guard
            raise AssertionError("canonical mapping did not decode to a mapping")
        return decoded


def _line(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\n" in value
        or "\r" in value
        or "\0" in value
    ):
        raise ConfigurationError(f"{label} must be a non-empty single line")
    return value


def _record_path(value: object) -> str:
    rendered = _line(value, "Candidate record path")
    path = PurePosixPath(rendered)
    if (
        path.is_absolute()
        or rendered != path.as_posix()
        or "\\" in rendered
        or any(part in {"", ".", ".."} or part.startswith(".") for part in path.parts)
        or path.suffix.lower() not in RECORD_SUFFIXES
    ):
        raise ConfigurationError(
            "Candidate record path must be a normalized relative YAML path"
        )
    return rendered


def _json_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{label} must be a mapping")
    try:
        decoded = json.loads(canonical_json_bytes(value))
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            f"{label} is not deterministic JSON: {error}"
        ) from error
    if not isinstance(decoded, dict):  # pragma: no cover - guarded above
        raise AssertionError("canonical mapping did not decode to a mapping")
    return decoded


def _without_annotations(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _without_annotations(item)
            for key, item in value.items()
            if key != "annotations"
        }
    if isinstance(value, list):
        return [_without_annotations(item) for item in value]
    return value


def source_claim_sha256(
    source_claim: Mapping[str, object],
    *,
    pid: str,
    record_path: str,
    deletion: bool = False,
) -> str:
    """Hash one normalized source-mapped claim independently of curated state.

    Addition and modification intentionally share the ``upsert`` action.  A
    human correction, including deletion of an accepted record, therefore
    cannot change an otherwise identical source claim merely by changing its
    current baseline.
    """

    target_pid = _line(pid, "Candidate PID")
    target_path = _record_path(record_path)
    if not isinstance(deletion, bool):
        raise ConfigurationError("Source-claim deletion flag must be Boolean")
    mapped = _without_annotations(_json_mapping(source_claim, "Source claim"))
    payload = {
        "action": "delete" if deletion else "upsert",
        "pid": target_pid,
        "record_path": target_path,
        "source_mapped": mapped,
    }
    try:
        encoded = canonical_json_bytes(payload)
    except (TypeError, ValueError) as error:  # pragma: no cover - mapped above
        raise ConfigurationError(
            f"Source claim is not deterministic JSON: {error}"
        ) from error
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _record(
    value: object,
    *,
    label: str,
    expected_pid: str,
) -> _ReadOnlyJsonMapping | None:
    if value is None:
        return None
    record = _json_mapping(value, label)
    if record.get("pid") != expected_pid:
        raise ConfigurationError(f"{label} PID does not match the candidate PID")
    _line(record.get("schema_type"), f"{label} schema_type")
    validate_stored_record(record)
    return _ReadOnlyJsonMapping(record)


def _companion(
    value: object,
    *,
    label: str,
    expected_pid: str,
    record: Mapping[str, object] | None,
) -> _ReadOnlyJsonMapping | None:
    if value is None:
        return None
    if record is None:
        raise ConfigurationError(f"{label} cannot exist without its record")
    companion = _json_mapping(value, label)
    assertions = companion.get("assertions")
    if not isinstance(assertions, list):
        raise ConfigurationError(f"{label} assertions must be a list")
    rebuilt = annotation_companion(expected_pid, assertions)
    if companion != rebuilt:
        raise ConfigurationError(
            f"{label} must have exact fields and deterministic assertion order"
        )
    validate_annotation_companion(record, rebuilt)
    return _ReadOnlyJsonMapping(companion)


def _friendly_label(record: Mapping[str, object], pid: str) -> str:
    for field in ("display_label", "formatted_name", "title", "name", "short_name"):
        value = record.get(field)
        if isinstance(value, str):
            rendered = " ".join(value.split())
            if rendered:
                return rendered
    return pid


@dataclass(frozen=True)
class CandidateFileChange:
    """One canonical repository-file change derived from a candidate plan."""

    path: str
    baseline: bytes | None
    proposed: bytes | None


@dataclass(frozen=True)
class Candidate:
    """One ephemeral source claim and its complete metadata proposal."""

    source_namespace: str
    source_record_id: str
    pid: str
    record_path: str
    baseline_record: Mapping[str, object] | None
    proposed_record: Mapping[str, object] | None
    baseline_companion: Mapping[str, object] | None
    proposed_companion: Mapping[str, object] | None
    source_claim: Mapping[str, object]
    blockers: Sequence[str] = ()

    def __post_init__(self) -> None:
        namespace = _line(self.source_namespace, "Candidate source namespace")
        source_id = _line(self.source_record_id, "Candidate source record ID")
        pid = _line(self.pid, "Candidate PID")
        path = _record_path(self.record_path)
        baseline_record = _record(
            self.baseline_record,
            label="Candidate baseline record",
            expected_pid=pid,
        )
        proposed_record = _record(
            self.proposed_record,
            label="Candidate proposed record",
            expected_pid=pid,
        )
        baseline_companion = _companion(
            self.baseline_companion,
            label="Candidate baseline companion",
            expected_pid=pid,
            record=baseline_record,
        )
        proposed_companion = _companion(
            self.proposed_companion,
            label="Candidate proposed companion",
            expected_pid=pid,
            record=proposed_record,
        )
        source_claim = _ReadOnlyJsonMapping(
            _without_annotations(_json_mapping(self.source_claim, "Source claim"))
        )
        if baseline_record is None and proposed_record is None:
            raise ConfigurationError(
                "Candidate must contain a proposed record or an explicit deletion"
            )
        if baseline_record == proposed_record:
            if baseline_companion != proposed_companion:
                raise ConfigurationError(
                    "Candidate cannot contain a provenance-only change"
                )
            raise ConfigurationError("Candidate record proposal is unchanged")
        if isinstance(self.blockers, (str, bytes)) or not isinstance(
            self.blockers, Sequence
        ):
            raise ConfigurationError("Candidate blockers must be a sequence")
        blockers = tuple(
            sorted(_line(item, "Candidate blocker") for item in self.blockers)
        )
        if len(blockers) != len(set(blockers)):
            raise ConfigurationError("Candidate blockers must be unique")

        object.__setattr__(self, "source_namespace", namespace)
        object.__setattr__(self, "source_record_id", source_id)
        object.__setattr__(self, "pid", pid)
        object.__setattr__(self, "record_path", path)
        object.__setattr__(self, "baseline_record", baseline_record)
        object.__setattr__(self, "proposed_record", proposed_record)
        object.__setattr__(self, "baseline_companion", baseline_companion)
        object.__setattr__(self, "proposed_companion", proposed_companion)
        object.__setattr__(self, "source_claim", source_claim)
        object.__setattr__(self, "blockers", blockers)

    @property
    def operation(self) -> CandidateOperation:
        if self.baseline_record is None:
            return CandidateOperation.ADD
        if self.proposed_record is None:
            return CandidateOperation.DELETE
        return CandidateOperation.MODIFY

    @property
    def label(self) -> str:
        record = self.proposed_record or self.baseline_record
        if record is None:  # pragma: no cover - constructor invariant
            raise AssertionError("candidate has no record")
        return _friendly_label(record, self.pid)

    @property
    def claim_sha256(self) -> str:
        return source_claim_sha256(
            self.source_claim,
            pid=self.pid,
            record_path=self.record_path,
            deletion=self.operation is CandidateOperation.DELETE,
        )

    @property
    def sort_key(self) -> tuple[str, str, str, str]:
        return (
            self.record_path,
            self.pid,
            self.source_namespace,
            self.source_record_id,
        )

    @property
    def record_repository_path(self) -> str:
        return (RECORD_ROOT / self.record_path).as_posix()

    @property
    def companion_repository_path(self) -> str:
        return (ANNOTATION_ROOT / self.record_path).as_posix()

    def canonical_record_bytes(self, *, proposed: bool) -> bytes | None:
        """Serialize one side of the record proposal with the shared writer."""

        record = self.proposed_record if proposed else self.baseline_record
        if record is None:
            return None
        return canonical_yaml_bytes(dict(record))

    def canonical_companion_bytes(self, *, proposed: bool) -> bytes | None:
        """Serialize one side of the companion proposal with the shared writer."""

        companion = self.proposed_companion if proposed else self.baseline_companion
        if companion is None:
            return None
        return canonical_yaml_bytes(dict(companion))

    def file_changes(self) -> tuple[CandidateFileChange, ...]:
        """Return only canonical file bytes that this candidate changes."""

        changes: list[CandidateFileChange] = []
        record = CandidateFileChange(
            path=self.record_repository_path,
            baseline=self.canonical_record_bytes(proposed=False),
            proposed=self.canonical_record_bytes(proposed=True),
        )
        changes.append(record)
        companion = CandidateFileChange(
            path=self.companion_repository_path,
            baseline=self.canonical_companion_bytes(proposed=False),
            proposed=self.canonical_companion_bytes(proposed=True),
        )
        if companion.baseline != companion.proposed:
            changes.append(companion)
        return tuple(sorted(changes, key=lambda item: item.path))


def _companion_assertions(
    companion: Mapping[str, object] | None,
) -> tuple[Mapping[str, object], ...]:
    if companion is None:
        return ()
    assertions = companion.get("assertions")
    if not isinstance(assertions, list) or not all(
        isinstance(assertion, Mapping) for assertion in assertions
    ):
        raise AssertionError("validated companion has invalid assertions")
    return tuple(assertions)


def _assertion_selector(assertion: Mapping[str, object]) -> tuple[str, str]:
    path = assertion.get("path")
    digest = assertion.get("assertion_sha256")
    if not isinstance(path, str) or not isinstance(digest, str):
        raise AssertionError("validated companion has an invalid selector")
    return path, digest


@dataclass(frozen=True)
class CandidatePlan:
    """One deterministic, ephemeral plan from one adapter/source run."""

    adapter: str
    adapter_version: str
    adapter_agent_pid: str
    source_namespace: str
    source_coordinate: Mapping[str, object]
    metadata_base: str
    candidates: Sequence[Candidate]

    def __post_init__(self) -> None:
        adapter = _line(self.adapter, "Candidate-plan adapter")
        adapter_version = _line(
            self.adapter_version, "Candidate-plan adapter version"
        )
        adapter_agent_pid = _line(
            self.adapter_agent_pid, "Candidate-plan adapter agent PID"
        )
        namespace = _line(
            self.source_namespace, "Candidate-plan source namespace"
        )
        metadata_base = _line(self.metadata_base, "Candidate-plan metadata base")
        if _GIT_COMMIT.fullmatch(metadata_base) is None:
            raise ConfigurationError(
                "Candidate-plan metadata base must be an exact lowercase "
                "40-hex Git commit"
            )
        coordinate = _json_mapping(
            self.source_coordinate, "Candidate-plan source coordinate"
        )
        if not coordinate:
            raise ConfigurationError(
                "Candidate-plan source coordinate must not be empty"
            )
        if isinstance(self.candidates, (str, bytes)) or not isinstance(
            self.candidates, Sequence
        ):
            raise ConfigurationError("Candidate-plan candidates must be a sequence")
        candidates = tuple(self.candidates)
        if not all(isinstance(candidate, Candidate) for candidate in candidates):
            raise ConfigurationError(
                "Candidate-plan candidates must contain only Candidate values"
            )
        if any(candidate.source_namespace != namespace for candidate in candidates):
            raise ConfigurationError(
                "Candidate source namespace does not match its plan"
            )
        for candidate in candidates:
            baseline_assertions = {
                _assertion_selector(assertion): canonical_json_bytes(assertion)
                for assertion in _companion_assertions(candidate.baseline_companion)
            }
            for assertion in _companion_assertions(candidate.proposed_companion):
                selector = _assertion_selector(assertion)
                encoded = canonical_json_bytes(assertion)
                if selector in baseline_assertions:
                    if encoded != baseline_assertions[selector]:
                        raise ConfigurationError(
                            "Candidate cannot rewrite provenance for an unchanged "
                            "assertion selector"
                        )
                    continue
                if assertion.get("pav:importedBy") != adapter_agent_pid:
                    raise ConfigurationError(
                        "New or changed companion assertion does not use the "
                        "candidate-plan adapter agent PID"
                    )

        identities = [
            (candidate.source_namespace, candidate.source_record_id)
            for candidate in candidates
        ]
        if len(identities) != len(set(identities)):
            raise ConfigurationError("Candidate plan repeats a source identity")
        pids = [candidate.pid for candidate in candidates]
        if len(pids) != len(set(pids)):
            raise ConfigurationError("Candidate plan repeats a target PID")
        paths = [candidate.record_path for candidate in candidates]
        if len(paths) != len(set(paths)):
            raise ConfigurationError("Candidate plan repeats a target record path")

        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(self, "adapter_version", adapter_version)
        object.__setattr__(self, "adapter_agent_pid", adapter_agent_pid)
        object.__setattr__(self, "source_namespace", namespace)
        object.__setattr__(
            self, "source_coordinate", _ReadOnlyJsonMapping(coordinate)
        )
        object.__setattr__(self, "metadata_base", metadata_base)
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(candidates, key=lambda item: item.sort_key)),
        )

    def file_changes(self) -> tuple[CandidateFileChange, ...]:
        """Return every plan change in deterministic repository-path order."""

        changes = [
            change
            for candidate in self.candidates
            for change in candidate.file_changes()
        ]
        return tuple(sorted(changes, key=lambda item: item.path))
