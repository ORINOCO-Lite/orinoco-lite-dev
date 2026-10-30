from pathlib import Path
from unittest.mock import patch

from orinoco_lite.upstream_runtime import copy_hugo_runtime, stage_upstream_runtime


def test_packaged_subset_matches_editable_assembly_and_excludes_website(tmp_path):
    source = tmp_path / 'source'
    files = {
        'themes/congo/theme.toml': 'name = "Congo"',
        'themes/congo/LICENSE': 'theme license',
        'themes/congo/layouts/baseof.html': 'theme code',
        'themes/congo/exampleSite/content/demo.md': 'exclude demo',
        'page_templates/page.md.j2': '{{ record }}',
        'code/pool2graph.py': 'print("graph")',
        'static/graph.js': 'graph code',
        'static/graph.json': 'upstream pool data',
        'static/favicon.ico': 'upstream identity',
        'assets/img/logo.png': 'upstream logo',
        'assets/img/meerkat_person.png': 'rendering fallback',
        'assets/img/unrelated.png': 'unrelated media',
        'layouts/term.html': 'rendering code',
        'content/persons/_index.md': '---\ntitle: Persons\n---\nUpstream editorial body',
        'content/persons/somebody/_index.md': 'upstream record',
        'NOTICE': 'upstream notice',
        '.forgejo/workflows/update-from-pool.yaml': 'selected projection workflow',
        '.git/config': 'private git state',
    }
    for name, content in files.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    payload = tmp_path / 'payload'
    with patch('orinoco_lite.annex_media.prepare_hugo_assets', return_value={}):
        stage_upstream_runtime(source, payload)
    assert (payload / 'NOTICE').read_text() == 'upstream notice'
    assert (payload / '.forgejo/workflows/update-from-pool.yaml').read_text() == 'selected projection workflow'
    assert (payload / 'themes/congo/LICENSE').is_file()
    for excluded in ('static/graph.json', 'static/favicon.ico', 'assets/img/logo.png',
                     'assets/img/unrelated.png', 'content/persons/somebody/_index.md',
                     'themes/congo/exampleSite', '.git'):
        assert not (payload / excluded).exists()
    assert 'editorial' not in (payload / 'content/persons/_index.md').read_text()
    editable, fixed = tmp_path / 'editable', tmp_path / 'fixed'
    copy_hugo_runtime(source, editable)
    copy_hugo_runtime(payload, fixed)
    def contents(root):
        return {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert contents(editable) == contents(fixed)
    (source / 'layouts/term.html').write_text('working edit')
    copy_hugo_runtime(source, editable)
    assert (editable / 'layouts/term.html').read_text() == 'working edit'
    assert (fixed / 'layouts/term.html').read_text() == 'rendering code'
