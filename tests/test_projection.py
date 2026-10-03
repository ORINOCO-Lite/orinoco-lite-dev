from pathlib import Path
import json
import os
import shutil
from unittest.mock import Mock, patch
import pytest
import yaml

from orinoco_lite import projection
from orinoco_lite.canonical import canonical_yaml
from orinoco_lite.config import load_workspace
from orinoco_lite.editor import _render_rdf_sources
from orinoco_lite.errors import ConfigurationError, DriverError
from orinoco_lite.projection import update_projection, validate_inputs, _route_for_pid
from orinoco_lite.records import record_sources
from orinoco_lite.resources import resolve_resources
from orinoco_lite.schema_conversion import build_format_converters

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def selected_tools(monkeypatch):
    monkeypatch.setattr("orinoco_lite.upstream_projection.resolve_tools",
                        lambda *a, **kw: PACKAGE_ROOT / "submodules")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "site"
    shutil.copytree(PACKAGE_ROOT / "tests/fixtures/template-candidate", root)
    monkeypatch.setattr(projection, "resolve_www_from_model",
                        lambda *_: PACKAGE_ROOT / "submodules/www-from-model")
    return load_workspace(root)


def test_override_fails_before_projection_or_cache(workspace):
    override = workspace.path("site") / "projection.yaml"
    override.write_text("version: 2\n")
    with pytest.raises(ConfigurationError, match="Remove this file"):
        update_projection(workspace, resolve_resources().root)
    assert not (workspace.path("generated") / "projection").exists()


@pytest.mark.parametrize("suffix", ["../escape", "%2e%2e/escape", "a//b", "a?b", "a#b", "%252e%252e/escape", "a\\b"])
def test_routes_cannot_escape_output(suffix):
    with pytest.raises(DriverError, match="unsafe route"):
        _route_for_pid("xyzrins:" + suffix, "xyzrins:")


def test_cache_validation_and_transactional_install(workspace, monkeypatch):
    resources = resolve_resources().root
    calls = []
    def render(w, r, destination, **kwargs):
        calls.append(destination)
        destination.mkdir(exist_ok=True)
        (destination / "records.jsonl").write_text("original\n")
        return {"records": 1, "pages": 1}
    monkeypatch.setattr(projection, "render_projection", render)
    first = update_projection(workspace, resources)
    editorial = workspace.path("editorial") / "about.md"
    editorial.write_text("New editorial content")
    assert update_projection(workspace, resources) == first
    assert len(calls) == 1
    sidecar = workspace.path("generated") / "projection/.gitattributes"
    sidecar.write_text("* -annex.largefiles\n")
    update_projection(workspace, resources)
    assert sidecar.read_text() == "* -annex.largefiles\n"
    assert len(calls) == 2
    with patch.object(projection, "validate_semantics", return_value={"records": 1}) as validation:
        validate_inputs(workspace, resources)
        validation.assert_not_called()
        validate_inputs(workspace, resources, no_cache=True)
        validation.assert_called_once()
    original_replace = os.replace
    count = 0
    def fail_twice(source, destination):
        nonlocal count
        count += 1
        if count in (2, 3):
            raise OSError("injected failure")
        return original_replace(source, destination)
    monkeypatch.setattr(projection.os, "replace", fail_twice)
    with pytest.raises(DriverError, match="original is preserved"):
        update_projection(workspace, resources, no_cache=True)
    backups = list(workspace.path("generated").glob(".projection-backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "records.jsonl").read_text() == "original\n"


def test_ancillary_record_survives_projection_and_editor_rdf(tmp_path, monkeypatch):
    root = tmp_path / "site"
    shutil.copytree(PACKAGE_ROOT / "tests/fixtures/template-candidate", root)
    www_from_model = PACKAGE_ROOT / "submodules/www-from-model"
    # Use real pinned templates and schema without resolving a network source.
    monkeypatch.setattr(
        "orinoco_lite.projection.resolve_www_from_model", lambda *_: www_from_model
    )
    workspace = load_workspace(root)
    resources = resolve_resources().root
    record = {
        "pid": "xyzrins:files/ancillary",
        "schema_type": "xyzri:XYZFile",
        "display_label": "Ancillary file",
    }
    path = workspace.path("records") / "XYZFile/ancillary.yaml"
    path.parent.mkdir()
    content = canonical_yaml(record)
    path.write_text(content, encoding="utf-8")

    update_projection(workspace, resources)
    projection = workspace.path("generated") / "projection"
    machine = [json.loads(line) for line in (projection / "records.jsonl").read_text().splitlines()]
    assert record in machine
    assert not (projection / "content/files/ancillary/_index.md").exists()
    to_rdf, to_json = build_format_converters(
        resources / "schema/demo-research-information/unreleased.yaml"
    )
    rdf, _ = _render_rdf_sources(record_sources(workspace), to_rdf)
    restored = to_json.convert(rdf[record["pid"]], "XYZFile")
    assert restored["display_label"] == record["display_label"]
    assert path.read_text(encoding="utf-8") == content

    record["schema_type"] = "xyzri:Unknown"
    path.write_text(canonical_yaml(record), encoding="utf-8")
    with pytest.raises(DriverError, match="unknown CURIE schema type xyzri:Unknown"):
        update_projection(workspace, resources)


def test_upstream_date_readback_does_not_block_projection_or_edit_stored_input(tmp_path, monkeypatch):
    root = tmp_path / "site"
    shutil.copytree(PACKAGE_ROOT / "tests/fixtures/template-candidate", root)
    monkeypatch.setattr("orinoco_lite.projection.resolve_www_from_model",
                        lambda *_: PACKAGE_ROOT / "submodules/www-from-model")
    workspace = load_workspace(root)
    resources = resolve_resources().root
    path = workspace.path("records") / "XYZPublication/example-publication.yaml"
    record = yaml.safe_load(path.read_text())
    record["generated_by"] = [{"schema_type": "dlthings:Generation", "at_time": "-",
                               "object": "xyzrins:projects/example-project"}]
    path.write_text(canonical_yaml(record))
    original = path.read_bytes()
    update_projection(workspace, resources)
    projection = workspace.path("generated") / "projection"
    projected = [json.loads(line) for line in (projection / "records.jsonl").read_text().splitlines()]
    assert record in projected
    assert path.read_bytes() == original

    # The editor and diagnostic readback use the selected upstream reader. Its
    # omission remains observable; build success is not a preservation claim.
    from dump_things_service.converter import FormatConverter
    writer, reader = build_format_converters(resources / "schema/demo-research-information/unreleased.yaml")
    assert type(reader) is FormatConverter
    rdf, _ = _render_rdf_sources(record_sources(workspace), writer)
    assert '"-"^^<https://concepts.datalad.org/s/things/v2/w3ctr-datetime>' in rdf[record["pid"]]
    restored = reader.convert(rdf[record["pid"]], "XYZPublication")
    assert "at_time" not in restored["generated_by"][0]
    assert path.read_bytes() == original
