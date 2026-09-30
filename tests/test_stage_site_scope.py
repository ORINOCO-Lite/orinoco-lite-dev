from orinoco_lite.stage_site_scope import site_scopes
from orinoco_lite.stage_reports import json_digest


def artifact(digest, inputs=None, flavor='upstream'):
    return {'digest':digest,'operation':{'operation':'build','inputs':inputs or {},'context':{'flavor':flavor}}}


def stage(left, right, name='rendering'):
    return ({}, {'stage':name,'mode':'complete-path','scope':{},'artifacts':{'left':left,'right':right}}, None)


def test_site_scope_uses_exact_producers_not_labels_or_bytes_alone():
    old,new = artifact('p1'),artifact('p2',flavor='lite')
    outputs=[artifact('html1',{'projection':{'digest':old['digest'],'producer':json_digest(old['operation'])}}),
             artifact('html2',{'projection':{'digest':new['digest'],'producer':json_digest(new['operation'])}},flavor='lite')]
    wrong = artifact('p1',{'different-input':{'digest':'other'}})
    stages={('site',0):stage(*outputs),('projection',0):stage(old,new,'projection'),('unrelated',0):stage(wrong,new,'projection')}
    pair=next(iter(site_scopes(stages).values()))
    assert pair['members']=={('site',0),('projection',0)}
    stages[('second-site',0)] = stage(artifact('other-html1'), artifact('other-html2',flavor='lite'))
    assert len(site_scopes(stages)) == 2  # Same labels do not merge distinct websites.
