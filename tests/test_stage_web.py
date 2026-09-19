"""Exercise the real loopback transport and its evidence/decision boundaries."""

from http.client import HTTPConnection
import json
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import pytest

from orinoco_lite import cli, stage_reports
from orinoco_lite.stage_bundle import ReviewModel, bundle
from orinoco_lite.stage_reports import write_report
from orinoco_lite.stage_web import review_servers


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_reports, "execution_context", lambda: {"schema_digest": "test-schema"})
    tree = tmp_path / "site"
    tree.mkdir()
    (tree / "index.html").write_text('''<!doctype html><html><head>
      <base href="https://invalid.example/"><meta http-equiv="refresh" content="0;url=https://invalid.example/">
      <link rel="stylesheet" href="/theme.css"></head><body onload="parent.changed=true">
      <script>parent.changed=true;fetch('https://invalid.example/')</script>
      <a href="https://invalid.example/">external</a><img src="/image.png">
      <h1>Evidence &amp; source</h1></body></html>''')
    (tree / "theme.css").write_text('body { background-image: url(/image.png); }')
    (tree / "image.png").write_bytes(b'\x89PNG\r\n\x1a\n')
    (tree / "vector.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
    (tree / "binary.bin").write_bytes(b'\x00\xff')
    (tree / ".git").write_text('gitdir: private-worktree-path')
    (tree / "unicode.txt").write_text('é' * 100)
    report = tmp_path / "report"
    data = write_report(report, stage="rendering", left=tree, right=tree,
                        comparator="files-v1", scope={"complete": True, "subjects": ["index.html"], "all_locations": True}, findings=[{
                            "subject": "index.html", "location": ["heading"], "change": "changed",
                            "before": None, "after": True, "before_present": False, "after_present": True,
                        }])
    destination = tmp_path / "bundle"
    bundle([report], destination)
    model = ReviewModel(destination)
    before = {p.relative_to(destination): p.read_bytes() for p in destination.rglob('*') if p.is_file()}
    with review_servers(model, port=0) as server:
        yield server, model, {"run_id": data["run_id"], "stage_index": 0, "role": "left"}
    assert before == {p.relative_to(destination): p.read_bytes() for p in destination.rglob('*') if p.is_file()}


def request(server, path, *, payload=None, headers=None):
    connection = HTTPConnection('127.0.0.1', server.server_port, timeout=10)
    body = json.dumps(payload) if payload is not None else None
    connection.request('POST' if payload is not None else 'GET', path, body=body, headers=headers or {})
    result = connection.getresponse()
    response = result.status, dict(result.getheaders()), result.read()
    connection.close()
    return response


def read_json(server, path, **kwargs):
    status, _, body = request(server, path, **kwargs)
    return status, json.loads(body)


def authorized(server):
    return {"Origin": f"http://127.0.0.1:{server.server_port}",
            "X-Review-Token": server.token, "Content-Type": "application/json"}


def test_actual_ui_and_paginated_api(web):
    server, model, artifact = web
    status, headers, body = request(server, '/')
    assert status == 200 and b'<html' in body
    for asset, kind in (("app.js", "text/javascript"), ("app.css", "text/css")):
        status, headers, asset_body = request(server, '/' + asset)
        assert status == 200 and headers['Content-Type'].startswith(kind) and asset_body
    assert "script-src 'self'" in headers['Content-Security-Policy']
    status, overview = read_json(server, '/api/review')
    assert status == 200 and overview['counts'] == {'new': 1}
    assert 'findings' not in overview and overview['csrf_token'] == server.token
    assert overview['integration'] == 'not-established'
    status, findings = read_json(server, '/api/findings?' + urlencode({
        'state': 'queue', 'run_id': artifact['run_id'], 'stage_index': 0, 'limit': 1}))
    assert status == 200 and findings['total'] == 1
    key = findings['items'][0]['key']
    assert read_json(server, '/api/finding?' + urlencode({'key': key}))[1] == model.finding(key)
    assert read_json(server, '/api/findings?offset=-1')[0] == 400
    assert read_json(server, '/api/findings?state=new&state=all')[0] == 400
    assert request(server, '/api/review', headers={'Host': 'untrusted.example'})[0] == 403
    assert request(server, '/review.json')[0] == 404


def test_decision_preview_requires_origin_token_and_rejects_stale_base(web):
    server, model, _ = web
    row = model.findings()['items'][0]
    payload = {'finding_key': row['key'], 'disposition': 'tolerated', 'author': 'Test reviewer',
               'rationale': 'Inspect the behavior again later', 'reconsider_when': 'Rendering changes'}
    assert request(server, '/api/decision', payload=payload)[0] == 403
    wrong = {**authorized(server), 'Origin': 'https://untrusted.example'}
    assert request(server, '/api/decision', payload=payload, headers=wrong)[0] == 403
    status, result = read_json(server, '/api/decision', payload=payload, headers=authorized(server))
    assert status == 200
    decision = result['decision']
    assert json.loads(result['decision_json']) == decision
    assert decision['expected']['before_present'] is False and decision['expected']['after'] is True
    changes = {'schema_version': 1, 'base_digest': model.base_digest,
               'edits': [{'id': decision['id'], 'action': 'add', 'decision': decision}]}
    status, preview = read_json(server, '/api/preview', payload=changes, headers=authorized(server))
    assert status == 200 and preview['counts'] == {'matched': 1} and preview['changes'] == changes
    assert json.loads(preview['changes_json']) == changes
    assert model.overview()['counts'] == {'new': 1}
    changes['base_digest'] = 'stale'
    status, error = read_json(server, '/api/preview', payload=changes, headers=authorized(server))
    assert status == 400 and 'stale' in error['error']
    assert request(server.preview, '/api/decision', payload=payload, headers=authorized(server))[0] == 403


def test_original_download_and_separate_sandboxed_preview(web):
    server, _, artifact = web
    status, listing = read_json(server, '/api/artifact?' + urlencode(artifact))
    assert status == 200 and listing['kind'] == 'directory'
    assert '.git' not in [entry['name'] for entry in listing['entries']]
    query = urlencode({**artifact, 'path': 'index.html'})
    status, item = read_json(server, '/api/artifact?' + query)
    assert status == 200 and item['kind'] == 'text' and 'onload=' in item['text']
    status, headers, original = request(server, item['download_url'])
    assert status == 200 and original.decode() == item['text']
    assert headers['Content-Type'] == 'application/octet-stream'
    assert headers['Content-Disposition'].startswith('attachment;')
    preview = urlsplit(item['preview_url'])
    assert preview.port != server.server_port and preview.hostname == '127.0.0.1'
    status, headers, rendered = request(server.preview, preview.path)
    assert status == 200 and b'<h1>Evidence &amp; source</h1>' in rendered
    assert "sandbox;" in headers['Content-Security-Policy'] and "script-src 'none'" in headers['Content-Security-Policy']
    assert b'<base' not in rendered and b'http-equiv="refresh"' not in rendered and b'onload=' not in rendered
    assert b'href="https://invalid.example/' not in rendered
    prefix = preview.path.rsplit('/', 1)[0]
    assert f'href="{prefix}/theme.css"'.encode() in rendered
    status, _, css = request(server.preview, prefix + '/theme.css')
    assert status == 200 and f'url({prefix}/image.png)'.encode() in css
    assert read_json(server, '/image?' + query)[0] == 400
    assert read_json(server, '/image?' + urlencode({**artifact, 'path': 'vector.svg'}))[0] == 400
    assert read_json(server, '/api/artifact?' + urlencode({**artifact, 'path': 'binary.bin'}))[1]['kind'] == 'binary'
    assert read_json(server.preview, '/api/review')[0] == 400


def test_mounted_preview_rejects_changed_evidence(web):
    server, model, artifact = web
    query = urlencode({**artifact, 'path': 'index.html'})
    _, item = read_json(server, '/api/artifact?' + query)
    target = model.artifact_root(artifact['run_id'], 0, 'left') / 'index.html'
    original = target.read_bytes()
    try:
        target.write_text('<p>Changed since review opened</p>')
        status, error = read_json(server.preview, urlsplit(item['preview_url']).path)
        assert status == 400 and 'changed' in error['error']
    finally:
        target.write_bytes(original)


@pytest.mark.parametrize('path', ['../review.json', '/etc/passwd', '.git/config', '..\\review.json', 'missing'])
def test_artifact_paths_cannot_escape_declared_evidence(web, path):
    server, _, artifact = web
    assert read_json(server, '/api/artifact?' + urlencode({**artifact, 'path': path}))[0] == 400


def test_text_limit_preserves_multibyte_text(web, monkeypatch):
    server, _, artifact = web
    monkeypatch.setattr('orinoco_lite.stage_web.TEXT_LIMIT', 11)
    status, item = read_json(server, '/api/artifact?' + urlencode({**artifact, 'path': 'unicode.txt'}))
    assert status == 200 and item['kind'] == 'text' and item['truncated'] and item['text'] == 'é' * 5


def test_cli_bundle_and_serve_respect_root(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(stage_reports, 'execution_context', lambda: {})
    (tmp_path / 'data.json').write_text('{}')
    write_report(tmp_path / 'report', stage='storage', left=tmp_path / 'data.json',
                 right=tmp_path / 'data.json', comparator='records-v1', findings=[])
    assert cli.main(['--root', str(tmp_path), 'dev', 'review', 'bundle', 'report',
                     '--output', 'bundle', '--title', 'CLI portability']) == 0
    assert ReviewModel(tmp_path / 'bundle').title == 'CLI portability'
    seen = []
    monkeypatch.setattr('orinoco_lite.stage_web.serve', lambda *args, **kwargs: seen.append((args, kwargs)))
    assert cli.main(['--root', str(tmp_path), 'dev', 'review', 'serve', 'bundle', '--port', '0']) == 0
    assert seen == [((tmp_path / 'bundle',), {'port': 0, 'open_browser': False})]
    capsys.readouterr()
