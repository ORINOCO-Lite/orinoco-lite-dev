#!/usr/bin/env python3
"""Validate a static editor review bundle and optionally update canonical YAML."""

from __future__ import annotations

import argparse
from dataclasses import replace
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any, Sequence

from dump_things_service import Format
from dump_things_service.converter import FormatConverter
import yaml

from build_con_site import BuildError
from con_projection import (
    SCHEMA,
    SITE,
    ProjectionError,
    SourceRecord,
    load_projection_contract,
    roundtrip_records,
    source_closure,
    require_no_ignored_files as projection_require_no_ignored_files,
    validate_record_contract,
)


FORMAT = "con-shacl-review-bundle"
VERSION = 1
MAX_BUNDLE_BYTES = 10 * 1024 * 1024
MAX_RECORDS = 50
TOP_LEVEL_KEYS = {"format", "records", "site_commit", "version"}
RECORD_KEYS = {
    "pid",
    "rdf_turtle",
    "schema_type",
    "source_path",
    "source_sha256",
}


def git_commit(path: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", result):
        raise BuildError(f"Could not determine commit for {path}")
    return result


def require_clean_checkout(path: Path) -> None:
    status = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status:
        raise BuildError(
            "Site checkout has tracked or untracked changes; preserve or commit "
            "them before applying a review bundle"
        )
    try:
        projection_require_no_ignored_files(
            path,
            "static editor canonical inputs",
            (
                "profiles/con/metadata",
                "profiles/con/profile.yaml",
                "profiles/con/projection.yaml",
            ),
        )
    except ProjectionError as error:
        raise BuildError(str(error)) from error


def read_bundle(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BuildError("Review bundle must be a regular file")
    if path.stat().st_size > MAX_BUNDLE_BYTES:
        raise BuildError("Review bundle is larger than 10 MiB")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError("Review bundle is not valid UTF-8 JSON") from error
    if not isinstance(value, dict) or set(value) != TOP_LEVEL_KEYS:
        raise BuildError("Review bundle has unexpected top-level fields")
    records = value.get("records")
    if (
        value.get("format") != FORMAT
        or value.get("version") != VERSION
        or not isinstance(records, list)
        or not 0 < len(records) <= MAX_RECORDS
        or not isinstance(value.get("site_commit"), str)
    ):
        raise BuildError("Review bundle does not satisfy version 1")
    return value


def preserve_order(value: Any, template: Any) -> Any:
    if isinstance(value, dict):
        template_dict = template if isinstance(template, dict) else {}
        ordered: dict[str, Any] = {}
        for key in template_dict:
            if key in value:
                ordered[key] = preserve_order(value[key], template_dict[key])
        for key in sorted(set(value) - set(ordered)):
            ordered[key] = preserve_order(value[key], None)
        return ordered
    if isinstance(value, list):
        template_list = template if isinstance(template, list) else []
        return [
            preserve_order(
                item, template_list[index] if index < len(template_list) else None
            )
            for index, item in enumerate(value)
        ]
    return value


def dump_yaml(record: dict[str, Any], original: dict[str, Any]) -> str:
    preferred = {"pid": record["pid"], "schema_type": record["schema_type"]}
    preferred.update(
        {key: value for key, value in record.items() if key not in preferred}
    )
    ordered = preserve_order(preferred, {"pid": None, "schema_type": None, **original})
    return yaml.safe_dump(
        ordered,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=80,
    )


def canonical_index(
    site: Path,
) -> tuple[dict[str, SourceRecord], list[SourceRecord], Any]:
    contract = load_projection_contract()
    records = source_closure(contract)
    canonical = {
        record.record["pid"]: record
        for record in records
        if record.category == "canonical"
    }
    if not canonical:
        raise BuildError("Canonical inventory is empty")
    for record in canonical.values():
        if site.resolve() not in record.path.resolve().parents:
            raise BuildError("Projection contract does not use the selected site")
    return canonical, records, contract


def validate_bundle(bundle: dict[str, Any], site: Path = SITE) -> dict[Path, str]:
    site = site.resolve()
    require_clean_checkout(site)
    if bundle["site_commit"] != git_commit(site):
        raise BuildError("Review bundle is stale for the current site commit")
    canonical, inventory, contract = canonical_index(site)
    converter = FormatConverter(str(SCHEMA), Format.ttl, Format.json)
    replacements: dict[str, SourceRecord] = {}
    rendered: dict[Path, str] = {}

    for item in bundle["records"]:
        if not isinstance(item, dict) or set(item) != RECORD_KEYS:
            raise BuildError("Review bundle record has unexpected fields")
        if not all(isinstance(item[key], str) for key in RECORD_KEYS):
            raise BuildError("Review bundle record fields must be strings")
        pid = item["pid"]
        if pid in replacements:
            raise BuildError(f"Review bundle contains duplicate PID: {pid}")
        source = canonical.get(pid)
        if source is None:
            raise BuildError(f"Review bundle PID is not canonical: {pid}")
        relative = PurePosixPath(item["source_path"])
        expected_relative = source.path.resolve().relative_to(site).as_posix()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != item["source_path"]
            or item["source_path"] != expected_relative
        ):
            raise BuildError(f"Review bundle source path does not match {pid}")
        if source.path.is_symlink() or not source.path.is_file():
            raise BuildError(f"Canonical source is not a regular file: {pid}")
        original_bytes = source.path.read_bytes()
        digest = hashlib.sha256(original_bytes).hexdigest()
        if item["source_sha256"] != digest:
            raise BuildError(f"Review bundle source digest is stale for {pid}")
        if item["schema_type"] != source.record["schema_type"]:
            raise BuildError(f"Review bundle schema type does not match {pid}")
        if len(item["rdf_turtle"].encode("utf-8")) > 2 * 1024 * 1024:
            raise BuildError(f"Review bundle RDF is too large for {pid}")
        try:
            restored = converter.convert(item["rdf_turtle"], source.class_name)
        except Exception as error:
            raise BuildError(
                f"Review bundle RDF is invalid for {pid}: {error}"
            ) from error
        if not isinstance(restored, dict):
            raise BuildError(f"Review bundle did not restore one record for {pid}")
        restored["schema_type"] = item["schema_type"]
        if restored.get("pid") != pid:
            raise BuildError(f"Review bundle RDF changed the PID for {pid}")
        replacements[pid] = replace(source, record=restored)
        rendered[source.path] = dump_yaml(restored, source.record)

    candidate = [replacements.get(item.record["pid"], item) for item in inventory]
    validate_record_contract(candidate, contract)
    roundtrip_records(candidate)
    return rendered


def diff_updates(updates: dict[Path, str], site: Path = SITE) -> str:
    site = site.resolve()
    chunks: list[str] = []
    for path, content in sorted(updates.items(), key=lambda item: str(item[0])):
        before = path.read_text(encoding="utf-8")
        relative = path.resolve().relative_to(site).as_posix()
        chunks.extend(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            )
        )
    return "".join(chunks)


def apply_updates(updates: dict[Path, str]) -> None:
    for path, content in updates.items():
        if path.is_symlink() or not path.is_file():
            raise BuildError(f"Refusing to replace non-regular source: {path}")
        mode = path.stat().st_mode
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary.write(content)
            temporary_path = Path(temporary.name)
        try:
            os.chmod(temporary_path, mode)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        updates = validate_bundle(read_bundle(args.bundle))
        difference = diff_updates(updates)
        if not difference:
            print("Review bundle is valid and produces no canonical YAML changes.")
            return 0
        print(difference, end="")
        if args.apply:
            apply_updates(updates)
            print(f"Applied {len(updates)} validated canonical record update(s).")
        else:
            print("Dry run only; rerun with --apply after reviewing this diff.")
        return 0
    except (BuildError, ProjectionError, OSError, ValueError) as error:
        print(f"CON editor bundle: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
