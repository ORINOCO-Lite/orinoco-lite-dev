"""Run the workflow's transport steps against real parent/child Git histories."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml

WORKFLOW = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / '.github/workflows/upstream-comparison-update.yml').read_text()
)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def commit(root, message):
    git(root, 'add', '.')
    git(root, 'commit', '-qm', message)
    return git(root, 'rev-parse', 'HEAD')


def step(job, name, root, env):
    script = next(s['run'] for s in WORKFLOW['jobs'][job]['steps'] if s.get('name') == name)
    return subprocess.run(['bash', '-euo', 'pipefail', '-c', script], cwd=root, env=env,
                          text=True, capture_output=True)


@pytest.fixture
def datasets(tmp_path, monkeypatch):
    for role in ('AUTHOR', 'COMMITTER'):
        monkeypatch.setenv(f'GIT_{role}_NAME', 'Transport test')
        monkeypatch.setenv(f'GIT_{role}_EMAIL', 'test@example.invalid')
    child, parent = tmp_path / 'published-inputs', tmp_path / 'downstream'
    for repo in (child, parent):
        repo.mkdir()
        git(repo, 'init', '-qb', 'main')
    (child / 'record.yaml').write_text('title: Before\n')
    child_base = commit(child, 'test: initial site inputs')
    git(parent, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(child), 'site-specific')
    base = commit(parent, 'test: record original gitlink')
    runner = tmp_path / 'runner'
    runner.mkdir()
    env = dict(os.environ, PARENT_BASE=base, SITE_BASE=child_base, RUNNER_TEMP=str(runner),
               GITHUB_OUTPUT=str(tmp_path / 'outputs'), GITHUB_STEP_SUMMARY=str(tmp_path / 'summary'))
    return parent, child, env


@pytest.mark.parametrize('case', ['unchanged', 'parent-only', 'child', 'retarget',
                                  'stale-parent', 'stale-child', 'wrong-child', 'dirty-child'])
def test_recorded_update_transport(datasets, tmp_path, case):
    parent, child, env = datasets
    changed_child = case not in ('unchanged', 'parent-only')
    if changed_child:
        for title in ('Intermediate', 'After'):
            (parent / 'site-specific/record.yaml').write_text(f'title: {title}\n')
            commit(parent / 'site-specific', f'test: record {title.lower()} inputs')
            commit(parent, f'test: select {title.lower()} inputs')
    elif case == 'parent-only':
        (parent / 'selection').write_text('new package selection\n')
        commit(parent, 'test: update parent only')
        # A parent-only change can retain a child pin older than child main.
        (child / 'later').write_text('separately accepted inputs\n')
        commit(child, 'test: advance published child')
    if case == 'retarget':
        modules = parent / '.gitmodules'
        modules.write_text(modules.read_text().replace(str(child), 'https://github.com/other/inputs.git'))
        commit(parent, 'test: unauthorized child repository change')
    if case == 'dirty-child':
        (parent / 'site-specific/record.yaml').write_text('unrecorded changes\n')
    result = step('prepare', 'Export recorded update', tmp_path, env)
    if case == 'dirty-child':
        assert result.returncode != 0
        assert not list((tmp_path / 'runner').glob('*.bundle'))
        return
    assert result.returncode == 0, result.stderr
    outputs = dict(line.split('=', 1) for line in Path(env['GITHUB_OUTPUT']).read_text().splitlines())
    assert outputs['changed'] == str(case != 'unchanged').lower()
    assert outputs['site_changed'] == str(changed_child).lower()
    if case == 'unchanged':
        assert not list((tmp_path / 'runner').glob('*.bundle'))
        return
    transport = tmp_path / 'runner/template-update'
    transport.mkdir()
    for bundle in (tmp_path / 'runner').glob('*.bundle'):
        bundle.rename(transport / bundle.name)
    # Clone only the accepted histories. Candidate commits arrive in the bundle.
    published = tmp_path / 'publisher'
    git(parent, 'branch', 'accepted', env['PARENT_BASE'])
    subprocess.run(['git', 'clone', '--quiet', '--no-local', '--single-branch', '--branch',
                    'accepted', str(parent), str(published)], check=True)
    assert subprocess.run(['git', '-C', str(published), 'cat-file', '-e',
                           git(parent, 'rev-parse', 'HEAD')], capture_output=True).returncode != 0
    git(published, 'checkout', '--detach', env['PARENT_BASE'])
    if case == 'stale-parent':
        (published / 'later').write_text('another accepted update\n')
        commit(published, 'test: advance parent after preparation')
    before = git(published, 'rev-parse', 'HEAD')
    result = step('publish', 'Import recorded commits without executing updated code', published, env)
    if case in ('retarget', 'stale-parent'):
        assert result.returncode != 0
        assert git(published, 'rev-parse', 'HEAD') == before
        return
    assert result.returncode == 0, result.stderr
    assert git(published, 'rev-parse', 'HEAD') == git(parent, 'rev-parse', 'HEAD')
    if case == 'stale-child':
        (child / 'later').write_text('another accepted update\n')
        commit(child, 'test: advance child after preparation')
    subprocess.run(['git', 'clone', '--quiet', str(child), str(published / 'site-specific')], check=True)
    git(published / 'site-specific', 'checkout', '--detach', env['SITE_BASE'])
    env['SITE_CHANGED'] = str(changed_child).lower()
    if case == 'wrong-child':
        (parent / 'site-specific/extra').write_text('not selected by the parent\n')
        extra = commit(parent / 'site-specific', 'test: unrelated child commit')
        git(parent / 'site-specific', 'branch', '-f', 'orinoco-site-result', extra)
        git(parent / 'site-specific', 'bundle', 'create', str(transport / 'site-specific-update.bundle'),
            'orinoco-site-result', '^' + env['SITE_BASE'])
    result = step('publish', 'Import the recorded site-specific commits', published, env)
    if case in ('stale-child', 'wrong-child'):
        assert result.returncode != 0
        return
    assert result.returncode == 0, result.stderr
    assert not git(published, 'status', '--porcelain')
    if changed_child:
        assert git(published / 'site-specific', 'rev-list', '--count', env['SITE_BASE'] + '..HEAD') == '2'
        for revision in git(parent, 'rev-list', env['PARENT_BASE'] + '..HEAD').splitlines():
            pinned = git(parent, 'rev-parse', f'{revision}:site-specific')
            git(published / 'site-specific', 'cat-file', '-e', f'{pinned}^{{commit}}')
        # The PR action restores its working base after publishing the child.
        child_head = git(published / 'site-specific', 'rev-parse', 'HEAD')
        git(published / 'site-specific', 'reset', '--hard', env['SITE_BASE'])
        env.update(SITE_PULL_URL='https://github.com/example/inputs/pull/1', SITE_PULL_HEAD=child_head)
        result = step('publish', 'Require published site-specific commits', published, env)
        assert result.returncode == 0, result.stderr
        assert not git(published, 'status', '--porcelain')


@pytest.mark.parametrize(('selection', 'reuse'), [('Retained capture', True), ('Refresh from Pool', False)])
def test_capture_selection_uses_existing_preparation_command(tmp_path, selection, reuse):
    executable = tmp_path / 'pixi'
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$ARGS"\n')
    executable.chmod(0o755)
    arguments = tmp_path / 'arguments'
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ['PATH'],
               SOURCE_DATA=selection, ARGS=str(arguments))
    result = step('prepare', 'Prepare selected upstream inputs', tmp_path, env)
    assert result.returncode == 0, result.stderr
    args = arguments.read_text().splitlines()
    assert args[:9] == ['exec', '--spec', 'git-annex==10.20260601', '--', 'pixi', 'run',
                        'orinoco-lite', 'dev', 'upstream']
    assert args[9:] == ['populate'] + (['--reuse-dump'] if reuse else [])
