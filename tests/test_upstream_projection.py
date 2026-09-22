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
        {"run": "query-things list --class xyzri:XYZPerson | query-things filter-linked-pid public xyzrins:. associated_with | query-things render-record page_templates/person.md.j2 'content/{__pid_curie_reference}/_index.md'"},
        {"run": "query-things list --pid xyzrins:. | query-things inject-links-pid --link part_of parts | query-things render-record page_templates/homepage.md.j2 'content/{__pid_curie_reference}/_index.md'"},
    ]
    (source / ".forgejo/workflows/update-from-pool.yaml").write_text(yaml.safe_dump({"jobs": {"create_pages": {"steps": steps}}}))
    (source / "page_templates").mkdir()
    (source / "page_templates/person.md.j2").write_text("{{ annotations['rdfs:label'] }}")
    (source / "page_templates/homepage.md.j2").write_text('{% for item in parts %}{{ item.pid }}{% endfor %}')
    (source / "code").mkdir()
    (source / "code/pool2graph.py").write_text('print(\'{"nodes": [], "edges": []}\')')
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
    report = run_upstream(capture, source, output, TOOLS)
    assert report["pages"] == 2
    assert (output / "content/persons/local/_index.md").read_text() == "Local"
    assert not (output / "content/persons/other/_index.md").exists()
    assert (output / "content/_index.md").read_text() == "xyzrins:projects/child"
    assert any(command[:2] == ["query-things", "render-record"] for command in report["operations"])


def test_missing_required_lookup_cannot_report_success(tmp_path):
    source, capture = fixture(tmp_path, homepage=False)
    with pytest.raises(DriverError, match="filter-linked-pid.*failed"):
        run_upstream(capture, source, tmp_path / "projection", TOOLS)


def test_tools_follow_owning_gitlinks_through_downstream_development_link(tmp_path):
    import subprocess
    from orinoco_lite.upstream_projection import resolve_tools

    def git(root, *arguments):
        return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()

    def repository(path):
        path.mkdir(parents=True)
        git(path, "init", "-q")
        git(path, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "--allow-empty", "--no-verify", "-m", "fixture")
        return git(path, "rev-parse", "HEAD")

    engineering = tmp_path / "selected"
    repository(engineering)
    presentation = engineering / "submodules/www-from-model"
    selected = {"www-from-model": repository(presentation)}
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    for name in ("query-things", "dump-things-pyclient"):
        selected[name] = repository(prepared / "submodules" / name)
    for name, commit in selected.items():
        git(engineering, "update-index", "--add", "--cacheinfo", "160000", commit, f"submodules/{name}")
    git(engineering, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--quiet", "--no-verify", "-m", "select fixtures")
    downstream = tmp_path / "downstream"
    (downstream / ".orinoco-lite").mkdir(parents=True)
    (downstream / ".orinoco-lite/dev").symlink_to(prepared)
    assert resolve_tools(downstream, presentation) == prepared / "submodules"
    query = prepared / "submodules/query-things"
    git(query, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--quiet", "--allow-empty", "--no-verify", "-m", "unselected change")
    with pytest.raises(DriverError, match="expected Gitlink"):
        resolve_tools(downstream, presentation)
