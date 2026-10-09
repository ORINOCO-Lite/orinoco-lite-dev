"""Observable block display, named chaining, and shell failure behavior."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from orinoco_lite.projection_blocks import (
    BlockExecutionError, CodeBlock, Pipeline, WORKFLOW, adjust_for_lite, parse_workflow,
)


def test_adjustment_history_keeps_raw_and_intermediate_states():
    raw = 'printf original\n'
    block = CodeBlock('Example', raw).replace('original', 'adjusted', reason='First change')
    assert block.raw == raw
    assert block.adjusted == 'printf adjusted\n'
    assert '-printf original' in block.diff()
    assert '+printf adjusted' in block.diff()
    restored = block.replace('adjusted', 'original', reason='Restore')
    assert len(restored.adjustments) == 2
    assert restored.diff() == ' printf original\n'
    assert 'First change' in restored.display('adjustments')
    assert 'Restore' in restored.display('adjustments')
    assert '[diff]' in repr(block)
    assert '[raw]' not in repr(block)
    assert all(f'[{view}]' in block.display('all') for view in ('raw', 'adjustments', 'adjusted', 'diff'))
    with pytest.raises(ValueError, match='exactly once'):
        block.replace('missing', '', reason='Drift')


def test_removed_and_whitespace_blocks_do_not_execute_or_require_a_directory(tmp_path):
    block = CodeBlock('Removed', 'exit 99\n').replace('exit 99\n', '', reason='Remove command')
    assert '-exit 99' in block.diff()
    assert not block.execute(cwd=tmp_path / 'missing')
    assert not CodeBlock('Whitespace', ' \n\t').execute(cwd=tmp_path / 'missing')


def test_names_determine_order_shared_files_and_separate_shells(tmp_path):
    pipeline = Pipeline((
        CodeBlock('Second', 'test -z "${BLOCK_VARIABLE-}"; cat sequence; printf second >> sequence'),
        CodeBlock('First', 'BLOCK_VARIABLE=local; printf first > sequence'),
        CodeBlock('Empty', ''),
    ))
    with pytest.raises(ValueError, match='Unknown block'):
        pipeline.chain('First', 'Unknown')
    assert not (tmp_path / 'sequence').exists()
    assert pipeline.chain('First', 'Empty', 'Second').execute(cwd=tmp_path) == ['First', 'Second']
    assert (tmp_path / 'sequence').read_text() == 'firstsecond'


def test_pipeline_failure_is_named_and_stops_later_blocks(tmp_path):
    pipeline = Pipeline((
        CodeBlock('Producer failure', '(exit 7) | cat'),
        CodeBlock('Must not execute', 'touch unexpected'),
    ))
    with pytest.raises(BlockExecutionError, match='Producer failure.*status 7'):
        pipeline.execute(cwd=tmp_path)
    assert not (tmp_path / 'unexpected').exists()


def test_duplicate_names_and_unnamed_steps_are_rejected(tmp_path):
    workflow = tmp_path / 'workflow.yaml'
    workflow.write_text('jobs:\n  create_pages:\n    steps:\n      - run: echo hello\n')
    with pytest.raises(ValueError, match='every step needs'):
        parse_workflow(workflow)
    with pytest.raises(ValueError, match='unique'):
        Pipeline((CodeBlock('Same', ''), CodeBlock('Same', '')))


def cli(*arguments, cwd=None):
    return subprocess.run([sys.executable, '-m', 'orinoco_lite.projection_blocks', *arguments],
                          cwd=cwd, capture_output=True, text=True)


def test_selected_workflow_displays_deletions_and_unchanged_page_commands():
    upstream = parse_workflow(WORKFLOW)
    lite = adjust_for_lite(upstream)
    for name in ('git-annex init', 'Install jq', 'Deposit annex keys'):
        block = lite.chain(name).blocks[0]
        assert block.adjusted == ''
        assert block.adjustments[0].before == block.raw
        assert block.adjustments[0].after == ''
    graph = lite.chain('Update navigation graph').blocks[0]
    assert 'git annex add static' in graph.raw
    assert 'git annex add static' not in graph.adjusted
    for name in ('Identify project members', 'Update persons', 'Update publications'):
        assert upstream.chain(name).blocks[0].raw == lite.chain(name).blocks[0].adjusted
    result = cli('show', 'Update navigation graph', '--json')
    assert result.returncode == 0, result.stderr
    assert result.stderr == ''
    state = json.loads(result.stdout)[0]
    assert state['name'] == 'Update navigation graph'
    assert state['adjustments']
    assert '-&& git annex add static' in state['diff']


def test_help_outside_workspace_and_execution_streams(tmp_path):
    assert cli('--help', cwd=tmp_path).returncode == 0
    workflow = tmp_path / 'workflow.yaml'
    workflow.write_text('jobs:\n  create_pages:\n    steps:\n      - name: Greeting\n        run: printf hello\n      - name: Empty\n        run: ""\n      - name: Fail\n        run: exit 6\n')
    result = cli('--workflow', str(workflow), '--upstream', 'run', 'Empty', 'Greeting',
                 '--cwd', str(tmp_path))
    assert result.returncode == 0
    assert result.stdout == 'hello'
    assert 'Executing Greeting' in result.stderr
    assert 'Executing Empty' not in result.stderr
    result = cli('--workflow', str(workflow), '--upstream', 'run', 'Fail', '--cwd', str(tmp_path))
    assert result.returncode == 6
    assert 'Fail: shell exited with status 6' in result.stderr
    assert 'Traceback' not in result.stderr


def test_closed_output_pipe_has_no_traceback(tmp_path):
    import yaml
    workflow = tmp_path / 'large.yaml'
    workflow.write_text(yaml.safe_dump({'jobs': {'create_pages': {'steps': [
        {'name': 'Large', 'run': 'printf hello\n' * 100000},
    ]}}}))
    process = subprocess.Popen([sys.executable, '-m', 'orinoco_lite.projection_blocks',
                               '--workflow', str(workflow), '--upstream', 'show', '--view', 'raw'],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.stdout.read(64)
    process.stdout.close()
    stderr = process.stderr.read().decode()
    assert process.wait(timeout=10) == 1
    assert 'Traceback' not in stderr


def test_default_is_unified_diff_and_color_is_optional():
    result = cli('show', 'Update navigation graph')
    assert result.returncode == 0
    assert '=== 4. Update navigation graph ===' in result.stdout
    assert '---' not in result.stdout
    assert '+++' not in result.stdout
    assert '[raw]' not in result.stdout
    assert '\033[' not in result.stdout
    result = cli('show', 'Update navigation graph', '--color', 'always')
    assert '\033[31m-&& git annex add static\033[0m' in result.stdout
    assert '\033[32m+&& mv static/graph.json_new static/graph.json\033[0m' in result.stdout
    result = cli('show', 'Update navigation graph', '--color', 'never')
    assert '\033[' not in result.stdout
    result = cli('show', 'Update navigation graph', '--json', '--color', 'always')
    assert '\033' not in json.loads(result.stdout)[0]['diff']


def test_numbers_are_stable_after_selection_and_work_in_cli():
    pipeline = adjust_for_lite(parse_workflow(WORKFLOW))
    assert pipeline[4].name == 'Update navigation graph'
    assert pipeline['4'] == pipeline['Update navigation graph']
    selected = pipeline.chain(5, 'Update navigation graph')
    assert [block.number for block in selected.blocks] == [5, 4]
    assert selected[4].name == 'Update navigation graph'
    assert cli('show', '4').stdout == cli('show', 'Update navigation graph').stdout
    assert '=== 4. Update navigation graph ===' in cli('list').stdout
    assert cli('show', '0').returncode == 1


def test_diff_displays_full_unchanged_context_without_headers():
    raw = ''.join(f'line {i}\n' for i in range(30))
    block = CodeBlock('Long', raw).replace('line 15\n', 'replacement\n', reason='Change middle')
    diff = block.diff()
    assert ' line 0\n' in diff
    assert ' line 29\n' in diff
    assert '-line 15\n' in diff
    assert '+replacement\n' in diff
    assert '---' not in diff and '+++' not in diff
    assert all(f' line {i}\n' in CodeBlock('Unchanged', raw).diff() for i in range(30))
