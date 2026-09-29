from __future__ import annotations

import json

import pytest

from orinoco_lite import cli, rdf_compare, rdf_stages
from orinoco_lite.upstream_snapshot import RecordEnvelope, write_jsonl


def graphs(tmp_path, left, right):
    paths = [tmp_path / "left.trig", tmp_path / "right.trig"]
    for path, data in zip(paths, (left, right)):
        path.write_text(data)
    return paths


@pytest.mark.parametrize(("left", "right", "equal"), [
    ('_:a <urn:p> "x"; <urn:q> _:b . _:b <urn:p> "y" .',
     '_:z <urn:p> "y" . _:w <urn:q> _:z; <urn:p> "x" .', True),
    ('_:a <urn:p> "x" .', '_:b <urn:p> "changed" .', False),
    ('_:a <urn:p> "x" .', '_:b <urn:p> "x" . <urn:s> <urn:p> "new" .', False),
    ('<urn:s> <urn:p> "01"^^<http://www.w3.org/2001/XMLSchema#integer> .',
     '<urn:s> <urn:p> "1"^^<http://www.w3.org/2001/XMLSchema#integer> .', False),
    ('<urn:s> <urn:p> "x" .',
     '<urn:s> <urn:p> "x"^^<http://www.w3.org/2001/XMLSchema#string> .', True),
    ('<urn:s> <urn:p> "x"@en .', '<urn:s> <urn:p> "x"@fr .', False),
    ('_:a <urn:p> _:a . _:b <urn:p> _:b .',
     '_:a <urn:p> _:b . _:b <urn:p> _:a .', False),
    ('<urn:s> <urn:p> ("a" "b" "a") .',
     '<urn:s> <urn:p> ("a" "a" "b") .', False),
    ('<urn:s> <urn:p> ("a" "a") .', '<urn:s> <urn:p> ("a") .', False),
])
def test_rdf_term_and_collection_equality(tmp_path, left, right, equal):
    paths = graphs(tmp_path, f"<urn:g> {{ {left} }}", f"<urn:g> {{ {right} }}")
    result, = rdf_compare.compare_graphs(*paths)["comparisons"]
    assert result["equal"] is equal



@pytest.mark.parametrize(('left', 'right', 'equal'), [
    ('<urn:old> { _:a <urn:p> "x" }', '<urn:new> { _:b <urn:p> "x" }', False),
    ('<urn:g> { _:a <urn:p> "x" } _:a <urn:q> "y" .',
     '_:z <urn:q> "y" . <urn:g> { _:z <urn:p> "x" }', True),
    ('<urn:g1> { _:a <urn:p> "x" } <urn:g2> { _:a <urn:p> "x" }',
     '<urn:g1> { _:a <urn:p> "x" } <urn:g2> { _:b <urn:p> "x" }', False),
    ('_:g { _:g <urn:p> _:b }', '_:other { _:other <urn:p> _:z }', True),
    ('', '', True),
])
def test_whole_dataset_graph_inventory_and_shared_blank_nodes(tmp_path, left, right, equal):
    result = rdf_compare.compare_graphs(*graphs(tmp_path, left, right))
    assert result['comparisons'][0]['equal'] is equal


@pytest.mark.parametrize('empty', ['<urn:empty> {}', '_:empty {}', '@prefix ex: <urn:> . GRAPH ex:empty {}'])
def test_empty_named_graphs_are_explicitly_not_evaluated(tmp_path, empty):
    with pytest.raises(rdf_compare.RDFComparisonError, match='empty named graphs'):
        rdf_compare.compare_graphs(*graphs(tmp_path, '<urn:s> <urn:p> "x" .', empty))


def test_deadline_invalid_input_and_existing_evidence(tmp_path, monkeypatch):
    paths = graphs(tmp_path, '<urn:s> <urn:p> "x" .', 'not RDF')
    with pytest.raises(rdf_compare.RDFComparisonError, match='exceeded'):
        rdf_compare.compare_graphs(*paths, timeout=.001)
    with pytest.raises(rdf_compare.RDFComparisonError, match='not evaluated'):
        rdf_compare.compare_graphs(*paths)
    report = tmp_path / 'report'
    assert rdf_stages.compare_outputs(*paths, report) == 2
    saved = (report / 'report.json').read_bytes()
    stage = json.loads(saved)['stages'][0]
    assert stage['status'] == 'skipped' and stage['scope']['result'] == 'not evaluated'
    assert cli.main(['dev', 'rdf', 'compare', *map(str, paths), '--report', str(report)]) == 2
    assert (report / 'report.json').read_bytes() == saved


def documents(tmp_path, monkeypatch, records, name):
    source = tmp_path / (name + '.jsonl')
    write_jsonl(source, [RecordEnvelope('Thing', {'pid': pid, 'schema_type': 'dlthings:Thing', 'rdf': rdf})
                         for pid, rdf in records.items()])
    class Writer:
        def convert(self, record, _class):
            if record['rdf'] == 'fail':
                raise ValueError('injected conversion failure')
            return record['rdf']
    monkeypatch.setattr(rdf_stages, 'build_format_converters', lambda _, **kw: (Writer(),))
    schema = tmp_path / 'schema.yaml'
    schema.write_text('schema input')
    output = tmp_path / name
    rdf_stages.jsonl_to_rdf(source, output, schema=schema)
    return output / 'graph.nt'


def test_record_attribution_cancellation_filter_and_missing_metadata(tmp_path, monkeypatch):
    a, b = '<urn:s> <urn:p> "a" .', '<urn:s> <urn:p> "b" .'
    left = documents(tmp_path, monkeypatch, {'ex:a': a, 'ex:b': b}, 'left')
    right = documents(tmp_path, monkeypatch, {'ex:a': b, 'ex:b': a}, 'right')
    for selection, expected in [(None, 2), (['ex:a'], 1), (['ex:absent'], None)]:
        report = tmp_path / ('report-' + str(expected))
        assert rdf_stages.compare_outputs(left, right, report, by_record=True, selected=selection) == 0
        whole = json.loads((report / 'report.json').read_text())['stages'][0]
        local = json.loads((report.with_name(report.name + '-records') / 'report.json').read_text())['stages'][0]
        assert whole['scope']['complete'] and whole['scope']['result'] == 'equal'
        if expected is None:
            assert local['status'] == 'skipped'
        else:
            assert len(local['findings']) == expected
            assert local['scope']['complete'] is (selection is None)
    left.with_name('conversion.json').unlink()
    assert rdf_stages.compare_outputs(left, right, tmp_path / 'missing', by_record=True) == 0
    assert json.loads((tmp_path / 'missing-records/report.json').read_text())['stages'][0]['status'] == 'skipped'


def test_forward_merge_renames_document_local_blank_nodes_and_retains_additions(tmp_path, monkeypatch):
    rdf = '_:a <urn:p> "x" .'
    left = documents(tmp_path, monkeypatch, {'ex:a': rdf}, 'left')
    right = documents(tmp_path, monkeypatch, {'ex:a': rdf, 'ex:b': rdf, 'ex:empty': ''}, 'right')
    assert rdf_stages.compare_outputs(left, right, tmp_path / 'report', by_record=True) == 1
    stage = json.loads((tmp_path / 'report-records/report.json').read_text())['stages'][0]
    assert {row['subject']: row['change'] for row in stage['findings']} == {'ex:b': 'added', 'ex:empty': 'added'}
    assert rdf_compare.compare_graphs(left, right)['comparisons'][0]['after'] == 2


def test_partial_forward_conversion_and_tampered_attribution(tmp_path, monkeypatch):
    left = documents(tmp_path, monkeypatch, {'ex:a': '<urn:s> <urn:p> "x" .', 'ex:b': 'fail'}, 'failed')
    assert not left.exists()
    assert left.with_name('partial.nt').is_file()
    assert json.loads(left.with_name('conversion.json').read_text())['status'] == 'failed'
    right = documents(tmp_path, monkeypatch, {'ex:a': '<urn:s> <urn:p> "x" .'}, 'right')
    next(right.parent.glob('records/*.ttl')).write_text('<urn:s> <urn:p> "changed" .')
    assert rdf_stages.compare_outputs(right, right, tmp_path / 'tampered', by_record=True) == 0
    assert json.loads((tmp_path / 'tampered-records/report.json').read_text())['stages'][0]['status'] == 'skipped'


def test_interruption_retains_failed_conversion(tmp_path, monkeypatch):
    source = tmp_path / 'source.jsonl'
    write_jsonl(source, [RecordEnvelope('Thing', {'pid': 'ex:s', 'schema_type': 'dlthings:Thing'})])
    schema = tmp_path / 'schema.yaml'; schema.write_text('schema input')
    def interrupt(*a, **kw):
        raise KeyboardInterrupt()
    monkeypatch.setattr(rdf_stages, 'build_format_converters', interrupt)
    with pytest.raises(KeyboardInterrupt):
        rdf_stages.jsonl_to_rdf(source, tmp_path / 'output', schema=schema)
    assert json.loads((tmp_path / 'output/conversion.json').read_text())['status'] == 'failed'


def test_forward_cli_accepts_explicit_paths(tmp_path, monkeypatch):
    from orinoco_lite import cli
    monkeypatch.chdir(tmp_path)
    documents(tmp_path, monkeypatch, {'ex:a': '<urn:s> <urn:p> "x" .'}, 'fixture')
    assert cli.main(['dev', 'records', 'jsonl-to-rdf', '--source', 'fixture.jsonl',
                     '--output', 'inspection/rdf']) == 0
    assert (tmp_path / 'inspection/rdf/graph.nt').is_file()
    assert not (tmp_path / 'upstream-diffing').exists()
