from pathlib import Path
import subprocess
import tomllib

import pytest

from orinoco_lite import development as dev
from orinoco_lite.errors import ConfigurationError


def commit(root, message):
    for args in (("add", "."), ("commit", "-qm", message)):
        subprocess.run(["git", "-C", str(root), *args], check=True)


@pytest.fixture
def downstream(tmp_path, monkeypatch):
    root = tmp_path / "site"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid")):
        subprocess.run(["git", "-C", str(root), "config", key, value], check=True)
    (root / "pixi.toml").write_text('[pypi-dependencies]\n# Keep this comment\norinoco-lite = { git = "https://example.invalid/package", rev = "abc" }\nother = "==1"\n')
    (root / "pixi.lock").write_text("original lock\n")
    (root / "page.md").write_text("initial content\n")
    commit(root, "test: initial selection")
    def install(*args, cwd):
        assert args[0:2] == ("pixi", "install")
        (root / "pixi.lock").write_text((root / "pixi.toml").read_text())
    monkeypatch.setattr(dev, "run", install)
    return root


def test_disable_preserves_site_edits_and_intervening_dependencies(downstream):
    root = downstream
    before = tomllib.loads((root / "pixi.toml").read_text())["pypi-dependencies"]["orinoco-lite"]
    dev.apply(root, "enable", root.parent / "orinoco-lite-dev")
    commit(root, "chore: enable editable Orinoco Lite")
    manifest = root / "pixi.toml"
    manifest.write_text(manifest.read_text().replace('other = "==1"', 'other = "==2"'))
    commit(root, "chore: update another dependency")
    (root / "page.md").write_text("uncommitted human edit\n")
    dev.check_workspace(root)
    dev.apply(root, "disable", None)
    dependencies = tomllib.loads(manifest.read_text())["pypi-dependencies"]
    assert dependencies["orinoco-lite"] == before
    assert dependencies["other"] == "==2"
    assert "# Keep this comment" in manifest.read_text()
    assert (root / "page.md").read_text() == "uncommitted human edit\n"
    assert not (root / dev.LINK).is_symlink()
    assert 'other = "==2"' in (root / "pixi.lock").read_text()


def test_failed_install_restores_connection_files(downstream, monkeypatch):
    root = downstream
    before = (root / "pixi.toml").read_bytes()
    def fail(*args, cwd):
        (root / "pixi.lock").write_text("partial solve")
        raise subprocess.CalledProcessError(1, "pixi")
    monkeypatch.setattr(dev, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        dev.apply(root, "enable", root.parent / "orinoco-lite-dev")
    assert (root / "pixi.toml").read_bytes() == before
    assert (root / "pixi.lock").read_text() == "original lock\n"
    assert not (root / dev.LINK).is_symlink()


def test_disable_refuses_changed_package_selection(downstream):
    root = downstream
    dev.apply(root, "enable", root.parent / "orinoco-lite-dev")
    commit(root, "chore: enable editable Orinoco Lite")
    manifest = root / "pixi.toml"
    manifest.write_text(manifest.read_text().replace('editable = true', 'editable = false'))
    before = manifest.read_bytes()
    with pytest.raises(ConfigurationError, match="connection changed"):
        dev.apply(root, "disable", None)
    assert manifest.read_bytes() == before
    assert (root / dev.LINK).is_symlink()


def test_enable_defaults_to_sibling_and_clones_when_missing(downstream, monkeypatch):
    root = downstream
    checkout = root.parent / "orinoco-lite-dev"
    calls = []
    def run(*args, cwd):
        calls.append(args)
        if args[:2] == ("git", "clone"):
            (checkout / "src/orinoco_lite").mkdir(parents=True)
            (checkout / "pyproject.toml").write_text('[project]\nname = "orinoco-lite"\n')
    monkeypatch.setattr(dev, "run", run)
    monkeypatch.setattr(dev, "record", lambda root, action, path: calls.append((action, path)))
    dev.enable(root)
    assert calls[0] == ("git", "clone", dev.PACKAGE_REPOSITORY, checkout)
    assert ("enable", checkout) in calls
    assert calls[-1][-3:] == ("orinoco-lite", "dev", "prepare-resources")


def test_dirty_connection_files_are_not_overwritten(downstream):
    manifest = downstream / "pixi.toml"
    manifest.write_text(manifest.read_text() + "# pending edit\n")
    with pytest.raises(ConfigurationError, match="Commit or discard"):
        dev.check_workspace(downstream)
