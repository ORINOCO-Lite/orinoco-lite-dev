from pathlib import Path
import subprocess
import tomllib

import pytest

from orinoco_lite import package_update
from orinoco_lite.errors import ConfigurationError


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.fixture
def remote(tmp_path, monkeypatch):
    source = tmp_path / "published"
    source.mkdir()
    git(source, "init", "-q")
    git(source, "config", "user.name", "Test")
    git(source, "config", "user.email", "test@example.invalid")
    (source / "README").write_text("Published fixture\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "test: published revision")
    commit = git(source, "rev-parse", "HEAD")
    git(source, "tag", "release-fixture")
    url = "https://package-fixture.invalid/published.git"
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{source.as_uri()}.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", url)
    yield url, commit


def test_remote_tag_resolves_to_commit_and_unknown_commit_fails(remote):
    url, commit = remote
    assert package_update.resolve_commit(url, "release-fixture") == commit
    assert package_update.resolve_commit(url, commit) == commit
    with pytest.raises(ConfigurationError, match="Use a full commit SHA"):
        package_update.resolve_commit(url, "f" * 40)


def test_local_repositories_are_not_treated_as_published(tmp_path):
    for value in (str(tmp_path), "../local", tmp_path.as_uri(), "git://example.org/repo.git"):
        with pytest.raises(ConfigurationError, match="remote"):
            package_update.remote_url(value)
    assert package_update.remote_url("git@github.com:owner/repo.git") == "ssh://git@github.com/owner/repo.git"


def test_update_pins_resolved_commit_preserves_other_settings_and_restores_on_failure(tmp_path, monkeypatch):
    root = tmp_path
    manifest = root / "pixi.toml"
    manifest.write_text('[pypi-dependencies]\n# retained comment\norinoco-lite = {git="https://example.org/repo",rev="old"}\nother="==1"\n')
    lock = root / "pixi.lock"
    lock.write_text("old lock\n")
    commit = "a" * 40
    selected = []
    monkeypatch.setattr(package_update, "resolve_commit", lambda repo, rev: selected.append((repo, rev)) or commit)
    before = manifest.read_bytes(), lock.read_bytes()
    assert package_update.update(root, "v-next", check=True) == commit
    assert (manifest.read_bytes(), lock.read_bytes()) == before
    def fail(command, **kwargs):
        assert command == ["pixi", "lock", "--manifest-path", "pixi.toml"]
        lock.write_text("partial lock")
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(package_update.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        package_update.update(root, "v-next")
    assert (manifest.read_bytes(), lock.read_bytes()) == before
    def solve(command, **kwargs):
        lock.write_text("solved lock")
    monkeypatch.setattr(package_update.subprocess, "run", solve)
    package_update.update(root, "v-next")
    dependencies = tomllib.loads(manifest.read_text())["pypi-dependencies"]
    assert dependencies["orinoco-lite"] == {"git": "https://example.org/repo", "rev": commit}
    assert dependencies["other"] == "==1"
    assert "# retained comment" in manifest.read_text()
    assert selected == [("https://example.org/repo", "v-next")] * 3


def test_unfetchable_revision_leaves_selection_untouched(tmp_path, monkeypatch):
    manifest = tmp_path / "pixi.toml"
    manifest.write_text('[pypi-dependencies]\norinoco-lite="*"\n')
    before = manifest.read_bytes()
    def unavailable(*args):
        raise ConfigurationError("not published")
    monkeypatch.setattr(package_update, "resolve_commit", unavailable)
    with pytest.raises(ConfigurationError, match="not published"):
        package_update.update(tmp_path, "private")
    assert manifest.read_bytes() == before
    assert not (tmp_path / "pixi.lock").exists()


def test_transform_refuses_stale_installed_package(tmp_path, monkeypatch):
    from orinoco_lite import cli
    commit = 'a' * 40
    (tmp_path / 'pixi.toml').write_text('[pypi-dependencies]\norinoco-lite={git="https://example.org/fork.git",rev="' + commit + '"}\n')
    monkeypatch.setattr(package_update, 'installed_git_source', lambda: ('ssh://git@example.org/fork.git', commit))
    package_update.check_environment(tmp_path)
    monkeypatch.setattr(package_update, 'installed_git_source', lambda: ('https://example.org/fork.git', 'b' * 40))
    with pytest.raises(SystemExit, match='2'):
        cli.main(['--root', str(tmp_path), 'dev', 'records', 'jsonl-to-yaml'])
    assert not (tmp_path / 'upstream-diffing').exists()
