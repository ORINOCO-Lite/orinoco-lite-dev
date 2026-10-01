from copy import deepcopy
import pytest
from orinoco_lite.stage_patterns import url_pattern, classifications, counts
from orinoco_lite.stage_reports import write_report, write_operation, load_report
from orinoco_lite.site_compare import compare_trees
from orinoco_lite.stage_bundle import bundle, ReviewModel


def sample():
    stage={'stage':'rendering','targets':{'left':{'url':'https://official.example/demo/'},'right':{'url':'https://draft.example/demo/'}},'artifacts':{}}
    a=['start','script',[['src','https://official.example/demo/js/x.js?a=1#part'],['integrity','sha256-same']]]
    b=deepcopy(a);b[2][0][1]=b[2][0][1].replace('official.example','draft.example')
    f={'location':['html','events',0,1],'before_present':True,'after_present':True,'before':[a],'after':[b]}
    return f,stage


def test_declared_prefix_preserves_suffix_and_other_attributes():
    f,s=sample()
    assert url_pattern(f,s)['category']=='recognized'
    s['targets']['left']['url']='/demo/'
    f['before'][0][2][0][1]='/demo/js/x.js?a=1#part'
    assert url_pattern(f,s)['subtype']=='absolute-root-relative'


@pytest.mark.parametrize('mutation',['path','query','fragment','integrity','mixed','canonical','unknown-host','missing-prefix','event-count'])
def test_meaningful_or_unestablished_edits_remain_unclassified(mutation):
    f,s=sample()
    if mutation=='path':f['after'][0][2][0][1]=f['after'][0][2][0][1].replace('x.js','y.js')
    elif mutation=='query':f['after'][0][2][0][1]=f['after'][0][2][0][1].replace('a=1','a=2')
    elif mutation=='fragment':f['after'][0][2][0][1]=f['after'][0][2][0][1].replace('#part','#other')
    elif mutation=='integrity':f['after'][0][2][1][1]='sha256-other'
    elif mutation=='mixed':f['before'].append(['text','old']);f['after'].append(['text','new'])
    elif mutation=='canonical':
        for side in ['before','after']:
            f[side][0][1]='link';f[side][0][2][0][0]='href';f[side][0][2].append(['rel','canonical'])
    elif mutation=='unknown-host':f['after'][0][2][0][1]=f['after'][0][2][0][1].replace('draft.example','other.example')
    elif mutation=='missing-prefix':del s['targets']['left']['url']
    else:f['after'].append(['text','extra'])
    assert url_pattern(f,s) is None


def test_capture_absence_classification_and_scoped_counts(tmp_path,monkeypatch):
    monkeypatch.setattr('orinoco_lite.stage_reports.execution_context',lambda:{})
    left=tmp_path/'left';right=tmp_path/'right';left.mkdir();right.mkdir()
    (right/'gone.html').write_text('present')
    (right/'unknown.html').write_text('present')
    (left/'index.html').write_text('<script src="/x.js"></script>')
    (right/'index.html').write_text('<script src="https://draft.example/x.js"></script>')
    write_operation(left,operation='capture',inputs={},context={'capture':{},'target':{'url':'https://official.example/','label':'Official'}})
    # Deliberately use same declared original prefix for the tested root-relative build.
    write_operation(right,operation='build',inputs={},context={})
    index=tmp_path/'http.cdx';index.write_text('header\nhttps://official.example/gone.html a b c 404\n')
    changes,_=compare_trees(left,right,rendered=True)
    output=tmp_path/'report'
    r=write_report(output,stage='rendering',left=left,right=right,findings=changes,comparator='site-files/1',evidence={'left-http-cdx':index},targets={'left':{'label':'Official','url':'https://official.example/'},'right':{'label':'Draft','url':'https://draft.example/'}},scope={'complete':False})
    classifications_by_key=classifications([load_report(output)])
    coverage=[c for c in classifications_by_key.values() if c['category']=='coverage']
    assert {c['subtype'] for c in coverage}=={'observed-absence','not-retained'}
    bundle([output],tmp_path/'bundle')
    model=ReviewModel(tmp_path/'bundle');o=model.overview();pair=o['comparisons'][0]
    scoped=model.overview(pair['id'])
    totals=scoped['classification_counts']
    assert totals['unclassified']+totals['recognized']+totals['coverage']==totals['differences']
    assert totals['differences']+totals['supporting']==totals['raw_observations']
    assert model.findings(state='all',classification='coverage',comparison=pair['id'])['total']==2
    assert model.decisions['decisions']==[]
    assert len(scoped['stages'])==1


def test_repeated_mixed_edits_are_grouped_without_claiming_equivalence(tmp_path,monkeypatch):
    monkeypatch.setattr('orinoco_lite.stage_reports.execution_context',lambda:{})
    left=tmp_path/'left';right=tmp_path/'right';left.mkdir();right.mkdir()
    for name in ['a.html','b.html']:
        (left/name).write_text('<script src="/old.js?v=1" integrity="old"></script>')
        (right/name).write_text('<script src="/new.js?v=2" integrity="new"></script>')
    changes,_=compare_trees(left,right,rendered=True)
    report=tmp_path/'report';data=write_report(report,stage='rendering',left=left,right=right,findings=changes,comparator='site-files/1')
    observed=classifications([load_report(report)])
    matches=[r for r in observed.values() if r.get('rule')=='repeated-html-edit']
    assert len(matches)==2 and matches[0]['group']==matches[1]['group']
    assert matches[0]['files']==2
    bundle([report],tmp_path/'bundle');model=ReviewModel(tmp_path/'bundle')
    pair=model.overview()['comparisons'][0]
    assert pair['counts']['unclassified']==0 and pair['counts']['recognized']==2
    assert model.findings(state='all',classification='recognized',group=matches[0]['group'])['total']==2
    assert model.original_files()['total']==2
    assert not model.decisions['decisions']


def test_narrow_prefix_precedes_repetition_and_mixed_remainder_stays_visible(tmp_path, monkeypatch):
    monkeypatch.setattr('orinoco_lite.stage_reports.execution_context', lambda: {})
    left, right = tmp_path/'left', tmp_path/'right'; left.mkdir(); right.mkdir()
    for name in ['a.html', 'b.html']:
        (left/name).write_text('<script src="https://old.example/a.js"></script>')
        (right/name).write_text('<script src="https://new.example/a.js"></script>')
    (left/'mixed.html').write_text('<p>unique old</p><script src="https://old.example/b.js"></script>')
    (right/'mixed.html').write_text('<p>unique new</p><script src="https://new.example/c.js"></script>')
    changes, _ = compare_trees(left, right, rendered=True)
    output = tmp_path/'report'
    write_report(output, stage='rendering', left=left, right=right, findings=changes,
        comparator='site-files/1', targets={'left':{'label':'Old','url':'https://old.example/'},'right':{'label':'New','url':'https://new.example/'}})
    rules = classifications([load_report(output)])
    assert sum(c.get('rule') == 'declared-url-prefix-change' for c in rules.values()) == 2
    assert not any(c.get('rule') == 'repeated-html-edit' for c in rules.values())
    assert any(c['category'] == 'unclassified' for c in rules.values())


def test_graph_order_recognition_preserves_all_content_and_multiplicity():
    from orinoco_lite.stage_patterns import graph_pattern
    f = {'subject':'graph.json', 'location':['json','nodes'], 'before_present':True,
         'after_present':True, 'before':[{'id':'a','size':1},{'id':'b','size':2}],
         'after':[{'id':'b','size':2},{'id':'a','size':1}]}
    assert graph_pattern(f)['subtype'] == 'graph-node-order'
    f['after'][0]['size'] = 3
    assert graph_pattern(f) is None
    f['location'] = ['json','edges']
    f['before'] = [{'id':'e0','source':'a','target':'b','weight':1},
                   {'id':'e1','source':'a','target':'b','weight':1}]
    f['after'] = [{'id':'e7','source':'a','target':'b','weight':1},
                  {'id':'e8','source':'a','target':'b','weight':1}]
    assert graph_pattern(f)['subtype'] == 'graph-edge-ids'
    for mutation in ['multiplicity','endpoint','property','duplicate-id','external-id','type']:
        changed = deepcopy(f)
        if mutation == 'multiplicity': changed['after'].pop()
        elif mutation == 'endpoint': changed['after'][0]['target'] = 'c'
        elif mutation == 'property': changed['after'][0]['weight'] = 2
        elif mutation == 'duplicate-id': changed['after'][0]['id'] = 'e8'
        elif mutation == 'external-id': changed['after'][0]['id'] = 'permanent-link'
        else: changed['after'][0]['weight'] = True
        assert graph_pattern(changed) is None, mutation


def test_named_html_patterns_reject_mixed_hunks():
    from orinoco_lite.stage_patterns import named_html_pattern
    f = {'location':['html','events',0,1], 'before_present':True, 'after_present':True,
         'before':[['start','a',[['href','https://example.org'],['target','_blank']]]],
         'after':[['start','a',[['href','https://example.org']]]]}
    assert named_html_pattern(f)['subtype'] == 'link-target-removal'
    f['after'][0][2][0][1] = 'https://other.example'
    assert named_html_pattern(f) is None
    f['before'] = [['start','script',[['src','/graph.js'],['integrity','original']]]]
    f['after'] = deepcopy(f['before']); f['after'][0][2][0][1] += '?v=' + 'a'*64
    assert named_html_pattern(f)['subtype'] == 'graph-script-version'
    f['after'][0][2][1][1] = 'changed'
    assert named_html_pattern(f) is None
    f['after'][0][2][1][1] = 'original'
    f['after'].append(['text','unmatched content'])
    assert named_html_pattern(f) is None


def test_graph_patterns_are_available_in_review_without_accepting_findings(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr('orinoco_lite.stage_reports.execution_context', lambda: {})
    left,right=tmp_path/'left',tmp_path/'right';left.mkdir();right.mkdir()
    nodes=[{'id':'a','label':'A'},{'id':'b','label':'B'}]
    edges=[{'id':'e0','source':'a','target':'b'}]
    (left/'graph.json').write_text(json.dumps({'nodes':nodes,'edges':edges}))
    (right/'graph.json').write_text(json.dumps({'nodes':nodes[::-1],'edges':[dict(edges[0],id='e2')]}))
    changes,_=compare_trees(left,right,rendered=True)
    report=tmp_path/'report'
    write_report(report,stage='rendering',left=left,right=right,findings=changes,comparator='site-files/1')
    bundle([report],tmp_path/'bundle');model=ReviewModel(tmp_path/'bundle')
    rows=model.findings(state='all',classification='recognized')['items']
    assert {r['classification']['subtype'] for r in rows} == {'graph-node-order','graph-edge-ids'}
    assert all(r['state']=='new' and r['unified_diff'] for r in rows)
    assert model.original_files()['total']==1
    assert not model.decisions['decisions']
