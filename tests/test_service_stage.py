import json

import pytest

from orinoco_lite.errors import ConfigurationError
from orinoco_lite.service_stage import roundtrip, selected_schema
from orinoco_lite.stage_reports import artifact_digest, execution_context, operation_receipt, read_json
from orinoco_lite.upstream_snapshot import load_jsonl, compare_snapshots


def test_retained_roundtrip_has_receipt_and_removes_transient_token(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"class_name": "XYZPublication", "record": {
        "pid": "https://example.org/stage-publication", "schema_type": "xyzri:XYZPublication",
        "title": "A retained publication", "about": ["https://example.org/b", "https://example.org/b"],
    }}) + "\n")
    output, scratch = tmp_path / "returned.jsonl", tmp_path / "service"
    result = roundtrip(source, output, scratch=scratch)
    assert result["status"] == "complete"
    compare_snapshots(load_jsonl(source), load_jsonl(output))
    receipt = operation_receipt(output)
    assert receipt["operation"] == "records.roundtrip"
    assert receipt["context"]["schema_digest"] == execution_context()["schema_digest"]
    assert receipt["context"]["schema_sha256"] == artifact_digest(selected_schema())
    assert read_json(scratch / "roundtrip.json")["status"] == "complete"
    assert not (scratch / "dumpthings.yaml").exists()


def test_existing_output_is_preserved(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text("retained source")
    output = tmp_path / "returned.jsonl"
    output.write_text("existing result")
    with pytest.raises(ConfigurationError, match="new and distinct"):
        roundtrip(source, output)
    assert output.read_text() == "existing result"


@pytest.mark.parametrize("status", ["partial", "failed", "stale"])
def test_incomplete_input_never_starts_service_or_creates_output(tmp_path, monkeypatch, status):
    from orinoco_lite import service_stage
    from orinoco_lite.stage_reports import write_operation
    from orinoco_lite.upstream_snapshot import SnapshotError

    source = tmp_path / ("returned.partial.jsonl" if status == "partial" else "records.jsonl")
    source.write_text(json.dumps({"class_name": "XYZPublication", "record": {
        "pid": "ex:publication", "schema_type": "xyzri:XYZPublication", "title": "Original",
    }}) + "\n")
    if status != "partial":
        write_operation(source, operation="fixture", inputs={},
                        context={"status": "failed" if status == "failed" else "complete"})
        if status == "stale":
            source.write_text(source.read_text().replace("Original", "Edited"))

    def unexpected(*args, **kwargs):
        pytest.fail("Incomplete input started a service")

    monkeypatch.setattr(service_stage, "local_service", unexpected)
    output, scratch = tmp_path / "output", tmp_path / "scratch"
    with pytest.raises((ConfigurationError, SnapshotError)):
        roundtrip(source, output, scratch=scratch, schema=tmp_path / "schema")
    assert not output.exists()
    assert not scratch.exists()
