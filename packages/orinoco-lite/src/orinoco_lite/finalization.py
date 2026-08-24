"""Host-neutral Git finalization for one regenerated candidate plan.

This module deliberately stops at metadata bytes.  It does not read or write a
decision cache, create commits, invoke DataLad, or provide host integration.
Git supplies the proposal transaction and three-way patch semantics; callers
remain responsible for validation, attribution, and an exact-head commit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
from typing import Any

import yaml
from yaml.nodes import MappingNode

from .annotations import (
    annotation_companion,
    reconcile_annotation_companion,
    validate_annotation_companion,
    validate_stored_record,
)
from .candidates import (
    ANNOTATION_ROOT,
    RECORD_ROOT,
    Candidate,
    CandidatePlan,
)
from .canonical import canonical_json_bytes, canonical_yaml_bytes
from .decisions import Disposition
from .errors import ConfigurationError


_GIT_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_REGULAR_GIT_MODE = "100644"


@dataclass(frozen=True)
class FinalizationResult:
    """The metadata worktree delta produced by finalization."""

    changed_paths: tuple[str, ...]
    metadata_changed: bool


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects keys whose value would be overwritten."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            repeated = key in result
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if repeated:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _git_environment() -> dict[str, str]:
    # Git's environment variables can replace the repository, worktree, index,
    # object database, or configuration.  None are caller inputs to this API.
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    return environment


def _git(
    repository: Path,
    arguments: Sequence[str],
    *,
    input_bytes: bytes | None = None,
    check: bool = True,
    operation: str,
) -> subprocess.CompletedProcess[bytes]:
    command = [
        "git",
        "-c",
        "core.quotepath=false",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "core.fsmonitor=false",
        "-C",
        os.fspath(repository),
        *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=_git_environment(),
        )
    except OSError as error:
        raise ConfigurationError(f"Git could not {operation}: {error}") from error
    if check and completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        if not detail:
            detail = f"Git exited with status {completed.returncode}"
        raise ConfigurationError(f"Git could not {operation}: {detail}")
    return completed


def _exact_commit(repository: Path, value: object, label: str) -> str:
    if not isinstance(value, str) or _GIT_COMMIT.fullmatch(value) is None:
        raise ConfigurationError(
            f"{label} must be an exact lowercase 40-hex Git commit"
        )
    resolved = _git(
        repository,
        ("rev-parse", "--verify", f"{value}^{{commit}}"),
        operation=f"resolve {label.lower()}",
    ).stdout.decode("ascii", "strict").strip()
    if resolved != value:
        raise ConfigurationError(f"{label} does not resolve to its exact commit")
    return value


def _require_clean_submitted_head(repository: Path, submitted_head: str) -> None:
    inside = _git(
        repository,
        ("rev-parse", "--is-inside-work-tree"),
        operation="inspect the finalization worktree",
    ).stdout
    if inside != b"true\n":
        raise ConfigurationError("Finalization requires a non-bare Git worktree")
    actual_head = _git(
        repository,
        ("rev-parse", "--verify", "HEAD^{commit}"),
        operation="read the current worktree head",
    ).stdout.decode("ascii", "strict").strip()
    if actual_head != submitted_head:
        raise ConfigurationError(
            "Submitted head is stale: the clean worktree HEAD no longer matches it"
        )
    status = _git(
        repository,
        ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        operation="inspect the finalization worktree",
    ).stdout
    if status:
        raise ConfigurationError(
            "Finalization requires a clean worktree with no staged, unstaged, "
            "or untracked paths"
        )


def _tree_blob(
    repository: Path,
    commit: str,
    path: str,
) -> bytes | None:
    listing = _git(
        repository,
        ("--literal-pathspecs", "ls-tree", "-z", "--full-tree", commit, "--", path),
        operation=f"inspect {path} at {commit}",
    ).stdout
    if not listing:
        return None
    entries = [entry for entry in listing.split(b"\0") if entry]
    if len(entries) != 1 or b"\t" not in entries[0]:
        raise ConfigurationError(f"Git tree contains an ambiguous entry for {path}")
    header, encoded_path = entries[0].split(b"\t", 1)
    try:
        mode, kind, object_id = header.decode("ascii").split(" ")
        actual_path = encoded_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as error:
        raise ConfigurationError(f"Git tree entry is malformed for {path}") from error
    if actual_path != path:
        raise ConfigurationError(f"Git tree returned an unexpected path for {path}")
    if mode != _REGULAR_GIT_MODE or kind != "blob":
        raise ConfigurationError(
            f"Metadata path must be a regular non-executable Git blob: {path}"
        )
    return _git(
        repository,
        ("cat-file", "blob", object_id),
        operation=f"read {path} at {commit}",
    ).stdout


def _load_mapping(data: bytes, label: str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
        value = yaml.load(text, Loader=_UniqueKeyLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f"{label} is not valid unambiguous UTF-8 YAML") from error
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ConfigurationError(f"{label} must contain a string-keyed mapping")
    return dict(value)


def _semantic_equal(actual: Mapping[str, Any], expected: Mapping[str, object]) -> bool:
    try:
        return canonical_json_bytes(actual) == canonical_json_bytes(expected)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(
            f"Metadata contains a value outside deterministic JSON: {error}"
        ) from error


def _verify_base_candidate(
    repository: Path,
    base: str,
    candidate: Candidate,
) -> None:
    record_bytes = _tree_blob(
        repository,
        base,
        candidate.record_repository_path,
    )
    companion_bytes = _tree_blob(
        repository,
        base,
        candidate.companion_repository_path,
    )
    expected_record = candidate.baseline_record
    expected_companion = candidate.baseline_companion
    if (record_bytes is None) != (expected_record is None):
        raise ConfigurationError(
            f"Candidate baseline record presence does not match Git at "
            f"{candidate.record_repository_path}"
        )
    if (companion_bytes is None) != (expected_companion is None):
        raise ConfigurationError(
            f"Candidate baseline companion presence does not match Git at "
            f"{candidate.companion_repository_path}"
        )
    record: dict[str, Any] | None = None
    if record_bytes is not None and expected_record is not None:
        record = _load_mapping(
            record_bytes,
            f"Baseline record {candidate.record_repository_path}",
        )
        validate_stored_record(record)
        if record.get("pid") != candidate.pid or not _semantic_equal(
            record, expected_record
        ):
            raise ConfigurationError(
                f"Regenerated candidate baseline does not match Git semantics at "
                f"{candidate.record_repository_path}"
            )
    if companion_bytes is not None and expected_companion is not None:
        if record is None:  # pragma: no cover - presence check above
            raise AssertionError("baseline companion has no baseline record")
        companion = _load_mapping(
            companion_bytes,
            f"Baseline companion {candidate.companion_repository_path}",
        )
        validate_annotation_companion(record, companion)
        if not _semantic_equal(companion, expected_companion):
            raise ConfigurationError(
                f"Regenerated candidate baseline does not match Git semantics at "
                f"{candidate.companion_repository_path}"
            )


def _diff_paths(repository: Path, older: str, newer: str) -> tuple[str, ...]:
    encoded = _git(
        repository,
        (
            "--literal-pathspecs",
            "diff",
            "--name-only",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            "-z",
            older,
            newer,
            "--",
        ),
        operation="inspect the proposal delta",
    ).stdout
    try:
        return tuple(
            sorted(item.decode("utf-8") for item in encoded.split(b"\0") if item)
        )
    except UnicodeDecodeError as error:
        raise ConfigurationError("Proposal paths must be valid UTF-8") from error


def _verify_proposal(
    repository: Path,
    plan: CandidatePlan,
    proposal_commit: str,
    submitted_head: str,
) -> None:
    base = _exact_commit(repository, plan.metadata_base, "Candidate metadata base")
    proposal = _exact_commit(repository, proposal_commit, "Proposal commit")
    parents = _git(
        repository,
        ("rev-list", "--parents", "-n", "1", proposal),
        operation="inspect proposal ancestry",
    ).stdout.decode("ascii", "strict").strip().split()
    if parents != [proposal, base]:
        raise ConfigurationError(
            "Proposal must be exactly one non-merge commit whose parent is the "
            "candidate metadata base"
        )
    ancestor = _git(
        repository,
        ("merge-base", "--is-ancestor", proposal, submitted_head),
        check=False,
        operation="verify proposal ancestry",
    )
    if ancestor.returncode != 0:
        raise ConfigurationError(
            "Proposal commit is not an ancestor of the submitted head"
        )

    for candidate in plan.candidates:
        _verify_base_candidate(repository, base, candidate)

    changes = plan.file_changes()
    expected_paths = tuple(change.path for change in changes)
    actual_paths = _diff_paths(repository, base, proposal)
    if actual_paths != expected_paths:
        missing = sorted(set(expected_paths) - set(actual_paths))
        extra = sorted(set(actual_paths) - set(expected_paths))
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ConfigurationError(
            "Proposal delta does not exactly match regenerated candidate paths: "
            + "; ".join(details)
        )
    for change in changes:
        actual = _tree_blob(repository, proposal, change.path)
        if actual != change.proposed:
            raise ConfigurationError(
                f"Proposal bytes are not the regenerated canonical bytes at "
                f"{change.path}"
            )


def _normalize_dispositions(
    plan: CandidatePlan,
    dispositions: Mapping[str, Disposition | str],
) -> dict[str, Disposition]:
    if not isinstance(dispositions, Mapping) or not all(
        isinstance(pid, str) for pid in dispositions
    ):
        raise ConfigurationError("Finalization dispositions must be a PID mapping")
    expected = {candidate.pid for candidate in plan.candidates}
    actual = set(dispositions)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ConfigurationError(
            "Finalization requires exactly one disposition per candidate: "
            + "; ".join(details)
        )
    normalized: dict[str, Disposition] = {}
    for pid, value in dispositions.items():
        try:
            normalized[pid] = Disposition(value)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Disposition for {pid} must be accept, reject, or defer"
            ) from error
    return normalized


def _candidate_patch(
    repository: Path,
    plan: CandidatePlan,
    proposal_commit: str,
    candidate: Candidate,
) -> bytes:
    paths = tuple(change.path for change in candidate.file_changes())
    patch = _git(
        repository,
        (
            "--literal-pathspecs",
            "diff",
            "--full-index",
            "--binary",
            "--no-renames",
            "--no-ext-diff",
            "--no-textconv",
            plan.metadata_base,
            proposal_commit,
            "--",
            *paths,
        ),
        operation=f"generate the proposal patch for {candidate.pid}",
    ).stdout
    if not patch:
        raise ConfigurationError(
            f"Proposal has no reversible patch for candidate {candidate.pid}"
        )
    return patch


def _clone_at_head(source: Path, destination: Path, head: str) -> None:
    parent = destination.parent
    completed = _git(
        parent,
        (
            "clone",
            "--quiet",
            "--no-hardlinks",
            "--no-checkout",
            "--",
            os.fspath(source),
            os.fspath(destination),
        ),
        operation="create the disposable finalization worktree",
    )
    if completed.returncode != 0:  # pragma: no cover - checked by _git
        raise AssertionError("checked clone failed")
    _git(
        destination,
        ("checkout", "--quiet", "--detach", head),
        operation="check out the submitted head in the disposable worktree",
    )


def _apply_reverse_patch(
    worktree: Path,
    patch: bytes,
    candidate: Candidate,
) -> None:
    try:
        _git(
            worktree,
            ("apply", "--reverse", "--3way", "--whitespace=nowarn", "-"),
            input_bytes=patch,
            operation=f"reverse candidate {candidate.pid}",
        )
    except ConfigurationError as error:
        raise ConfigurationError(
            f"Candidate {candidate.pid} overlaps submitted-head metadata; "
            "correct the conflict and resubmit: "
            f"{error}"
        ) from error


def _worktree_mapping(
    worktree: Path,
    path: str,
    *,
    label: str,
    canonical: bool,
) -> tuple[bytes, dict[str, Any]] | None:
    absolute = worktree / PurePosixPath(path)
    if not absolute.exists() and not absolute.is_symlink():
        return None
    if absolute.is_symlink() or not absolute.is_file():
        raise ConfigurationError(f"{label} must be a regular file: {path}")
    try:
        data = absolute.read_bytes()
    except OSError as error:
        raise ConfigurationError(f"Could not read {label.lower()} {path}: {error}") from error
    value = _load_mapping(data, f"{label} {path}")
    if canonical and canonical_yaml_bytes(value) != data:
        raise ConfigurationError(f"{label} is not canonically serialized: {path}")
    return data, value


def _assertions(
    companion: Mapping[str, object] | None,
) -> tuple[dict[str, str], ...]:
    if companion is None:
        return ()
    raw = companion.get("assertions")
    if not isinstance(raw, list) or not all(isinstance(item, Mapping) for item in raw):
        raise AssertionError("validated candidate companion has invalid assertions")
    return tuple(dict(item) for item in raw)


def _selector(assertion: Mapping[str, str]) -> tuple[str, str]:
    return assertion["path"], assertion["assertion_sha256"]


def _selector_is_stale(
    record: Mapping[str, Any] | None,
    pid: str,
    assertion: Mapping[str, str],
) -> bool:
    if record is None:
        return True
    single = annotation_companion(pid, [assertion])
    try:
        reconciled = reconcile_annotation_companion(record, single)
    except ConfigurationError as error:
        raise ConfigurationError(
            f"Annotation selector {_selector(assertion)!r} is ambiguous: {error}"
        ) from error
    retained = reconciled.get("assertions")
    if not isinstance(retained, list):  # pragma: no cover - helper invariant
        raise AssertionError("reconciled companion has invalid assertions")
    return not retained


def _reconcile_accepted_companion(worktree: Path, candidate: Candidate) -> None:
    record_source = _worktree_mapping(
        worktree,
        candidate.record_repository_path,
        label="Accepted record",
        canonical=False,
    )
    record = record_source[1] if record_source is not None else None
    if record is not None:
        validate_stored_record(record)
        if record.get("pid") != candidate.pid:
            raise ConfigurationError(
                f"Accepted record PID or path changed during review for {candidate.pid}"
            )

    companion_source = _worktree_mapping(
        worktree,
        candidate.companion_repository_path,
        label="Accepted companion",
        canonical=True,
    )
    baseline = {_selector(item): item for item in _assertions(candidate.baseline_companion)}
    proposed = {_selector(item): item for item in _assertions(candidate.proposed_companion)}
    proposal_added = set(proposed) - set(baseline)
    retained_baseline = set(proposed) & set(baseline)

    if companion_source is None:
        missing = sorted(retained_baseline)
        if missing:
            raise ConfigurationError(
                f"Accepted companion removed non-proposal assertions for "
                f"{candidate.pid}: {missing!r}"
            )
        return

    _, current = companion_source
    raw_assertions = current.get("assertions")
    if not isinstance(raw_assertions, list):
        raise ConfigurationError(
            f"Accepted companion assertions must be a list for {candidate.pid}"
        )
    rebuilt = annotation_companion(candidate.pid, raw_assertions)
    if current != rebuilt:
        raise ConfigurationError(
            f"Accepted companion has changed fields, identity, or assertion order "
            f"for {candidate.pid}"
        )
    current_assertions = tuple(dict(item) for item in rebuilt["assertions"])
    current_by_selector = {_selector(item): item for item in current_assertions}
    missing = retained_baseline - set(current_by_selector)
    if missing:
        raise ConfigurationError(
            f"Accepted companion removed non-proposal assertions for "
            f"{candidate.pid}: {sorted(missing)!r}"
        )

    retained: list[dict[str, str]] = []
    removed = False
    for assertion in current_assertions:
        selector = _selector(assertion)
        expected = proposed.get(selector)
        if expected is not None and assertion != expected:
            raise ConfigurationError(
                f"Accepted companion changed a reviewed assertion for "
                f"{candidate.pid} at {selector!r}"
            )
        if expected is None and selector in baseline and assertion != baseline[selector]:
            raise ConfigurationError(
                f"Accepted companion changed a non-proposal assertion for "
                f"{candidate.pid} at {selector!r}"
            )
        try:
            stale = _selector_is_stale(record, candidate.pid, assertion)
        except ConfigurationError as error:
            raise ConfigurationError(
                f"Accepted companion cannot be reconciled for {candidate.pid}: "
                f"{error}"
            ) from error
        if stale:
            if selector not in proposal_added or assertion != proposed[selector]:
                raise ConfigurationError(
                    f"Accepted companion contains a stale non-proposal assertion "
                    f"for {candidate.pid} at {selector!r}"
                )
            removed = True
            continue
        retained.append(assertion)

    path = worktree / PurePosixPath(candidate.companion_repository_path)
    if not retained:
        try:
            path.unlink()
        except OSError as error:
            raise ConfigurationError(
                f"Could not delete empty companion for {candidate.pid}: {error}"
            ) from error
        return
    if removed:
        try:
            path.write_bytes(
                canonical_yaml_bytes(annotation_companion(candidate.pid, retained))
            )
        except OSError as error:
            raise ConfigurationError(
                f"Could not reconcile companion for {candidate.pid}: {error}"
            ) from error


def _changed_paths(repository: Path, head: str) -> tuple[str, ...]:
    encoded = _git(
        repository,
        (
            "--literal-pathspecs",
            "diff",
            "--name-only",
            "--no-renames",
            "-z",
            head,
            "--",
        ),
        operation="inspect finalized metadata",
    ).stdout
    try:
        return tuple(
            sorted(item.decode("utf-8") for item in encoded.split(b"\0") if item)
        )
    except UnicodeDecodeError as error:  # pragma: no cover - candidate paths are UTF-8
        raise ConfigurationError("Finalized paths must be valid UTF-8") from error


def _within_metadata_roots(path: str) -> bool:
    candidate = PurePosixPath(path)
    roots = (RECORD_ROOT.parts, ANNOTATION_ROOT.parts)
    return any(candidate.parts[: len(root)] == root for root in roots)


def _require_safe_worktree_path(worktree: Path, path: str) -> Path:
    relative = PurePosixPath(path)
    parent = worktree
    for part in relative.parts[:-1]:
        parent /= part
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ConfigurationError(
                f"Finalized metadata parent is not a regular directory: {path}"
            )
    destination = worktree / relative
    if destination.is_symlink() or (
        destination.exists() and not destination.is_file()
    ):
        raise ConfigurationError(
            f"Finalized metadata destination is not a regular file: {path}"
        )
    return destination


def _copy_finalized_paths(
    rehearsal: Path,
    worktree: Path,
    paths: Sequence[str],
) -> None:
    prepared: list[tuple[Path, bytes | None]] = []
    for path in paths:
        source = rehearsal / PurePosixPath(path)
        destination = _require_safe_worktree_path(worktree, path)
        if source.is_symlink() or (source.exists() and not source.is_file()):
            raise ConfigurationError(f"Finalized metadata is not a regular file: {path}")
        if source.exists():
            try:
                prepared.append((destination, source.read_bytes()))
            except OSError as error:
                raise ConfigurationError(
                    f"Could not prepare finalized metadata {path}: {error}"
                ) from error
            continue
        prepared.append((destination, None))

    # All paths and bytes are checked before the first caller-worktree write.
    for destination, data in prepared:
        if data is not None:
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            except OSError as error:
                raise ConfigurationError(
                    f"Could not write finalized metadata {destination}: {error}"
                ) from error
            continue
        if destination.exists():
            try:
                destination.unlink()
            except OSError as error:
                raise ConfigurationError(
                    f"Could not delete finalized metadata {destination}: {error}"
                ) from error


def finalize_candidate_plan(
    worktree: Path,
    *,
    plan: CandidatePlan,
    proposal_commit: str,
    submitted_head: str,
    dispositions: Mapping[str, Disposition | str],
) -> FinalizationResult:
    """Apply complete decisions to one exact proposal and submitted head.

    Reject and defer dispositions reverse candidate-specific proposal patches
    using Git's three-way merge.  The operation is rehearsed in a temporary
    clone, so a conflict or invalid companion cannot alter the caller's clean
    worktree.  Only the resulting candidate paths below the two metadata roots
    are copied back; this function does not stage or commit them.
    """

    if not isinstance(plan, CandidatePlan):
        raise ConfigurationError("Finalization requires a regenerated CandidatePlan")
    if not plan.candidates:
        raise ConfigurationError(
            "Finalization requires at least one regenerated candidate"
        )
    repository = Path(worktree).resolve()
    submitted = _exact_commit(repository, submitted_head, "Submitted head")
    _require_clean_submitted_head(repository, submitted)
    normalized = _normalize_dispositions(plan, dispositions)
    proposal = _exact_commit(repository, proposal_commit, "Proposal commit")
    _verify_proposal(repository, plan, proposal, submitted)

    allowed_paths = {
        path
        for candidate in plan.candidates
        for path in (
            candidate.record_repository_path,
            candidate.companion_repository_path,
        )
    }
    if any(not _within_metadata_roots(path) for path in allowed_paths):
        raise ConfigurationError(
            "Candidate finalization paths must remain below the two metadata roots"
        )

    with tempfile.TemporaryDirectory(prefix="orinoco-finalization-") as temporary:
        rehearsal = Path(temporary) / "worktree"
        _clone_at_head(repository, rehearsal, submitted)
        for path in sorted(allowed_paths):
            _require_safe_worktree_path(rehearsal, path)
        for candidate in plan.candidates:
            if normalized[candidate.pid] is Disposition.ACCEPT:
                continue
            patch = _candidate_patch(repository, plan, proposal, candidate)
            _apply_reverse_patch(rehearsal, patch, candidate)
        for candidate in plan.candidates:
            if normalized[candidate.pid] is Disposition.ACCEPT:
                _reconcile_accepted_companion(rehearsal, candidate)

        changed_paths = _changed_paths(rehearsal, submitted)
        unexpected = sorted(set(changed_paths) - allowed_paths)
        if unexpected or any(not _within_metadata_roots(path) for path in changed_paths):
            raise ConfigurationError(
                "Finalization attempted to change a path outside candidate metadata: "
                + ", ".join(unexpected or changed_paths)
            )

        # Recheck immediately before the only mutation of the caller's worktree.
        _require_clean_submitted_head(repository, submitted)
        _copy_finalized_paths(rehearsal, repository, changed_paths)

    return FinalizationResult(
        changed_paths=changed_paths,
        metadata_changed=bool(changed_paths),
    )
