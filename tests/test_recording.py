import argparse
from pathlib import Path
import subprocess

import pytest

from orinoco_lite import pool_capture, recording
from orinoco_lite.errors import ConfigurationError


def mock_pixi(monkeypatch, callback):
    original = subprocess.run

    def run(command, **kwargs):
        if command[0] == "git":
            return original(command, **kwargs)
        return callback(command, **kwargs)

    monkeypatch.setattr(recording.subprocess, "run", run)


@pytest.fixture
def downstream(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "pixi.toml").write_text('[workspace]\nname = "site"\n')
    (root / "pixi.lock").write_text("version: 6\n")
    return root


def test_recording_uses_public_cli_relative_paths_and_locked_environment(downstream, monkeypatch):
    calls = []
    mock_pixi(monkeypatch, lambda command, **kwargs: calls.append((command, kwargs)))
    capture = downstream / "site-specific/sources/pool/records.jsonl"
    recording.record(
        downstream,
        ["dev", "records", "get", "site-specific/sources/pool/records.jsonl", "--no-record"],
        inputs=("pixi.toml",), outputs=(capture, str(capture) + ".manifest.json"),
        message="chore: capture public Pool records",
    )
    command, options = calls[0]
    assert command[:8] == [
        "pixi", "run", "--locked", "python", "-c",
        "from datalad.cli.main import main; main()", "run", "--explicit",
    ]
    separator = command.index("--")
    assert command[separator + 1:] == [
        "pixi", "run", "--locked", "orinoco-lite", "dev", "records", "get",
        "site-specific/sources/pool/records.jsonl", "--no-record",
    ]
    assert command.count("pixi.toml") == 1
    assert "pixi.lock" in command
    assert "site-specific/sources/pool/records.jsonl.manifest.json" in command
    assert all(str(downstream) not in argument for argument in command)
    assert options == {"cwd": downstream, "check": True}


@pytest.mark.parametrize("path", ["../outside.jsonl", ".git/config", "."])
def test_recording_refuses_outputs_outside_operation_boundary(downstream, monkeypatch, path):
    mock_pixi(monkeypatch, lambda *args, **kwargs: pytest.fail("must not start a command"))
    with pytest.raises(ConfigurationError, match="Recorded paths|operation-owned"):
        recording.record(downstream, ["dev", "records", "get", path, "--no-record"],
                         outputs=(path,), message="test: blocked")


def test_recording_refuses_an_output_through_an_external_symlink(downstream, tmp_path):
    (downstream / "outside").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ConfigurationError, match="must remain inside"):
        recording.relative_path(downstream, "outside/capture.jsonl")


def test_recording_preserves_linked_read_only_input_but_rejects_linked_output(downstream, tmp_path, monkeypatch):
    checkout = tmp_path / "source"
    checkout.mkdir()
    (checkout / "input.json").write_text("{}")
    (downstream / "source").symlink_to(Path("../source"), target_is_directory=True)
    calls = []
    mock_pixi(monkeypatch, lambda command, **kwargs: calls.append(command))
    recording.record(downstream, ["dev", "example", "--no-record"],
                     inputs=("source/input.json",), outputs=("result.json",), message="test: read source")
    assert "source/input.json" in calls[0]
    assert str(checkout) not in " ".join(calls[0])
    with pytest.raises(ConfigurationError, match="must remain inside"):
        recording.record(downstream, ["dev", "example", "--no-record"],
                         outputs=("source/result.json",), message="test: reject escape")


def test_recording_requires_a_lock_and_prevents_nested_recording(downstream, monkeypatch):
    mock_pixi(monkeypatch, lambda *args, **kwargs: pytest.fail("must not start a command"))
    with pytest.raises(ConfigurationError, match="include --no-record"):
        recording.record(downstream, ["dev", "records", "get", "capture.jsonl"],
                         outputs=("capture.jsonl",), message="test: blocked")
    (downstream / "pixi.lock").unlink()
    with pytest.raises(ConfigurationError, match="requires pixi.lock"):
        recording.record(downstream, ["dev", "records", "get", "capture.jsonl", "--no-record"],
                         outputs=("capture.jsonl",), message="test: blocked")


def test_capture_records_only_capture_and_acquisition_facts(downstream, monkeypatch):
    calls = []
    monkeypatch.setattr(recording, "record", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(pool_capture, "capture", lambda *args, **kwargs: pytest.fail("parent must not capture twice"))
    args = argparse.Namespace(
        root=downstream, output=Path("site-specific/sources/pool/records.jsonl"),
        api=pool_capture.DEFAULT_API, refresh=True, no_record=False,
    )
    assert pool_capture.execute(args) == 0
    positional, keywords = calls[0]
    assert positional[0] == downstream
    assert positional[1] == [
        "dev", "records", "get", "site-specific/sources/pool/records.jsonl",
        "--api", pool_capture.DEFAULT_API, "--no-record", "--refresh",
    ]
    assert keywords["outputs"] == (
        "site-specific/sources/pool/records.jsonl",
        "site-specific/sources/pool/records.jsonl.manifest.json",
    )


def test_no_record_writes_without_git_or_datalad(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(pool_capture, "capture", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(recording, "record", lambda *args, **kwargs: pytest.fail("must not invoke DataLad"))
    args = argparse.Namespace(root=tmp_path, output=Path("capture.jsonl"),
                              api=pool_capture.DEFAULT_API, refresh=False, no_record=True)
    assert pool_capture.execute(args) == 0
    assert calls == [((tmp_path / "capture.jsonl",), {"api": pool_capture.DEFAULT_API, "refresh": False})]


def test_ready_maintainer_inputs_skip_datalad_retrieval(downstream, monkeypatch):
    calls = []
    mock_pixi(monkeypatch, lambda command, **kwargs: calls.append(command))
    recording.record(downstream, ["dev", "example", "--no-record"],
                     inputs=(".orinoco-lite/dev",), outputs=("site-specific/site.yaml",),
                     message="test: import prepared input", assume_ready_inputs=True)
    option = calls[0].index("--assume-ready")
    assert calls[0][option + 1] == "inputs"


def test_import_records_retained_development_link_and_preflights_source(downstream, tmp_path, monkeypatch):
    from orinoco_lite import dev_site
    checkout = tmp_path / "engineering"
    source = checkout / "submodules/www-from-model"
    source.mkdir(parents=True)
    (downstream / ".orinoco-lite").mkdir()
    (downstream / ".orinoco-lite/dev").symlink_to(Path("../../engineering"), target_is_directory=True)
    calls = []
    monkeypatch.setattr(recording, "record", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(dev_site, "_selection", lambda args: (tmp_path / "resources", source))
    def preflight(path):
        assert path == source
        return {Path("content/_index.md"): b"prepared bytes"}
    monkeypatch.setattr(dev_site, "selected_site_files", preflight)
    args = argparse.Namespace(root=downstream, dev_command="inputs", inputs_command="import",
                              inputs=Path("site-specific"), resources=None, no_record=False,
                              presentation=Path(".orinoco-lite/dev/submodules/www-from-model"))
    assert dev_site.execute(args) == 0
    assert calls[0][0][1][-2:] == ["--presentation", ".orinoco-lite/dev/submodules/www-from-model"]
    assert calls[0][1]["inputs"] == [".orinoco-lite/dev"]
    assert calls[0][1]["assume_ready_inputs"] is True


def test_linked_import_rejects_unprepared_bytes_before_recording(downstream, tmp_path, monkeypatch):
    from orinoco_lite import dev_site
    source = tmp_path / "presentation"
    (source / "assets/img").mkdir(parents=True)
    (source / "assets/img/logo.png").write_bytes(b"/annex/objects/unavailable")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    (downstream / "presentation").symlink_to(Path("../presentation"), target_is_directory=True)
    monkeypatch.setattr(dev_site, "_selection", lambda args: (tmp_path / "resources", source))
    monkeypatch.setattr(recording, "record", lambda *args, **kwargs: pytest.fail("unprepared import must not run"))
    args = argparse.Namespace(root=downstream, dev_command="inputs", inputs_command="import",
                              inputs=Path("site-specific"), resources=None, no_record=False,
                              presentation=Path("presentation"))
    assert dev_site.execute(args) == 2
    assert not (downstream / "site-specific").exists()
