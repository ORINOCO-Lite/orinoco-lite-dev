"""Localize the exact pinned LinkML source import closure for offline resources use."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

import yaml

from .errors import DriverError


def _source_for_import(source_root: Path, current: Path, import_name: str) -> Path | None:
    if import_name == "linkml:types":
        return None
    if import_name.startswith("dlschemas:"):
        relative = PurePosixPath(import_name.removeprefix("dlschemas:") + ".yaml")
        return source_root.joinpath(*relative.parts)
    relative = PurePosixPath(import_name + ".yaml")
    return current.parent.joinpath(*relative.parts)


def localize_schema(source_root: Path, entry: Path, destination: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    entry = entry.resolve()
    if source_root not in entry.parents or entry.is_symlink() or not entry.is_file():
        raise DriverError("Schema entrypoint must be a regular file below its source root")
    destination.mkdir(parents=True, exist_ok=True)
    pending = [entry]
    seen: set[Path] = set()
    while pending:
        source = pending.pop()
        if source in seen:
            continue
        seen.add(source)
        try:
            raw = source.read_bytes()
            value = yaml.safe_load(raw)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
            raise DriverError(f"Schema source is invalid: {source}") from error
        if not isinstance(value, dict):
            raise DriverError(f"Schema source is not a mapping: {source}")
        imports = value.get("imports", [])
        if not isinstance(imports, list) or not all(isinstance(item, str) for item in imports):
            raise DriverError(f"Schema imports are invalid: {source}")
        relative = source.relative_to(source_root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        localized: list[str] = []
        for import_name in imports:
            imported = _source_for_import(source_root, source, import_name)
            if imported is None:
                localized.append(import_name)
                continue
            imported = imported.resolve()
            if source_root not in imported.parents or imported.is_symlink() or not imported.is_file():
                raise DriverError(f"Schema source import is missing: {import_name}")
            pending.append(imported)
            # LinkML resolves imports relative to the importing file. Preserve
            # the source tree and drop only the extension in the import name.
            target_parent = target.parent
            localized_path = Path(
                os.path.relpath(
                    destination / imported.relative_to(source_root), target_parent
                )
            )
            localized.append(localized_path.with_suffix("").as_posix())
        value["imports"] = localized
        target.write_text(
            yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    return {
        "entrypoint": entry.relative_to(source_root).as_posix(),
        "sources": len(seen),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--entry", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = localize_schema(
            args.source_root, args.entry, args.destination.resolve()
        )
    except DriverError as error:
        parser.exit(1, f"orinoco schema release: {error}\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
