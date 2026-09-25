from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from orinoco_lite import publication
from orinoco_lite.publication import PublicationError, prepare, publish, record_projection


BUNDLE = "build/pages-publication.bundle"


def git(root, *args, check=True):
    result = subprocess.run(["git", *map(str, args)], cwd=root, text=True,
                            capture_output=True, check=check)
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path, monkeypatch):
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Publication Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "publication@example.invalid")
    root = tmp_path / "site"
    root.mkdir()
    git(root, "init", "-b", "main")
    (root / ".gitignore").write_text("/build/\n/generated/\n")
    (root / "input.txt").write_text("first\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "feat: add site source")
    remote = tmp_path / "remote.git"
    git(root, "init", "--bare", remote)
    git(root, "remote", "add", "origin", remote)
    git(root, "push", "origin", "main")
    # Exercise real DataLad/Git recording with a small deterministic projection
    # executable; the full package projection is covered by candidate builds.
    binaries = tmp_path / "bin"
    binaries.mkdir()
    executable = binaries / "orinoco-lite"
    executable.write_text(
        '#!/bin/sh\nset -eu\n'
        'mkdir -p generated/projection/content\n'
        'cp input.txt generated/projection/records.jsonl\n'
        'cp input.txt generated/projection/content/_index.md\n'
    )
    executable.chmod(0o755)
    annex = binaries / "git-annex"
    annex.write_text(f'#!/bin/sh\ntouch "{tmp_path}/annex-called"\nexit 99\n')
    annex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binaries}{os.pathsep}{os.environ['PATH']}")
    yield root, remote
    assert not (tmp_path / "annex-called").exists()


def prepare_build(root):
    projection = record_projection(root)
    site = root / "build/pages"
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text((root / "input.txt").read_text())
    prepare(root, projection, "build/pages", BUNDLE)
    return projection


def advance(root, text):
    (root / "input.txt").write_text(text)
    git(root, "add", "input.txt")
    git(root, "commit", "-m", "feat: update source")


def test_projection_is_one_datalad_commit_and_can_be_replayed(repository, tmp_path):
    root, remote = repository
    source = git(root, "rev-parse", "HEAD")
    projection = prepare_build(root)
    publish(root, BUNDLE)
    assert git(remote, "rev-parse", "latest-hugo-projection^") == source
    message = git(remote, "show", "-s", "--format=%B", projection)
    record = json.loads(message.split("=== Do not change lines below ===\n")[1]
                        .split("\n^^^ Do not change lines above ^^^")[0])
    assert "orinoco-lite projection update --no-cache" in record["cmd"]
    assert record["inputs"] == ["."]
    assert record["outputs"] == ["generated/projection"]
    assert git(remote, "show", f"{projection}:generated/projection/records.jsonl") == "first"
    assert git(root, "rev-parse", "HEAD") == source
    assert not git(root, "status", "--porcelain", "--untracked-files=no")
    assert git(remote, "merge-base", "main", "gh-pages", check=False) == ""
    assert git(remote, "ls-tree", "-r", "--name-only", "gh-pages") == "index.html"

    clone = tmp_path / "replay"
    git(root, "clone", remote, clone)
    git(clone, "checkout", "--detach", "origin/latest-hugo-projection")
    expected = git(clone, "rev-parse", "HEAD:generated/projection")
    # A new location with none of the publication checkout's caches or outputs.
    subprocess.run(["datalad", "rerun", "--report", "HEAD"], cwd=clone, check=True, capture_output=True)
    git(clone, "checkout", "--detach", source)
    subprocess.run(["datalad", "rerun", "--onto", "", projection], cwd=clone,
                   check=True, capture_output=True)
    assert git(clone, "rev-parse", "HEAD:generated/projection") == expected


@pytest.mark.parametrize("limit", [1, 3])
def test_latest_successful_snapshots_are_bounded_and_keep_their_trees(repository, limit):
    root, remote = repository
    trees = []
    for index in range(5):
        advance(root, str(index))
        prepare_build(root)
        # Merely building does not change the last successful publication.
        if trees:
            assert git(remote, "rev-parse", "gh-pages^{tree}") == trees[-1]
        publish(root, BUNDLE, limit)
        trees.append(git(remote, "rev-parse", "gh-pages^{tree}"))
        assert git(remote, "log", "--format=%T", "gh-pages").splitlines() == trees[-limit:][::-1]
    before = git(remote, "rev-parse", "gh-pages")
    publish(root, BUNDLE, limit)
    assert git(remote, "rev-parse", "gh-pages") == before
    publish(root, BUNDLE, 1)
    assert git(remote, "rev-list", "--count", "gh-pages") == "1"


def test_old_source_linked_history_is_detached(repository):
    root, remote = repository
    projection = prepare_build(root)
    tree = git(root, "rev-parse", f"{projection}^{{tree}}")
    old = git(root, "commit-tree", tree, "-p", projection, "-m",
              f"chore(pages): publish generated site\n\nProjection-Commit: {projection}")
    git(root, "push", "origin", f"{old}:refs/heads/gh-pages")
    prepare_build(root)
    publish(root, BUNDLE)
    assert git(remote, "rev-list", "--count", "gh-pages") == "2"
    assert git(remote, "rev-parse", "gh-pages~1^{tree}") == tree
    assert not git(remote, "merge-base", "main", "gh-pages", check=False)


def test_failed_projection_or_dirty_source_leaves_published_refs_alone(repository):
    root, remote = repository
    prepare_build(root)
    publish(root, BUNDLE)
    refs = git(remote, "show-ref")
    advance(root, "second")
    executable = Path(os.environ["PATH"].split(os.pathsep)[0]) / "orinoco-lite"
    executable.write_text("#!/bin/sh\nexit 7\n")
    with pytest.raises(PublicationError):
        record_projection(root)
    assert git(remote, "show-ref") == refs
    (root / "input.txt").write_text("dirty")
    with pytest.raises(PublicationError, match="Tracked worktree changes"):
        record_projection(root)


def test_wrong_source_and_invalid_limit_do_not_publish(repository):
    root, remote = repository
    prepare_build(root)
    refs = git(remote, "show-ref")
    with pytest.raises(PublicationError, match="at least 1"):
        publish(root, BUNDLE, 0)
    advance(root, "new source")
    with pytest.raises(PublicationError, match="does not belong to this source"):
        publish(root, BUNDLE)
    assert git(remote, "show-ref") == refs


def test_atomic_push_rejection_keeps_both_previous_refs(repository):
    root, remote = repository
    prepare_build(root)
    publish(root, BUNDLE)
    refs = git(remote, "show-ref")
    advance(root, "second")
    prepare_build(root)
    hook = remote / "hooks/update"
    hook.write_text('#!/bin/sh\n[ "$1" != "refs/heads/gh-pages" ]\n')
    hook.chmod(0o755)
    with pytest.raises(PublicationError):
        publish(root, BUNDLE)
    assert git(remote, "show-ref") == refs


def test_concurrent_remote_change_is_not_overwritten(repository, monkeypatch):
    root, remote = repository
    prepare_build(root)
    publish(root, BUNDLE)
    old_projection = git(remote, "rev-parse", "latest-hugo-projection")
    advance(root, "second")
    prepare_build(root)
    original = publication._run
    raced = []

    def run(command, **kwargs):
        if command[:2] == ["git", "push"]:
            tree = git(remote, "rev-parse", "gh-pages^{tree}")
            commit = git(remote, "commit-tree", tree, "-p", "gh-pages", "-m", "another publication")
            git(remote, "update-ref", "refs/heads/gh-pages", commit)
            raced.append(commit)
        return original(command, **kwargs)

    monkeypatch.setattr(publication, "_run", run)
    with pytest.raises(PublicationError):
        publish(root, BUNDLE)
    assert git(remote, "rev-parse", "gh-pages") == raced[0]
    assert git(remote, "rev-parse", "latest-hugo-projection") == old_projection


def test_projection_uses_checked_out_submodule_without_remote_access(repository):
    root, _ = repository
    metadata = root.parent / "metadata"
    metadata.mkdir()
    git(metadata, "init")
    (metadata / "record.txt").write_text("submodule input")
    git(metadata, "add", ".")
    git(metadata, "commit", "-m", "feat: add metadata")
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", metadata, "site-specific")
    git(root, "config", "-f", ".gitmodules", "submodule.site-specific.url", "https://unavailable.invalid/metadata.git")
    git(root, "add", ".")
    git(root, "commit", "-m", "feat: select metadata")
    executable = Path(os.environ["PATH"].split(os.pathsep)[0]) / "orinoco-lite"
    executable.write_text(executable.read_text().replace("cp input.txt", "cp site-specific/record.txt"))
    projection = record_projection(root)
    assert git(root, "show", f"{projection}:generated/projection/records.jsonl") == "submodule input"
    assert git(root, "rev-parse", f"{projection}:site-specific") == git(metadata, "rev-parse", "HEAD")
