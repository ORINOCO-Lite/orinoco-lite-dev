"""Shared access to the single downstream metadata record inventory."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

from .annotations import (
    companion_sources,
    join_annotations,
    validate_stored_record,
)
from .config import WorkspaceConfig
from .errors import ConfigurationError


RECORD_SUFFIXES = {".yaml", ".yml"}
RECORD_SOURCE_CONTROL_NAME = ".dumpthings.yaml"


def record_files(workspace: WorkspaceConfig) -> list[Path]:
    """Return every Thing from the configured record root, failing closed."""

    root = workspace.path("records")
    control = root / RECORD_SOURCE_CONTROL_NAME
    records: list[Path] = []
    for candidate in sorted(root.rglob("*")):
        if candidate.is_symlink():
            raise ConfigurationError(
                f"Metadata records cannot contain symlinks: {candidate}"
            )
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise ConfigurationError(f"Metadata record path is not regular: {candidate}")
        if candidate == control:
            continue
        if (
            candidate.suffix.lower() not in RECORD_SUFFIXES
            or any(
                part.startswith(".")
                for part in candidate.relative_to(root).parts
            )
        ):
            raise ConfigurationError(
                "Everything below paths.records must be a Thing YAML record; "
                f"found unsupported content: {candidate}"
            )
        records.append(candidate)
    return records


def record_sources(workspace: WorkspaceConfig) -> list[dict[str, str]]:
    """Load stable source coordinates for every configured Thing."""

    records: list[dict[str, str]] = []
    pids: set[str] = set()
    for path in record_files(workspace):
        content = path.read_text(encoding="utf-8")
        value = yaml.safe_load(content)
        if not isinstance(value, dict):
            raise ConfigurationError(f"Metadata record must be a mapping: {path}")
        validate_stored_record(value)
        pid = value.get("pid")
        schema_type = value.get("schema_type")
        if not isinstance(pid, str) or not isinstance(schema_type, str):
            raise ConfigurationError(f"Metadata record identity is invalid: {path}")
        if pid in pids:
            raise ConfigurationError(f"Metadata record PID is duplicated: {pid}")
        pids.add(pid)
        records.append(
            {
                "content": content,
                "path": path.relative_to(workspace.root).as_posix(),
                "pid": pid,
                "schema_type": schema_type,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )
    records.sort(key=lambda item: (item["pid"], item["path"]))
    return records


def stored_records(workspace: WorkspaceConfig) -> list[dict[str, Any]]:
    """Load the human-facing record tree without machine annotations."""

    return [yaml.safe_load(source["content"]) for source in record_sources(workspace)]


def joined_records(
    workspace: WorkspaceConfig,
    schema: Path,
) -> list[dict[str, Any]]:
    """Load records joined with their mirrored machine PAV companions."""

    # Retain the schema argument as part of the established record-loading
    # surface.  Annotation joining no longer derives assertions from scalar
    # slots and therefore does not need schema slot semantics.
    del schema

    sources = record_sources(workspace)
    companions = {
        source.record_path.resolve(): source.value
        for source in companion_sources(workspace)
    }
    if not companions:
        return [yaml.safe_load(source["content"]) for source in sources]

    joined: list[dict[str, Any]] = []
    for source in sources:
        path = workspace.root / source["path"]
        record = yaml.safe_load(source["content"])
        joined.append(
            join_annotations(record, companions.get(path.resolve()))
        )
    return joined
