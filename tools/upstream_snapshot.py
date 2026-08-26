#!/usr/bin/env python3
"""Materialize and audit lossless upstream JSONL/YAML snapshots.

The upstream API snapshot is an envelope JSONL stream whose records include a
top-level ``schema_type``.  Dump Things record-directory stores serialize the
same JSON values as YAML, but the default schema-type layer removes that field
on disk and reconstructs it from the class directory on read.  Orinoco Lite,
by contrast, requires ``schema_type`` in every canonical YAML record.

This module keeps those two representations explicit.  It never performs an
RDF conversion, schema normalization, list de-duplication, or graph closure.
Exact canonical JSON is the semantic equality boundary for JSON/YAML
round-trips; RDF validation remains a separate operation.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from dump_things_service.utils import json2yaml, order_dict
import yaml
from yaml.constructor import ConstructorError


CLASS_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
CONTROL_FILES = frozenset({".directory_dir_index.db", ".dumpthings.yaml"})
FORMAT_NAME = "orinoco-upstream-record-snapshot-v1"


class SnapshotError(RuntimeError):
    """Report malformed, ambiguous, or lossy snapshot data."""


@dataclass(frozen=True)
class RecordEnvelope:
    """One class-qualified JSON record from a snapshot."""

    class_name: str
    record: dict[str, Any]

    @property
    def pid(self) -> str:
        return self.record["pid"]

    @property
    def schema_type(self) -> str:
        return self.record["schema_type"]


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that does not silently collapse duplicate keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from error
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value}")


def _strict_json_value(value: Any, *, location: str) -> Any:
    """Validate that a value is exact JSON data and return it unchanged."""

    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise SnapshotError(f"{location}: JSON mapping keys must be strings")
        for key, item in value.items():
            _strict_json_value(item, location=f"{location}.{key}")
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            _strict_json_value(item, location=f"{location}[{index}]")
        return value
    if value is None or isinstance(value, (bool, int, float, str)):
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise SnapshotError(f"{location}: value is not finite JSON data") from error
        return value
    raise SnapshotError(
        f"{location}: {type(value).__name__} is not a JSON value"
    )


def canonical_json(value: Any) -> str:
    """Return strict canonical JSON while preserving list order and number type."""

    _strict_json_value(value, location="record")
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_yaml_bytes(record: Mapping[str, Any]) -> bytes:
    """Use the upstream serializer that Orinoco Lite also pins."""

    _strict_json_value(record, location="record")
    return json2yaml(order_dict(dict(record))).encode("utf-8")


def _schema_class_name(schema_type: str) -> str:
    local_name = re.split(r"[:/#]", schema_type)[-1]
    if not local_name:
        raise SnapshotError(f"schema_type has no class name: {schema_type!r}")
    return local_name


def _validate_envelope(
    class_name: Any,
    record: Any,
    *,
    location: str,
) -> RecordEnvelope:
    if not isinstance(class_name, str) or not CLASS_NAME.fullmatch(class_name):
        raise SnapshotError(f"{location}: invalid class_name {class_name!r}")
    if not isinstance(record, dict):
        raise SnapshotError(f"{location}: record must be a JSON object")
    _strict_json_value(record, location=f"{location}.record")
    pid = record.get("pid")
    if not isinstance(pid, str) or not pid:
        raise SnapshotError(f"{location}: record must have a non-empty string pid")
    schema_type = record.get("schema_type")
    if not isinstance(schema_type, str) or not schema_type:
        raise SnapshotError(
            f"{location}: record must have a non-empty string schema_type"
        )
    if _schema_class_name(schema_type) != class_name:
        raise SnapshotError(
            f"{location}: class_name {class_name!r} does not match "
            f"schema_type {schema_type!r}"
        )
    return RecordEnvelope(class_name=class_name, record=record)


def _check_unique(envelopes: Iterable[RecordEnvelope], *, location: str) -> None:
    seen: dict[str, str] = {}
    for envelope in envelopes:
        previous = seen.get(envelope.pid)
        if previous is not None:
            raise SnapshotError(
                f"{location}: duplicate record pid {envelope.pid!r} in "
                f"{previous} and {envelope.class_name}"
            )
        seen[envelope.pid] = envelope.class_name


def load_jsonl(path: Path) -> list[RecordEnvelope]:
    """Load an exact envelope JSONL snapshot without accepting ambiguity."""

    envelopes: list[RecordEnvelope] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            location = f"{path}:{line_number}"
            if not line.strip():
                raise SnapshotError(f"{location}: blank JSONL line")
            try:
                item = json.loads(line, parse_constant=_reject_json_constant)
            except (json.JSONDecodeError, ValueError) as error:
                raise SnapshotError(f"{location}: invalid JSON: {error}") from error
            if not isinstance(item, dict):
                raise SnapshotError(f"{location}: expected a JSON object")
            if set(item) != {"class_name", "record"}:
                raise SnapshotError(
                    f"{location}: envelope keys must be exactly "
                    "'class_name' and 'record'"
                )
            envelopes.append(
                _validate_envelope(
                    item["class_name"],
                    item["record"],
                    location=location,
                )
            )
    if not envelopes:
        raise SnapshotError(f"{path}: snapshot has no records")
    _check_unique(envelopes, location=str(path))
    return envelopes


def sorted_envelopes(
    envelopes: Iterable[RecordEnvelope],
) -> list[RecordEnvelope]:
    return sorted(envelopes, key=lambda item: (item.class_name, item.pid))


def canonical_jsonl_bytes(envelopes: Iterable[RecordEnvelope]) -> bytes:
    """Render a deterministic JSONL stream; source line order is not semantic."""

    ordered = sorted_envelopes(envelopes)
    _check_unique(ordered, location="snapshot")
    lines = [
        canonical_json(
            {"class_name": envelope.class_name, "record": envelope.record}
        )
        for envelope in ordered
    ]
    if not lines:
        raise SnapshotError("snapshot has no records")
    return ("\n".join(lines) + "\n").encode("utf-8")


def semantic_digest(envelopes: Iterable[RecordEnvelope]) -> str:
    """Hash exact records independently of JSONL ordering and whitespace."""

    return hashlib.sha256(canonical_jsonl_bytes(envelopes)).hexdigest()


def class_schema_types(
    envelopes: Iterable[RecordEnvelope],
) -> dict[str, str]:
    """Derive the unambiguous schema CURIE associated with each class name."""

    result: dict[str, str] = {}
    for envelope in envelopes:
        previous = result.setdefault(envelope.class_name, envelope.schema_type)
        if previous != envelope.schema_type:
            raise SnapshotError(
                f"class {envelope.class_name!r} has multiple schema types: "
                f"{previous!r} and {envelope.schema_type!r}"
            )
    return result


def record_relative_path(envelope: RecordEnvelope) -> Path:
    """Return a collision-resistant path independent of PID punctuation."""

    digest = hashlib.sha256(envelope.pid.encode("utf-8")).hexdigest()
    return Path(envelope.class_name) / f"{digest}.yaml"


def _assert_safe_destination(path: Path) -> None:
    resolved = path.resolve()
    if resolved == resolved.parent or path.name in {"", ".", ".."}:
        raise SnapshotError(f"refusing unsafe records destination {path}")


def write_records_tree(
    envelopes: Iterable[RecordEnvelope],
    records_root: Path,
    *,
    replace: bool = False,
) -> None:
    """Atomically write an Orinoco-compatible canonical YAML record tree."""

    ordered = sorted_envelopes(envelopes)
    if not ordered:
        raise SnapshotError("snapshot has no records")
    _check_unique(ordered, location="snapshot")
    _assert_safe_destination(records_root)
    records_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{records_root.name}.new-",
            dir=records_root.parent,
        )
    )
    try:
        paths: set[Path] = set()
        for envelope in ordered:
            relative = record_relative_path(envelope)
            if relative in paths:
                raise SnapshotError(f"record path collision at {relative}")
            paths.add(relative)
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(canonical_yaml_bytes(envelope.record))
        if records_root.exists():
            if not replace:
                raise SnapshotError(
                    f"records destination already exists: {records_root}"
                )
            if records_root.is_symlink() or not records_root.is_dir():
                raise SnapshotError(
                    f"records destination is not a real directory: {records_root}"
                )
            shutil.rmtree(records_root)
        os.replace(temporary, records_root)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _data_yaml_paths(records_root: Path) -> list[Path]:
    if records_root.is_symlink() or not records_root.is_dir():
        raise SnapshotError(f"records root is not a real directory: {records_root}")
    paths: list[Path] = []
    for path in sorted(records_root.rglob("*")):
        relative = path.relative_to(records_root)
        if path.is_symlink():
            raise SnapshotError(f"record tree contains a symlink: {relative}")
        if path.is_dir():
            continue
        if path.name in CONTROL_FILES:
            continue
        if path.suffix != ".yaml":
            raise SnapshotError(f"unexpected record-tree file: {relative}")
        if len(relative.parts) < 2:
            raise SnapshotError(
                f"record YAML is not under a class directory: {relative}"
            )
        paths.append(path)
    if not paths:
        raise SnapshotError(f"{records_root}: record tree has no YAML records")
    return paths


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise SnapshotError(f"{path}: invalid YAML: {error}") from error
    if not isinstance(value, dict):
        raise SnapshotError(f"{path}: YAML record must be a mapping")
    _strict_json_value(value, location=str(path))
    return value


def load_records_tree(
    records_root: Path,
    *,
    schema_types: Mapping[str, str] | None = None,
    require_canonical: bool = True,
) -> list[RecordEnvelope]:
    """Load canonical YAML, optionally rehydrating an upstream disk store.

    ``schema_types`` is only needed for Dump Things stores using its default
    schema-type layer.  It maps a class directory name to the exact CURIE that
    the service would reinsert.  Orinoco record trees already carry the field.
    """

    envelopes: list[RecordEnvelope] = []
    for path in _data_yaml_paths(records_root):
        relative = path.relative_to(records_root)
        class_name = relative.parts[0]
        if not CLASS_NAME.fullmatch(class_name):
            raise SnapshotError(
                f"{path}: invalid class directory name {class_name!r}"
            )
        stored = _load_yaml_mapping(path)
        if require_canonical and path.read_bytes() != canonical_yaml_bytes(stored):
            raise SnapshotError(f"{path}: YAML record is not canonical")
        record = dict(stored)
        configured_schema_type = (
            schema_types.get(class_name) if schema_types is not None else None
        )
        if "schema_type" not in record:
            if configured_schema_type is None:
                raise SnapshotError(
                    f"{path}: record is missing schema_type and no class mapping "
                    "was provided"
                )
            record["schema_type"] = configured_schema_type
        elif (
            configured_schema_type is not None
            and record["schema_type"] != configured_schema_type
        ):
            raise SnapshotError(
                f"{path}: schema_type {record['schema_type']!r} does not match "
                f"class mapping {configured_schema_type!r}"
            )
        envelopes.append(
            _validate_envelope(class_name, record, location=str(path))
        )
    _check_unique(envelopes, location=str(records_root))
    return sorted_envelopes(envelopes)


def compare_snapshots(
    expected: Iterable[RecordEnvelope],
    actual: Iterable[RecordEnvelope],
    *,
    expected_label: str = "expected",
    actual_label: str = "actual",
) -> None:
    """Require exact JSON type/value equality for every PID and class."""

    expected_items = list(expected)
    actual_items = list(actual)
    _check_unique(expected_items, location=expected_label)
    _check_unique(actual_items, location=actual_label)
    expected_by_pid = {item.pid: item for item in expected_items}
    actual_by_pid = {item.pid: item for item in actual_items}
    missing = sorted(expected_by_pid.keys() - actual_by_pid.keys())
    extra = sorted(actual_by_pid.keys() - expected_by_pid.keys())
    if missing or extra:
        raise SnapshotError(
            f"snapshot PID mismatch: {actual_label} is missing {missing[:5]} "
            f"and has extra {extra[:5]}"
        )
    for pid in sorted(expected_by_pid):
        left = expected_by_pid[pid]
        right = actual_by_pid[pid]
        if left.class_name != right.class_name:
            raise SnapshotError(
                f"{pid}: class changed from {left.class_name!r} to "
                f"{right.class_name!r}"
            )
        if canonical_json(left.record) != canonical_json(right.record):
            raise SnapshotError(
                f"{pid}: JSON record differs between {expected_label} and "
                f"{actual_label}"
            )


def records_tree_digest(records_root: Path) -> str:
    """Hash canonical record paths and bytes, excluding backend control files."""

    digest = hashlib.sha256()
    for path in _data_yaml_paths(records_root):
        relative = path.relative_to(records_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _package_version() -> str:
    try:
        return version("dump-things-service")
    except PackageNotFoundError:
        return "source-checkout"


def snapshot_manifest(
    source_path: Path,
    envelopes: Sequence[RecordEnvelope],
    records_root: Path,
) -> dict[str, Any]:
    """Describe source bytes, semantic records, and materialized YAML bytes."""

    classes = Counter(item.class_name for item in envelopes)
    return {
        "class_counts": dict(sorted(classes.items())),
        "dump_things_service_version": _package_version(),
        "format": FORMAT_NAME,
        "record_count": len(envelopes),
        "records_semantic_sha256": semantic_digest(envelopes),
        "records_tree_sha256": records_tree_digest(records_root),
        "serialization": "dump_things_service.utils.json2yaml",
        "source_jsonl": str(source_path),
        "source_jsonl_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
    }


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(f".{path.name}.new")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def write_jsonl(path: Path, envelopes: Iterable[RecordEnvelope]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.new")
    temporary.write_bytes(canonical_jsonl_bytes(envelopes))
    os.replace(temporary, path)


def materialize(
    source: Path,
    records_root: Path,
    *,
    manifest_path: Path | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    """Write, reload, and exactly verify an Orinoco-compatible YAML tree."""

    expected = load_jsonl(source)
    write_records_tree(expected, records_root, replace=replace)
    actual = load_records_tree(records_root)
    compare_snapshots(expected, actual)
    manifest = snapshot_manifest(source, expected, records_root)
    if manifest_path is not None:
        write_json(manifest_path, manifest)
    return manifest


def export_records(records_root: Path, destination: Path) -> list[RecordEnvelope]:
    """Export canonical YAML records as deterministic envelope JSONL."""

    envelopes = load_records_tree(records_root)
    write_jsonl(destination, envelopes)
    reloaded = load_jsonl(destination)
    compare_snapshots(envelopes, reloaded)
    return reloaded


def verify(
    source: Path,
    records_root: Path,
    *,
    upstream_store: bool = False,
) -> dict[str, Any]:
    """Verify exact source equality against Orinoco YAML or an upstream store."""

    expected = load_jsonl(source)
    schema_types = class_schema_types(expected) if upstream_store else None
    actual = load_records_tree(records_root, schema_types=schema_types)
    compare_snapshots(
        expected,
        actual,
        expected_label="source JSONL",
        actual_label="upstream YAML store" if upstream_store else "YAML records",
    )
    return snapshot_manifest(source, actual, records_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    materialize_parser = commands.add_parser(
        "materialize", help="write an Orinoco-compatible YAML record tree"
    )
    materialize_parser.add_argument("source", type=Path)
    materialize_parser.add_argument("records_root", type=Path)
    materialize_parser.add_argument("--manifest", type=Path)
    materialize_parser.add_argument("--replace", action="store_true")

    export_parser = commands.add_parser(
        "export", help="write canonical envelope JSONL from YAML records"
    )
    export_parser.add_argument("records_root", type=Path)
    export_parser.add_argument("destination", type=Path)

    verify_parser = commands.add_parser(
        "verify", help="compare source JSONL exactly with a YAML record tree"
    )
    verify_parser.add_argument("source", type=Path)
    verify_parser.add_argument("records_root", type=Path)
    verify_parser.add_argument(
        "--upstream-store",
        action="store_true",
        help="rehydrate schema_type omitted by Dump Things on disk",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "materialize":
            result = materialize(
                args.source,
                args.records_root,
                manifest_path=args.manifest,
                replace=args.replace,
            )
        elif args.command == "export":
            records = export_records(args.records_root, args.destination)
            result = {
                "destination": str(args.destination),
                "record_count": len(records),
                "records_semantic_sha256": semantic_digest(records),
            }
        else:
            result = verify(
                args.source,
                args.records_root,
                upstream_store=args.upstream_store,
            )
    except SnapshotError as error:
        raise SystemExit(f"upstream-snapshot: {error}") from error
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
