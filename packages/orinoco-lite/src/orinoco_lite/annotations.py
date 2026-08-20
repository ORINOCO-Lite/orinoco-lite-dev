"""Validation and joining for machine-assertion annotation companions."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from .canonical import canonicalize_yaml_text
from .config import WorkspaceConfig
from .errors import ConfigurationError


ANNOTATION_FIELDS = frozenset(
    {"path", "assertion_sha256", "pav:importedBy", "pav:importedFrom"}
)
COMPANION_FIELDS = frozenset({"record", "assertions"})
ATTRIBUTE_SPECIFICATION = "dlthings:AttributeSpecification"
PAV_IMPORTED_BY = "pav:importedBy"
PAV_IMPORTED_FROM = "pav:importedFrom"
PAV_IMPORTED_BY_URI = "http://purl.org/pav/importedBy"
PAV_IMPORTED_FROM_URI = "http://purl.org/pav/importedFrom"
_MACHINE_PAV_TAGS = frozenset(
    {
        PAV_IMPORTED_BY,
        PAV_IMPORTED_FROM,
        PAV_IMPORTED_BY_URI,
        PAV_IMPORTED_FROM_URI,
    }
)
_ASSERTION_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
ANNOTATION_ROOT = Path("metadata/overlays/annotations")


@dataclass(frozen=True)
class CompanionSource:
    """One validated companion and its mirrored stored record."""

    path: Path
    record_path: Path
    value: Mapping[str, object]
    assertion_count: int


@dataclass(frozen=True)
class SlotSemantics:
    """Schema-derived representation for one direct metadata slot."""

    predicate: str
    class_range: bool
    datatype: str | None = None


class _SelectorNoMatch(ConfigurationError):
    """A previously valid selector no longer identifies an assertion."""


def _canonical_assertion(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _canonical_assertion(item)
            for key, item in value.items()
            if key != "annotations"
        }
    if isinstance(value, list):
        return [_canonical_assertion(item) for item in value]
    return value


def assertion_sha256(value: Any) -> str:
    """Fingerprint one assertion with nested annotations excluded."""

    try:
        serialized = json.dumps(
            _canonical_assertion(value),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            f"Assertion is not deterministic JSON: {error}"
        ) from error
    return "sha256:" + hashlib.sha256(serialized).hexdigest()


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


def _annotation_entry(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != ANNOTATION_FIELDS:
        raise ConfigurationError(
            "Annotation assertion has missing or unexpected fields"
        )
    path = _line(value.get("path"), "Annotation path")
    tokens = _pointer_tokens(path)
    if tokens[-1] in {"pid", "schema_type"}:
        raise ConfigurationError(
            "Structural pid and schema_type slots cannot be imported assertions"
        )
    digest = _line(value.get("assertion_sha256"), "Assertion digest")
    if _ASSERTION_DIGEST.fullmatch(digest) is None:
        raise ConfigurationError(
            "Assertion digest must be sha256 followed by 64 lowercase hex digits"
        )
    return {
        "path": path,
        "assertion_sha256": digest,
        PAV_IMPORTED_BY: _line(value.get(PAV_IMPORTED_BY), PAV_IMPORTED_BY),
        PAV_IMPORTED_FROM: _line(value.get(PAV_IMPORTED_FROM), PAV_IMPORTED_FROM),
    }


def annotation_companion(
    record: str,
    assertions: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build one deterministic companion from current assertion provenance."""

    pid = _line(record, "Companion record")
    entries = [_annotation_entry(value) for value in assertions]
    entries.sort(key=lambda item: (item["path"], item["assertion_sha256"]))
    selectors = [(item["path"], item["assertion_sha256"]) for item in entries]
    if len(selectors) != len(set(selectors)):
        raise ConfigurationError("Annotation companion repeats an assertion selector")
    return {"record": pid, "assertions": entries}


def validate_stored_record(record: Mapping[str, Any]) -> None:
    """Reject machine PAV that bypasses the annotation companion tree."""

    def inspect(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if key in _MACHINE_PAV_TAGS or (
                    key == "annotation_tag" and item in _MACHINE_PAV_TAGS
                ):
                    raise ConfigurationError(
                        "Machine pav:importedBy and pav:importedFrom annotations "
                        "must be stored in metadata/overlays/annotations"
                    )
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(record)


def _validated_companion(value: object, record_pid: str) -> list[dict[str, str]]:
    if not isinstance(value, Mapping) or set(value) != COMPANION_FIELDS:
        raise ConfigurationError(
            "Annotation companion has missing or unexpected top-level fields"
        )
    if value.get("record") != record_pid:
        raise ConfigurationError(
            "Annotation companion record does not match the mirrored Thing PID"
        )
    assertions = value.get("assertions")
    if not isinstance(assertions, list):
        raise ConfigurationError("Annotation companion assertions must be a list")
    entries = [_annotation_entry(item) for item in assertions]
    expected = sorted(entries, key=lambda item: (item["path"], item["assertion_sha256"]))
    if entries != expected:
        raise ConfigurationError(
            "Annotation assertions must be ordered by path and assertion_sha256"
        )
    selectors = [(item["path"], item["assertion_sha256"]) for item in entries]
    if len(selectors) != len(set(selectors)):
        raise ConfigurationError("Annotation companion repeats an assertion selector")
    return entries


def annotation_root(workspace: WorkspaceConfig) -> Path:
    """Return the one specification-defined annotation overlay root."""

    return workspace.root / ANNOTATION_ROOT


def annotation_files(workspace: WorkspaceConfig) -> list[Path]:
    """Return every regular canonical companion, failing closed."""

    root = annotation_root(workspace)
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise ConfigurationError(
            f"Annotation overlay root must be a regular directory: {root}"
        )
    companions: list[Path] = []
    for candidate in sorted(root.rglob("*")):
        if candidate.is_symlink():
            raise ConfigurationError(
                f"Annotation overlays cannot contain symlinks: {candidate}"
            )
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ConfigurationError(
                f"Annotation companion path is not regular: {candidate}"
            )
        relative = candidate.relative_to(root)
        if (
            candidate.suffix.lower() not in {".yaml", ".yml"}
            or any(part.startswith(".") for part in relative.parts)
        ):
            raise ConfigurationError(
                "Everything below metadata/overlays/annotations must be a Thing "
                f"annotation companion; found unsupported content: {candidate}"
            )
        companions.append(candidate)
    return companions


def _pointer_tokens(pointer: str) -> tuple[str, ...]:
    if not pointer.startswith("/"):
        raise ConfigurationError(
            "Annotation path must be a non-empty RFC 6901 JSON Pointer"
        )
    tokens: list[str] = []
    for raw in pointer[1:].split("/"):
        token = ""
        index = 0
        while index < len(raw):
            if raw[index] != "~":
                token += raw[index]
                index += 1
                continue
            if index + 1 == len(raw) or raw[index + 1] not in {"0", "1"}:
                raise ConfigurationError(
                    f"Annotation path contains an invalid JSON Pointer escape: {pointer}"
                )
            token += "~" if raw[index + 1] == "0" else "/"
            index += 2
        tokens.append(token)
    return tuple(tokens)


def _resolve_pointer(
    record: dict[str, Any], pointer: str
) -> tuple[dict[str, Any] | list[Any], str | int, Any]:
    current: Any = record
    parent: dict[str, Any] | list[Any] = record
    resolved: str | int = ""
    for token in _pointer_tokens(pointer):
        parent = current
        if isinstance(current, dict):
            if token not in current:
                raise _SelectorNoMatch(
                    f"Annotation selector matched zero assertions at {pointer}"
                )
            resolved = token
            current = current[token]
        elif isinstance(current, list):
            raise ConfigurationError(
                "Annotation path must identify a collection rather than an "
                f"array item at {pointer}"
            )
        else:
            raise _SelectorNoMatch(
                f"Annotation selector matched zero assertions at {pointer}"
            )
    return parent, resolved, current


def _expanded_annotations(value: object) -> dict[str, dict[str, object]]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigurationError("Joined annotations must be a mapping")
    expanded: dict[str, dict[str, object]] = {}
    for raw_tag, raw_value in value.items():
        tag = _line(raw_tag, "Annotation tag")
        if isinstance(raw_value, Mapping):
            if set(raw_value) != {"annotation_tag", "annotation_value"}:
                raise ConfigurationError("Expanded annotation object is malformed")
            if raw_value.get("annotation_tag") != tag:
                raise ConfigurationError(
                    "Expanded annotation tag does not match its mapping key"
                )
            annotation_value = raw_value.get("annotation_value")
        else:
            annotation_value = raw_value
        if annotation_value is not None and not isinstance(annotation_value, str):
            raise ConfigurationError("Annotation value must be a string or null")
        expanded[tag] = {
            "annotation_tag": tag,
            "annotation_value": annotation_value,
        }
    return expanded


def _machine_annotations(entry: Mapping[str, str]) -> dict[str, dict[str, str]]:
    return {
        tag: {"annotation_tag": tag, "annotation_value": entry[tag]}
        for tag in (PAV_IMPORTED_BY, PAV_IMPORTED_FROM)
    }


def _attach_to_object(target: dict[str, Any], entry: Mapping[str, str]) -> None:
    annotations = _expanded_annotations(target.get("annotations"))
    for tag, annotation in _machine_annotations(entry).items():
        if tag in annotations:
            raise ConfigurationError(
                f"Joined assertion already contains machine annotation {tag}"
            )
        annotations[tag] = annotation
    target["annotations"] = annotations


def _attach_scalar(
    parent: object,
    slot: object,
    value: Any,
    entry: Mapping[str, str],
    semantics_for_slot: Callable[[str], SlotSemantics],
) -> None:
    if not isinstance(parent, dict) or not isinstance(slot, str):
        raise ConfigurationError(
            "A scalar assertion path must name a slot on a mapping"
        )
    semantics = semantics_for_slot(slot)
    if not isinstance(semantics, SlotSemantics):
        raise ConfigurationError(f"Schema semantics are invalid for slot {slot}")
    predicate = _line(semantics.predicate, f"Predicate for slot {slot}")
    if ":" not in predicate:
        raise ConfigurationError(
            f"Predicate for scalar assertion slot {slot} must be a CURIE"
        )
    if semantics.class_range:
        if not isinstance(value, str):
            raise ConfigurationError(
                f"Class-range assertion slot {slot} requires a URI string"
            )
        statements = parent.setdefault("characterized_by", [])
        if not isinstance(statements, list):
            raise ConfigurationError(
                "Class-range assertion parent has a non-list characterized_by "
                f"slot at {entry['path']}"
            )
        statements.append(
            {
                "annotations": _machine_annotations(entry),
                "object": value,
                "predicate": predicate,
            }
        )
        return

    range_value: str | None = None
    if isinstance(value, str):
        lexical_value = value
    elif value is None or isinstance(value, (dict, list)):
        raise ConfigurationError(
            f"Data assertion slot {slot} is not a supported JSON scalar"
        )
    else:
        datatype = semantics.datatype
        if not isinstance(datatype, str) or ":" not in datatype:
            raise ConfigurationError(
                f"Schema has no CURIE datatype for non-string assertion slot {slot}"
            )
        try:
            lexical_value = json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Data assertion slot {slot} has no canonical lexical form"
            ) from error
        range_value = datatype
    attributes = parent.setdefault("attributes", [])
    if not isinstance(attributes, list):
        raise ConfigurationError(
            f"Scalar assertion parent has a non-list attributes slot at {entry['path']}"
        )
    attribute = {
        "annotations": _machine_annotations(entry),
        "predicate": predicate,
        "schema_type": ATTRIBUTE_SPECIFICATION,
        "value": lexical_value,
    }
    if range_value is not None:
        attribute["range"] = range_value
    attributes.append(attribute)


def _matched_assertion(
    record: dict[str, Any], entry: Mapping[str, str]
) -> tuple[dict[str, Any] | list[Any], str | int, Any]:
    parent, slot, target = _resolve_pointer(record, entry["path"])
    digest = entry["assertion_sha256"]
    if isinstance(target, list):
        matches = [item for item in target if assertion_sha256(item) == digest]
        if not matches:
            raise _SelectorNoMatch(
                f"Annotation selector matched zero assertions at {entry['path']}"
            )
        if len(matches) != 1:
            raise ConfigurationError(
                f"Annotation selector matched {len(matches)} assertions at {entry['path']}"
            )
        return parent, slot, matches[0]
    if assertion_sha256(target) != digest:
        raise _SelectorNoMatch(
            f"Annotation selector matched zero assertions at {entry['path']}"
        )
    return parent, slot, target


def _apply_entry(
    record: dict[str, Any],
    entry: Mapping[str, str],
    semantics_for_slot: Callable[[str], SlotSemantics],
) -> None:
    parent, slot, assertion = _matched_assertion(record, entry)
    if isinstance(assertion, dict):
        _attach_to_object(assertion, entry)
    else:
        _attach_scalar(parent, slot, assertion, entry, semantics_for_slot)


def validate_annotation_companion(
    record: Mapping[str, Any], companion: Mapping[str, object]
) -> int:
    """Validate companion shape, identity, order, and every selector."""

    copied = deepcopy(dict(record))
    pid = copied.get("pid")
    if not isinstance(pid, str) or not pid:
        raise ConfigurationError("Annotated Thing requires a non-empty PID")
    entries = _validated_companion(companion, pid)
    for entry in entries:
        _matched_assertion(copied, entry)
    return len(entries)


def reconcile_annotation_companion(
    record: Mapping[str, Any], companion: Mapping[str, object]
) -> dict[str, object]:
    """Drop machine provenance whose assertion no longer has one match."""

    copied = deepcopy(dict(record))
    validate_stored_record(copied)
    pid = copied.get("pid")
    if not isinstance(pid, str) or not pid:
        raise ConfigurationError("Annotated Thing requires a non-empty PID")
    retained: list[dict[str, str]] = []
    for entry in _validated_companion(companion, pid):
        try:
            _matched_assertion(copied, entry)
        except _SelectorNoMatch:
            continue
        retained.append(entry)
    return annotation_companion(pid, retained)


def companion_sources(workspace: WorkspaceConfig) -> list[CompanionSource]:
    """Load canonical companions and bind each to its mirrored record."""

    overlay = annotation_root(workspace)
    records = workspace.path("records")
    sources: list[CompanionSource] = []
    for path in annotation_files(workspace):
        relative = path.relative_to(overlay)
        record_path = records / relative
        if record_path.is_symlink() or not record_path.is_file():
            raise ConfigurationError(
                f"Annotation companion has no mirrored metadata record: {path}"
            )
        try:
            text = path.read_text(encoding="utf-8")
            value = yaml.safe_load(text)
            record = yaml.safe_load(record_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
            raise ConfigurationError(
                f"Annotation companion or mirrored record is invalid UTF-8 YAML: {path}"
            ) from error
        if not isinstance(value, Mapping) or not isinstance(record, Mapping):
            raise ConfigurationError(
                f"Annotation companion and mirrored record must be mappings: {path}"
            )
        if canonicalize_yaml_text(text) != text:
            raise ConfigurationError(
                f"Annotation companion is not canonically serialized: {path}"
            )
        validate_stored_record(record)
        count = validate_annotation_companion(record, value)
        sources.append(CompanionSource(path, record_path, value, count))
    return sources


def join_annotations(
    record: Mapping[str, Any],
    companion: Mapping[str, object] | None,
    semantics_for_slot: Callable[[str], SlotSemantics],
) -> dict[str, Any]:
    """Join one stored Thing and its optional annotation companion."""

    joined = deepcopy(dict(record))
    validate_stored_record(joined)
    pid = joined.get("pid")
    if not isinstance(pid, str) or not pid:
        raise ConfigurationError("Joined Thing requires a non-empty PID")
    if companion is None:
        return joined
    for entry in _validated_companion(companion, pid):
        _apply_entry(joined, entry, semantics_for_slot)
    return joined
