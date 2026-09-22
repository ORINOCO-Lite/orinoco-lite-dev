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
from .annotations import assertion_sha256
from .errors import ConfigurationError


COMPARATOR = "records-v1"
SCHEMA_RELATIVE = Path("schema/demo-research-information/unreleased.yaml")
_MISSING = object()

# Describe the operation that produced each state; none of these reads a live API.
RECORD_STATES = {
    "downloaded": ("downloaded", "Downloaded records (JSONL)"),
    "yaml": ("yaml", "Records after conversion to YAML"),
    "yaml-jsonl": ("yaml-jsonl", "Records after YAML → JSONL"),
}


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


def _check_record_input(path: Path) -> None:
    from .stage_reports import operation_receipt, read_json

    operation_receipt(path)
    # Interruptions can leave evidence before the CLI writes its receipt.
    if path.name == "returned.partial.jsonl":
        raise snapshot.SnapshotError(f"Incomplete RDF return cannot be a complete record input: {path}")
    conversion = path.with_name("conversion.json")
    if path.name == "records.jsonl" and conversion.is_file():
        result = read_json(conversion)
        if not isinstance(result, dict) or result.get("status") != "complete":
            raise snapshot.SnapshotError(f"RDF conversion did not complete: {conversion}")


def jsonl_to_yaml(source: Path, site_inputs: Path) -> dict[str, Any]:
    """Replace records and companions, preserving authored inputs and captures."""

    _check_record_input(source)
    targets = [site_inputs / "metadata/records",
               site_inputs / "metadata/overlays/annotations"]
    for target in targets:
        _safe_output(target)
        if source.resolve().is_relative_to(target.resolve()):
            raise snapshot.SnapshotError(f"capture is inside a replaced output: {source}")
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
    """Join canonical records with only their validated mirrored companions."""

    records_root = site_inputs / "metadata/records"
    companions_root = site_inputs / "metadata/overlays/annotations"
    stored = snapshot.load_records_tree(records_root)
    # Canonical human-edited record names need not be generated PID hashes.
    by_pid = {item.pid: item for item in stored}
    companions: dict[str, dict[str, Any]] = {}
    if companions_root.exists():
        if companions_root.is_symlink() or not companions_root.is_dir():
            raise snapshot.SnapshotError(f"invalid companion root: {companions_root}")
        for path in sorted(companions_root.rglob("*")):
            if path.is_symlink():
                raise snapshot.SnapshotError(f"companion must not be a symlink: {path}")
            if path.is_dir():
                continue
            relative = path.relative_to(companions_root)
            if path.suffix != ".yaml" or not (records_root / relative).is_file():
                raise snapshot.SnapshotError(f"companion has no mirrored YAML record: {path}")
            companion = storage._load_companion(path)
            mirrored = snapshot._load_yaml_mapping(records_root / relative)
            pid = companion.get("record")
            if pid not in by_pid or pid in companions or mirrored.get("pid") != pid:
                raise snapshot.SnapshotError(f"companion identity does not match its record: {path}")
            companions[pid] = companion
    joined = [snapshot.RecordEnvelope(item.class_name,
              storage.compact_enrichment_view(item.record, companions.get(item.pid), preserve_source=True)) for item in stored]
    _safe_output(output)
    if output.resolve().is_relative_to(records_root.resolve()) or output.resolve().is_relative_to(companions_root.resolve()):
        raise snapshot.SnapshotError("export output must be outside records and companions")
    snapshot.write_jsonl(output, joined)
    return joined


def register(subparsers: Any) -> None:
    from .diagnostics import options
    parser = subparsers.add_parser("jsonl-to-yaml", help="write YAML records from downloaded JSONL",
        description="Convert JSONL to YAML records and annotation companions. Defaults use the investigation directory; --destination selects a site-input directory. Only metadata/records and metadata/overlays/annotations are replaced, with --force required for existing metadata.")
    options(parser)
    parser.add_argument("--source", type=Path, help="JSONL input (default: DIRECTORY/downloaded/records.jsonl)")
    parser.add_argument("--destination", type=Path, help="site-input directory (default: DIRECTORY/yaml)")
    parser.set_defaults(records_action="jsonl-to-yaml")
    parser = subparsers.add_parser("yaml-to-jsonl", help="rejoin YAML records and annotations into JSONL",
        description="Rejoin the investigation's YAML records and annotation companions into yaml-jsonl/records.jsonl. Existing output requires --force.")
    options(parser)
    parser.add_argument("--source", type=Path, help="site-input directory containing metadata (default: DIRECTORY/yaml)")
    parser.add_argument("--output", type=Path, help="JSONL destination (default: DIRECTORY/yaml-jsonl/records.jsonl)")
    parser.set_defaults(records_action="yaml-to-jsonl")
    parser = subparsers.add_parser("diff", help="compare two representations of the records",
        description="Compare existing records: downloaded against yaml-jsonl by default. Use 'all' to list available states and compare each conversion. No downloads or conversions are run. Results are always displayed; existing saved reports are replaced only with --force. Exit 1 means differences, 2 means an error.")
    names = ", ".join(RECORD_STATES)
    parser.add_argument("left", nargs="?", default="downloaded", metavar="STATE|PATH|all", help="JSONL file, site-input directory, or state: " + names)
    parser.add_argument("right", nargs="?", metavar="STATE|PATH", help="JSONL file, site-input directory, or state: " + names)
    parser.add_argument("--report", type=Path, help="comparison report directory (required for explicit input paths)")
    parser.add_argument("--summary", action="store_true", help="show counts without individual differences")
    parser.add_argument("--limit", type=_limit, default=30, help="maximum displayed differences per comparison (default: 30)")
    parser.add_argument("--record", action="append", help="select a record identifier; repeat for several")
    parser.add_argument("--field", help="show differences within this top-level field")
    parser.add_argument("--full-values", action="store_true", help="print complete before/after values instead of abbreviating them")
    options(parser)
    parser.set_defaults(records_action="diff")


def execute(args: argparse.Namespace) -> int:
    from .stage_reports import write_operation, write_report

    from .diagnostics import directory, record_path, prepare_output, explicit_path

    action = args.records_action
    try:
        root = directory(args)
        if action == "diff" and args.left == "all":
            if args.right is not None:
                raise ConfigurationError("Use 'diff all' without a second state")
            available = set()
            results = []
            print("Record states in this investigation:")
            for name, (previous, label) in RECORD_STATES.items():
                try:
                    path = record_path(root, previous)
                except ConfigurationError as error:
                    if (root / previous).exists():
                        print(f"  {name}: incomplete output. {error}")
                        results.append(2)
                    else:
                        print(f"  {name}: not written")
                else:
                    available.add(name)
                    print(f"  {name}: {label}\n    {path}")
            pairs = [("downloaded", "yaml"), ("yaml", "yaml-jsonl"), ("downloaded", "yaml-jsonl")]
            for left, right in pairs:
                if left in available and right in available:
                    print()
                    results.append(execute(argparse.Namespace(**{**vars(args), "left": left, "right": right})))
            if not results:
                raise ConfigurationError("No pair of record states is available. Run 'records get', 'records jsonl-to-yaml', and 'records yaml-to-jsonl' first.")
            return max(results)
        if action == "jsonl-to-yaml":
            source = getattr(args, "source", None)
            destination = getattr(args, "destination", None)
            args.source = explicit_path(args, source) if source else record_path(root, "downloaded")
            _check_record_input(args.source)
            snapshot.load_jsonl(args.source)
            args.site_inputs = explicit_path(args, destination) if destination else root / "yaml"
            # Never delete the enclosing site directory: it may be a subdataset.
            for name in ("metadata/records", "metadata/overlays/annotations"):
                target = args.site_inputs / name
                _safe_output(target)
                if target.exists() and not args.force:
                    raise ConfigurationError(f"Metadata output already exists: {target}; use --force to replace it")
        elif action == "yaml-to-jsonl":
            source = getattr(args, "source", None)
            output = getattr(args, "output", None)
            args.site_inputs = explicit_path(args, source) if source else record_path(root, "yaml")
            args.output = explicit_path(args, output) if output else root / "yaml-jsonl/records.jsonl"
            _safe_output(args.output)
            if args.output.exists() and not args.force:
                raise ConfigurationError(f"JSONL output already exists: {args.output}; use --force to replace it")
        elif action == "diff":
            left_name, right_name = args.left, args.right or "yaml-jsonl"
            def selected(value):
                if value in RECORD_STATES:
                    key, label = RECORD_STATES[value]
                    return record_path(root, key), label
                path = explicit_path(args, Path(value))
                if not path.exists():
                    raise ConfigurationError(f"Record input does not exist: {path}")
                return path, value
            args.left, left_label = selected(left_name)
            args.right, right_label = selected(right_name)
            args.stage = "storage"
            args.mode = "isolated"
            report = getattr(args, "report", None)
            if report:
                args.report = explicit_path(args, report)
            elif left_name in RECORD_STATES and right_name in RECORD_STATES:
                args.report = root / "reports" / f"{left_name}-vs-{right_name}"
            else:
                raise ConfigurationError("Explicit record paths require --report DIRECTORY")
            if any(path.resolve().is_relative_to(args.report.resolve()) for path in (args.left, args.right)):
                raise ConfigurationError("Comparison report must not contain an input")
            for path in (args.left, args.right):
                if path.is_file():
                    _check_record_input(path)
            if args.report.is_symlink():
                raise ConfigurationError(f"Report must not be a symbolic link: {args.report}")
        if action == "jsonl-to-yaml":
            result = jsonl_to_yaml(args.source, args.site_inputs)
            print(f"Converted {result['record_count']} records (YAML): {args.site_inputs}")
        elif action == "yaml-to-jsonl":
            joined = yaml_to_jsonl(args.site_inputs, args.output)
            inputs = {"metadata": args.site_inputs / "metadata"}
            write_operation(args.output, operation="records yaml-to-jsonl", inputs=inputs, command=getattr(args, "invocation", []))
            print(f"Wrote {len(joined)} records (JSONL): {args.output}")
        elif action == "diff":
            # A failed conversion cannot support a completed comparison.
            _check_record_input(args.left)
            _check_record_input(args.right)
            def read(path):
                if path.is_dir():
                    with tempfile.TemporaryDirectory() as temporary:
                        return yaml_to_jsonl(path, Path(temporary) / "records.jsonl")
                return snapshot.load_jsonl(path)
            left, right = read(args.left), read(args.right)
            comparison_status, diagnostics = "complete", []
            findings = compare_records(left, right)
            print(f"{left_label} → {right_label}")
            print(f"  Before: {args.left}\n  After:  {args.right}")
            if comparison_status == "complete":
                print(f"{len(left)} records before; {len(right)} after; {len({item['subject'] for item in findings})} records differ.")
            else:
                print(diagnostics[0], file=sys.stderr)
            fields = defaultdict(set)
            for item in findings:
                fields[str(item['location'][0]) if item['location'] else '<whole record>'].add(item['subject'])
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
                print("Filters affect displayed differences only; counts, exit status, and saved report cover all records.")
            if args.report.exists() and not args.force:
                print(f"Existing report kept: {args.report}. The comparison above is current; use --force to replace the saved report.")
            else:
                prepare_output(args.report, args.force)
                evidence: dict[str, Path] = {}
                write_report(args.report, stage=args.stage, left=args.left, right=args.right,
                             findings=findings, comparator=COMPARATOR, mode=args.mode,
                             status=comparison_status, diagnostics=diagnostics,
                             scope={"complete": comparison_status == "complete",
                                    "subjects": sorted({item.pid for item in [*left, *right]}),
                                    "all_locations": True, "selection": "all records",
                                    "exclusions": []},
                             command=getattr(args, "invocation", []), evidence=evidence)
                print(f"Report: {args.report}")
            return 2 if comparison_status != "complete" else 1 if findings else 0
        else:
            raise ValueError(f"unknown record operation: {action}")
    except (OSError, ValueError, ConfigurationError, snapshot.SnapshotError, storage.StorageProjectionError) as error:
        print(f"records {action}: {error}", file=sys.stderr)
        return 2
    return 0
