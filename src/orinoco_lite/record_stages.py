"""Inspect record preservation across JSONL and YAML before website projection.

Comparator ``records-v1`` preserves the raw JSON model: scalar types, missing
versus null, sequence order, and multiplicity. The selected Things schema gives
Things a ``pid`` and Annotation a keyed ``annotation_tag``. Inline attributes,
qualified relations, and identifiers have no schema identifier. Unique
predicate/type, object/predicate/type, and creator/notation/type contexts can
support structural comparison, but are explicitly not persistent identities.
Repeated contexts are unmatched. Exact unchanged objects can be paired by
content; array positions never establish assertion identity. Every changed
list also retains its complete raw before/after values, including reordering.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Sequence

from . import upstream_orinoco_records as storage
from . import upstream_snapshot as snapshot
from .annotations import assertion_sha256, _check_overlay_path
from .errors import ConfigurationError


_MISSING = object()


def _limit(value):
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError("Limit must be zero or greater")
    return result


def _display_location(parts):
    result = []
    for part in parts:
        if isinstance(part, str) and part.startswith("@{"):
            context = json.loads(part[1:])
            result.append("[" + ", ".join(f"{key}={value}" for key, value in context.items()) + "]")
        elif isinstance(part, str) and part.startswith("@assertion:"):
            result.append("[matched assertion]")
        elif isinstance(part, str) and part.startswith("@unmatched:"):
            result.append("[unmatched item]")
        else:
            result.append(str(part))
    return " / ".join(result) or "<whole record>"


def _equal(left: Any, right: Any) -> bool:
    return snapshot.canonical_json(left) == snapshot.canonical_json(right)


def _assertion_key(value: dict[str, Any]) -> tuple[str, str] | None:
    """Use schema keys first, then an explicitly structural comparison context."""

    for field in ("pid", "annotation_tag"):
        if isinstance(value.get(field), str) and value[field]:
            return "stable", snapshot.canonical_json({field: value[field]})
    if "object" in value:
        fields = ("object", "predicate", "schema_type")
    elif "predicate" in value:
        fields = ("predicate", "schema_type")
    elif "notation" in value:
        fields = ("creator", "notation", "schema_type")
    else:
        return None
    return "structural", snapshot.canonical_json(
        {field: value[field] for field in fields if field in value}
    )


def compare_records(
    left: Sequence[snapshot.RecordEnvelope],
    right: Sequence[snapshot.RecordEnvelope],
) -> list[dict[str, Any]]:
    """Return typed, field-level findings without choosing ambiguous matches."""

    # Also protects callers using envelopes directly instead of load_jsonl.
    snapshot.canonical_jsonl_bytes(left)
    snapshot.canonical_jsonl_bytes(right)
    findings: list[dict[str, Any]] = []

    def finding(
        subject: str,
        location: list[str | int],
        before: Any,
        after: Any,
        *,
        change: str | None = None,
        identity: str = "stable",
    ) -> None:
        findings.append({
            "subject": subject,
            "location": location,
            "change": change or (
                "added" if before is _MISSING else
                "removed" if after is _MISSING else "changed"
            ),
            "before": None if before is _MISSING else deepcopy(before),
            "after": None if after is _MISSING else deepcopy(after),
            "before_present": before is not _MISSING,
            "after_present": after is not _MISSING,
            "identity": identity,
        })

    def walk(subject, location, before, after, identity="stable"):
        if before is _MISSING or after is _MISSING:
            finding(subject, location, before, after, identity=identity)
        elif _equal(before, after):
            return
        elif isinstance(before, dict) and isinstance(after, dict):
            for key in sorted(before.keys() | after.keys()):
                walk(subject, [*location, key], before.get(key, _MISSING),
                     after.get(key, _MISSING), identity)
        elif isinstance(before, list) and isinstance(after, list):
            finding(subject, location, before, after, change="list-changed",
                    identity=identity)
            before_counts = Counter(snapshot.canonical_json(item) for item in before)
            after_counts = Counter(snapshot.canonical_json(item) for item in after)
            findings[-1]["list_comparison"] = {
                "same_items": before_counts == after_counts,
                "removed_occurrences": sum((before_counts - after_counts).values()),
                "added_occurrences": sum((after_counts - before_counts).values()),
            }
            if not all(isinstance(item, dict) for item in [*before, *after]):
                return
            left_keys = Counter(_assertion_key(item) for item in before)
            right_keys = Counter(_assertion_key(item) for item in after)
            right_indices = {
                _assertion_key(item): index for index, item in enumerate(after)
            }
            used_left: set[int] = set()
            used_right: set[int] = set()
            for index, item in enumerate(before):
                key = _assertion_key(item)
                if key is None or left_keys[key] != 1 or right_keys[key] != 1:
                    continue
                target = right_indices[key]
                used_left.add(index)
                used_right.add(target)
                walk(subject, [*location, "@" + key[1]], item, after[target], key[0])
            # An unchanged assertion's native content can disambiguate an
            # attribution change among repeated predicates/relationship targets.
            # This digest never identifies an assertion after its value changes.
            left_native = Counter(assertion_sha256(item) for item in before)
            right_native = Counter(assertion_sha256(item) for item in after)
            native_indices = {assertion_sha256(item): index
                              for index, item in enumerate(after)}
            for index, item in enumerate(before):
                digest = assertion_sha256(item)
                if (index in used_left or left_native[digest] != 1
                        or right_native[digest] != 1):
                    continue
                target = native_indices[digest]
                if target in used_right:
                    continue
                used_left.add(index)
                used_right.add(target)
                walk(subject, [*location, "@assertion:" + digest],
                     item, after[target], "structural")
            # Pair only exact remaining objects. Do not assign persistent
            # identity to duplicate occurrences or infer changes from position.
            exact: dict[str, list[int]] = defaultdict(list)
            for index, item in enumerate(after):
                if index not in used_right:
                    exact[snapshot.canonical_json(item)].append(index)
            for index, item in enumerate(before):
                if index in used_left:
                    continue
                candidates = exact[snapshot.canonical_json(item)]
                if candidates:
                    used_left.add(index)
                    used_right.add(candidates.pop())
            for values, used, side in ((before, used_left, "before"),
                                       (after, used_right, "after")):
                for index, item in enumerate(values):
                    if index in used:
                        continue
                    digest = hashlib.sha256(
                        snapshot.canonical_json(item).encode("utf-8")
                    ).hexdigest()
                    finding(subject, [*location, f"@unmatched:{side}:{digest}", index],
                            item if side == "before" else _MISSING,
                            item if side == "after" else _MISSING,
                            identity="unmatched")
        else:
            finding(subject, location, before, after, identity=identity)

    left_by_pid = {item.pid: item for item in left}
    right_by_pid = {item.pid: item for item in right}
    for pid in sorted(left_by_pid.keys() | right_by_pid.keys()):
        before, after = left_by_pid.get(pid), right_by_pid.get(pid)
        if before is None or after is None:
            finding(pid, [], before.record if before else _MISSING,
                    after.record if after else _MISSING)
            continue
        walk(pid, [], before.record, after.record)
    return findings


def _safe_output(path: Path) -> None:
    if path.is_symlink():
        raise snapshot.SnapshotError(f"output must not be a symlink: {path}")


def jsonl_to_yaml(source: Path, site_inputs: Path) -> dict[str, Any]:
    """Replace records and overlay files, preserving authored inputs and dumps."""

    _check_overlay_path(site_inputs / "metadata")
    targets = [site_inputs / "metadata/records",
               site_inputs / "metadata/overlays/machine-provenance-annotations"]
    for target in targets:
        _safe_output(target)
        if source.resolve().is_relative_to(target.resolve()):
            raise snapshot.SnapshotError(f"dump is inside a replaced output: {source}")
        if target.exists() and not target.is_dir():
            raise snapshot.SnapshotError(f"metadata output is not a directory: {target}")
    site_inputs.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".record-conversion-", dir=site_inputs.parent) as tmp:
        temporary = Path(tmp)
        projected = temporary / "projection"
        result = storage.project(source, projected)
        installed: list[tuple[Path, Path]] = []
        try:
            for index, target in enumerate(targets):
                target.parent.mkdir(parents=True, exist_ok=True)
                backup = temporary / f"previous-{index}"
                if target.exists():
                    os.replace(target, backup)
                installed.append((target, backup))
                os.replace(projected / target.relative_to(site_inputs), target)
        except BaseException:
            for target, backup in reversed(installed):
                if target.exists():
                    shutil.rmtree(target)
                if backup.exists():
                    os.replace(backup, target)
            raise
    return result


def yaml_to_jsonl(site_inputs: Path, output: Path) -> list[snapshot.RecordEnvelope]:
    """Join canonical records with only their validated mirrored overlay files."""

    _check_overlay_path(site_inputs / "metadata")
    records_root = site_inputs / "metadata/records"
    companions_root = site_inputs / "metadata/overlays/machine-provenance-annotations"
    stored = snapshot.load_records_tree(records_root)
    # Canonical human-edited record names need not be generated PID hashes.
    by_pid = {item.pid: item for item in stored}
    companions: dict[str, dict[str, Any]] = {}
    if companions_root.exists():
        if companions_root.is_symlink() or not companions_root.is_dir():
            raise snapshot.SnapshotError(f"invalid overlay root: {companions_root}")
        for path in sorted(companions_root.rglob("*")):
            if path.is_symlink():
                raise snapshot.SnapshotError(f"overlay file must not be a symlink: {path}")
            if path.is_dir():
                continue
            relative = path.relative_to(companions_root)
            if path.suffix != ".yaml" or not (records_root / relative).is_file():
                raise snapshot.SnapshotError(f"overlay file has no mirrored YAML record: {path}")
            companion = storage._load_companion(path)
            mirrored = snapshot._load_yaml_mapping(records_root / relative)
            pid = companion.get("record")
            if pid not in by_pid or pid in companions or mirrored.get("pid") != pid:
                raise snapshot.SnapshotError(f"overlay file identity does not match its record: {path}")
            companions[pid] = companion
    joined = [snapshot.RecordEnvelope(item.class_name,
              storage.compact_enrichment_view(item.record, companions.get(item.pid), preserve_source=True)) for item in stored]
    _safe_output(output)
    if output.resolve().is_relative_to(records_root.resolve()) or output.resolve().is_relative_to(companions_root.resolve()):
        raise snapshot.SnapshotError("export output must be outside records and overlay files")
    snapshot.write_jsonl(output, joined)
    return joined


def register(subparsers: Any) -> None:
    from .diagnostics import options
    parser = subparsers.add_parser("jsonl-to-yaml", help="write YAML records from downloaded JSONL",
        description="Convert a JSONL dump into site-specific/metadata. Only metadata/records "
                    "and metadata/overlays/machine-provenance-annotations are replaced; use --force for existing metadata.")
    options(parser)
    parser.add_argument("--source", type=Path, help="JSONL input (default: DIRECTORY/downloaded/records.jsonl)")
    parser.add_argument("--destination", type=Path, default=Path("site-specific"),
                        help="site-input directory (default: %(default)s)")
    parser.set_defaults(records_action="jsonl-to-yaml")
    parser = subparsers.add_parser("yaml-to-jsonl", help="rejoin YAML records and annotations into JSONL",
        description="Rejoin site-specific metadata into sourcedata/yaml-jsonl/records.jsonl. "
                    "Use --source and --output for other paths; existing output requires --force.")
    options(parser)
    parser.add_argument("--source", type=Path, default=Path("site-specific"),
                        help="site-input directory containing metadata (default: %(default)s)")
    parser.add_argument("--output", type=Path, help="JSONL destination (default: DIRECTORY/yaml-jsonl/records.jsonl)")
    parser.set_defaults(records_action="yaml-to-jsonl")
    parser = subparsers.add_parser("diff", help="compare two representations of the records",
        description="Compare sourcedata/downloaded/records.jsonl with site-specific metadata by default. "
                    "Pass two paths to compare other JSONL files or site-input directories. "
                    "Print differences without writing files, downloading, or changing inputs. "
                    "Exit 0 means equal, 1 means differences, and 2 means an error.")
    parser.add_argument("left", nargs="?", type=Path, help="JSONL file or site-input directory (default: DIRECTORY/downloaded/records.jsonl)")
    parser.add_argument("right", nargs="?", type=Path, default=Path("site-specific"),
                        help="JSONL file or site-input directory (default: %(default)s)")
    parser.add_argument("--summary", action="store_true", help="show counts without individual differences")
    parser.add_argument("--limit", type=_limit, default=30, help="maximum displayed differences (default: 30)")
    parser.add_argument("--record", action="append", help="select a record identifier; repeat for several")
    parser.add_argument("--field", help="show differences within this top-level field")
    parser.add_argument("--full-values", action="store_true", help="print complete before/after values instead of abbreviating them")
    options(parser, replace=False)
    parser.set_defaults(records_action="diff")


def execute(args: argparse.Namespace) -> int:
    from .diagnostics import directory, explicit_path, require

    action = args.records_action
    try:
        data = directory(args)
        if action == "jsonl-to-yaml":
            source = explicit_path(args, args.source) if args.source else require(data / "downloaded/records.jsonl", "records get")
            site_inputs = explicit_path(args, args.destination)
            # Never delete the enclosing site directory: it may be a subdataset.
            for name in ("metadata/records", "metadata/overlays/machine-provenance-annotations"):
                target = site_inputs / name
                _safe_output(target)
                if target.exists() and not args.force:
                    raise ConfigurationError(f"Metadata output already exists: {target}; use --force to replace it")
            result = jsonl_to_yaml(source, site_inputs)
            print(f"Converted {result['record_count']} records (YAML): {site_inputs}")
        elif action == "yaml-to-jsonl":
            site_inputs = explicit_path(args, args.source)
            output = explicit_path(args, args.output) if args.output else data / "yaml-jsonl/records.jsonl"
            _safe_output(output)
            if output.exists() and not args.force:
                raise ConfigurationError(f"JSONL output already exists: {output}; use --force to replace it")
            joined = yaml_to_jsonl(site_inputs, output)
            print(f"Wrote {len(joined)} records (JSONL): {output}")
        elif action == "diff":
            left_path = explicit_path(args, args.left) if args.left else require(data / "downloaded/records.jsonl", "records get")
            right_path = explicit_path(args, args.right)
            def read(path):
                if path.is_dir():
                    with tempfile.TemporaryDirectory() as temporary:
                        return yaml_to_jsonl(path, Path(temporary) / "records.jsonl")
                return snapshot.load_jsonl(path)
            left, right = read(left_path), read(right_path)
            findings = compare_records(left, right)
            print(f"Before: {left_path}\nAfter:  {right_path}")
            print(f"{len(left)} records before; {len(right)} after; {len({item['subject'] for item in findings})} records differ.")
            fields = defaultdict(set)
            for item in findings:
                fields[str(item["location"][0]) if item["location"] else '<whole record>'].add(item['subject'])
            for field, subjects in sorted(fields.items(), key=lambda item: (-len(item[1]), item[0])):
                print(f"  {field}: {len(subjects)} records")
            selected = [item for item in findings if
                        (not args.record or item['subject'] in args.record) and
                        (not args.field or (item['location'] and item['location'][0] == args.field))]
            shown = [] if args.summary else selected[:args.limit]
            for item in shown:
                location = _display_location(item["location"])
                if item["change"] == "list-changed" and not args.full_values:
                    detail = item["list_comparison"]
                    description = ("same items, different order" if detail["same_items"] else
                                   f"{detail['removed_occurrences']} removed, {detail['added_occurrences']} added occurrences")
                    print(f"  {item['subject']}\n    {location}: {description} ({len(item['before'])} → {len(item['after'])} items; use --full-values to inspect the list)")
                    continue
                before = json.dumps(item["before"], ensure_ascii=False) if item["before_present"] else "<missing>"
                after = json.dumps(item["after"], ensure_ascii=False) if item["after_present"] else "<missing>"
                if not args.full_values and len(before) > 180:
                    before = before[:177] + "..."
                if not args.full_values and len(after) > 180:
                    after = after[:177] + "..."
                print(f"  {item['subject']}\n    {location}: {item['change']}\n    before: {before}\n    after:  {after}")
            if not args.summary:
                print(f"Showing {len(shown)} of {len(selected)} selected differences ({len(findings)} total).")
            if findings:
                print("Difference counts include both changed lists and changes within them.")
            if args.record or args.field:
                print("Filters affect displayed differences only; counts and exit status cover all records.")
            return 1 if findings else 0
        else:
            raise ValueError(f"unknown record operation: {action}")
    except (OSError, ValueError, ConfigurationError, snapshot.SnapshotError, storage.StorageProjectionError) as error:
        print(f"records {action}: {error}", file=sys.stderr)
        return 2
    return 0
