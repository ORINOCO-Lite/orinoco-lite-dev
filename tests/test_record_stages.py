from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

import pytest
from rdflib import Dataset, Graph

from orinoco_lite import record_stages as stages
from orinoco_lite import upstream_snapshot as snapshot


def envelope(**values):
    return snapshot.RecordEnvelope("XYZPublication", {
        "pid": "xyzrins:publications/example", "schema_type": "xyzri:XYZPublication",
        **values,
    })


def capture(tmp_path, *envelopes):
    path = tmp_path / "captured.jsonl"
    snapshot.write_jsonl(path, list(envelopes))
    return path


def test_diff_preserves_scalar_types_missing_null_order_and_duplicates():
    left = envelope(title=True, description=1, display_label=None,
                    exact_mappings=["ex:a", "ex:b", "ex:a"])
    right = envelope(title=1, description=1.0,
                     exact_mappings=["ex:a", "ex:a", "ex:b"])
    original = deepcopy(left.record)
    findings = stages.compare_records([left], [right])
    by_location = {tuple(item["location"]): item for item in findings}
    assert len(findings) == 4
    assert by_location["title",]["before"] is True
    assert type(by_location["title",]["after"]) is int
    assert type(by_location["description",]["after"]) is float
    missing = by_location["display_label",]
    assert missing["before_present"] is True
    assert missing["after_present"] is False
    assert missing["before"] is None and missing["after"] is None
    assert by_location["exact_mappings",]["change"] == "list-changed"
    assert left.record == original


def test_stable_entity_identity_and_unique_structural_assertions():
    left = envelope(
        attributes=[{"predicate": "ex:p", "value": "old"}],
        generated_by=[{"object": "ex:process", "at_time": "2024"}],
        about=[{"pid": "ex:thing", "display_label": "Old"}],
    )
    right = envelope(
        attributes=[{"predicate": "ex:p", "value": "new"}],
        generated_by=[{"object": "ex:process", "at_time": "2025"}],
        about=[{"pid": "ex:thing", "display_label": "New"}],
    )
    findings = stages.compare_records([left], [right])
    changed = [item for item in findings if item["change"] == "changed"]
    assert {item["location"][-1] for item in changed} == {"value", "at_time", "display_label"}
    assert {item["identity"] for item in changed if item["location"][-1] != "display_label"} == {"structural"}
    assert next(item for item in changed if item["location"][-1] == "display_label")["identity"] == "stable"
    assert len([item for item in findings if item["change"] == "list-changed"]) == 3


@pytest.mark.parametrize("field,first,second", [
    ("attributes", {"predicate": "ex:p", "value": "one"}, {"predicate": "ex:p", "value": "two"}),
    ("generated_by", {"object": "ex:a", "at_time": "2024"}, {"object": "ex:a", "at_time": "2025"}),
    ("about", {"pid": "ex:a", "display_label": "one"}, {"pid": "ex:a", "display_label": "two"}),
])
def test_repeated_assertion_contexts_are_unmatched_not_positional(field, first, second):
    changed = {**first, "description": "new"}
    findings = stages.compare_records([envelope(**{field: [first, second]})],
                                     [envelope(**{field: [second, changed]})])
    assert len(findings) == 3
    assert findings[0]["change"] == "list-changed"
    assert {item["change"] for item in findings[1:]} == {"added", "removed"}
    assert {item["identity"] for item in findings[1:]} == {"unmatched"}


def test_duplicate_count_change_is_retained_without_fabricated_identity():
    attribute = {"predicate": "ex:p", "value": "one"}
    findings = stages.compare_records([envelope(attributes=[attribute, attribute])],
                                     [envelope(attributes=[attribute])])
    assert len(findings) == 2
    assert findings[0]["before"] == [attribute, attribute]
    assert findings[1]["identity"] == "unmatched"
    assert findings[1]["change"] == "removed"


def test_unchanged_native_assertion_disambiguates_attribution_change():
    first = {"predicate": "ex:p", "value": "one", "annotations": {"ex:review": "old"}}
    second = {"predicate": "ex:p", "value": "two"}
    changed = {**first, "annotations": {"ex:review": "new"}}
    findings = stages.compare_records([envelope(attributes=[first, second])],
                                     [envelope(attributes=[second, changed])])
    assert len(findings) == 2
    assert findings[1]["location"][-2:] == ["annotations", "ex:review"]
    assert findings[1]["identity"] == "structural"
    assert findings[1]["before"] == "old"
    assert findings[1]["after"] == "new"


def test_annotation_equivalence_keeps_raw_changes():
    left = envelope(annotations={"ex:review": "yes"})
    right = envelope(annotations={"ex:review": {"annotation_tag": "ex:review", "annotation_value": "yes"}})
    findings = stages.compare_records([left], [right])
    assert len(findings) == 1
    assert findings[0]["before"] == "yes"
    assert findings[0]["representation_equivalence"] == "annotation-representation-v1"


def test_duplicate_json_keys_fail_before_comparison(tmp_path):
    source = tmp_path / "ambiguous.jsonl"
    source.write_text('{"class_name":"XYZPublication","record":{"pid":"ex:a",'
                      '"schema_type":"xyzri:XYZPublication","title":"a","title":"b"}}\n')
    with pytest.raises(snapshot.SnapshotError, match="duplicate JSON key"):
        snapshot.load_jsonl(source)


def test_convert_and_export_preserve_authored_inputs_capture_and_source_marker(tmp_path):
    inputs = tmp_path / "site-specific"
    inputs.mkdir()
    (inputs / "site.yaml").write_text("title: Authored\n")
    (inputs / "content").mkdir()
    (inputs / "content/index.md").write_bytes(b"Authored page\n")
    source_dir = inputs / "sources/pool"
    source_dir.mkdir(parents=True)
    record = envelope(generated_by=[{"object": "ex:process", "at_time": "-",
                      "schema_type": "dlthings:Generation"}], attributes=[{
        "predicate": "ex:title", "value": "Authored value",
        "annotations": {"pav:importedBy": "ex:adapter", "pav:importedFrom": "https://example.org/source"},
    }])
    source = capture(source_dir, record)
    original = source.read_bytes()
    stages.convert(source, inputs)
    report = stages.convert(source, inputs)
    exported = stages.export_records(inputs, tmp_path / "joined.jsonl")
    assert source.read_bytes() == original
    assert (inputs / "site.yaml").read_text() == "title: Authored\n"
    assert (inputs / "content/index.md").read_bytes() == b"Authored page\n"
    assert not (inputs / "manifest.json").exists()
    assert report["annotation_companions"] == 1
    assert exported[0].record["generated_by"][0]["at_time"] == "-"
    differences = stages.compare_records([record], exported)
    assert all(item.get("representation_equivalence") == "annotation-representation-v1" for item in differences)


def test_failed_conversion_preserves_existing_metadata(tmp_path):
    inputs = tmp_path / "site-specific"
    source = capture(tmp_path, envelope(title="Initial"))
    stages.convert(source, inputs)
    existing = next((inputs / "metadata/records").rglob("*.yaml"))
    original = existing.read_bytes()
    source.write_text('{"class_name":"XYZPublication","record":{}}\n')
    with pytest.raises(snapshot.SnapshotError):
        stages.convert(source, inputs)
    assert existing.read_bytes() == original


def test_public_export_accepts_reviewed_edits_to_converted_records(tmp_path, capsys):
    from orinoco_lite import cli

    source = capture(tmp_path, envelope(title="Original title"))
    inputs, output = tmp_path / "inputs", tmp_path / "joined.jsonl"
    assert cli.main(["dev", "records", "convert", str(source), str(inputs), "--no-record"]) == 0
    record = next((inputs / "metadata/records").rglob("*.yaml"))
    record.write_text(record.read_text().replace("Original title", "Reviewed title"))

    assert cli.main(["dev", "records", "export", str(inputs), str(output)]) == 0
    assert snapshot.load_jsonl(output)[0].record["title"] == "Reviewed title"
    assert snapshot.load_jsonl(source)[0].record["title"] == "Original title"
    capsys.readouterr()


def test_convert_rejects_capture_inside_replaced_metadata(tmp_path):
    records = tmp_path / "metadata/records"
    records.mkdir(parents=True)
    source = capture(records, envelope())
    with pytest.raises(snapshot.SnapshotError, match="inside a replaced"):
        stages.convert(source, tmp_path)
    assert source.exists()


def test_export_rejects_orphan_companion_before_output(tmp_path):
    source = capture(tmp_path, envelope())
    inputs = tmp_path / "inputs"
    stages.convert(source, inputs)
    companion = inputs / "metadata/overlays/annotations/XYZPublication/orphan.yaml"
    companion.parent.mkdir(parents=True)
    companion.write_text("record: ex:missing\nassertions: []\n")
    output = tmp_path / "joined.jsonl"
    with pytest.raises(snapshot.SnapshotError, match="no mirrored"):
        stages.export_records(inputs, output)
    assert not output.exists()


def test_rdf_comparison_ignores_blank_node_labels_but_detects_value_changes():
    left = Graph().parse(data='@prefix ex: <https://example.org/> . ex:a ex:p [ ex:q "one" ] .', format="turtle")
    right = Graph().parse(data='@prefix ex: <https://example.org/> . ex:a ex:p _:renamed . _:renamed ex:q "one" .', format="turtle")
    assert stages.rdf_graph_difference(left, right)["isomorphic"] is True
    changed = Graph().parse(data='@prefix ex: <https://example.org/> . ex:a ex:p [ ex:q "two" ] .', format="turtle")
    assert stages.rdf_graph_difference(left, changed)["isomorphic"] is False


def test_rdf_failure_retains_partial_graph_and_returned_records(tmp_path, monkeypatch):
    source = capture(tmp_path, envelope())
    schema = tmp_path / "schema.yaml"
    schema.write_text("schema input")

    class Writer:
        def convert(self, _record, _class):
            return '<https://example.org/a> <https://example.org/p> "value" .'

    class Reader:
        def convert(self, _rdf, _class):
            raise ValueError("injected inverse failure")

    monkeypatch.setattr(stages, "build_format_converters", lambda _: (Writer(), Reader()))
    output = tmp_path / "rdf"
    result = stages.rdf_roundtrip(source, output, schema=schema)
    assert result["status"] == "failed"
    assert "injected inverse failure" in result["diagnostics"][0]
    assert len(Dataset().parse(output / "intermediate.rdf", format="trig")) == 1
    assert not (output / "returned.jsonl").exists()
    assert (output / "returned.partial.jsonl").read_text() == ""
    assert json.loads((output / "conversion.json").read_text())["status"] == "failed"


def test_interrupted_rdf_conversion_never_records_complete(tmp_path, monkeypatch):
    source = capture(tmp_path, envelope())
    schema = tmp_path / "schema.yaml"
    schema.write_text("schema input")

    def interrupt(_schema):
        raise KeyboardInterrupt()

    monkeypatch.setattr(stages, "build_format_converters", interrupt)
    output = tmp_path / "rdf"
    with pytest.raises(KeyboardInterrupt):
        stages.rdf_roundtrip(source, output, schema=schema)
    assert json.loads((output / "conversion.json").read_text())["status"] == "failed"
    assert not (output / "returned.jsonl").exists()


def test_interrupted_partial_records_cannot_be_compared_or_reused(tmp_path, monkeypatch, capsys):
    from orinoco_lite import cli

    first = envelope()
    second = envelope(pid="xyzrins:publications/second")
    source = capture(tmp_path, first, second)
    schema = tmp_path / "schema.yaml"
    schema.write_text("schema input")

    class Writer:
        def convert(self, record, _class):
            if record["pid"] == second.pid:
                raise KeyboardInterrupt()
            return '<https://example.org/a> <https://example.org/p> "value" .'

    class Reader:
        def convert(self, _rdf, _class):
            return first.record

    monkeypatch.setattr(stages, "build_format_converters", lambda _: (Writer(), Reader()))
    output = tmp_path / "rdf"
    with pytest.raises(KeyboardInterrupt):
        stages.rdf_roundtrip(source, output, schema=schema)
    partial = output / "returned.partial.jsonl"
    assert snapshot.load_jsonl(partial) == [first]
    report = tmp_path / "report"
    assert cli.main(["dev", "records", "diff", str(partial), str(partial), "--report", str(report)]) == 2
    assert not report.exists()
    converted = tmp_path / "converted"
    assert cli.main(["dev", "records", "convert", str(partial), str(converted), "--no-record"]) == 2
    assert not converted.exists()
    retry = tmp_path / "retry"
    assert cli.main(["dev", "records", "rdf-roundtrip", str(partial), str(retry)]) == 2
    assert not retry.exists()
    assert "Incomplete RDF return" in capsys.readouterr().err


@pytest.mark.parametrize("status", ["failed", "stale"])
def test_rdf_rejects_failed_or_stale_input_before_writing_output(tmp_path, monkeypatch, status):
    from orinoco_lite.stage_reports import write_operation

    source = capture(tmp_path, envelope(title="Initial"))
    write_operation(source, operation="test", inputs={}, context={"status": "failed" if status == "failed" else "complete"})
    if status == "stale":
        snapshot.write_jsonl(source, [envelope(title="Changed")])
    monkeypatch.setattr(stages, "build_format_converters", lambda _: pytest.fail("Invalid input reached conversion"))
    output = tmp_path / "rdf"
    args = argparse.Namespace(records_action="rdf-roundtrip", source=source, output=output, compare_rdf=False)
    assert stages.execute(args) == 2
    assert not output.exists()


def test_diff_cli_exit_codes_and_report_raw_findings(tmp_path, capsys):
    left = capture(tmp_path, envelope(title="before"))
    right = tmp_path / "right.jsonl"
    snapshot.write_jsonl(right, [envelope(title="after")])
    parser = argparse.ArgumentParser()
    stages.register(parser.add_subparsers())
    report = tmp_path / "report"
    args = parser.parse_args(["diff", str(left), str(right), "--report", str(report)])
    assert stages.execute(args) == 1
    assert "1 raw findings" in capsys.readouterr().out
    raw = json.loads((report / "report.json").read_text())
    assert raw["stages"][0]["findings"][0]["location"] == ["title"]
    assert stages.execute(parser.parse_args(["diff", str(left), str(left)])) == 0
    assert stages.execute(parser.parse_args(["diff", str(left), str(tmp_path / "missing")])) == 2
