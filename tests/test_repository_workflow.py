"""Exercise branch integration with real Git histories and rewritten merges."""
from pathlib import Path
import subprocess

import pytest

from orinoco_lite import repository_workflow as worker


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def commit(root, name, content):
    (root / name).write_text(content)
    git(root, "add", name)
    git(root, "commit", "-qm", "test: fixture change")
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repositories(tmp_path, monkeypatch):
    paths = {}
    for name in ("website", "metadata"):
        root = tmp_path / name
        root.mkdir()
        git(root, "init", "-q", "--initial-branch=main")
        git(root, "config", "user.name", "Fixture")
        git(root, "config", "user.email", "fixture@example.invalid")
        commit(root, "README.md", "initial\n")
        remote = tmp_path / f"{name}.git"
        git(tmp_path, "clone", "--quiet", "--bare", str(root), str(remote))
        git(root, "remote", "add", "origin", str(remote))
        paths[name] = root, remote
    original = worker.git

    def local_git(root, *arguments, **options):
        arguments = tuple(
            str(paths[arg.split("/")[-1][:-4]][1])
            if arg.startswith("https://github.com/fixture/") else arg
            for arg in arguments
        )
        return original(root, *arguments, **options)

    monkeypatch.setattr(worker, "git", local_git)
    return paths


ENV = worker.identity({"submitter": {"id": 1, "login": "fixture"}}, "2026-01-01T00:00:00Z")


def test_materialized_bundle_can_be_exported_again(repositories, tmp_path):
    root, _ = repositories["metadata"]
    worker.bundle(root, tmp_path / "input.bundle")
    restored = tmp_path / "restored"
    worker.restore_bundle(tmp_path / "input.bundle", restored)
    (restored / "record.yaml").write_text("name: edited\n")
    worker.git(restored, "add", "record.yaml")
    worker.git(restored, "commit", "-qm", "test: materialized edit", environment=ENV)
    expected = worker.git(restored, "rev-parse", "HEAD")
    worker.bundle(restored, tmp_path / "result.bundle")
    worker.restore_bundle(tmp_path / "result.bundle", tmp_path / "result")
    assert worker.git(tmp_path / "result", "rev-parse", "HEAD") == expected
    assert (tmp_path / "result/record.yaml").read_text() == "name: edited\n"


def test_integration_preserves_concurrent_work_and_is_repeatable(repositories):
    root, remote = repositories["metadata"]
    base = git(root, "rev-parse", "HEAD")
    proposed = commit(root, "record.yaml", "name: proposed\n")
    git(root, "checkout", "--quiet", "--detach", base)
    commit(root, "README.md", "concurrent website work\n")
    git(root, "push", "--quiet", "origin", "HEAD:refs/heads/proposal")
    git(root, "checkout", "--quiet", "--detach", proposed)
    result = worker.integrate(root, "fixture/metadata", "proposal", "fixture-token", ENV)
    assert git(remote, "show", "proposal:README.md") == "concurrent website work"
    assert git(remote, "show", "proposal:record.yaml") == "name: proposed"
    git(root, "checkout", "--quiet", "--detach", proposed)
    assert worker.integrate(root, "fixture/metadata", "proposal", "fixture-token", ENV) == result


def test_conflict_does_not_overwrite_the_remote(repositories):
    root, remote = repositories["metadata"]
    base = git(root, "rev-parse", "HEAD")
    proposed = commit(root, "README.md", "proposed\n")
    git(root, "checkout", "--quiet", "--detach", base)
    concurrent = commit(root, "README.md", "concurrent\n")
    git(root, "push", "--quiet", "origin", "HEAD:refs/heads/proposal")
    git(root, "checkout", "--quiet", "--detach", proposed)
    with pytest.raises(RuntimeError, match="conflicts"):
        worker.integrate(root, "fixture/metadata", "proposal", "fixture-token", ENV)
    assert git(remote, "rev-parse", "proposal") == concurrent


@pytest.mark.parametrize("merge_method", ["merge", "squash", "rebase"])
def test_metadata_merge_preserves_website_edits(repositories, merge_method):
    metadata, metadata_remote = repositories["metadata"]
    base = git(metadata, "rev-parse", "HEAD")
    proposal = commit(metadata, "record.yaml", "name: edited\n")
    git(metadata, "branch", "proposal", proposal)
    git(metadata, "checkout", "--quiet", "--detach", base)
    target = commit(metadata, "unrelated.yaml", "name: other work\n")
    if merge_method == "merge":
        git(metadata, "merge", "--no-edit", proposal)
    elif merge_method == "squash":
        git(metadata, "merge", "--squash", proposal)
        git(metadata, "commit", "-qm", "test: squash metadata")
    else:
        git(metadata, "checkout", "--quiet", "--detach", proposal)
        git(metadata, "rebase", "--onto", target, base)
    merged = git(metadata, "rev-parse", "HEAD")
    git(metadata, "push", "--quiet", "origin", "HEAD:refs/heads/main", "proposal")

    website, website_remote = repositories["website"]
    (website / ".gitmodules").write_text(
        '[submodule "site-specific"]\npath = site-specific\nurl = https://github.com/fixture/metadata.git\n')
    git(website, "add", ".gitmodules")
    git(website, "update-index", "--add", "--cacheinfo", f"160000,{proposal},site-specific")
    git(website, "commit", "-qm", "test: propose metadata gitlink")
    git(website, "push", "--quiet", "origin", "HEAD:refs/heads/proposal")
    commit(website, "README.md", "retain this concurrent website edit\n")
    git(website, "push", "--quiet", "origin", "HEAD:refs/heads/proposal")
    git(website, "clone", "--quiet", str(metadata_remote), "site-specific")
    result = worker.advance_gitlink(website, "fixture/website", "proposal", "website-token",
        "fixture/metadata", "metadata-token", proposal, merged, ENV)
    assert merged in git(website_remote, "ls-tree", result, "site-specific")
    assert git(website_remote, "show", f"{result}:README.md") == "retain this concurrent website edit"
    assert worker.advance_gitlink(website, "fixture/website", "proposal", "website-token",
        "fixture/metadata", "metadata-token", proposal, merged, ENV) == result


def test_private_input_cannot_be_processed_in_website_job(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "fixture/website")
    with pytest.raises(RuntimeError, match="keep private input"):
        worker.require_input_owner({"input_repository": "fixture/metadata"})


def test_materialization_refuses_a_job_with_oidc(tmp_path, monkeypatch):
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "fixture-oidc")
    with pytest.raises(RuntimeError, match="without credentials"):
        worker.materialize(tmp_path)


def test_copied_receipt_cannot_select_another_submission(repositories):
    import hashlib
    import json
    root, remote = repositories['metadata']
    value = json.dumps({'operation': 'shacl', 'bundle': {'source_commit': 'a' * 40}})
    (root / '.orinoco-lite').mkdir()
    commit_sha = commit(root, '.orinoco-lite/submission.json', value + '\n')
    git(root, 'push', '--quiet', 'origin', 'HEAD:refs/heads/input')
    authorization = {'input_repository': 'fixture/metadata', 'input_commit': commit_sha,
                     'scope': {'source': {'repository': 'fixture/website', 'commit': 'a' * 40}}}
    branch = 'orinoco/submissions/' + hashlib.sha256(('fixture/website\n' + value + '\n').encode()).hexdigest()
    assert worker.read_input(root, authorization, branch, 'fixture-token')['operation'] == 'shacl'
    with pytest.raises(RuntimeError, match='does not identify'):
        worker.read_input(root, authorization, 'orinoco/submissions/' + '0' * 64, 'fixture-token')


def test_completion_reuses_merged_pr_when_nothing_remains(monkeypatch):
    pull = {'state': 'closed', 'merged_at': '2026-01-01', 'html_url': 'https://example.invalid/pr'}
    monkeypatch.setattr(worker, 'find_pull', lambda *args: pull)
    monkeypatch.setattr(worker, 'api', lambda repository, path, token: {'files': []})
    assert worker.ensure_pull({'name': 'fixture/website', 'defaultBranch': 'main'},
                              'proposal', 'fixture-token', 'Fixture') == pull


def test_closed_unmerged_pr_is_not_reopened(monkeypatch):
    pull = {'state': 'closed', 'merged_at': None, 'html_url': 'https://example.invalid/pr'}
    monkeypatch.setattr(worker, 'find_pull', lambda *args: pull)
    with pytest.raises(RuntimeError, match='already closed'):
        worker.ensure_pull({'name': 'fixture/website', 'defaultBranch': 'main'},
                           'proposal', 'fixture-token', 'Fixture')
