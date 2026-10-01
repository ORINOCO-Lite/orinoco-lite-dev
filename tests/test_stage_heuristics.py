"""User-facing heuristic selection and reclassification over retained evidence."""
import json
from pathlib import Path

import pytest

from orinoco_lite import cli, stage_reports
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.site_compare import compare_trees
from orinoco_lite.stage_bundle import ReviewModel, bundle
from orinoco_lite.stage_patterns import load_heuristic
from orinoco_lite.stage_reports import write_report


@pytest.fixture
def comparison(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_reports, 'execution_context', lambda: {})
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir(); right.mkdir()
    (left / 'graph.json').write_text('{"nodes":[{"id":"a"},{"id":"b"}]}')
    (right / 'graph.json').write_text('{"nodes":[{"id":"b"},{"id":"a"}]}')
    (left / 'index.html').write_text('<p>old</p>')
    (right / 'index.html').write_text('<p>new</p>')
    findings, _ = compare_trees(left, right, rendered=True)
    report = tmp_path / 'sourcedata/reports/example'
    write_report(report, stage='rendering', left=left, right=right,
                 findings=findings, comparator='site-files/1')
    return report


def test_cli_defaults_show_both_classified_and_unclassified(comparison, tmp_path, capsys):
    assert cli.main(['--root', str(tmp_path), 'dev', 'review', 'show', '--format', 'json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert {r['classification']['category'] for r in result['findings']} == {'recognized', 'unclassified'}
    assert result['heuristic']['rules'][-1] == 'url_pattern'
    assert not any(r['decision'] for r in result['findings'])


def test_ordered_python_rules_need_no_explanations_and_cannot_mutate_inputs(tmp_path):
    path = tmp_path / 'heuristic.py'
    path.write_text('''def specific(finding, stage):
    finding['before'] = 'mutated'
    stage['scope']['selection'] = 'mutated'
    return 'specific' if finding['subject'] == 'chosen' else None

def general(finding, stage):
    assert finding['before'] == 'original'
    assert stage['scope']['selection'] == 'original'
    return 'general'

RULES = [specific, general]
''')
    heuristic = load_heuristic(path)
    stage = {'scope': {'selection': 'original'}}
    finding = {'subject': 'chosen', 'before': 'original'}
    assert heuristic.classify(finding, stage)['rule'] == 'specific'
    assert finding['before'] == stage['scope']['selection'] == 'original'
    finding['subject'] = 'another'
    assert heuristic.classify(finding, stage)['rule'] == 'general'


def test_portable_bundle_never_executes_saved_heuristic_path(comparison, tmp_path):
    path = tmp_path / 'heuristic.py'
    path.write_text("def classify(finding, stage):\n    return 'local-category'\nRULES = [classify]\n")
    output = tmp_path / 'bundle'
    bundle([comparison], output, heuristic=path)
    path.write_text("raise RuntimeError('this must not execute when opening a bundle')\n")
    model = ReviewModel(output)
    rows = model.findings(state='all', raw=False)['items']
    assert all(r['classification']['rule'] == 'local-category' for r in rows)
    assert all(not r['decision'] for r in rows)
    path.write_text("def classify(finding, stage):\n    return None\nRULES = [classify]\n")
    reclassified = ReviewModel(output, heuristic=path)
    assert all(r['classification']['category'] == 'unclassified' for r in reclassified.findings(state='all', raw=False)['items'])
    assert model.heuristic['sha256'] != reclassified.heuristic['sha256']
    assert ReviewModel(output).findings(state='all', raw=False)['items'][0]['classification']['rule'] == 'local-category'


def test_invalid_rule_result_is_an_error_not_unclassified(tmp_path):
    path = tmp_path / 'heuristic.py'
    path.write_text('def broken(finding, stage):\n    return False\nRULES = [broken]\n')
    with pytest.raises(ConfigurationError, match='must return'):
        load_heuristic(path).classify({}, {})


def test_incomplete_retained_classification_has_actionable_error(comparison, tmp_path):
    output = tmp_path / 'bundle'
    bundle([comparison], output)
    path = output / 'review.json'
    document = json.loads(path.read_text())
    recognized = next(item for item in document['classifications'].values()
                      if item['category'] == 'recognized')
    del recognized['label']
    path.write_text(json.dumps(document))
    with pytest.raises(ConfigurationError, match='retained heuristic classification name'):
        ReviewModel(output)


def test_experiments_available_without_reports(tmp_path, capsys):
    assert cli.main(['--root', str(tmp_path), 'dev', 'review', 'experiments', '--format', 'json']) == 0
    items = json.loads(capsys.readouterr().out)
    assert all(item['status'] == 'not run in this review' for item in items)
    assert {'software-change', 'input-change', 'downstream-update'} <= {item['id'] for item in items}
    assert all(item['fixed'] and item['varied'] and item['command'] for item in items)


def test_declared_experiment_is_shared_by_cli_and_overview(comparison, tmp_path, capsys):
    assert cli.main(['--root', str(tmp_path), 'dev', 'review', 'compare',
                     str(tmp_path / 'left'), str(tmp_path / 'right'), '--name', 'update',
                     '--experiment', 'software-change']) == 1
    assert 'What it establishes' in capsys.readouterr().out
    output = tmp_path / 'bundle'
    bundle([comparison.parent / 'update'], output)
    overview = ReviewModel(output).overview()
    assert 'software update' in overview['comparisons'][0]['purpose']['establishes']
    assert 'Declared' in overview['comparisons'][0]['purpose']['basis']
    items = {i['id']: i for i in overview['experiment_guidance']}
    assert items['software-change']['status'] == 'completed'
    assert items['input-change']['status'] == 'not run in this review'
