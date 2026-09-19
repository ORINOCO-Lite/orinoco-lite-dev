import json

import pytest

from orinoco_lite.errors import ConfigurationError
from orinoco_lite.service_stage import roundtrip
from orinoco_lite.stage_reports import operation_receipt, read_json
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
    assert operation_receipt(output)["operation"] == "records.roundtrip"
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
