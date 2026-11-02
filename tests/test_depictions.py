from pathlib import Path
import os
import subprocess
import sys

import pytest

from orinoco_lite.depictions import (
    bundle_depictions, flatten_depictions, validate_depictions,
)
from orinoco_lite.errors import ConfigurationError


def test_move_depictions_and_keep_authored_content(tmp_path):
    files = {
        "people/alice_smith/portrait.png": b"portrait",
        "projects/example/logo.svg": b"logo",
        "topics/example/depiction.jpg": b"depiction",
        "people/alice_smith/_index.md": b"page",
        "people/alice_smith/diagram.png": b"other image",
        "people/already_portrait.webp": b"already flat",
        "pages/article/subpage/logo.png": b"nested editorial image",
    }
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    with pytest.raises(ConfigurationError, match="orinoco-lite flatten-depictions"):
        validate_depictions(tmp_path)
    assert flatten_depictions(tmp_path) == 3
    assert not (tmp_path / "projects/example").exists()
    assert (tmp_path / "people/alice_smith/_index.md").read_bytes() == b"page"
    assert (tmp_path / "people/alice_smith/diagram.png").read_bytes() == b"other image"
    assert (tmp_path / "pages/article/subpage/logo.png").read_bytes() == b"nested editorial image"
    validate_depictions(tmp_path)
    assert flatten_depictions(tmp_path) == 0
    bundle_depictions(tmp_path)
    for name, data in files.items():
        if name == "people/already_portrait.webp":
            name = "people/already/portrait.webp"
        assert (tmp_path / name).read_bytes() == data


@pytest.mark.parametrize("conflict", ["file", "directory", "symlink"])
def test_collision_does_not_move_any_files(tmp_path, conflict):
    for person in ("alice", "zoe"):
        path = tmp_path / "persons" / person / "portrait.png"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"original")
    target = tmp_path / "persons/zoe_portrait.png"
    if conflict == "file":
        target.write_bytes(b"existing")
    elif conflict == "directory":
        target.mkdir()
    else:
        target.symlink_to("missing")
    with pytest.raises(ConfigurationError, match="destination already exists"):
        flatten_depictions(tmp_path)
    for person in ("alice", "zoe"):
        assert (tmp_path / "persons" / person / "portrait.png").read_bytes() == b"original"
    assert not (tmp_path / "persons/alice_portrait.png").exists()


def test_relative_symlink_keeps_its_target_without_payload(tmp_path):
    path = tmp_path / "content/persons/alice/portrait.png"
    path.parent.mkdir(parents=True)
    payload = tmp_path / ".git/annex/objects/missing"
    path.symlink_to(os.path.relpath(payload, path.parent))
    assert flatten_depictions(tmp_path / "content") == 1
    moved = tmp_path / "content/persons/alice_portrait.png"
    assert moved.is_symlink()
    assert moved.resolve() == payload
    assert not path.is_symlink()


def test_cli_moves_files_reports_conflicts_and_helps_without_workspace(tmp_path):
    def run(*args):
        return subprocess.run([sys.executable, "-m", "orinoco_lite", *args],
                              cwd=tmp_path, text=True, capture_output=True)

    result = run("flatten-depictions", "--help")
    assert result.returncode == 0
    assert "persons/alice_portrait.png" in result.stdout
    (tmp_path / "pyproject.toml").write_text(
        '[tool.orinoco.paths]\neditorial = "authored"\n'
        '[tool.orinoco.site.identity]\ntitle = "Test"\n'
        'description = "Test"\nbase_url = "https://example.org/"\n'
    )
    path = tmp_path / "authored/persons/alice/portrait.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"image")
    result = run("flatten-depictions")
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert "Moved 1" in result.stderr
    assert (tmp_path / "authored/persons/alice_portrait.png").read_bytes() == b"image"
    path.parent.mkdir()
    path.write_bytes(b"different")
    result = run("flatten-depictions")
    assert result.returncode == 2
    assert "destination already exists" in result.stderr
    assert "Traceback" not in result.stderr
