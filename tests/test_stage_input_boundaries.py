"""Incomplete diagnostic inputs must fail before downstream side effects."""

from argparse import Namespace
import json

import pytest

from orinoco_lite import dev_site, projection, upstream_projection
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.stage_reports import write_operation
from orinoco_lite.upstream_snapshot import SnapshotError


def invalid_records(root, status):
    path = root / ("returned.partial.jsonl" if status == "partial" else "records.jsonl")
    path.write_text(json.dumps({"class_name": "XYZPublication", "record": {
        "pid": "ex:publication", "schema_type": "xyzri:XYZPublication", "title": "Original",
    }}) + "\n")
    if status != "partial":
        write_operation(path, operation="fixture", inputs={},
                        context={"status": "failed" if status == "failed" else "complete"})
        if status == "stale":
            path.write_text(path.read_text().replace("Original", "Edited"))
    return path


@pytest.mark.parametrize("status", ["partial", "failed"])
@pytest.mark.parametrize("consumer", ["upstream", "subprocess", "lite"])
def test_record_consumers_reject_incomplete_inputs_before_side_effects(tmp_path, monkeypatch, capsys, status, consumer):
    records = invalid_records(tmp_path, status)
    output, scratch = tmp_path / "output", tmp_path / "scratch"

    def unexpected(*args, **kwargs):
        pytest.fail("Incomplete input reached a downstream operation")

    monkeypatch.setattr(projection, "load_contract", unexpected)
    monkeypatch.setattr(dev_site, "load_workspace", unexpected)
    if consumer.startswith("cli-"):
        args = Namespace(root=tmp_path, dev_command="hugo", hugo_command="project",
                         flavor=consumer[4:], records=records, output=output)
        assert dev_site.execute(args) == 2
        capsys.readouterr()
    else:
        with pytest.raises((ConfigurationError, SnapshotError)):
            if consumer == "upstream":
                upstream_projection.project(records, tmp_path / "presentation", output)
            elif consumer == "subprocess":
                upstream_projection.run_upstream(records, tmp_path / "presentation", output, tmp_path / "tools")
            else:
                projection.render_projection(None, tmp_path / "resources", output, records_input=records)
    assert not output.exists()
    assert not scratch.exists()
