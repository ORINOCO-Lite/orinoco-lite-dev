"""Exercise selected upstream command implementations, including lookup failures."""
from pathlib import Path
import json

import pytest
import yaml

from orinoco_lite.errors import DriverError
from orinoco_lite.upstream_projection import run_upstream

TOOLS = Path(__file__).resolve().parents[1] / "submodules"
pytestmark = pytest.mark.skipif(
    not (TOOLS / "query-things/query_things").is_dir(),
    reason="selected query-things checkout is unavailable",
)


def fixture(tmp_path, *, homepage=True):
    source = tmp_path / "presentation"
    (source / ".forgejo/workflows").mkdir(parents=True)
    steps = [
        {"name": "Update navigation graph", "run": "dtc get-records ${DUMPTHINGS_APIURL} public | query-things cache | python3 code/pool2graph.py > static/graph.json_new \\\n&& mv static/graph.json_new static/graph.json \\\n&& git annex add static\n"},
        {"name": "Update persons", "run": "query-things list --class xyzri:XYZPerson | query-things filter-linked-pid public xyzrins:. associated_with | query-things render-record page_templates/person.md.j2 'content/{__pid_curie_reference}/_index.md'"},
        {"name": "Update frontpage", "run": "query-things list --pid xyzrins:. | query-things inject-links-pid --link part_of parts | query-things render-record page_templates/homepage.md.j2 'content/{__pid_curie_reference}/_index.md'"},
    ]
    (source / ".forgejo/workflows/update-from-pool.yaml").write_text(yaml.safe_dump({"jobs": {"create_pages": {"steps": steps}}}))
    (source / "page_templates").mkdir()
    (source / "page_templates/person.md.j2").write_text("{{ annotations['rdfs:label'] }}")
    (source / "page_templates/homepage.md.j2").write_text('{% for item in parts %}{{ item.pid }}{% endfor %}')
    (source / "code").mkdir()
    (source / "code/pool2graph.py").write_text('import sys; sys.stdin.read(); print(\'{"nodes": [], "edges": []}\')')
    records = [
        {"pid": "xyzrins:persons/local", "schema_type": "xyzri:XYZPerson", "annotations": {"rdfs:label": {"annotation_tag": "rdfs:label", "annotation_value": "Local"}}},
        {"pid": "xyzrins:persons/other", "schema_type": "xyzri:XYZPerson", "annotations": {"rdfs:label": "Other"}},
        {"pid": "xyzrins:projects/child", "schema_type": "xyzri:XYZProject", "part_of": ["xyzrins:."]},
    ]
    if homepage:
        records.append({"pid": "xyzrins:.", "schema_type": "xyzri:XYZProject", "associated_with": [{"object": "xyzrins:persons/local"}]})
    capture = tmp_path / "records.jsonl"
    capture.write_text("".join(json.dumps({"class_name": record["schema_type"].split(":")[-1], "record": record}) + "\n" for record in records))
    return source, capture


def test_selected_commands_filter_members_inject_reverse_links_and_render_annotations(tmp_path):
    source, capture = fixture(tmp_path)
    output = tmp_path / "projection"
    report = run_upstream(capture, source, output)
    assert report["pages"] == 2
    assert (output / "content/persons/local/_index.md").read_text() == "Local"
    assert not (output / "content/persons/other/_index.md").exists()
    assert (output / "content/_index.md").read_text() == "xyzrins:projects/child"
    assert report["operations"] == ["Update navigation graph", "Update persons", "Update frontpage"]


def test_missing_required_lookup_cannot_report_success(tmp_path):
    source, capture = fixture(tmp_path, homepage=False)
    with pytest.raises(DriverError, match="Update persons.*status 1"):
        run_upstream(capture, source, tmp_path / "projection")
