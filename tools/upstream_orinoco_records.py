#!/usr/bin/env python3
"""Project exact upstream YAML into Orinoco records plus PAV companions."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from orinoco_lite.annotations import (
    annotation_semantic_view,
    compact_enrichment_view,
    join_annotations,
    split_enrichment_view,
    validate_annotation_companion,
)
import yaml

if __package__:
    from . import upstream_snapshot
else:  # Direct ``python tools/...`` use.
    import upstream_snapshot


FORMAT_NAME = "orinoco-upstream-storage-projection-v2"


class StorageProjectionError(RuntimeError):
    """Report a non-reversible upstream-to-Orinoco storage projection."""


PAV_ALIASES = {
    "http://purl.org/pav/importedBy": "pav:importedBy",
    "http://purl.org/pav/importedFrom": "pav:importedFrom",
}


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def normalize_schema_compatibility(
    value: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Omit the one observed invalid optional datetime sentinel, with evidence."""

    normalized = deepcopy(dict(value))
    pid = normalized.get("pid")
    if not isinstance(pid, str) or not pid:
        raise StorageProjectionError("schema compatibility input has no PID")
    adjustments: list[dict[str, str]] = []

    def inspect(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key, child in tuple(item.items()):
                child_path = f"{path}/{_pointer_token(str(key))}"
                if key == "at_time" and child == "-":
                    adjustments.append(
                        {
                            "action": "omit-invalid-optional-datetime-sentinel",
                            "path": child_path,
                            "pid": pid,
                            "source_value": "-",
                        }
                    )
                    del item[key]
                    continue
                inspect(child, child_path)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                inspect(child, f"{path}/{index}")

    inspect(normalized, "")
    return normalized, adjustments


def normalize_machine_pav(
    value: Mapping[str, Any],
) -> tuple[dict[str, Any], int, int]:
    """Normalize URI spellings and expanded values to compact companion form."""

    normalized = deepcopy(dict(value))
    alias_count = 0
    expanded_count = 0

    def inspect(item: Any) -> None:
        nonlocal alias_count, expanded_count
        if isinstance(item, dict):
            for alias, canonical in PAV_ALIASES.items():
                if alias not in item:
                    continue
                if canonical in item:
                    raise StorageProjectionError(
                        f"machine annotation contains both {canonical!r} and {alias!r}"
                    )
                item[canonical] = item.pop(alias)
                alias_count += 1
            for canonical in set(PAV_ALIASES.values()):
                raw = item.get(canonical)
                if not isinstance(raw, Mapping):
                    continue
                if set(raw) != {"annotation_tag", "annotation_value"}:
                    raise StorageProjectionError(
                        f"expanded machine annotation {canonical!r} is malformed"
                    )
                annotation_tag = raw.get("annotation_tag")
                valid_tags = {canonical} | {
                    alias for alias, target in PAV_ALIASES.items() if target == canonical
                }
                if annotation_tag not in valid_tags:
                    raise StorageProjectionError(
                        f"expanded machine annotation tag is malformed: {annotation_tag!r}"
                    )
                item[canonical] = raw.get("annotation_value")
                expanded_count += 1
            for child in item.values():
                inspect(child)
        elif isinstance(item, list):
            for child in item:
                inspect(child)

    inspect(normalized)
    return normalized, alias_count, expanded_count


def compact_annotation_count(value: Any) -> int:
    """Count annotation scalar values expanded by the semantic storage view."""

    count = 0
    if isinstance(value, Mapping):
        annotations = value.get("annotations")
        if isinstance(annotations, Mapping):
            count += sum(not isinstance(item, Mapping) for item in annotations.values())
        count += sum(compact_annotation_count(item) for item in value.values())
    elif isinstance(value, list):
        count += sum(compact_annotation_count(item) for item in value)
    return count


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
    """Prove that stored records plus compact companions recreate the source."""

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

    normalized_expected: list[upstream_snapshot.RecordEnvelope] = []
    reconstructed: list[upstream_snapshot.RecordEnvelope] = []
    joined: list[upstream_snapshot.RecordEnvelope] = []
    assertion_count = 0
    normalized_aliases = 0
    normalized_expanded = 0
    schema_adjustments: list[dict[str, str]] = []
    for pid in sorted(expected_by_pid):
        expected_item = expected_by_pid[pid]
        normalized_record, alias_count, expanded_count = normalize_machine_pav(
            expected_item.record
        )
        normalized_aliases += alias_count
        normalized_expanded += expanded_count
        normalized_record, adjustments = normalize_schema_compatibility(
            normalized_record
        )
        schema_adjustments.extend(adjustments)
        normalized_expected.append(
            upstream_snapshot.RecordEnvelope(
                expected_item.class_name,
                annotation_semantic_view(normalized_record),
            )
        )
        stored_item = stored_by_pid[pid]
        companion = companions.get(pid)
        if companion is not None:
            assertion_count += validate_annotation_companion(
                stored_item.record, companion
            )
        compact = compact_enrichment_view(stored_item.record, companion)
        reconstructed.append(
            upstream_snapshot.RecordEnvelope(stored_item.class_name, compact)
        )
        expanded = join_annotations(stored_item.record, companion)
        joined.append(
            upstream_snapshot.RecordEnvelope(stored_item.class_name, expanded)
        )
    upstream_snapshot.compare_snapshots(
        normalized_expected,
        joined,
        expected_label="annotation-normalized upstream snapshot",
        actual_label="joined Orinoco semantic records",
    )
    return {
        "annotation_assertions": assertion_count,
        "annotation_companions": len(companions),
        "compact_annotation_values_expanded": sum(
            compact_annotation_count(item.record) for item in expected
        ),
        "compact_reconstruction_semantic_sha256": upstream_snapshot.semantic_digest(
            reconstructed
        ),
        "format": FORMAT_NAME,
        "joined_orinoco_semantic_sha256": upstream_snapshot.semantic_digest(joined),
        "machine_pav_uri_aliases_normalized": normalized_aliases,
        "machine_pav_expanded_values_normalized": normalized_expanded,
        "record_count": len(stored),
        "schema_compatibility_adjustments": schema_adjustments,
        "schema_compatibility_adjustment_count": len(schema_adjustments),
        "source_semantic_sha256": upstream_snapshot.semantic_digest(expected),
        "normalized_source_semantic_sha256": upstream_snapshot.semantic_digest(
            normalized_expected
        ),
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
            compatible, _ = normalize_schema_compatibility(envelope.record)
            stored, companion = split_enrichment_view(compatible)
            stored = annotation_semantic_view(stored)
        except Exception as error:
            raise StorageProjectionError(
                f"could not split machine PAV for {envelope.pid}: {error}"
            ) from error
        projected.append(
            upstream_snapshot.RecordEnvelope(envelope.class_name, stored)
        )
        if companion is not None:
            companions[envelope.pid] = companion
        reconstructed = join_annotations(stored, companion)
        normalized, _, _ = normalize_machine_pav(envelope.record)
        normalized, _ = normalize_schema_compatibility(normalized)
        normalized = annotation_semantic_view(normalized)
        if upstream_snapshot.canonical_json(reconstructed) != upstream_snapshot.canonical_json(
            normalized
        ):
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
