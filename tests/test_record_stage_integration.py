"""Exercise record stages through the public CLI and shared review contract."""

from copy import deepcopy
import json

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
    capture = root / "site-specific/sources/pool/records.jsonl"
    source(capture, annotation=annotation)
    original = capture.read_bytes()
    inputs = root / "site-specific"
    authored = inputs / "content/about.md"
    authored.parent.mkdir(parents=True)
    authored.write_text("Authored content\n")
    assert cli.main(["dev", "records", "convert", str(capture), str(inputs), "--no-record"]) == 0
    joined = root / "joined.jsonl"
    assert cli.main(["dev", "records", "export", str(inputs), str(joined)]) == 0
    report = root / "report"
    assert cli.main(["dev", "records", "diff", str(capture), str(joined), "--report", str(report)]) == 1
    assert capture.read_bytes() == original
    assert authored.read_text() == "Authored content\n"
    assert not any(p.suffix == ".json" for p in (inputs / "metadata/records").rglob("*"))
    return report


def test_public_storage_commands_carry_exact_decision_across_two_runs(tmp_path, capsys):
    first = storage_run(tmp_path / "first")
    data, _ = stage_reports.load_report(first)
    stage = data["stages"][0]
    finding = stage["findings"][0]
    assert finding["representation_equivalence"] == "annotation-representation-v1"
    decisions = tmp_path / "decisions.json"
    assert cli.main(["dev", "review", "decide", str(first), finding["id"],
                     "--decisions", str(decisions), "--disposition", "tolerated",
                     "--rationale", "Known annotation encoding retained for review",
                     "--reconsider-when", "Stored annotation encoding changes",
                     "--author", "Codex (test)", "--write"]) == 0
    second = storage_run(tmp_path / "second")
    summary = tmp_path / "summary"
    assert cli.main(["dev", "review", "summarize", str(second), "--decisions", str(decisions),
                     "--output", str(summary)]) == 0
    result = json.loads((summary / "review.json").read_text())
    assert result["counts"] == {"matched": 1}
    assert result["findings"][0]["finding"]["before"] == "yes"
    assert "outstanding" in (summary / "summary.md").read_text()
    third = storage_run(tmp_path / "third", annotation="changed")
    changed = stage_review.summarize([third], stage_review.load_decisions(decisions))
    assert changed["counts"] == {"changed": 1}
    capsys.readouterr()


def test_rdf_report_keeps_intermediate_evidence_and_complete_schema_context(tmp_path, monkeypatch, capsys):
    capture = tmp_path / "records.jsonl"
    original = source(capture)
    schema = {"schema_digest": "first-complete-schema-closure"}
    monkeypatch.setattr(stage_reports, "execution_context", lambda: deepcopy(schema))

    def conversion(_source, output, **_kwargs):
        output.mkdir()
        restored = snapshot.RecordEnvelope(original.class_name, {
            **original.record, "title": "Returned title",
        })
        snapshot.write_jsonl(output / "returned.jsonl", [restored])
        (output / "intermediate.rdf").write_text('<urn:record> { <urn:s> <urn:p> "value" . }\n')
        result = {"status": "complete", "schema_sha256": "same-top-level-schema-file",
                  "rdf_format": "trig", "records": [{"subject": original.pid}], "diagnostics": []}
        stage_reports.write_json(output / "conversion.json", result)
        return result

    monkeypatch.setattr(record_stages, "rdf_roundtrip", conversion)

    def run(name):
        output, report = tmp_path / name, tmp_path / (name + "-report")
        assert cli.main(["dev", "records", "rdf-roundtrip", str(capture), str(output)]) == 0
        assert cli.main(["dev", "records", "diff", str(capture), str(output / "returned.jsonl"),
                         "--stage", "rdf", "--report", str(report)]) == 1
        data, _ = stage_reports.load_report(report)
        return report, data

    first, data = run("first")
    stage = data["stages"][0]
    assert {"right-intermediate.rdf", "right-conversion.json"} <= stage["artifacts"].keys()
    assert stage["artifacts"]["right"]["operation"]["context"]["schema_digest"] == schema["schema_digest"]
    decision = stage_review.decision_for(stage, stage["findings"][0], disposition="undecided",
                                        rationale="Investigate returned title", reconsider_when="Schema changes",
                                        author="Codex (test)", report=data)
    decisions = {"schema_version": 1, "decisions": [decision]}
    assert stage_review.summarize([first], decisions)["counts"] == {"matched": 1}
    schema["schema_digest"] = "changed-imported-schema-closure"
    second, _ = run("second")
    assert stage_review.summarize([second], decisions)["counts"] == {"changed": 1}
    capsys.readouterr()


def test_failed_or_stale_record_producer_cannot_appear_clean_without_report(tmp_path, capsys):
    left, right = tmp_path / "source.jsonl", tmp_path / "returned.partial.jsonl"
    source(left)
    source(right)
    stage_reports.write_operation(right, operation="records rdf-roundtrip", inputs={"source": left},
                                  context={"status": "failed"})
    assert cli.main(["dev", "records", "diff", str(left), str(right)]) == 2
    assert "did not complete" in capsys.readouterr().err
    stage_reports.write_operation(right, operation="records rdf-roundtrip", inputs={"source": left})
    source(right, annotation="Edited after conversion")
    assert cli.main(["dev", "records", "diff", str(left), str(right)]) == 2
    assert "changed since its operation" in capsys.readouterr().err
