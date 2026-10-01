"""Observable CLI/Web differences and bounded replay evidence."""
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from orinoco_lite.errors import ConfigurationError
from orinoco_lite.site_compare import compare_trees, finding
from orinoco_lite.stage_reports import write_report, write_json, load_report
from orinoco_lite.stage_review import summarize, load_decisions
from orinoco_lite.stage_bundle import bundle, ReviewModel
from orinoco_lite.stage_presentation import diff_text, render_rows
from orinoco_lite.stage_investigation import replay, effects, execute


@pytest.fixture(autouse=True)
def context(monkeypatch):
    monkeypatch.setattr('orinoco_lite.stage_reports.execution_context', lambda: {'package_commit': 'test'})


def projection(tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    for path, creator in [(left, '{name: Library}'), (right, 'https://example.org/library')]:
        (path / 'content').mkdir(parents=True)
        (path / 'content/person.md').write_text(f'---\ncreator: {creator}\n---\nSame body\n')
    changes, names = compare_trees(left, right)
    out = tmp_path / 'projection'
    data = write_report(out, stage='projection', left=left, right=right, findings=changes,
                        comparator='hugo-content/1', scope={'complete': True, 'subjects': names})
    selected = next(f for f in data['stages'][0]['findings'] if f['location'][0] != 'bytes')
    return out, data, selected, right


def test_group_unified_diff_problems_and_exact_values(tmp_path):
    path, data, selected, _ = projection(tmp_path)
    check = tmp_path / 'check'
    write_report(check, stage='site-check', left=path, right=path,
                 findings=[finding('page.html', ['links', '/missing'], '/missing', {'error': 'missing'})], comparator='local-html-targets/2')
    output = tmp_path / 'bundle'
    bundle([path, check], output)
    model = ReviewModel(output)
    diffs = model.findings(category='differences', raw=False)
    assert diffs['total'] == 1
    row = diffs['items'][0]
    assert row['finding']['id'] == selected['id']
    assert '-  "name": "Library"' in row['unified_diff']
    assert '+"https://example.org/library"' in row['unified_diff']
    assert len(row['supporting_observations']) == 2
    assert model.findings(category='problems', raw=False)['total'] == 1
    assert model.findings(raw=True)['total'] == 4
    assert model.overview()['observation_count'] == 3
    assert model.overview()['presentation_counts'] == {'differences': 1, 'problems': 1}


def test_diff_preserves_numeric_types_missing_and_multiline_text(tmp_path):
    path, data, selected, _ = projection(tmp_path)
    stage = data['stages'][0]
    value = finding('record', ['numbers'], [1, 1.0, 9007199254740993], [1.0, 1, 9007199254740992])
    text = diff_text(value, stage, path)
    assert '-  9007199254740993' in text
    assert '+  9007199254740992' in text
    text = diff_text(finding('record', ['optional'], after=None), stage, path)
    assert '+null' in text
    assert '-null' not in text


@pytest.mark.parametrize('visible', [False, True])
def test_replay_demonstrates_effect_or_absence_and_rejects_changed_context(tmp_path, monkeypatch, visible):
    path, data, selected, assembly = projection(tmp_path)
    monkeypatch.setattr('orinoco_lite.config.load_workspace', lambda root: SimpleNamespace(root=root))
    monkeypatch.setattr('orinoco_lite.resources.resolve_resources', lambda: SimpleNamespace(root=tmp_path))
    def build(workspace, resources, source, destination, base_url, **kwargs):
        destination.mkdir()
        (destination / 'index.html').write_text((source / 'content/person.md').read_text() if visible else 'same website')
    monkeypatch.setattr('orinoco_lite.site.build_hugo', build)
    output = tmp_path / 'replay'
    replay(path, selected['id'], assembly, output, base_url='/demo/', flavor='lite', workspace_root=tmp_path)
    observations = effects([load_report(path), load_report(output)])
    key = f"{data['run_id']}/{selected['id']}"
    assert observations[key][0]['status'] == ('verified' if visible else 'no-effect')
    result = summarize([path, output], load_decisions(None))
    assert next(r for r in result['findings'] if r['key'] == key)['effects']
    changed, _ = load_report(output)
    changed['stages'][0]['artifacts']['right']['operation']['context']['flavor'] = 'upstream'
    write_json(output / 'report.json', changed)
    assert effects([load_report(path), load_report(output)]) == {}


def test_replay_rejects_unrelated_change_in_file(tmp_path, monkeypatch):
    path, data, selected, assembly = projection(tmp_path)
    stage = data['stages'][0]
    other = {**selected, 'id': 'projection:99', 'location': ['markdown']}
    stage['findings'].append(other)
    write_json(path / 'report.json', data)
    with pytest.raises(ConfigurationError, match='sole semantic change'):
        replay(path, selected['id'], assembly, tmp_path / 'out', base_url='/', flavor='lite', workspace_root=tmp_path)


def test_replay_rejects_unstable_baseline(tmp_path, monkeypatch):
    path, data, selected, assembly = projection(tmp_path)
    monkeypatch.setattr('orinoco_lite.config.load_workspace', lambda root: SimpleNamespace(root=root))
    monkeypatch.setattr('orinoco_lite.resources.resolve_resources', lambda: SimpleNamespace(root=tmp_path))
    def build(workspace, resources, source, destination, *args, **kwargs):
        destination.mkdir()
        (destination / 'index.html').write_text(destination.name)
    monkeypatch.setattr('orinoco_lite.site.build_hugo', build)
    with pytest.raises(ConfigurationError, match='inconclusive'):
        replay(path, selected['id'], assembly, tmp_path / 'out', base_url='/', flavor='lite', workspace_root=tmp_path)


def test_compare_revisions_and_paired_link_problems(tmp_path):
    left, right = tmp_path / 'official', tmp_path / 'draft'
    for path, text in [(left, '<a href="/gone">old</a><a href="/shared">same</a>'),
                       (right, '<a href="/new-missing">new</a><a href="/shared">same</a>')]:
        path.mkdir(); (path / 'index.html').write_text(text)
    args = Namespace(review_command='compare', left=left, right=right, name='deployment',
                     stage='rendering', mode='complete-path', check_links=True,
                     left_base_url='/', right_base_url='/', root=tmp_path)
    for side, label in [('left', 'Official site'), ('right', 'Draft deployment')]:
        for key in ['label', 'url', 'branch_url', 'revision', 'captured_at', 'deployed_at']:
            setattr(args, f'{side}_{key}', label if key == 'label' else None)
    args.right_branch_url = 'https://example.org/hub/branch/draft'
    assert execute(args, tmp_path) == 1
    report, _ = load_report(tmp_path / 'reports/deployment')
    assert report['stages'][0]['targets']['right']['branch_url'] == args.right_branch_url
    report, _ = load_report(tmp_path / 'reports/deployment-checks')
    assert {f['problem_status'] for f in report['stages'][0]['findings']} == {'existing', 'introduced', 'resolved'}


def test_recomparison_retains_capture_and_build_provenance(tmp_path, capsys):
    import json
    from orinoco_lite import cli
    from orinoco_lite.stage_reports import write_operation, operation_receipt
    left, right = tmp_path/'local', tmp_path/'captured'
    left.mkdir(); right.mkdir()
    (left/'index.html').write_text('<p>local</p>')
    (right/'index.html').write_text('<p>draft</p>')
    build = write_operation(left, operation='hugo-build-lite', inputs={},
        command=['orinoco-lite', 'dev', 'hugo', 'build'],
        context={'flavor':'lite', 'dirty':True, 'base_url':'/demo/'})
    capture = write_operation(right, operation='site-capture', inputs={},
        command=['wget', 'https://draft.example/'], context={
            'target':{'label':'Draft site', 'url':'https://draft.example/', 'captured_at':'2026-10-01'},
            'capture':{'routes':[''], 'retrieval_complete':True}})
    cdx=tmp_path/'http.cdx'; cdx.write_text('CDX header\nhttps://draft.example/ 0 x x 200\n')
    source=tmp_path/'source'
    original=write_report(source, stage='rendering', left=left, right=right,
        findings=[], comparator='site-files/1', evidence={'right-http-cdx':cdx},
        targets={'left':{'label':'My local build'}, 'right':{'label':'Draft deployment', 'url':'https://draft.example/'}})
    assert operation_receipt(source/'artifacts/left') == build
    assert operation_receipt(source/'artifacts/right') == capture
    assert cli.main(['--root',str(tmp_path),'dev','review','compare',
        str(source/'artifacts/left'),str(source/'artifacts/right'),'--name','again']) == 1
    capsys.readouterr()
    again=tmp_path/'sourcedata/reports/again'
    stage=load_report(again)[0]['stages'][0]
    assert stage['targets']['left']['label']=='My local build'
    assert stage['targets']['right']['label']=='Draft deployment'
    assert stage['artifacts']['right']['operation']==capture
    assert 'right-http-cdx' in stage['artifacts']
    assert not stage['scope']['complete']
    assert cli.main(['--root',str(tmp_path),'dev','review','show','again','--format','json']) == 0
    result=json.loads(capsys.readouterr().out)
    assert result['stages'][0]['target_provenance']['left']['operation']==build
    output=tmp_path/'bundle'; bundle([again],output)
    assert ReviewModel(output).overview()['comparisons'][0]['target_provenance']['right']['operation']==capture
    # The report-writing API also preserves labels when it reuses copied inputs.
    rewritten=write_report(tmp_path/'rewritten',stage='rendering',
        left=source/'artifacts/left',right=source/'artifacts/right',findings=[],comparator='test')
    assert rewritten['stages'][0]['targets']==original['stages'][0]['targets']
    (source/'artifacts/left/index.html').write_text('edited after capture')
    assert operation_receipt(source/'artifacts/left') is None
