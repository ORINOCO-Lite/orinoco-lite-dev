"""Forward RDF conversion and independently scoped comparison reports."""
from __future__ import annotations

from importlib.metadata import version
from pathlib import Path
import hashlib
import json
import shutil
import sys
from time import perf_counter

from . import rdf_compare, upstream_snapshot as snapshot
from .errors import ConfigurationError
from .record_stages import SCHEMA_RELATIVE, _check_record_input
from .resources import resolve_resources
from .schema_conversion import build_format_converters
from .stage_reports import artifact_digest, read_json, safe_artifact, write_json, write_operation, write_report


def jsonl_to_rdf(source: Path, output: Path, *, schema: Path | None = None) -> dict:
    """Use the upstream per-record writer and the parser's standard RDF merge.

    Preserve each original Turtle document for optional record attribution.
    The combined output is one default graph, with independent blank-node scopes.
    """
    from pyoxigraph import Dataset, RdfFormat, parse, serialize

    _check_record_input(source)
    envelopes = snapshot.load_jsonl(source)
    schema = schema or resolve_resources().root / SCHEMA_RELATIVE
    if output.exists() or output.is_symlink():
        raise ConfigurationError(f"RDF output already exists: {output}; choose a fresh directory")
    if source.resolve().is_relative_to(output.resolve()):
        raise ConfigurationError("RDF output must not contain its source")
    output.mkdir(parents=True)
    (output / "records").mkdir()
    shutil.copyfile(source, output / "source.jsonl")
    started = perf_counter()
    result = {"version": 1, "status": "failed", "operation": "records jsonl-to-rdf",
              "schema_sha256": artifact_digest(schema), "rdf_format": "n-triples",
              "producer": {name: version(name) for name in
                           ("dump-things-service", "linkml-runtime", "rdflib", "pyoxigraph")},
              "source_sha256": artifact_digest(output / "source.jsonl"),
              "records": [], "diagnostics": []}
    dataset = Dataset()
    try:
        writer, = build_format_converters(schema, writer_only=True)
        for item in envelopes:
            relative = "records/" + hashlib.sha256(item.pid.encode()).hexdigest() + ".ttl"
            path = output / relative
            rdf = writer.convert(item.record, item.class_name)
            path.write_text(rdf, encoding="utf-8")
            # Upstream exposes convert(data, target_class), one record per call.
            # Standard RDF merge must not coalesce labels from separate documents.
            for quad in parse(input=rdf, format=RdfFormat.TURTLE, rename_blank_nodes=True):
                dataset.add(quad)
            result["records"].append({"subject": item.pid, "class": item.class_name,
                                      "path": relative, "sha256": artifact_digest(path)})
        result["status"] = "complete"
    except BaseException as error:
        result["diagnostics"].append(f"{len(result['records'])}/{len(envelopes)} records converted: {type(error).__name__}: {error}")
        if not isinstance(error, Exception):
            raise
    finally:
        name = "graph.nt" if result["status"] == "complete" else "partial.nt"
        serialize((quad.triple for quad in dataset), output=output / name, format=RdfFormat.N_TRIPLES)
        result["output"] = name
        result["output_sha256"] = artifact_digest(output / name)
        result["seconds"] = perf_counter() - started
        write_json(output / "conversion.json", result)
        write_operation(output, operation="records jsonl-to-rdf", inputs={"records": source},
                        context={"status": result["status"], "schema_sha256": result["schema_sha256"]})
    return result


def _record_documents(path: Path) -> dict[str, str]:
    conversion = read_json(path.with_name("conversion.json"))
    if (conversion.get("version") != 1 or conversion.get("status") != "complete"
            or conversion.get("operation") != "records jsonl-to-rdf"
            or conversion.get("output") != path.name
            or conversion.get("output_sha256") != artifact_digest(path)):
        raise ConfigurationError(f"No matching complete JSONL → RDF evidence for {path}")
    source = path.with_name("source.jsonl")
    if artifact_digest(source) != conversion.get("source_sha256"):
        raise ConfigurationError(f"Source records changed: {source}")
    envelopes = snapshot.load_jsonl(source)
    records = {}
    for record in conversion["records"]:
        document = safe_artifact(path.parent, record["path"])
        if artifact_digest(document) != record["sha256"] or record["subject"] in records:
            raise ConfigurationError(f"Invalid record attribution evidence: {document}")
        records[record["subject"]] = str(document)
    if set(records) != {item.pid for item in envelopes}:
        raise ConfigurationError(f"Record attribution is incomplete: {path.parent}")
    return records


def _findings(result: dict) -> list[dict]:
    return [{"subject": row["subject"], "location": ["Complete RDF output" if row["subject"] == "Complete RDF output" else "RDF emitted for this record"],
             "change": "added" if not row["before_present"] else "removed" if not row["after_present"] else "changed",
             "identity": "stable", "before_present": row["before_present"], "after_present": row["after_present"],
             "before": {"quads": row["before"]}, "after": {"quads": row["after"]}}
            for row in result["comparisons"]
            if not row["equal"] or row["before_present"] != row["after_present"]]


def compare_outputs(left: Path, right: Path, report: Path, *, by_record: bool = False,
                    selected: list[str] | None = None, left_format: str | None = None,
                    right_format: str | None = None, timeout: float = rdf_compare.DEFAULT_TIMEOUT,
                    command: list[str] | None = None) -> int:
    """Save whole-output evidence first; attribution cannot alter its result."""
    from .diagnostics import prepare_output
    prepare_output(report)
    started = perf_counter()
    scope = {"complete": True, "selection": "complete RDF outputs", "all_locations": True,
             "exclusions": [], "timeout_seconds": timeout}
    try:
        result = rdf_compare.compare_graphs(left, right, left_format=left_format,
                                           right_format=right_format, timeout=timeout)
        findings, status = _findings(result), "complete"
        outcome = "different" if findings else "equal"
        diagnostics = [f"Whole RDF output: {outcome}.", json.dumps(result)]
        scope["result"] = outcome
    except rdf_compare.RDFComparisonError as error:
        findings, status = [], "skipped"
        scope.update(complete=False, result="not evaluated")
        diagnostics = [str(error)]
    scope["comparison_seconds"] = perf_counter() - started
    write_report(report, stage="rdf", left=left, right=right, findings=findings,
                 comparator=rdf_compare.COMPARATOR, scope=scope, status=status,
                 diagnostics=diagnostics, command=command)
    print(f"Complete RDF outputs: {scope['result']} ({scope['comparison_seconds']:.3f}s). Report: {report}")
    if status != "complete":
        print(diagnostics[0], file=sys.stderr)
    if by_record or selected:
        attribution_report = report.with_name(report.name + "-records")
        prepare_output(attribution_report)
        attribution_scope = {"complete": False, "selection": "requested source records" if selected else "all source records",
                             "subjects": sorted(set(selected or [])), "all_locations": True,
                             "exclusions": ["Cross-record interactions in the combined output"], "timeout_seconds": timeout}
        diagnostics = ["Each original per-record Turtle document is compared independently. This locates a difference; it does not establish its cause or identify minimal assertion edits. Differences can cancel in the combined RDF graph."]
        evidence = {}
        started = perf_counter()
        try:
            before, after = _record_documents(left), _record_documents(right)
            subjects = set(before) | set(after)
            if selected:
                if set(selected) - subjects:
                    raise ConfigurationError("Requested record has no conversion evidence")
                subjects = set(selected)
            pairs = [{"subject": subject, "left": before.get(subject), "right": after.get(subject)}
                     for subject in sorted(subjects)]
            result = rdf_compare.compare_records(pairs, timeout=timeout)
            findings, attribution_status = _findings(result), "complete"
            attribution_scope.update(complete=not bool(selected), subjects=sorted(subjects),
                                     result="different" if findings else "equal")
            diagnostics.append(f"Source-record RDF: {attribution_scope['result']}; "
                               f"{len(subjects)} evaluated, {len(findings)} with findings.")
            diagnostics.append(json.dumps({key: value for key, value in result.items()
                                           if key != "comparisons"}))
            evidence = {"left-source": left.with_name("source.jsonl"),
                        "right-source": right.with_name("source.jsonl"),
                        "left-conversion": left.with_name("conversion.json"),
                        "right-conversion": right.with_name("conversion.json")}
            # Retain the original documents needed to inspect findings. Copying
            # every unchanged document is expensive and adds no review evidence.
            for finding in findings:
                subject = finding["subject"]
                suffix = hashlib.sha256(subject.encode()).hexdigest()
                for side, documents in (("left", before), ("right", after)):
                    if subject in documents:
                        evidence[f"{side}-rdf-{suffix}"] = Path(documents[subject])
        except (ValueError, OSError, KeyError, TypeError, ConfigurationError) as error:
            findings, attribution_status = [], "skipped"
            attribution_scope["result"] = "not evaluated"
            diagnostics.append(str(error))
        attribution_scope["comparison_seconds"] = perf_counter() - started
        write_report(attribution_report, stage="rdf-attribution", left=left, right=right,
                     findings=findings, comparator=rdf_compare.ATTRIBUTION_COMPARATOR,
                     scope=attribution_scope, status=attribution_status, diagnostics=diagnostics,
                     command=command, evidence=evidence)
        print(f"Record attribution: {attribution_scope['result']}. Report: {attribution_report}")
        if attribution_status != "complete":
            print(diagnostics[-1], file=sys.stderr)
        for finding in findings[:10]:
            print(f"  {finding['subject']}: RDF emitted for this record {finding['change']}")
    return 2 if status != "complete" else 1 if scope["result"] == "different" else 0


def register(dev_commands, record_commands):
    from .diagnostics import options
    parser = record_commands.add_parser("jsonl-to-rdf", help="convert existing JSONL to RDF with the selected upstream writer")
    parser.add_argument("source_state", nargs="?", default="yaml-jsonl", choices=("downloaded", "yaml-jsonl"))
    options(parser, replace=False)
    parser.add_argument("--source", type=Path, help="JSONL input instead of the selected state")
    parser.add_argument("--output", type=Path, help="fresh RDF output directory (default: DIRECTORY/STATE-rdf)")
    rdf = dev_commands.add_parser("rdf", help="compare complete RDF outputs, with optional source-record attribution")
    commands = rdf.add_subparsers(dest="rdf_action", required=True)
    parser = commands.add_parser("compare", help="bounded RDFC-1.0 comparison; no entailment or JSON roundtrip claim")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--report", type=Path, required=True, help="fresh report directory")
    for side in ("left", "right"):
        parser.add_argument(f"--{side}-format", choices=sorted(set(rdf_compare.FORMATS.values())))
    parser.add_argument("--by-record", action="store_true", help="also compare original per-record RDF documents when conversion evidence is available")
    parser.add_argument("--record", action="append", help="limit only optional record attribution; whole-output comparison is unchanged")


def execute(args):
    from .diagnostics import directory, record_path, explicit_path
    try:
        if getattr(args, "records_command", None) == "jsonl-to-rdf":
            root = directory(args)
            source = getattr(args, "source", None)
            selected = explicit_path(args, source) if source else record_path(root, args.source_state)
            output = getattr(args, "output", None)
            output = explicit_path(args, output) if output else root / (args.source_state + "-rdf")
            result = jsonl_to_rdf(selected, output)
            print(f"JSONL → RDF: {result['status']}; {len(result['records'])} records; {output}")
            for diagnostic in result["diagnostics"]:
                print(diagnostic, file=sys.stderr)
            return 0 if result["status"] == "complete" else 2
        return compare_outputs(args.left.resolve(), args.right.resolve(), args.report.resolve(),
                               by_record=args.by_record, selected=args.record,
                               left_format=args.left_format, right_format=args.right_format,
                               command=getattr(args, "invocation", []))
    except (ValueError, OSError, ConfigurationError, snapshot.SnapshotError) as error:
        print(f"RDF operation: {error}", file=sys.stderr)
        return 2
