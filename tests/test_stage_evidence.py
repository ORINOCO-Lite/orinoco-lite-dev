"""Evidence remains inspectable without making Annex a comparison dependency."""
import shutil
import subprocess

import pytest

from orinoco_lite import stage_reports
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.stage_bundle import ReviewModel, bundle
from orinoco_lite.stage_evidence import ReviewOverview, materialize
from orinoco_lite.stage_reports import write_report, read_json


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(stage_reports, 'execution_context', lambda: {})
    left, right = tmp_path/'left', tmp_path/'right'
    left.write_text('before'); right.write_text('after')
    report = tmp_path/'report'
    write_report(report, stage='storage', left=left, right=right, findings=[], comparator='test')
    output = tmp_path/'source/bundle'
    bundle([report], output)
    return output


def test_saved_overview_survives_absent_evidence_and_disallows_decisions(evidence):
    shutil.rmtree(evidence/'reports')
    overview = ReviewOverview(evidence)
    assert overview.overview()['metadata_only']
    assert 'not been retrieved or verified' in overview.overview()['evidence_status']
    with pytest.raises(ConfigurationError, match='Materialize'):
        overview.decision({})
    with pytest.raises(ConfigurationError):
        ReviewModel(evidence)


def test_materialize_plain_bundle_verifies_bytes(evidence, tmp_path):
    destination = tmp_path/'materialized'
    materialize(evidence, destination)
    assert ReviewModel(destination).overview()['title'] == ReviewModel(evidence).overview()['title']
    report = read_json(evidence/'reports/0001/report.json')
    (evidence/'reports/0001'/report['stages'][0]['artifacts']['left']['path']).write_text('corrupt')
    with pytest.raises(ConfigurationError, match='digest'):
        materialize(evidence, tmp_path/'corrupt')
    assert not (tmp_path/'corrupt').exists()


def test_materialize_rejects_arbitrary_symlink(evidence, tmp_path):
    path = evidence/'unexpected'
    path.symlink_to(tmp_path/'left')
    with pytest.raises(ConfigurationError, match='not a Git Annex file'):
        materialize(evidence, tmp_path/'bad-link')


def test_annex_retrieval_from_separate_clone(evidence, tmp_path):
    if not shutil.which('git-annex'):
        pytest.skip('git-annex is unavailable in this environment')
    root = evidence.parent
    def git(*args, cwd=root):
        return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True, text=True).stdout
    git('init')
    git('config', 'user.name', 'Test Fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    git('annex', 'init', 'test source')
    (root/'.gitattributes').write_text('* annex.largefiles=anything\nbundle/overview.json annex.largefiles=nothing\n')
    git('add', '.gitattributes', 'bundle/overview.json')
    git('annex', 'add', 'bundle')
    git('commit', '-m', 'test fixture')
    clone = tmp_path/'clone'
    subprocess.run(['git', 'clone', str(root), str(clone)], check=True, capture_output=True)
    git('annex', 'init', 'test clone', cwd=clone)
    assert ReviewOverview(clone/'bundle').overview()['metadata_only']
    with pytest.raises(ConfigurationError, match='not available locally'):
        materialize(clone/'bundle', tmp_path/'missing')
    materialize(clone/'bundle', tmp_path/'retrieved', get=True)
    assert ReviewModel(tmp_path/'retrieved').overview()['title'] == 'Staged comparison review'
    assert not any(p.is_symlink() for p in (tmp_path/'retrieved').rglob('*'))
