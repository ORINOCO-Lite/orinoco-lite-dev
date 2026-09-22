from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

import pytest

from orinoco_lite.errors import ConfigurationError
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


def test_annotation_restructuring_is_a_difference():
    left = envelope(annotations={"ex:review": "yes"})
    right = envelope(annotations={"ex:review": {"annotation_tag": "ex:review", "annotation_value": "yes"}})
    findings = stages.compare_records([left], [right])
    assert len(findings) == 1
    assert findings[0]["before"] == "yes"
    assert "representation_equivalence" not in findings[0]


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
    stages.jsonl_to_yaml(source, inputs)
    report = stages.jsonl_to_yaml(source, inputs)
    exported = stages.yaml_to_jsonl(inputs, tmp_path / "joined.jsonl")
    assert source.read_bytes() == original
    assert (inputs / "site.yaml").read_text() == "title: Authored\n"
    assert (inputs / "content/index.md").read_bytes() == b"Authored page\n"
    assert not (inputs / "manifest.json").exists()
    assert report["annotation_companions"] == 1
    assert exported[0].record["generated_by"][0]["at_time"] == "-"
    differences = stages.compare_records([record], exported)
    assert differences == []


def test_failed_conversion_preserves_existing_metadata(tmp_path):
    inputs = tmp_path / "site-specific"
    source = capture(tmp_path, envelope(title="Initial"))
    stages.jsonl_to_yaml(source, inputs)
    existing = next((inputs / "metadata/records").rglob("*.yaml"))
    original = existing.read_bytes()
    source.write_text('{"class_name":"XYZPublication","record":{}}\n')
    with pytest.raises(snapshot.SnapshotError):
        stages.jsonl_to_yaml(source, inputs)
    assert existing.read_bytes() == original


def test_public_workflow_preserves_curated_inputs_and_requires_explicit_replacement(tmp_path, monkeypatch, capsys):
    from orinoco_lite import cli

    monkeypatch.chdir(tmp_path)
    root = tmp_path / "upstream-diffing"
    root.mkdir()
    snapshot.write_jsonl(root / "downloaded/records.jsonl", [envelope(title="Original title")])
    curated = tmp_path / "site-specific/metadata/records/human.yaml"
    curated.parent.mkdir(parents=True)
    curated.write_text("Human curated input\n")
    def run(*args):
        return cli.main(["dev", "records", *args])
    assert run("jsonl-to-yaml") == 0
    record = next((root / "yaml/metadata/records").rglob("*.yaml"))
    record.write_text(record.read_text().replace("Original title", "Reviewed title"))
    before = record.read_bytes()
    assert run("jsonl-to-yaml") == 2
    assert record.read_bytes() == before
    assert run("yaml-to-jsonl") == 0
    assert run("diff") == 1
    report = root / "reports/downloaded-vs-yaml-jsonl/report.json"
    assert "Reviewed title" in report.read_text()
    saved_report = report.read_bytes()
    assert run("diff") == 1
    assert report.read_bytes() == saved_report
    assert run("diff", "--force") == 1
    assert run("jsonl-to-yaml", "--force") == 0
    assert "Original title" in record.read_text()
    assert curated.read_text() == "Human curated input\n"
    assert run("jsonl-to-yaml", "--directory", "another-investigation") == 2
    assert "records get" in capsys.readouterr().err


def test_convert_rejects_capture_inside_replaced_metadata(tmp_path):
    records = tmp_path / "metadata/records"
    records.mkdir(parents=True)
    source = capture(records, envelope())
    with pytest.raises(snapshot.SnapshotError, match="inside a replaced"):
        stages.jsonl_to_yaml(source, tmp_path)
    assert source.exists()


def test_export_rejects_orphan_companion_before_output(tmp_path):
    source = capture(tmp_path, envelope())
    inputs = tmp_path / "inputs"
    stages.jsonl_to_yaml(source, inputs)
    companion = inputs / "metadata/overlays/annotations/XYZPublication/orphan.yaml"
    companion.parent.mkdir(parents=True)
    companion.write_text("record: ex:missing\nassertions: []\n")
    output = tmp_path / "joined.jsonl"
    with pytest.raises(snapshot.SnapshotError, match="no mirrored"):
        stages.yaml_to_jsonl(inputs, output)
    assert not output.exists()











def test_diff_accepts_deliberate_diagnostic_edits_without_false_producer_attribution(tmp_path):
    from orinoco_lite import cli
    from orinoco_lite.stage_reports import write_operation
    left = tmp_path / "downloaded/records.jsonl"
    right = tmp_path / "yaml-jsonl/records.jsonl"
    snapshot.write_jsonl(left, [envelope(title="before")])
    snapshot.write_jsonl(right, [envelope(title="before")])
    write_operation(right, operation="records yaml-to-jsonl", inputs={"records": left})
    snapshot.write_jsonl(right, [envelope(title="after")])
    assert cli.main(["dev", "records", "diff", "--directory", str(tmp_path)]) == 1
    raw = json.loads((tmp_path / "reports/downloaded-vs-yaml-jsonl/report.json").read_text())
    assert raw["stages"][0]["findings"][0]["location"] == ["title"]
    assert raw["stages"][0]["artifacts"]["right"]["operation"] is None


def test_native_temporary_path_is_a_valid_investigation_directory():
    import tempfile
    from orinoco_lite import cli
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        snapshot.write_jsonl(root / "downloaded/records.jsonl", [envelope()])
        assert cli.main(["dev", "records", "jsonl-to-yaml", "--directory", temporary]) == 0


def test_public_conversion_preserves_annotation_values_without_edits(tmp_path, monkeypatch):
    from orinoco_lite import cli

    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'upstream-diffing'
    root.mkdir()
    original = envelope(annotations={'ex:review': 'yes'}, attributes=[{
        'predicate': 'ex:title', 'value': 'A title',
        'annotations': {'pav:importedBy': 'ex:adapter',
                        'pav:importedFrom': 'https://example.org/source',
                        'ex:review': {'annotation_tag': 'ex:review', 'annotation_value': 'keep this shape'}},
    }])
    snapshot.write_jsonl(root / 'downloaded/records.jsonl', [original])
    for command in ('jsonl-to-yaml', 'yaml-to-jsonl', 'diff'):
        assert cli.main(['dev', 'records', command]) == 0
    assert snapshot.load_jsonl(root / 'yaml-jsonl/records.jsonl')[0].record == original.record


def test_diff_all_filters_and_repeat_inspection_preserve_saved_report(tmp_path, monkeypatch, capsys):
    from orinoco_lite import cli

    monkeypatch.chdir(tmp_path)
    root = tmp_path / 'upstream-diffing'
    root.mkdir()
    snapshot.write_jsonl(root / 'downloaded/records.jsonl', [envelope(title='before', description='old')])
    for command in ('jsonl-to-yaml', 'yaml-to-jsonl'):
        assert cli.main(['dev', 'records', command]) == 0
    snapshot.write_jsonl(root / 'yaml-jsonl/records.jsonl', [envelope(title='after', description='new')])
    assert cli.main(['dev', 'records', 'diff', 'all', '--summary']) == 1
    output = capsys.readouterr().out
    assert 'Downloaded records (JSONL)' in output
    assert 'Records after YAML → JSONL' in output
    assert '1 records differ' in output
    report = root / 'reports/downloaded-vs-yaml-jsonl/report.json'
    before = report.read_bytes()
    assert cli.main(['dev', 'records', 'diff', '--field', 'title', '--limit', '1']) == 1
    output = capsys.readouterr().out
    assert 'before: "before"' in output and 'after:  "after"' in output
    assert 'before: "old"' not in output
    assert report.read_bytes() == before
    # A failed re-comparison must not erase evidence, even with --force.
    (root / 'yaml-jsonl/records.jsonl').write_text('not JSON\n')
    assert cli.main(['dev', 'records', 'diff', '--force']) == 2
    assert report.read_bytes() == before


def test_diff_all_without_inputs_explains_what_to_run(tmp_path, monkeypatch, capsys):
    from orinoco_lite import cli
    monkeypatch.chdir(tmp_path)
    assert cli.main(['dev', 'records', 'diff', 'all']) == 2
    assert 'records get' in capsys.readouterr().err




@pytest.mark.parametrize('prefix', ['pav:', 'http://purl.org/pav/'])
@pytest.mark.parametrize('expanded', [False, True])
def test_public_roundtrip_preserves_original_pav_forms(tmp_path, prefix, expanded):
    from orinoco_lite import cli
    annotations = {prefix + 'importedBy': 'ex:adapter', prefix + 'importedFrom': 'https://example.org/source'}
    if expanded:
        annotations = {key: {'annotation_tag': key, 'annotation_value': value} for key, value in annotations.items()}
    original = envelope(attributes=[{'predicate': 'ex:title', 'value': 'Title', 'annotations': annotations}])
    snapshot.write_jsonl(tmp_path / 'downloaded/records.jsonl', [original])
    for command in ('jsonl-to-yaml', 'yaml-to-jsonl', 'diff'):
        assert cli.main(['dev', 'records', command, '--directory', str(tmp_path)]) == 0
    assert snapshot.load_jsonl(tmp_path / 'yaml-jsonl/records.jsonl')[0].record == original.record
    # Retained original syntax must not contradict the provenance values.
    if prefix != 'pav:' or expanded:
        import yaml
        companion = next((tmp_path / 'yaml/metadata/overlays/annotations').rglob('*.yaml'))
        value = yaml.safe_load(companion.read_text())
        value['assertions'][0]['pav:importedBy'] = 'ex:different-adapter'
        companion.write_bytes(snapshot.canonical_yaml_bytes(value))
        with pytest.raises(ConfigurationError, match='disagree'):
            stages.yaml_to_jsonl(tmp_path / 'yaml', tmp_path / 'invalid.jsonl')




@pytest.mark.parametrize(("before", "after", "same", "removed", "added"), [
    (["a", "b", "a"], ["a", "a", "b"], True, 0, 0),
    (["a", "a"], ["a"], False, 1, 0),
    ([1], [True], False, 1, 1),
    ([{"items": [1, 2]}], [{"items": [2, 1]}], False, 1, 1),
])
def test_list_summary_counts_occurrences_without_approving_order(before, after, same, removed, added):
    left = snapshot.RecordEnvelope("Thing", {"pid": "ex:s", "schema_type": "dlthings:Thing", "items": before})
    right = snapshot.RecordEnvelope("Thing", {**left.record, "items": after})
    findings = stages.compare_records([left], [right])
    assert findings[0]["change"] == "list-changed"
    assert findings[0]["before"] == before
    assert findings[0]["after"] == after
    assert findings[0]["list_comparison"] == {
        "same_items": same, "removed_occurrences": removed, "added_occurrences": added,
    }


def test_download_yaml_jsonl_can_be_verified_by_byte_comparison(tmp_path, monkeypatch):
    from orinoco_lite import cli, pool_capture

    rows = [
        envelope(pid="ex:z", title="Données 🧠", exact_mappings=["ex:b", "ex:a", "ex:b"],
                 attributes=[{"predicate": "ex:title", "value": "ü",
                              "annotations": {"pav:importedBy": "ex:adapter",
                                              "pav:importedFrom": "https://example.org/source"}}]).record,
        envelope(pid="ex:a", title="First after ordering").record,
    ]
    monkeypatch.setattr(pool_capture, "fetch_live", lambda api: ({r["pid"]: r for r in rows}, {}))
    assert cli.main(["dev", "records", "get", "--directory", str(tmp_path)]) == 0
    for command in ("jsonl-to-yaml", "yaml-to-jsonl"):
        assert cli.main(["dev", "records", command, "--directory", str(tmp_path)]) == 0

    downloaded = (tmp_path / "downloaded/records.jsonl").read_bytes()
    reconstructed = (tmp_path / "yaml-jsonl/records.jsonl").read_bytes()
    # Independent standard-library expectation; no project comparator.
    expected = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":")) + "\n" for row in reversed(rows)).encode()
    assert downloaded == expected
    assert reconstructed == downloaded


def test_explicit_paths_roundtrip_downstream_and_preserve_unrelated_files(tmp_path, monkeypatch):
    from orinoco_lite import cli
    monkeypatch.chdir(tmp_path)
    source = capture(tmp_path, envelope(title="Explicit inputs"))
    inputs = tmp_path / "site-specific"
    inputs.mkdir()
    (inputs / "site.yaml").write_text("authored: true\n")
    (inputs / ".git").write_text("gitdir: ../subdataset.git\n")
    command = ["dev", "records", "jsonl-to-yaml", "--source", source.name,
               "--destination", "site-specific"]
    assert cli.main(command) == 0
    assert cli.main(command) == 2
    assert cli.main(command + ["--force"]) == 0
    assert (inputs / "site.yaml").read_text() == "authored: true\n"
    assert (inputs / ".git").read_text() == "gitdir: ../subdataset.git\n"
    export = ["dev", "records", "yaml-to-jsonl", "--source", "site-specific",
              "--output", "inspection/roundtrip.jsonl"]
    assert cli.main(export) == 0
    assert cli.main(export) == 2
    assert cli.main(export + ["--force"]) == 0
    assert snapshot.load_jsonl(source) == snapshot.load_jsonl(tmp_path / "inspection/roundtrip.jsonl")
    assert cli.main(["dev", "records", "diff", source.name, "site-specific",
                     "--report", "inspection/comparison"]) == 0
    assert cli.main(["dev", "records", "diff", source.name, "site-specific",
                     "--report", ".", "--force"]) == 2
    assert source.is_file()


def test_forced_conversion_cannot_delete_its_source(tmp_path, monkeypatch):
    from orinoco_lite import cli
    monkeypatch.chdir(tmp_path)
    source_dir = tmp_path / "site-specific/metadata/records"
    source_dir.mkdir(parents=True)
    source = capture(source_dir, envelope(title="Keep"))
    original = source.read_bytes()
    assert cli.main(["dev", "records", "jsonl-to-yaml", "--source", str(source),
                     "--destination", "site-specific", "--force"]) == 2
    assert source.read_bytes() == original
