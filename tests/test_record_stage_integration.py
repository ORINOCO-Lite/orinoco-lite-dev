"""Exercise record stages through the public CLI and shared review contract."""

from copy import deepcopy
import json
import yaml

from orinoco_lite import cli, record_stages, stage_reports, stage_review
from orinoco_lite import upstream_snapshot as snapshot


def source(path, *, annotation="yes"):
    record = snapshot.RecordEnvelope("XYZPublication", {
        "pid": "xyzrins:publications/example", "schema_type": "xyzri:XYZPublication",
        "annotations": {"ex:review": annotation},
        "title": "Unchanged authored title",
    })
    snapshot.write_jsonl(path, [record])
    return record


def storage_run(root, *, annotation="yes"):
    capture = root / "downloaded/records.jsonl"
    source(capture, annotation=annotation)
    original = capture.read_bytes()
    inputs = root / "yaml"
    authored = root / "site-specific/content/about.md"
    authored.parent.mkdir(parents=True)
    authored.write_text("Authored content\n")
    assert cli.main(["dev", "records", "jsonl-to-yaml", "--directory", str(root), "--destination", str(inputs)]) == 0
    # A deliberate YAML edit, not a conversion artifact, requires review.
    yaml_record = next((inputs / "metadata/records").rglob("*.yaml"))
    edited = yaml.safe_load(yaml_record.read_text())
    edited["annotations"]["ex:review"] = "reviewed"
    yaml_record.write_bytes(snapshot.canonical_yaml_bytes(edited))
    joined = root / "yaml-jsonl/records.jsonl"
    assert cli.main(["dev", "records", "yaml-to-jsonl", "--directory", str(root), "--source", str(inputs)]) == 0
    report = root / "reports/downloaded-vs-yaml-jsonl"
    assert cli.main(["dev", "records", "diff", "downloaded", "yaml-jsonl", "--report", str(report), "--directory", str(root)]) == 1
    assert capture.read_bytes() == original
    assert authored.read_text() == "Authored content\n"
    assert not any(p.suffix == ".json" for p in (inputs / "metadata/records").rglob("*"))
    return report


def test_public_storage_commands_carry_exact_decision_across_two_runs(tmp_path, capsys):
    first = storage_run(tmp_path / "first")
    data, _ = stage_reports.load_report(first)
    stage = data["stages"][0]
    finding = stage["findings"][0]
    assert finding["before"] == "yes"
    assert finding["after"] == "reviewed"
    decisions = tmp_path / "first/decisions.json"
    assert cli.main(["dev", "review", "decide", "downloaded-vs-yaml-jsonl", finding["id"],
                     "--directory", str(tmp_path / "first"), "--disposition", "tolerated",
                     "--rationale", "Deliberate annotation edit retained for review",
                     "--reconsider-when", "Reviewed value changes",
                     "--author", "Codex (test)", "--write"]) == 0
    second = storage_run(tmp_path / "second")
    import shutil
    shutil.copyfile(decisions, tmp_path / "second/decisions.json")
    summary = tmp_path / "second/review"
    assert cli.main(["dev", "review", "summarize", "--directory", str(tmp_path / "second")]) == 0
    result = json.loads((summary / "review.json").read_text())
    assert result["counts"] == {"matched": 1}
    assert result["findings"][0]["finding"]["before"] == "yes"
    assert "outstanding" in (summary / "summary.md").read_text()
    third = storage_run(tmp_path / "third", annotation="changed")
    changed = stage_review.summarize([third], stage_review.load_decisions(decisions))
    assert changed["counts"] == {"changed": 1}
    capsys.readouterr()




def test_failed_record_producer_cannot_appear_clean(tmp_path, capsys):
    left, right = tmp_path / "downloaded/records.jsonl", tmp_path / "yaml-jsonl/records.jsonl"
    source(left)
    source(right)
    stage_reports.write_operation(right, operation="records yaml-to-jsonl", inputs={"source": left},
                                  context={"status": "failed"})
    assert cli.main(["dev", "records", "diff", "--directory", str(tmp_path)]) == 2
    assert "did not complete" in capsys.readouterr().err






def test_real_forward_rdf_compact_and_expanded_annotations(tmp_path):
    compact = source(tmp_path / 'downloaded/records.jsonl')
    expanded = deepcopy(compact.record)
    expanded['annotations'] = {'ex:review': {'annotation_tag': 'ex:review', 'annotation_value': 'yes'}}
    snapshot.write_jsonl(tmp_path / 'yaml-jsonl/records.jsonl', [snapshot.RecordEnvelope(compact.class_name, expanded)])
    for state in ('downloaded', 'yaml-jsonl'):
        assert cli.main(['dev', 'records', 'jsonl-to-rdf', state, '--directory', str(tmp_path)]) == 0
    report = tmp_path / 'reports/rdf'
    assert cli.main(['dev', 'rdf', 'compare', str(tmp_path / 'downloaded-rdf/graph.nt'),
                     str(tmp_path / 'yaml-jsonl-rdf/graph.nt'), '--report', str(report), '--by-record']) == 0
    for path in (report, report.with_name('rdf-records')):
        data, _ = stage_reports.load_report(path)
        assert data['stages'][0]['scope']['result'] == 'equal'
    assert cli.main(['dev', 'records', 'diff', 'downloaded', 'yaml-jsonl', '--directory', str(tmp_path)]) == 1
    assert cli.main(['dev', 'records', 'jsonl-to-rdf', '--directory', str(tmp_path)]) == 2
