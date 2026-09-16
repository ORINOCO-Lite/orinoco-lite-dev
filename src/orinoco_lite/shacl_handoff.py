"""Inspect and materialize the fixed SHACL Vue Git handoff as untrusted data."""

from __future__ import annotations

import argparse
import configparser
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Sequence


HANDOFF_PATH = ".orinoco-lite/shacl-vue-review-bundle.json"
BUNDLE_FORMAT = "orinoco-shacl-review-bundle"
BUNDLE_VERSION = 2
MAX_BUNDLE_BYTES = 10 * 1024 * 1024
MAX_BUNDLE_RECORDS = 50
RECORD_ROOT = PurePosixPath("site-specific/metadata/records")
ANNOTATION_ROOT = PurePosixPath("site-specific/metadata/overlays/annotations")
SHA40 = re.compile(r"[0-9a-f]{40}")
SOURCE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def site_submodule(root: Path, commit: str) -> dict[str, str] | None:
    """Resolve the bounded gitlink from Git, never from worktree config."""
    entry = _tree_entry(root, commit, "site-specific")
    if entry is None or entry[:2] == ("040000", "tree"):
        return None
    if entry[:2] != ("160000", "commit"):
        raise HandoffError("site-specific must be a directory or Git submodule")
    parser = configparser.RawConfigParser(strict=True)
    try:
        parser.read_string(_tree_blob(root, commit, ".gitmodules").decode("utf-8"))
        matches = [
            section
            for section in parser.sections()
            if parser.get(section, "path", fallback=None) == "site-specific"
        ]
        if len(matches) != 1 or not re.fullmatch(r'submodule "[^"\r\n]+"', matches[0]):
            raise ValueError("ambiguous submodule")
        url = parser.get(matches[0], "url")
    except (ValueError, UnicodeDecodeError, configparser.Error) as error:
        raise HandoffError("site-specific needs one exact .gitmodules URL") from error
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
        r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?",
        url,
    )
    if match is None or ".." in match[1]:
        raise HandoffError("site-specific requires an absolute GitHub HTTPS or SSH URL")
    return {"repository": match[1], "source_commit": entry[2]}


class HandoffError(RuntimeError):
    """A Git object is outside the reviewed SHACL Vue handoff boundary."""


def _exact_sha(value: str, label: str) -> str:
    if SHA40.fullmatch(value) is None:
        raise HandoffError(f"{label} must be an exact lowercase Git SHA")
    return value


def _git(root: Path, *arguments: str, text: bool = False) -> bytes | str:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    completed = subprocess.run(
        ["git", "-C", os.fspath(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise HandoffError(f"Git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.decode("utf-8") if text else completed.stdout


def _head(root: Path) -> str:
    return str(_git(root, "rev-parse", "--verify", "HEAD^{commit}", text=True)).strip()


def _parents(root: Path, commit: str) -> tuple[str, ...]:
    line = str(
        _git(root, "rev-list", "--parents", "-n", "1", commit, text=True)
    ).strip()
    values = line.split()
    if not values or values[0] != commit:
        raise HandoffError("Git returned invalid commit parents")
    return tuple(values[1:])


def _diff_entries(
    root: Path,
    parent: str,
    commit: str,
    *,
    cached: bool = False,
) -> tuple[tuple[str, str], ...]:
    arguments = [
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
    ]
    if cached:
        arguments.extend(("--cached", parent))
    else:
        arguments.extend((parent, commit))
    arguments.append("--")
    raw = bytes(_git(root, *arguments)).split(b"\0")
    values = [value for value in raw if value]
    if len(values) % 2:
        raise HandoffError("Git returned malformed no-rename diff entries")
    entries: list[tuple[str, str]] = []
    for raw_status, raw_path in zip(values[::2], values[1::2], strict=True):
        try:
            entries.append((raw_status.decode("ascii"), raw_path.decode("utf-8")))
        except UnicodeDecodeError as error:
            raise HandoffError("Git diff path is not UTF-8") from error
    return tuple(entries)


def _metadata_path(value: str, *, in_submodule: bool = False) -> str | None:
    if in_submodule:
        return value if _metadata_path("site-specific/" + value) is not None else None
    path = PurePosixPath(value)
    if (
        any(character in value for character in "\\\r\n\0")
        or path.is_absolute()
        or path.as_posix() != value
        or path.suffix.lower() not in {".yaml", ".yml"}
        or any(part in {"", ".", ".."} or part.startswith(".") for part in path.parts)
    ):
        return None
    if path.parts[:3] == RECORD_ROOT.parts and len(path.parts) >= 4:
        return value
    if path.parts[:4] == ANNOTATION_ROOT.parts and len(path.parts) >= 5:
        return value
    return None


def _decision_cache_path(value: str) -> str | None:
    path = PurePosixPath(value)
    if (
        any(character in value for character in "\\\r\n\0")
        or path.is_absolute()
        or path.as_posix() != value
        or len(path.parts) != 3
        or path.parts[:2] != ("site-specific", "curation-records")
        or path.suffix.lower() not in {".yaml", ".yml"}
        or SOURCE_ID.fullmatch(path.stem) is None
    ):
        return None
    return value


def _tree_entry(root: Path, commit: str, path: str) -> tuple[str, str, str] | None:
    listing = bytes(
        _git(
            root,
            "--literal-pathspecs",
            "ls-tree",
            "-z",
            "--full-tree",
            commit,
            "--",
            path,
        )
    )
    entries = [entry for entry in listing.split(b"\0") if entry]
    if not entries:
        return None
    if len(entries) != 1 or b"\t" not in entries[0]:
        raise HandoffError(f"Path is not one Git object: {path}")
    header, raw_path = entries[0].split(b"\t", 1)
    try:
        mode, kind, object_id = header.decode("ascii").split(" ")
        rendered = raw_path.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as error:
        raise HandoffError(f"Git returned an invalid tree entry: {path}") from error
    if rendered != path:
        raise HandoffError(f"Git returned a mismatched tree path: {path}")
    return mode, kind, object_id


def _tree_blob(root: Path, commit: str, path: str) -> bytes:
    entry = _tree_entry(root, commit, path)
    if entry is None:
        raise HandoffError(f"Path is absent from the Git tree: {path}")
    mode, kind, object_id = entry
    if mode != "100644" or kind != "blob":
        raise HandoffError(f"Path is not a regular Git blob: {path}")
    return bytes(_git(root, "cat-file", "blob", object_id))


def _assert_regular_blob(root: Path, commit: str, path: str) -> None:
    _tree_blob(root, commit, path)


def _status(root: Path) -> bytes:
    return bytes(_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all"))


def _merge_base(root: Path, base_sha: str, head_sha: str) -> str:
    values = str(
        _git(root, "merge-base", "--all", base_sha, head_sha, text=True)
    ).splitlines()
    if len(values) != 1 or SHA40.fullmatch(values[0]) is None:
        raise HandoffError("Pull-request history must have one exact merge base")
    return values[0]


def _proposal_commit_count(root: Path, merge_base: str, head_sha: str) -> int:
    """Count proposal commits without treating earlier feature changes as payload."""

    commits = str(
        _git(root, "rev-list", f"{merge_base}..{head_sha}", text=True)
    ).splitlines()
    if not commits:
        raise HandoffError("Proposal history has no commit")
    return len(commits)


def _read_bundle_blob(root: Path, head_sha: str) -> tuple[dict[str, object], bytes]:
    payload = _tree_blob(root, head_sha, HANDOFF_PATH)
    if len(payload) > MAX_BUNDLE_BYTES + 64 * 1024:
        raise HandoffError("SHACL Vue bundle exceeds 10 MiB")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HandoffError("SHACL Vue bundle is not valid UTF-8 JSON") from error
    if (
        isinstance(value, dict)
        and value.get("format") == "orinoco-shacl-submodule-handoff"
    ):
        if (
            set(value) != {"format", "version", "bundle", "metadata"}
            or value["version"] != 1
        ):
            raise HandoffError("Invalid coordinated handoff envelope")
        value = value["bundle"]
        payload = (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8")
    if len(payload) > MAX_BUNDLE_BYTES:
        raise HandoffError("SHACL Vue bundle exceeds 10 MiB")
    if (
        not isinstance(value, dict)
        or value.get("format") != BUNDLE_FORMAT
        or value.get("version") != BUNDLE_VERSION
        or SHA40.fullmatch(str(value.get("source_commit", ""))) is None
        or not isinstance(value.get("records"), list)
        or not 0 < len(value["records"]) <= MAX_BUNDLE_RECORDS
    ):
        raise HandoffError("SHACL Vue bundle does not satisfy bounded version 2")
    return value, payload


def submodule_handoff(root: Path, head_sha: str) -> dict[str, object] | None:
    """Validate operational coordinates against the exact website parent."""
    raw = json.loads(_tree_blob(root, head_sha, HANDOFF_PATH))
    parents = _parents(root, head_sha)
    if len(parents) != 1:
        raise HandoffError("Handoff must have exactly one parent")
    source = site_submodule(root, parents[0])
    if source is None:
        if raw.get("format") == "orinoco-shacl-submodule-handoff":
            raise HandoffError("Coordinated handoff has no site-specific gitlink")
        return None
    metadata = raw.get("metadata")
    if (
        raw.get("format") != "orinoco-shacl-submodule-handoff"
        or not isinstance(metadata, dict)
        or set(metadata)
        != {"repository", "source_commit", "head_sha", "branch", "pull_request"}
        or metadata.get("repository") != source["repository"]
        or metadata.get("source_commit") != source["source_commit"]
        or SHA40.fullmatch(str(metadata.get("head_sha", ""))) is None
        or re.fullmatch(
            r"curation/shacl-vue-" + parents[0][:12] + r"-[0-9a-f]{16}",
            str(metadata.get("branch", "")),
        )
        is None
        or type(metadata.get("pull_request")) is not int
        or metadata["pull_request"] < 1
    ):
        raise HandoffError(
            "Metadata proposal does not match the deployed site-specific gitlink"
        )
    return metadata


def inspect_proposal(
    root: Path,
    *,
    base_sha: str,
    head_sha: str,
) -> dict[str, object]:
    """Classify one exact head without executing bytes from the proposal."""

    root = root.resolve()
    base_sha = _exact_sha(base_sha, "Base SHA")
    head_sha = _exact_sha(head_sha, "Head SHA")
    if _head(root) != head_sha:
        raise HandoffError("Proposal checkout HEAD differs from the event head")
    if _status(root):
        raise HandoffError("Proposal checkout must be clean")
    parents = _parents(root, head_sha)
    if len(parents) == 1:
        parent_sha = parents[0]
        head_entries = _diff_entries(root, parent_sha, head_sha)
    elif len(parents) == 2 and base_sha in parents:
        parent_sha = base_sha
        head_entries = _diff_entries(root, base_sha, head_sha)
    else:
        fixed = _tree_entry(root, head_sha, HANDOFF_PATH)
        net = _diff_entries(root, base_sha, head_sha)
        if fixed is not None or any(
            _metadata_path(path) is not None or _decision_cache_path(path) is not None
            for _status, path in net
        ):
            raise HandoffError(
                "Canonical merge head must include the exact trusted base"
            )
        return {
            "base_sha": base_sha,
            "head_sha": head_sha,
            "parent_sha": "0" * 40,
            "paths": [],
            "phase": "irrelevant",
        }
    changed = {path for _status_name, path in head_entries}
    if changed == {"site-specific"}:
        before = site_submodule(root, parent_sha)
        after = site_submodule(root, head_sha)
        if (
            before is not None
            and after is not None
            and before["repository"] == after["repository"]
        ):
            return {
                "base_sha": base_sha,
                "head_sha": head_sha,
                "parent_sha": parent_sha,
                "paths": ["site-specific"],
                "phase": "canonical",
                "metadata": after,
            }
    metadata = sorted(path for path in changed if _metadata_path(path) is not None)
    curation_state = sorted(
        path for path in changed if _decision_cache_path(path) is not None
    )
    if HANDOFF_PATH not in changed and not metadata and not curation_state:
        return {
            "base_sha": base_sha,
            "head_sha": head_sha,
            "parent_sha": parent_sha,
            "paths": [],
            "phase": "irrelevant",
        }
    if HANDOFF_PATH in changed:
        if len(parents) != 1:
            raise HandoffError("The handoff head must be a one-parent commit")
        if head_entries != (("A", HANDOFF_PATH),):
            raise HandoffError(
                "The handoff head must add exactly the fixed bundle path"
            )
        phase = "handoff"
    else:
        outside = sorted(
            path
            for _status_name, path in head_entries
            if path not in metadata and path not in curation_state
        )
        if outside:
            raise HandoffError(
                "Canonical metadata head also changes an unapproved path: "
                + ", ".join(outside)
            )
        phase = "canonical"

    merge_base = _merge_base(root, base_sha, head_sha)
    commit_count = _proposal_commit_count(root, merge_base, head_sha)
    report: dict[str, object] = {
        "base_sha": base_sha,
        "commit_count": commit_count,
        "head_sha": head_sha,
        "merge_base_sha": merge_base,
        "parent_sha": parent_sha,
        "paths": [HANDOFF_PATH] if phase == "handoff" else metadata,
        "phase": phase,
    }
    if phase == "handoff":
        bundle, _payload = _read_bundle_blob(root, head_sha)
        if bundle["source_commit"] != parent_sha:
            raise HandoffError(
                "Bundle source_commit must equal the exact handoff parent"
            )
        report["source_commit"] = bundle["source_commit"]
        report["record_count"] = len(bundle["records"])
        metadata_handoff = submodule_handoff(root, head_sha)
        if metadata_handoff is not None:
            report["metadata"] = metadata_handoff
    return report


def extract_bundle(root: Path, *, head_sha: str, output: Path) -> dict[str, object]:
    """Copy the already-validated fixed-path blob to an ephemeral local file."""

    root = root.resolve()
    head_sha = _exact_sha(head_sha, "Head SHA")
    bundle, payload = _read_bundle_blob(root, head_sha)
    output = output.resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and (output.is_symlink() or not output.is_file()):
        raise HandoffError("Bundle output must be a regular file")
    output.write_bytes(payload)
    return {
        "bytes": len(payload),
        "output": os.fspath(output),
        "record_count": len(bundle["records"]),
        "source_commit": bundle["source_commit"],
    }


def verify_submodule_handoff(
    root: Path,
    *,
    head_sha: str,
    metadata_root: Path,
    pull: dict[str, object],
    permission: dict[str, object],
    commit: dict[str, object],
    curator: str,
    curator_id: str,
) -> dict[str, object]:
    """Check both Git histories and fresh GitHub authority before replacement."""
    metadata = submodule_handoff(root, head_sha)
    if metadata is None:
        raise HandoffError("Website handoff has no metadata proposal")
    base, head = pull.get("base", {}), pull.get("head", {})
    author = commit.get("author", {})
    user = permission.get("user", {})
    if (
        pull.get("state") != "open"
        or pull.get("draft") is not True
        or pull.get("number") != metadata["pull_request"]
        or base.get("repo", {}).get("full_name") != metadata["repository"]
        or base.get("ref") != base.get("repo", {}).get("default_branch")
        or base.get("sha") != metadata["source_commit"]
        or head.get("repo", {}).get("full_name") != metadata["repository"]
        or head.get("ref") != metadata["branch"]
        or head.get("sha") != metadata["head_sha"]
        or commit.get("sha") != metadata["head_sha"]
        or author.get("login") != curator
        or str(author.get("id")) != curator_id
        or permission.get("permission") not in {"write", "admin"}
        or user.get("login") != curator
        or str(user.get("id")) != curator_id
    ):
        raise HandoffError(
            "Metadata draft head, pinned base, or curator authority changed; inspect both pull requests before retrying"
        )
    metadata_head = str(metadata["head_sha"])
    metadata_source = str(metadata["source_commit"])
    if _parents(metadata_root, metadata_head) != (metadata_source,):
        raise HandoffError("Metadata handoff must have the exact gitlink parent")
    if _diff_entries(metadata_root, metadata_source, metadata_head) != (
        ("A", HANDOFF_PATH),
    ):
        raise HandoffError("Metadata handoff must add only the fixed bundle")
    bundle, _ = _read_bundle_blob(root, head_sha)
    other, _ = _read_bundle_blob(metadata_root, metadata_head)
    if bundle != other:
        raise HandoffError("Website and metadata handoff bundles differ")
    return metadata


def inspect_materialized_changes(
    root: Path,
    *,
    source_commit: str,
    in_submodule: bool = False,
) -> dict[str, object]:
    """Require one nonempty canonical metadata-only worktree change."""

    root = root.resolve()
    source_commit = _exact_sha(source_commit, "Source commit")
    if _head(root) != source_commit:
        raise HandoffError("Materialization checkout is not the exact source commit")
    submodule = None if in_submodule else site_submodule(root, source_commit)
    if submodule is not None:
        entries = [entry for entry in _status(root).split(b"\0") if entry]
        if any(entry[3:] != b"site-specific" for entry in entries):
            raise HandoffError("Materialization changed a path outside site-specific")
        report = inspect_materialized_changes(
            root / "site-specific",
            source_commit=submodule["source_commit"],
            in_submodule=True,
        )
        return {
            "paths": ["site-specific/" + path for path in report["paths"]],
            "source_commit": source_commit,
            "metadata": submodule,
        }
    raw = _status(root).split(b"\0")
    paths: list[str] = []
    for entry in raw:
        if not entry:
            continue
        if len(entry) < 4 or entry[2:3] != b" ":
            raise HandoffError("Git returned malformed worktree status")
        status = entry[:2].decode("ascii", "strict")
        if "R" in status or "C" in status:
            raise HandoffError("Materialized metadata may not rename or copy paths")
        try:
            path = entry[3:].decode("utf-8")
        except UnicodeDecodeError as error:
            raise HandoffError("Materialized path is not UTF-8") from error
        if _metadata_path(path, in_submodule=in_submodule) is None:
            raise HandoffError(f"Materialization changed an unapproved path: {path}")
        filesystem_path = root.joinpath(*PurePosixPath(path).parts)
        if "D" not in status and (
            filesystem_path.is_symlink() or not filesystem_path.is_file()
        ):
            raise HandoffError(f"Materialized path is not a regular file: {path}")
        paths.append(path)
    if not paths:
        raise HandoffError("SHACL Vue bundle produced no canonical metadata change")
    return {"paths": sorted(paths), "source_commit": source_commit}


def verify_materialized_commit(
    root: Path,
    *,
    source_commit: str,
    commit: str,
    in_submodule: bool = False,
) -> dict[str, object]:
    """Prove the replacement is one clean metadata commit on the source."""

    root = root.resolve()
    source_commit = _exact_sha(source_commit, "Source commit")
    commit = _exact_sha(commit, "Materialized commit")
    if _head(root) != commit or _status(root):
        raise HandoffError("Materialized commit checkout must be exact and clean")
    if _parents(root, commit) != (source_commit,):
        raise HandoffError("Materialized commit must have the handoff parent")
    entries = _diff_entries(root, source_commit, commit)
    if not entries:
        raise HandoffError("Materialized commit has no metadata change")
    submodule = None if in_submodule else site_submodule(root, source_commit)
    if submodule is not None:
        updated = site_submodule(root, commit)
        if (
            entries != (("M", "site-specific"),)
            or updated is None
            or updated["repository"] != submodule["repository"]
        ):
            raise HandoffError(
                "Website replacement must change only the site-specific gitlink"
            )
        verify_materialized_commit(
            root / "site-specific",
            source_commit=submodule["source_commit"],
            commit=updated["source_commit"],
            in_submodule=True,
        )
        return {
            "commit": commit,
            "source_commit": source_commit,
            "paths": ["site-specific"],
            "metadata": updated,
        }
    paths: list[str] = []
    for status, path in entries:
        if (
            status not in {"A", "M", "D"}
            or _metadata_path(path, in_submodule=in_submodule) is None
        ):
            raise HandoffError(
                f"Materialized commit changes an unapproved path: {path}"
            )
        if status in {"A", "M"}:
            _assert_regular_blob(root, commit, path)
        if status in {"M", "D"}:
            _assert_regular_blob(root, source_commit, path)
        paths.append(path)
    if _tree_entry(root, commit, HANDOFF_PATH) is not None:
        raise HandoffError("Materialized commit retained the temporary handoff")
    return {
        "commit": commit,
        "paths": sorted(paths),
        "source_commit": source_commit,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="handoff_command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--root", type=Path, required=True)
    inspect.add_argument("--base-sha", required=True)
    inspect.add_argument("--head-sha", required=True)
    extract = commands.add_parser("extract")
    extract.add_argument("--root", type=Path, required=True)
    extract.add_argument("--head-sha", required=True)
    extract.add_argument("--output", type=Path, required=True)
    materialized = commands.add_parser("inspect-materialized")
    materialized.add_argument("--root", type=Path, required=True)
    materialized.add_argument("--source-commit", required=True)
    verify = commands.add_parser("verify-commit")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--source-commit", required=True)
    verify.add_argument("--commit", required=True)
    submodule = commands.add_parser("verify-submodule")
    submodule.add_argument("--root", type=Path, required=True)
    submodule.add_argument("--head-sha", required=True)
    submodule.add_argument("--metadata-root", type=Path, required=True)
    for name in ("pull", "permission", "commit"):
        submodule.add_argument(f"--{name}-json", type=Path, required=True)
    submodule.add_argument("--curator", required=True)
    submodule.add_argument("--curator-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return execute(_parser().parse_args(argv))


def execute(args: argparse.Namespace) -> int:
    try:
        if args.handoff_command == "inspect":
            value: object = inspect_proposal(
                args.root,
                base_sha=args.base_sha,
                head_sha=args.head_sha,
            )
        elif args.handoff_command == "extract":
            value = extract_bundle(
                args.root,
                head_sha=args.head_sha,
                output=args.output,
            )
        elif args.handoff_command == "inspect-materialized":
            value = inspect_materialized_changes(
                args.root,
                source_commit=args.source_commit,
            )
        elif args.handoff_command == "verify-commit":
            value = verify_materialized_commit(
                args.root,
                source_commit=args.source_commit,
                commit=args.commit,
            )
        elif args.handoff_command == "verify-submodule":
            value = verify_submodule_handoff(
                args.root,
                head_sha=args.head_sha,
                metadata_root=args.metadata_root,
                pull=json.loads(args.pull_json.read_text()),
                permission=json.loads(args.permission_json.read_text()),
                commit=json.loads(args.commit_json.read_text()),
                curator=args.curator,
                curator_id=args.curator_id,
            )
        else:
            raise AssertionError(f"unhandled command: {args.handoff_command}")
    except HandoffError as error:
        print(f"SHACL Vue handoff error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
