"""Copy licensed build inputs into the Python package before it is built."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Sequence

import yaml

from .errors import ConfigurationError, IntegrityError, OrinocoError


def _relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ConfigurationError(f"{label} must be a safe relative path")
    path = PurePosixPath(value)
    if value == "." or path.is_absolute() or path.as_posix() != value or any(
        part in {".", "..", ".git"} for part in path.parts
    ):
        raise ConfigurationError(f"{label} must be a safe relative path")
    return value


def _copy(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise IntegrityError(f"Package source cannot be a symlink: {source}")
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir()):
            if child.name in {".git", "__pycache__"} or child.suffix in {
                ".pyc", ".pyo", ".egg-info"
            }:
                continue
            _copy(child, destination / child.name)
    elif source.is_file():
        if destination.exists():
            raise ConfigurationError(f"Package output path is repeated: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o755 if source.stat().st_mode & 0o111 else 0o644)
    else:
        raise IntegrityError(f"Package source is missing or not regular: {source}")


def stage_package_resources(
    spec_path: Path, destination: Path, *, source_commit: str
) -> dict[str, object]:
    """Stage ordinary files directly, without an intermediate release artifact."""

    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ConfigurationError("Package source commit must be a full lowercase Git SHA")
    if destination.exists():
        raise IntegrityError(f"Package resource destination already exists: {destination}")
    try:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ConfigurationError("Package resource source map is invalid YAML") from error
    if not isinstance(spec, dict) or not isinstance(spec.get("resources"), list):
        raise ConfigurationError("Package resource source map requires resources")
    source_root = spec_path.resolve().parent.parent
    if "source_root" in spec:
        source_root = spec_path.resolve().parent / _relative(spec["source_root"], "source_root")
    licenses = spec.get("licenses")
    if not isinstance(licenses, list) or not licenses:
        raise ConfigurationError("Package resource source map requires licenses")
    destination.mkdir(parents=True)
    try:
        for item in spec["resources"]:
            if not isinstance(item, dict):
                raise ConfigurationError("Package resource entries must be mappings")
            source = _relative(item.get("source"), "Resource source")
            target = _relative(item.get("destination"), "Resource destination")
            # Check every ancestor as well as the final entry for symlink escapes.
            candidate = source_root / source
            for parent in (candidate, *candidate.parents):
                if parent == source_root.parent:
                    break
                if parent.is_symlink():
                    raise IntegrityError(f"Package source cannot be a symlink: {parent}")
            _copy(candidate, destination / target)
        for value in licenses:
            license_path = destination / _relative(value, "License path")
            if not license_path.is_file():
                raise ConfigurationError(f"Package license is absent: {value}")
        commit_file = destination / "source-commit.txt"
        if commit_file.exists():
            raise ConfigurationError("Package output path is repeated: source-commit.txt")
        commit_file.write_text(source_commit + "\n", encoding="ascii")
    except Exception:
        shutil.rmtree(destination)
        raise
    return {"root": str(destination), "files": sum(p.is_file() for p in destination.rglob("*"))}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args(argv)
    try:
        stage_package_resources(args.spec, args.destination, source_commit=args.source_commit)
    except OrinocoError as error:
        parser.exit(1, f"orinoco package resources: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
