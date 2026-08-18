"""Shared access to the single downstream metadata record inventory."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

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
