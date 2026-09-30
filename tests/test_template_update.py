"""Exercise Copier's merge and DataLad recording, including a submodule."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml
from copier import run_copy

from orinoco_lite import template_update
from orinoco_lite.errors import ConfigurationError
from .test_package_update import remote, git


@pytest.fixture
def downstream(tmp_path, remote, monkeypatch):
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Template update test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.invalid")
    url, package_commit = remote
    source = tmp_path / "published"
    (source / "copier.yml").write_text(yaml.safe_dump({
        "_subdirectory": "template", "_skip_if_exists": ["site-specific/**", "extensions/**", "pyproject.toml"],
        "package_repository": {"type": "str", "default": url},
        "package_revision": {"type": "str", "default": package_commit},
        "project_name": {"type": "str", "default": "Example"},
        "include_site_specific": {"type": "bool", "default": True, "when": False},
    }))
    scaffold = source / "template"
    scaffold.mkdir()
    (scaffold / ".copier-answers.yml.jinja").write_text(
        '{{ dict(_copier_answers, _commit=_copier_conf.vcs_ref_hash, include_site_specific=include_site_specific) | to_nice_yaml }}\n')
    (scaffold / "pixi.toml.jinja").write_text(
        '[pypi-dependencies]\norinoco-lite = {git="{{ package_repository }}", rev="{{ package_revision }}"}\n')
    (scaffold / "pixi.lock").write_text("initial lock\n")
    (scaffold / "scaffold.txt").write_text("initial\n")
    (scaffold / "obsolete.txt").write_text("remove me\n")
    (scaffold / "pyproject.toml").write_text("site configuration\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "test: first template")
    git(source, "tag", "v1.0.0")
    old = git(source, "rev-parse", "HEAD")
    root = tmp_path / "downstream"
    subprocess.run(["datalad", "create", "--no-annex", str(root)], check=True)
    run_copy(url, root, vcs_ref=old, defaults=True, data={"project_name": "Retained", "include_site_specific": False})
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", str(source), "site-specific")
    (root / "pyproject.toml").write_text("custom site configuration\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "test: downstream")
    (scaffold / "scaffold.txt").write_text("updated\n")
    (scaffold / "obsolete.txt").unlink()
    (scaffold / "added.txt").write_text("new\n")
    # A later template must not write through the downstream's site-specific
    # submodule during an update.
    (scaffold / "site-specific").mkdir()
    (scaffold / "site-specific" / "site.yaml").write_text("template content\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "test: next template")
    git(source, "tag", "v2.0.0")
    new = git(source, "rev-parse", "HEAD")
    # Isolate the external lock solver; this test exercises actual Copier and
    # DataLad, while end-to-end downstream validation exercises real Pixi.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    solver = bin_dir / "pixi"
    solver.write_text('#!/bin/sh\n[ "$1" = lock ] || exit 2\nprintf "solved lock\\n" > pixi.lock\n')
    solver.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    return root, url, package_commit, old, new


def test_update_records_actual_copier_operation_preserves_submodule_and_replays(downstream, tmp_path, monkeypatch):
    root, url, package_commit, old, new = downstream
    execution_environment = f"{url}@{old}"
    monkeypatch.setenv("ORINOCO_UPDATE_ENVIRONMENT", execution_environment)
    before = git(root, "rev-parse", "HEAD")
    site = git(root, "ls-tree", "HEAD", "site-specific")
    assert template_update.update(root, new) == 0
    assert (root / "scaffold.txt").read_text() == "updated\n"
    assert (root / "added.txt").exists()
    assert not (root / "obsolete.txt").exists()
    assert (root / "pyproject.toml").read_text() == "custom site configuration\n"
    assert git(root, "ls-tree", "HEAD", "site-specific") == site
    assert yaml.safe_load((root / ".copier-answers.yml").read_text())["project_name"] == "Retained"
    assert yaml.safe_load((root / ".copier-answers.yml").read_text())["include_site_specific"] is False
    message = git(root, "log", "-1", "--format=%B")
    assert "orinoco-lite template apply" in message and new in message
    assert execution_environment in message
    tree = git(root, "rev-parse", "HEAD^{tree}")
    recorded = git(root, "rev-parse", "HEAD")
    clone = tmp_path / "replay"
    subprocess.run(["git", "clone", str(root), str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "-c", "protocol.file.allow=always", "submodule", "update", "--init"], check=True)
    subprocess.run(["datalad", "rerun", "--onto", before, recorded], cwd=clone, check=True)
    assert git(clone, "rev-parse", "HEAD^{tree}") == tree
    assert template_update.update(root, new) == 0
    assert git(root, "rev-parse", "HEAD") == recorded


def test_conflicts_are_committed_for_browser_resolution(downstream):
    root, _, _, _, new = downstream
    (root / "scaffold.txt").write_text("site customization\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "test: customize scaffold")
    assert template_update.update(root, new) == 1
    assert "<<<<<<< before updating" in (root / "scaffold.txt").read_text()
    assert git(root, "status", "--porcelain") == ""
    assert template_update.conflicts(root) == ["scaffold.txt"]
    (root / "scaffold.txt").write_text("resolved customization\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "test: resolve in browser")
    assert template_update.update(root, new) == 0


def test_dirty_downstream_is_untouched(downstream):
    root, _, _, _, new = downstream
    (root / "uncommitted").write_text("keep")
    head = git(root, "rev-parse", "HEAD")
    with pytest.raises(ConfigurationError, match="Commit or stash"):
        template_update.update(root, new)
    assert git(root, "rev-parse", "HEAD") == head
    assert (root / "uncommitted").read_text() == "keep"


def test_package_override_is_separate_and_next_update_uses_template_default(downstream):
    root, url, package_commit, old, new = downstream
    assert template_update.update(root, new, package_revision=old) == 0
    assert "package override" in git(root, "log", "-1", "--format=%B")
    assert "update downstream template" in git(root, "log", "-1", "--format=%B", "HEAD^")
    assert yaml.safe_load((root / ".copier-answers.yml").read_text())["package_revision"] == old
    recorded = git(root, "rev-parse", "HEAD")
    assert template_update.update(root, new, package_revision=old) == 0
    assert git(root, "rev-parse", "HEAD") == recorded
    assert template_update.update(root, new) == 0
    assert yaml.safe_load((root / ".copier-answers.yml").read_text())["package_revision"] == package_commit
    assert not template_update.conflicts(root)


def test_git_revert_restores_the_update_without_reverting_site_edits(downstream):
    root, _, _, _, new = downstream
    before = (root / ".copier-answers.yml").read_bytes()
    assert template_update.update(root, new) == 0
    update_commit = git(root, "rev-parse", "HEAD")
    (root / "pyproject.toml").write_text("later site change\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "test: later site change")
    git(root, "revert", "--no-edit", update_commit)
    assert (root / ".copier-answers.yml").read_bytes() == before
    assert (root / "scaffold.txt").read_text() == "initial\n"
    assert (root / "obsolete.txt").exists()
    assert not (root / "added.txt").exists()
    assert (root / "pyproject.toml").read_text() == "later site change\n"


def test_latest_release_uses_copier_tags_not_unreleased_head(downstream):
    root, url, _, _, released = downstream
    source = root.parent / "published"
    git(source, "commit", "--allow-empty", "-qm", "test: unreleased work")
    assert template_update.resolve_template(url, "latest") == released
    git(source, "tag", "v2.1.0rc1")
    assert template_update.resolve_template(url, "latest") == git(source, "rev-parse", "HEAD")
    assert template_update.update(root) == 0
    assert yaml.safe_load((root / ".copier-answers.yml").read_text())["_commit"] == git(source, "rev-parse", "HEAD")


def test_unmerged_template_sha_selects_its_unmerged_package_sha(downstream):
    root, url, _, _, _ = downstream
    source = root.parent / "published"
    git(source, "checkout", "-b", "candidate-package")
    git(source, "commit", "--allow-empty", "-qm", "test: unmerged package candidate")
    package = git(source, "rev-parse", "HEAD")
    git(source, "checkout", "-b", "candidate-template")
    path = source / "copier.yml"
    declaration = yaml.safe_load(path.read_text())
    declaration["package_revision"]["default"] = package
    path.write_text(yaml.safe_dump(declaration))
    git(source, "add", "copier.yml")
    git(source, "commit", "-qm", "test: select unmerged package")
    template = git(source, "rev-parse", "HEAD")
    assert template_update.update(root, template) == 0
    selected = yaml.safe_load((root / ".copier-answers.yml").read_text())
    assert selected["package_revision"] == package
    assert selected["_commit"] == template
    assert "package override" not in git(root, "log", "-1", "--format=%B")
