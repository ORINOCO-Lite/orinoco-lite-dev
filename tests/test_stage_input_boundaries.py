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


@pytest.mark.parametrize("status", ["partial", "failed", "stale"])
@pytest.mark.parametrize("consumer", ["upstream", "subprocess", "lite", "cli-upstream", "cli-lite"])
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


@pytest.mark.parametrize("status", ["failed", "stale"])
@pytest.mark.parametrize("consumer", ["build", "assemble-projection", "assemble-inputs", "content-diff", "site-diff", "site-check"])
def test_tree_consumers_reject_failed_or_stale_producers_without_report(tmp_path, monkeypatch, capsys, status, consumer):
    source, other, output = tmp_path / "source", tmp_path / "other", tmp_path / "output"
    source.mkdir()
    other.mkdir()
    (source / "index.html").write_text("Original")
    write_operation(source, operation="fixture", inputs={},
                    context={"status": "failed" if status == "failed" else "complete"})
    if status == "stale":
        (source / "index.html").write_text("Edited")

    def unexpected(*args, **kwargs):
        pytest.fail("Invalid producer reached a downstream operation")

    monkeypatch.setattr(dev_site, "load_workspace", lambda _: Namespace(root=tmp_path))
    monkeypatch.setattr(dev_site, "_selection", lambda _: (tmp_path / "resources", tmp_path / "presentation"))
    monkeypatch.setattr(dev_site, "_revision", lambda _: None)
    for name in ("build_hugo", "assemble_hugo", "_load_site_data", "compare_trees", "check_site"):
        monkeypatch.setattr(dev_site, name, unexpected)
    args = Namespace(root=tmp_path, output=output, resources=tmp_path / "resources", flavor="lite", report=None)
    if consumer == "build":
        args.dev_command, args.hugo_command, args.assembly = "hugo", "build", source
    elif consumer.startswith("assemble-"):
        args.dev_command, args.hugo_command = "hugo", "assemble"
        args.projection = source if consumer == "assemble-projection" else other
        args.inputs = source if consumer == "assemble-inputs" else other
    elif consumer.endswith("diff"):
        args.dev_command = consumer.split("-")[0]
        args.site_command, args.left, args.right = "diff", other, source
    else:
        args.dev_command, args.site_command, args.site = "site", "check", source
    assert dev_site.execute(args) == 2
    assert not output.exists()
    capsys.readouterr()
