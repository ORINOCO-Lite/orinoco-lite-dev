import shutil
import pytest
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.stage_reports import write_report, write_json, read_json
from orinoco_lite.stage_bundle import bundle, ReviewModel
from orinoco_lite.stage_annotations import load_annotations


def fixture(tmp_path):
    left, right = tmp_path/'left', tmp_path/'right'
    left.mkdir(); right.mkdir()
    (left/'format.json').write_bytes(b'{"value":1}\r\n')
    (right/'format.json').write_bytes(b'{\n  "value": 1\n}\n')
    (left/'empty').touch()
    (right/'new.txt').write_bytes(b'new without newline')
    (left/'binary').write_bytes(b'\0old'); (right/'binary').write_bytes(b'\0new')
    (left/'same').write_text('same'); (right/'same').write_text('same')
    report = tmp_path/'report'
    data = write_report(report, stage='projection', left=left, right=right, findings=[{
        'subject':'format.json','location':['bytes','sha256'],'change':'changed',
        'before':'old','after':'new','before_present':True,'after_present':True}], comparator='test')
    return report, data


def test_original_files_are_independent_of_findings_and_include_all_bytes(tmp_path):
    report, data = fixture(tmp_path)
    bundle([report],tmp_path/'bundle')
    model = ReviewModel(tmp_path/'bundle')
    rows = model.original_files()['items']
    assert {r['subject'] for r in rows} == {'format.json','empty','new.txt','binary'}
    values = {r['subject']:model.original_file(r['key']) for r in rows}
    assert '-{"value":1}\r\n' in values['format.json']['unified_diff']
    assert '\\ No newline at end of file' in values['new.txt']['unified_diff']
    assert 'Empty file removed' in values['empty']['unified_diff']
    assert values['binary']['binary'] is True
    assert values['new.txt']['digests']['left'] is None
    assert values['empty']['digests']['right'] is None
    assert model.original_files(q='format')['total'] == 1


def test_annotations_copy_evidence_and_do_not_make_decisions(tmp_path):
    report, data = fixture(tmp_path)
    evidence=tmp_path/'experiment.py'; evidence.write_text('print("example")\n')
    note={'finding_key':data['run_id']+'/projection:1','author':'Codex',
          'explanation':'A hypothesis based on these inputs.', 'hypothesis':'Spacing may explain it.',
          'limits':'Not yet tested.', 'tags':['unresolved'],
          'commands':[['python','experiment.py']], 'evidence':[{'label':'Experiment','path':'experiment.py'}]}
    source=tmp_path/'annotations.json'; write_json(source,{'annotations':[note]})
    bundle([report], tmp_path/'bundle', annotations=source)
    shutil.rmtree(report); source.unlink(); evidence.unlink()
    model=ReviewModel(tmp_path/'bundle')
    row=model.findings()['items'][0]
    assert row['annotations'][0]['author']=='Codex'
    assert row['decision'] is None and row['state']=='new'
    assert model.annotation_artifact(0,0).read_text()=='print("example")\n'
    model.annotation_artifact(0,0).write_text('changed')
    with pytest.raises(ConfigurationError,match='changed'):
        model.annotation_artifact(0,0)
    with pytest.raises(ConfigurationError,match='digest'):
        ReviewModel(tmp_path/'bundle')


@pytest.mark.parametrize('mutation', ['disposition','missing-evidence','unknown-finding'])
def test_annotations_reject_acceptance_and_unsupported_claims(tmp_path, mutation):
    report,data=fixture(tmp_path)
    note={'finding_key':data['run_id']+'/projection:1','author':'Codex','explanation':'Example',
          'limits':'Example limits','evidence':[{'label':'Inputs','path':'left'}]}
    if mutation=='disposition':note['disposition']='intended'
    elif mutation=='missing-evidence':note['evidence']=[]
    else:note['finding_key']='unknown'
    source=tmp_path/'notes.json';write_json(source,{'annotations':[note]})
    with pytest.raises(ConfigurationError):load_annotations(source,[(data,report)])
