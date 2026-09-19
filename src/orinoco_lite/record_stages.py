"""Inspect record storage and RDF conversion before website projection.

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

from rdflib import Dataset, Graph, URIRef
from rdflib.compare import graph_diff, isomorphic, to_isomorphic

from . import upstream_orinoco_records as storage
from . import upstream_snapshot as snapshot
from .annotations import annotation_semantic_view, assertion_sha256, join_annotations
from .errors import ConfigurationError
from .resources import resolve_resources
from .schema_conversion import build_format_converters


COMPARATOR = "records-v1"
SCHEMA_RELATIVE = Path("schema/demo-research-information/unreleased.yaml")
_MISSING = object()


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
        start = len(findings)
        walk(pid, [], before.record, after.record)
        # Mark a known annotation spelling/encoding equivalence while retaining
        # all raw findings. This is evidence, never an approval decision.
        if len(findings) > start:
            try:
                normalized_before, _, _ = storage.normalize_machine_pav(before.record)
                normalized_after, _, _ = storage.normalize_machine_pav(after.record)
            except storage.StorageProjectionError:
                # Malformed annotations still have exact, reviewable raw
                # changes; they cannot establish representation equivalence.
                continue
            if _equal(annotation_semantic_view(normalized_before),
                      annotation_semantic_view(normalized_after)):
                for item in findings[start:]:
                    item["representation_equivalence"] = "annotation-representation-v1"
    return findings


def _safe_output(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise snapshot.SnapshotError(f"output must not pass through a symlink: {ancestor}")


def _check_record_input(path: Path) -> None:
    from .stage_reports import operation_receipt, read_json

    operation_receipt(path)
    # Interruptions can leave evidence before the CLI writes its receipt.
    if path.name == "returned.partial.jsonl":
        raise snapshot.SnapshotError(f"Incomplete RDF return cannot be a complete record input: {path}")
    conversion = path.with_name("conversion.json")
    if path.name == "returned.jsonl" and conversion.is_file():
        result = read_json(conversion)
        if not isinstance(result, dict) or result.get("status") != "complete":
            raise snapshot.SnapshotError(f"RDF conversion did not complete: {conversion}")


def convert(source: Path, site_inputs: Path) -> dict[str, Any]:
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


def export_records(site_inputs: Path, output: Path) -> list[snapshot.RecordEnvelope]:
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
              join_annotations(item.record, companions.get(item.pid))) for item in stored]
    _safe_output(output)
    if output.resolve().is_relative_to(records_root.resolve()) or output.resolve().is_relative_to(companions_root.resolve()):
        raise snapshot.SnapshotError("export output must be outside records and companions")
    snapshot.write_jsonl(output, joined)
    return joined


def rdf_graph_difference(left: Graph, right: Graph) -> dict[str, Any]:
    """Compare RDF modulo blank-node labels, independently of record equality."""

    same = isomorphic(left, right)
    common, removed, added = graph_diff(to_isomorphic(left), to_isomorphic(right))
    return {"isomorphic": same, "common_triples": len(common),
            "removed_triples": len(removed), "added_triples": len(added)}


def rdf_roundtrip(
    source: Path,
    output: Path,
    *,
    schema: Path | None = None,
    compare_rdf: bool = False,
) -> dict[str, Any]:
    """Run the selected conversion pair per record and retain partial evidence.

    ``intermediate.rdf`` is TriG: a named graph for each source PID preserves
    the per-record boundary used by the selected inverse converter. Its blank
    node labels are serialization details, not assertion identities.
    """

    _check_record_input(source)
    envelopes = snapshot.load_jsonl(source)
    schema = schema or resolve_resources().root / SCHEMA_RELATIVE
    _safe_output(output)
    if source.resolve().is_relative_to(output.resolve()):
        raise snapshot.SnapshotError("RDF output must not contain its source capture")
    output.mkdir(parents=True, exist_ok=True)
    owned = ("intermediate.rdf", "returned.jsonl", "returned.partial.jsonl", "conversion.json")
    if any((output / name).exists() for name in owned):
        raise snapshot.SnapshotError("RDF output already contains conversion artifacts; choose a fresh directory")
    dataset = Dataset()
    returned: list[snapshot.RecordEnvelope] = []
    result: dict[str, Any] = {
        "status": "complete", "operation": "records rdf-roundtrip",
        "schema_sha256": hashlib.sha256(schema.read_bytes()).hexdigest(),
        "rdf_format": "trig", "records": [], "diagnostics": [],
    }
    try:
        writer, reader = build_format_converters(schema)
        for item in envelopes:
            rdf = writer.convert(item.record, item.class_name)
            graph = dataset.graph(URIRef("urn:orinoco:record:" + hashlib.sha256(item.pid.encode()).hexdigest()))
            graph.parse(data=rdf, format="turtle")
            restored = reader.convert(rdf, item.class_name)
            returned.append(snapshot.RecordEnvelope(item.class_name, restored))
            comparison: dict[str, Any] = {"status": "not-evaluated"}
            if compare_rdf:
                reencoded = Graph().parse(data=writer.convert(restored, item.class_name), format="turtle")
                comparison = {"status": "complete", **rdf_graph_difference(graph, reencoded)}
            result["records"].append({"subject": item.pid, "graph": str(graph.identifier),
                                      "rdf_reencoding": comparison})
    except BaseException as error:
        result["status"] = "failed"
        result["diagnostics"].append(f"{len(returned)}/{len(envelopes)} records returned: {type(error).__name__}: {error}")
        if not isinstance(error, Exception):
            raise
    finally:
        dataset.serialize(destination=str(output / "intermediate.rdf"), format="trig")
        returned_path = output / (
            "returned.jsonl" if result["status"] == "complete" else "returned.partial.jsonl"
        )
        if returned:
            snapshot.write_jsonl(returned_path, returned)
        else:
            returned_path.write_text("", encoding="utf-8")
        snapshot.write_json(output / "conversion.json", result)
    return result


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("convert", help="Split captured records and machine annotations")
    parser.add_argument("source", type=Path)
    parser.add_argument("site_inputs", type=Path)
    parser.add_argument("--no-record", action="store_true")
    parser.set_defaults(records_action="convert")
    parser = subparsers.add_parser("export", help="Join stored records and annotation companions")
    parser.add_argument("site_inputs", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--no-record", action="store_true")
    parser.set_defaults(records_action="export")
    parser = subparsers.add_parser("diff", help="Inspect exact typed record and assertion changes")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--stage", default="storage")
    parser.add_argument("--mode", choices=("isolated", "complete-path"), default="isolated")
    parser.set_defaults(records_action="diff")
    parser = subparsers.add_parser("rdf-roundtrip", help="Retain RDF and returned records from the selected converter pair")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--no-record", action="store_true")
    parser.add_argument("--compare-rdf", action="store_true",
                        help="Also compare reencoded RDF modulo blank-node labels; large symmetric graphs may be expensive")
    parser.set_defaults(records_action="rdf-roundtrip")


def execute(args: argparse.Namespace) -> int:
    from .stage_reports import write_operation, write_report

    action = args.records_action
    try:
        if action == "convert":
            result = convert(args.source, args.site_inputs)
            print(f"Converted {result['record_count']} records and {result['annotation_companions']} annotation companions into {args.site_inputs}")
        elif action == "export":
            joined = export_records(args.site_inputs, args.output)
            inputs = {"metadata": args.site_inputs / "metadata"}
            write_operation(args.output, operation="records export", inputs=inputs, command=getattr(args, "invocation", []))
            print(f"Exported {len(joined)} joined records to {args.output}")
        elif action == "rdf-roundtrip":
            result = rdf_roundtrip(args.source, args.output, compare_rdf=args.compare_rdf)
            write_operation(args.output, operation="records rdf-roundtrip", inputs={"records": args.source},
                            command=getattr(args, "invocation", []), context={"schema_sha256": result["schema_sha256"], "status": result["status"]})
            returned_path = args.output / (
                "returned.jsonl" if result["status"] == "complete" else "returned.partial.jsonl"
            )
            write_operation(returned_path, operation="records rdf-roundtrip",
                            inputs={"records": args.source}, command=getattr(args, "invocation", []),
                            context={"schema_sha256": result["schema_sha256"], "status": result["status"]})
            print(f"RDF conversion {result['status']}: {len(result['records'])} returned records; evidence in {args.output}")
            for diagnostic in result["diagnostics"]:
                print(diagnostic, file=sys.stderr)
            return 0 if result["status"] == "complete" else 2
        elif action == "diff":
            # A failed or stale producer cannot support a completed boundary
            # comparison, including when the caller does not request a report.
            _check_record_input(args.left)
            _check_record_input(args.right)
            left, right = snapshot.load_jsonl(args.left), snapshot.load_jsonl(args.right)
            findings = compare_records(left, right)
            print(f"{args.stage}: {len(left)} left records, {len(right)} right records, {len(findings)} raw findings")
            print(f"Inputs: {args.left} -> {args.right}; comparator: {COMPARATOR}")
            for item in findings[:30]:
                location = "/".join(str(part) for part in item["location"]) or "<record>"
                before = json.dumps(item["before"], ensure_ascii=False) if item["before_present"] else "<missing>"
                after = json.dumps(item["after"], ensure_ascii=False) if item["after_present"] else "<missing>"
                if len(before) > 180:
                    before = before[:177] + "..."
                if len(after) > 180:
                    after = after[:177] + "..."
                print(f"  {item['subject']} {location}: {item['change']} ({item['identity']}) {before} -> {after}")
            equivalent = sum("representation_equivalence" in item for item in findings)
            if equivalent:
                print(f"Annotation representation equivalents: {equivalent}; raw differences remain recorded.")
            if len(findings) > 30:
                print(f"Showing 30 of {len(findings)} findings. Use --report to retain every finding and full values.")
            if args.report:
                evidence: dict[str, Path] = {}
                if args.stage == "rdf":
                    for side, path in (("left", args.left), ("right", args.right)):
                        if path.name != "returned.jsonl":
                            continue
                        for name in ("intermediate.rdf", "conversion.json"):
                            artifact = path.with_name(name)
                            if artifact.is_file():
                                evidence[f"{side}-{name}"] = artifact
                write_report(args.report, stage=args.stage, left=args.left, right=args.right,
                             findings=findings, comparator=COMPARATOR, mode=args.mode,
                             scope={"complete": True,
                                    "subjects": sorted({item.pid for item in [*left, *right]}),
                                    "all_locations": True, "selection": "all records",
                                    "exclusions": []},
                             command=getattr(args, "invocation", []), evidence=evidence)
                print(f"Report: {args.report}")
            return 1 if findings else 0
        else:
            raise ValueError(f"unknown record operation: {action}")
    except (OSError, ValueError, ConfigurationError, snapshot.SnapshotError, storage.StorageProjectionError) as error:
        print(f"records {action}: {error}", file=sys.stderr)
        return 2
    return 0
