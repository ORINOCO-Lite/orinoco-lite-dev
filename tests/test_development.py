from pathlib import Path
import subprocess
import tomllib

import pytest
import tomlkit

from orinoco_lite import development as dev
from orinoco_lite.errors import ConfigurationError


def commit(root, message):
    dev.git(root, "add", ".")
    dev.git(root, "commit", "-qm", message)


def repository(path):
    path.mkdir()
    dev.git(path, "init", "-q")
    dev.git(path, "config", "user.name", "Development test")
    dev.git(path, "config", "user.email", "test@example.invalid")
    return path


@pytest.fixture
def downstream(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    client = repository(tmp_path / "client")
    (client / "client.py").write_text("value = 1\n")
    commit(client, "test: client source")
    source = repository(tmp_path / "package")
    (source / "src/orinoco_lite").mkdir(parents=True)
    (source / "src/orinoco_lite/__init__.py").write_text("value = 1\n")
    (source / "pyproject.toml").write_text(
        '[project]\nname = "orinoco-lite"\n'
        '[tool.uv.sources]\n'
        'dump-things-pyclient = {path = "submodules/dump-things-pyclient", editable = true}\n'
    )
    dev.git(source, "submodule", "add", str(client), "submodules/dump-things-pyclient")
    commit(source, "test: package with nested dependency")
    root = repository(tmp_path / "site")
    manifest = tomlkit.parse(
        '[pypi-dependencies]\n# Keep this comment\nother = "==1"\n'
        '[pypi-options]\nindex-strategy = "first-index"\n'
        '[pypi-options.dependency-overrides]\nunrelated = ">=1"\n'
    )
    manifest["pypi-dependencies"]["orinoco-lite"] = {"git": str(source), "rev": dev.git(source, "rev-parse", "HEAD")}
    (root / "pixi.toml").write_text(tomlkit.dumps(manifest))
    (root / "pixi.lock").write_text("original lock\n")
    (root / "page.md").write_text("initial content\n")
    commit(root, "test: pinned package")
    original_run = dev.run

    def run(*args, cwd, env=None):
        if args[0] == "pixi":
            assert args[:2] == ("pixi", "install")
            assert "PIXI_LOCKED" not in env
            (root / "pixi.lock").write_text((root / "pixi.toml").read_text())
        else:
            original_run(*args, cwd=cwd, env=env)

    monkeypatch.setattr(dev, "run", run)
    monkeypatch.setattr(dev, "prepare_resources", lambda checkout: None)
    return root


def read(root):
    return tomllib.loads((root / "pixi.toml").read_text())


def test_enable_initializes_real_submodule_and_nested_dependency(downstream, capfd):
    dev.enable(downstream)
    source = downstream / dev.SUBMODULE
    assert (source / ".git").is_file()
    assert not source.is_symlink()
    assert (source / "submodules/dump-things-pyclient/client.py").is_file()
    assert dev.git(downstream, "ls-files", "--stage", "--", dev.SUBMODULE).startswith("160000 ")
    assert read(downstream)["pypi-dependencies"]["orinoco-lite"] == dev.EDITABLE
    assert read(downstream)["pypi-options"]["dependency-overrides"][dev.CLIENT] == dev.CLIENT_SOURCE
    assert dev.RECOVERY in capfd.readouterr().err


def test_disable_and_reenable_preserve_source_edits_and_downstream_additions(downstream):
    root = downstream
    original = read(root)
    dev.enable(root)
    commit(root, "chore: enable development")
    manifest = tomlkit.parse((root / "pixi.toml").read_text())
    manifest["pypi-dependencies"]["other"] = "==2"
    manifest["pypi-dependencies"]["new-library"] = "*"
    (root / "pixi.toml").write_text(tomlkit.dumps(manifest))
    commit(root, "chore: add downstream dependencies")
    (root / "page.md").write_text("uncommitted site edit\n")
    client = root / dev.SUBMODULE / "submodules/dump-things-pyclient/client.py"
    client.write_text("value = 2\n")
    dev.disable(root)
    result = read(root)
    assert result["pypi-dependencies"]["orinoco-lite"] == original["pypi-dependencies"]["orinoco-lite"]
    assert result["pypi-dependencies"]["other"] == "==2"
    assert result["pypi-dependencies"]["new-library"] == "*"
    assert result["pypi-options"] == original["pypi-options"]
    assert client.read_text() == "value = 2\n"
    assert (root / "page.md").read_text() == "uncommitted site edit\n"
    assert "# Keep this comment" in (root / "pixi.toml").read_text()
    commit(root, "chore: disable development")
    dev.enable(root)
    assert client.read_text() == "value = 2\n"


def test_repeat_cycle_restores_most_recent_package_selection(downstream):
    dev.enable(downstream)
    commit(downstream, "chore: enable development")
    dev.disable(downstream)
    doc = tomlkit.parse((downstream / "pixi.toml").read_text())
    doc["pypi-dependencies"]["orinoco-lite"]["rev"] = "new-package-selection"
    (downstream / "pixi.toml").write_text(tomlkit.dumps(doc))
    commit(downstream, "chore: select another package")
    dev.enable(downstream)
    commit(downstream, "chore: enable again")
    dev.disable(downstream)
    assert read(downstream)["pypi-dependencies"]["orinoco-lite"]["rev"] == "new-package-selection"


def test_restores_preexisting_client_override(downstream):
    doc = tomlkit.parse((downstream / "pixi.toml").read_text())
    doc["pypi-options"]["dependency-overrides"][dev.CLIENT] = ">=0.3"
    (downstream / "pixi.toml").write_text(tomlkit.dumps(doc))
    commit(downstream, "test: previous override")
    dev.enable(downstream)
    commit(downstream, "chore: enable")
    dev.disable(downstream)
    assert read(downstream)["pypi-options"]["dependency-overrides"][dev.CLIENT] == ">=0.3"


def test_restoration_uses_lock_immediately_before_enable(downstream):
    # A lock-only update must not be lost by looking only at manifest commits.
    (downstream / "pixi.lock").write_text("newer dependency resolution\n")
    commit(downstream, "chore: refresh lock")
    dev.enable(downstream)
    commit(downstream, "chore: enable")
    _, lock = dev.previous_environment(downstream)
    assert lock == "newer dependency resolution\n"


@pytest.mark.parametrize("action", ["enable", "disable"])
def test_failed_install_restores_manifest_and_lock_without_removing_sources(downstream, monkeypatch, action):
    if action == "disable":
        dev.enable(downstream)
        commit(downstream, "chore: enable")
    before = {name: (downstream / name).read_bytes() for name in dev.FILES}
    original_run = dev.run

    def fail(*args, cwd, env=None):
        if args[0] == "pixi":
            (downstream / "pixi.lock").write_text("partial solve")
            raise subprocess.CalledProcessError(1, "pixi")
        original_run(*args, cwd=cwd, env=env)

    monkeypatch.setattr(dev, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        getattr(dev, action)(downstream)
    assert {name: (downstream / name).read_bytes() for name in dev.FILES} == before
    assert (downstream / dev.SUBMODULE / ".git").is_file()


def test_disable_requires_committed_enable_and_rejects_changed_override(downstream):
    dev.enable(downstream)
    with pytest.raises(ConfigurationError, match="Commit or stash"):
        dev.disable(downstream)
    doc = tomlkit.parse((downstream / "pixi.toml").read_text())
    doc["pypi-options"]["dependency-overrides"][dev.CLIENT] = "==0.1"
    (downstream / "pixi.toml").write_text(tomlkit.dumps(doc))
    commit(downstream, "test: changed managed override")
    before = (downstream / "pixi.toml").read_bytes()
    with pytest.raises(ConfigurationError, match="selection changed"):
        dev.disable(downstream)
    assert (downstream / "pixi.toml").read_bytes() == before


def test_enable_rejects_source_checkout_and_symlink(downstream):
    (downstream / "src/orinoco_lite").mkdir(parents=True)
    with pytest.raises(ConfigurationError, match="Run 'dev enable'"):
        dev.enable(downstream)
    (downstream / "src/orinoco_lite").rmdir()
    source = downstream / dev.SUBMODULE
    source.parent.mkdir()
    source.symlink_to(downstream.parent / "package")
    with pytest.raises(ConfigurationError, match="real Git submodule"):
        dev.enable(downstream)


def test_switch_relaxes_lock_only_for_child_install(downstream, monkeypatch):
    monkeypatch.setenv("PIXI_LOCKED", "true")
    dev.enable(downstream)
    assert dev.os.environ["PIXI_LOCKED"] == "true"
    commit(downstream, "chore: enable")
    dev.disable(downstream)
    assert dev.os.environ["PIXI_LOCKED"] == "true"
