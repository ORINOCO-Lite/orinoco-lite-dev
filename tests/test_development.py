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
    adapter = root / ".orinoco-lite/hugo-adapter/layouts/example.html"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("tracked adapter\n")
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


def test_enable_clones_nested_sources_without_registering_or_staging(downstream, capfd):
    original = read(downstream)
    dev.enable(downstream)
    source = downstream / dev.CHECKOUT
    assert (source / ".git").is_dir()
    assert (source / "submodules/dump-things-pyclient/client.py").is_file()
    assert dev.git(downstream, "ls-files", ".orinoco-lite") == ".orinoco-lite/hugo-adapter/layouts/example.html"
    assert not (downstream / ".gitmodules").exists()
    assert not dev.git(downstream, "diff", "--cached", "--name-only")
    assert dev.git(downstream, "check-ignore", dev.CHECKOUT) == dev.CHECKOUT
    assert read(downstream)["pypi-dependencies"]["orinoco-lite"] == dev.EDITABLE
    assert read(downstream)["pypi-options"] == original["pypi-options"]
    assert "no files were staged" in capfd.readouterr().err


def test_reenable_preserves_uncommitted_sources_and_downstream_dependencies(downstream):
    dev.enable(downstream)
    doc = tomlkit.parse((downstream / "pixi.toml").read_text())
    doc["pypi-dependencies"]["new-library"] = "*"
    (downstream / "pixi.toml").write_text(tomlkit.dumps(doc))
    client = downstream / dev.CHECKOUT / "submodules/dump-things-pyclient/client.py"
    client.write_text("value = 2\n")
    dev.enable(downstream)
    assert client.read_text() == "value = 2\n"
    assert read(downstream)["pypi-dependencies"]["new-library"] == "*"
    assert not dev.git(downstream, "diff", "--cached", "--name-only")


def test_failed_install_restores_uncommitted_manifest_and_lock(downstream, monkeypatch):
    manifest = downstream / "pixi.toml"
    manifest.write_text(manifest.read_text() + "\n# local change\n")
    before = {name: (downstream / name).read_bytes() for name in dev.FILES}
    original_run = dev.run

    def fail(*args, cwd, env=None):
        if args[0] == "pixi":
            (downstream / "pixi.lock").write_text("partial solve")
            raise subprocess.CalledProcessError(1, "pixi")
        original_run(*args, cwd=cwd, env=env)

    monkeypatch.setattr(dev, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        dev.enable(downstream)
    assert {name: (downstream / name).read_bytes() for name in dev.FILES} == before
    assert (downstream / dev.CHECKOUT / ".git").is_dir()


def test_enable_rejects_source_checkout_and_symlink(downstream):
    (downstream / "src/orinoco_lite").mkdir(parents=True)
    with pytest.raises(ConfigurationError, match="Run 'dev enable'"):
        dev.enable(downstream)
    (downstream / "src/orinoco_lite").rmdir()
    source = downstream / dev.CHECKOUT
    source.parent.mkdir(exist_ok=True)
    source.symlink_to(downstream.parent / "package")
    with pytest.raises(ConfigurationError, match="real source checkout"):
        dev.enable(downstream)


def test_enable_relaxes_lock_only_for_child_install(downstream, monkeypatch):
    monkeypatch.setenv("PIXI_LOCKED", "true")
    dev.enable(downstream)
    assert dev.os.environ["PIXI_LOCKED"] == "true"


def test_disable_is_not_a_command():
    from orinoco_lite.cli import main
    with pytest.raises(SystemExit) as error:
        main(["dev", "disable"])
    assert error.value.code == 2
