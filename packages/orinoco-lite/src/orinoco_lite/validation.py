"""Fast, dependency-light validation of the downstream repository contract."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import subprocess
from typing import Any, Iterator

import yaml

from .annotations import annotation_root, companion_sources, validate_stored_record
from .config import WorkspaceConfig
from .errors import ConfigurationError
from .integrity import tree_sha256
from .records import record_files


MAX_RECORD_BYTES = 10 * 1024 * 1024
REQUIRED_INPUT_PATHS = (
    "records",
    "provenance",
    "editorial",
    "assets",
    "site",
    "source_adapters",
)


def _files(root: Path) -> Iterator[Path]:
    for candidate in sorted(root.rglob("*")):
        if candidate.is_symlink():
            raise ConfigurationError(
                f"Site-owned paths cannot contain symlinks: {candidate}"
            )
        if candidate.is_file():
            yield candidate
        elif not candidate.is_dir():
            raise ConfigurationError(f"Site-owned path is not regular: {candidate}")


def _load_record(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise ConfigurationError(f"Metadata record is larger than 10 MiB: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Metadata record is invalid UTF-8 YAML: {path}") from error
    if not isinstance(value, dict):
        raise ConfigurationError(f"Metadata record must be a YAML mapping: {path}")
    validate_stored_record(value)
    pid = value.get("pid")
    schema_type = value.get("schema_type")
    if not isinstance(pid, str) or not pid or not isinstance(schema_type, str) or not schema_type:
        raise ConfigurationError(
            f"Metadata record requires non-empty pid and schema_type: {path}"
        )
    if schema_type.startswith(("http://", "https://")):
        raise ConfigurationError(
            f"Metadata schema_type must retain its reviewed CURIE form: {path}"
        )
    return value


def _gitlinks(root: Path) -> list[str]:
    if not (root / ".git").exists():
        return []
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return []
    links: list[str] = []
    for line in result.stdout.splitlines():
        metadata, _, name = line.partition("\t")
        if metadata.startswith("160000 "):
            links.append(name)
    return links


def _validate_metadata_boundary(workspace: WorkspaceConfig) -> None:
    """Allow only records and the specification-defined annotation overlay."""

    metadata_root = workspace.root / "metadata"
    if not metadata_root.exists():
        return
    if metadata_root.is_symlink() or not metadata_root.is_dir():
        raise ConfigurationError(
            f"The metadata boundary must be a regular directory: {metadata_root}"
        )
    records_root = workspace.path("records")
    annotations_root = annotation_root(workspace)
    allowed_roots = (records_root, annotations_root)
    for candidate in sorted(metadata_root.rglob("*")):
        if candidate.is_symlink():
            raise ConfigurationError(
                f"Site-owned paths cannot contain symlinks: {candidate}"
            )
        if any(candidate == root or root in candidate.parents for root in allowed_roots):
            continue
        if any(candidate in root.parents for root in allowed_roots):
            if not candidate.is_dir():
                raise ConfigurationError(
                    f"Metadata namespace parent must be a directory: {candidate}"
                )
            continue
        raise ConfigurationError(
            "Everything below metadata must be part of paths.records or "
            "metadata/overlays/annotations; "
            f"found undeclared content: {candidate}"
        )


def validate_workspace(workspace: WorkspaceConfig) -> dict[str, Any]:
    """Validate path ownership and the basic record inventory.

    The released schema/projection driver performs semantic validation. This
    check deliberately runs before that driver so malformed or unsafe
    downstream structure fails without downloading or executing a runtime.
    """

    if (workspace.root / ".gitmodules").exists():
        raise ConfigurationError(
            "A downstream Orinoco repository must not contain .gitmodules"
        )
    links = _gitlinks(workspace.root)
    if links:
        raise ConfigurationError(
            f"A downstream Orinoco repository must not contain gitlinks: {links}"
        )
    for name in REQUIRED_INPUT_PATHS:
        path = workspace.path(name)
        if not path.is_dir():
            raise ConfigurationError(f"Required site-owned directory is missing: {path}")
    _validate_metadata_boundary(workspace)

    records = [(path, _load_record(path)) for path in record_files(workspace)]
    if not records:
        raise ConfigurationError("Metadata record inventory is empty")

    pids: dict[str, Path] = {}
    classes: Counter[str] = Counter()
    for path, record in records:
        pid = record["pid"]
        if pid in pids:
            raise ConfigurationError(
                f"Metadata PID {pid!r} is duplicated in {pids[pid]} and {path}"
            )
        pids[pid] = path
        classes[record["schema_type"]] += 1

    companions = companion_sources(workspace)

    asset_manifest = workspace.path("assets") / "manifest.yaml"
    if not asset_manifest.is_file() or asset_manifest.is_symlink():
        raise ConfigurationError(
            f"Site asset ownership manifest is missing: {asset_manifest}"
        )
    provenance_files = list(_files(workspace.path("provenance")))
    if not provenance_files:
        raise ConfigurationError("Metadata provenance inventory is empty")

    file_counts = {
        name: sum(1 for _ in _files(workspace.path(name)))
        for name in REQUIRED_INPUT_PATHS
    }
    file_counts["annotations"] = len(companions)
    assertion_count = sum(source.assertion_count for source in companions)
    tree_hashes = {
        name: tree_sha256(workspace.path(name)) for name in REQUIRED_INPUT_PATHS
    }
    tree_hashes["annotations"] = tree_sha256(annotation_root(workspace))
    return {
        "annotation_assertions": assertion_count,
        "annotation_companions": len(companions),
        "records": len(records),
        "record_classes": dict(sorted(classes.items())),
        "files": file_counts,
        "site": workspace.site_name,
        "site_owned_tree_sha256": tree_hashes,
        "version": 2,
    }


def report_json(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
