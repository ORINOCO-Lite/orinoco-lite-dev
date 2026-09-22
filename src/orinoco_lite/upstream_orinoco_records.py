#!/usr/bin/env python3
"""Convert upstream JSONL to YAML records and separated machine PAV."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from orinoco_lite.annotations import (
    compact_enrichment_view,
    split_enrichment_view,
    validate_annotation_companion,
)
import yaml

from . import upstream_snapshot


FORMAT_NAME = "orinoco-upstream-storage-projection-v2"


class StorageProjectionError(RuntimeError):
    """Report a non-reversible upstream-to-Orinoco storage projection."""


def _load_companion(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise StorageProjectionError(f"invalid annotation companion {path}") from error
    if not isinstance(value, dict):
        raise StorageProjectionError(f"annotation companion is not a mapping: {path}")
    if path.read_bytes() != upstream_snapshot.canonical_yaml_bytes(value):
        raise StorageProjectionError(f"annotation companion is not canonical: {path}")
    return value


def _write_companions(
    projected: Sequence[upstream_snapshot.RecordEnvelope],
    companions: Mapping[str, Mapping[str, object]],
    root: Path,
) -> None:
    by_pid = {item.pid: item for item in projected}
    for pid, companion in sorted(companions.items()):
        envelope = by_pid[pid]
        path = root / upstream_snapshot.record_relative_path(envelope)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(upstream_snapshot.canonical_yaml_bytes(companion))


def verify_projection(
    source: Path,
    output: Path,
) -> dict[str, Any]:
    """Verify exact reconstruction of the downloaded records."""

    expected = upstream_snapshot.load_jsonl(source)
    records_root = output / "metadata" / "records"
    companions_root = output / "metadata" / "overlays" / "annotations"
    stored = upstream_snapshot.load_records_tree(records_root)
    stored_by_pid = {item.pid: item for item in stored}
    expected_by_pid = {item.pid: item for item in expected}
    if stored_by_pid.keys() != expected_by_pid.keys():
        raise StorageProjectionError("projected stored record inventory changed")

    companions: dict[str, dict[str, Any]] = {}
    if companions_root.exists():
        for path in sorted(companions_root.rglob("*.yaml")):
            relative = path.relative_to(companions_root)
            record_path = records_root / relative
            if not record_path.is_file():
                raise StorageProjectionError(
                    f"annotation companion has no mirrored record: {path}"
                )
            companion = _load_companion(path)
            pid = companion.get("record")
            if not isinstance(pid, str) or pid in companions:
                raise StorageProjectionError(
                    f"annotation companion has invalid or duplicate PID: {path}"
                )
            companions[pid] = companion

    reconstructed: list[upstream_snapshot.RecordEnvelope] = []
    assertion_count = 0
    for pid in sorted(expected_by_pid):
        stored_item = stored_by_pid[pid]
        companion = companions.get(pid)
        if companion is not None:
            assertion_count += validate_annotation_companion(
                stored_item.record, companion
            )
        compact = compact_enrichment_view(stored_item.record, companion, preserve_source=True)
        reconstructed.append(
            upstream_snapshot.RecordEnvelope(stored_item.class_name, compact)
        )
    upstream_snapshot.compare_snapshots(
        expected, reconstructed,
        expected_label="downloaded records",
        actual_label="records reconstructed from YAML",
    )
    return {
        "annotation_assertions": assertion_count,
        "annotation_companions": len(companions),
        "reconstructed_semantic_sha256": upstream_snapshot.semantic_digest(reconstructed),
        "format": FORMAT_NAME,
        "record_count": len(stored),
        "source_semantic_sha256": upstream_snapshot.semantic_digest(expected),
        "stored_records_semantic_sha256": upstream_snapshot.semantic_digest(stored),
        "stored_records_tree_sha256": upstream_snapshot.records_tree_digest(
            records_root
        ),
    }


def project(
    source: Path,
    output: Path,
    *,
    replace: bool = False,
) -> dict[str, Any]:
    """Split supported compact machine PAV and atomically verify the result."""

    expected = upstream_snapshot.load_jsonl(source)
    projected: list[upstream_snapshot.RecordEnvelope] = []
    companions: dict[str, Mapping[str, object]] = {}
    for envelope in expected:
        try:
            stored, companion = split_enrichment_view(envelope.record)
        except Exception as error:
            raise StorageProjectionError(
                f"could not split machine PAV for {envelope.pid}: {error}"
            ) from error
        projected.append(
            upstream_snapshot.RecordEnvelope(envelope.class_name, stored)
        )
        if companion is not None:
            companions[envelope.pid] = companion
        reconstructed = compact_enrichment_view(stored, companion, preserve_source=True)
        if upstream_snapshot.canonical_json(reconstructed) != upstream_snapshot.canonical_json(envelope.record):
            raise StorageProjectionError(
                f"machine PAV split is not reversible for {envelope.pid}"
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.new-", dir=output.parent)
    )
    try:
        records_root = temporary / "metadata" / "records"
        companions_root = temporary / "metadata" / "overlays" / "annotations"
        upstream_snapshot.write_records_tree(projected, records_root)
        companions_root.mkdir(parents=True)
        _write_companions(projected, companions, companions_root)
        report = verify_projection(source, temporary)
        upstream_snapshot.write_json(temporary / "manifest.json", report)
        if output.exists():
            if not replace:
                raise StorageProjectionError(
                    f"storage projection destination already exists: {output}"
                )
            if output.is_symlink() or not output.is_dir():
                raise StorageProjectionError(
                    f"storage projection destination is unsafe: {output}"
                )
            shutil.rmtree(output)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("project", "verify"))
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--replace", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "project":
            result = project(args.source, args.output, replace=args.replace)
        else:
            result = verify_projection(args.source, args.output)
    except (StorageProjectionError, upstream_snapshot.SnapshotError) as error:
        parser.exit(1, f"upstream-orinoco-records: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
