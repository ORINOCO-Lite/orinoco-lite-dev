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


def test_nonmember_http_pid_is_retained_without_becoming_a_page(tmp_path):
    source, capture = fixture(tmp_path)
    pid = 'https://example.org/people/other'
    capture.write_text(capture.read_text().replace('xyzrins:persons/other', pid))
    output = tmp_path / 'projection'

    report = run_upstream(capture, source, output)

    assert report['pages'] == 2
    assert {path.relative_to(output / 'content').as_posix()
            for path in (output / 'content').rglob('*.md')} == {
        '_index.md', 'persons/local/_index.md',
    }
    assert pid in {json.loads(line)['pid']
                   for line in (output / 'records.jsonl').read_text().splitlines()}


def test_parent_traversal_cannot_escape_upstream_content(tmp_path):
    source, capture = fixture(tmp_path)
    capture.write_text(capture.read_text().replace(
        'xyzrins:persons/local', 'xyzrins:../outside'))

    with pytest.raises(DriverError, match='PID escapes upstream content directory'):
        run_upstream(capture, source, tmp_path / 'projection')


def test_native_jinja_inheritance_preserves_selected_project_template(tmp_path):
    from query_things.render_record import make_jinja_env, render_records
    from orinoco_lite.upstream_projection import stage_templates
    source = TOOLS / 'www-from-model'
    site = tmp_path / 'site-specific'
    templates = site / 'projection-templates'
    templates.mkdir(parents=True)
    (templates / 'local-project.md.j2').write_text(
        '{% extends "project.md.j2" %}\n'
        '{% block frontmatter_params %}{{ super() }}\n  conContribution: true\n{% endblock %}\n'
        '{% block content %}{{ super() }}\nLocal editorial addition.\n{% endblock %}'
    )
    staged = tmp_path / 'page_templates'
    stage_templates(source, staged, site)
    record = {'pid': 'xyzrins:projects/bids', 'title': 'BIDS', 'description': 'Upstream content',
              'associated_with': [], 'influenced_by': [], 'part_of': [], 'parts': [], 'generated': []}
    output = tmp_path / 'project.md'
    environment = make_jinja_env(staged)
    render_records([json.dumps(record)], environment.get_template('local-project.md.j2'),
                   output_filename_template=[str(output)])
    rendered = output.read_text()
    frontmatter = yaml.safe_load(rendered.split('---', 2)[1])
    assert frontmatter['params']['graphRootNodePID'] == record['pid']
    assert frontmatter['params']['conContribution'] is True
    assert 'Upstream content' in rendered
    assert 'Local editorial addition.' in rendered
    assert (staged / 'project.md.j2').read_bytes() == (source / 'page_templates/project.md.j2').read_bytes()


def test_local_templates_cannot_shadow_upstream_or_follow_symlinks(tmp_path):
    from orinoco_lite.upstream_projection import stage_templates
    source = TOOLS / 'www-from-model'
    site = tmp_path / 'site'
    templates = site / 'projection-templates'
    templates.mkdir(parents=True)
    local = templates / 'project.md.j2'
    local.write_text('accidental copy')
    with pytest.raises(DriverError, match='replace an upstream template'):
        stage_templates(source, tmp_path / 'shadow', site)
    local.unlink()
    local.symlink_to(source / 'page_templates/project.md.j2')
    with pytest.raises(DriverError, match='symlinks'):
        stage_templates(source, tmp_path / 'symlink', site)


def test_homepage_selection_uses_the_adjusted_workflow(tmp_path):
    from orinoco_lite.upstream_projection import homepage_pid
    source, _ = fixture(tmp_path)
    site = tmp_path / 'site'
    site.mkdir()
    (site / 'projection.yaml').write_text(yaml.safe_dump({
        'version': 3, 'extends': 'upstream', 'adjustments': [{
            'step': 'Update frontpage', 'old': 'xyzrins:.', 'new': 'xyzrins:new-home',
            'reason': 'Select this organization',
        }],
    }))
    assert homepage_pid(source, site) == 'xyzrins:new-home'
    assert homepage_pid(source) == 'xyzrins:.'
