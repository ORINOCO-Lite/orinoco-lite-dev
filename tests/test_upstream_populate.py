"""Exercise the shared workflow with real DataLad commits and reruns."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from orinoco_lite import upstream


def run(root, *command, env=None):
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def commit(root, message):
    run(root, "git", "add", ".")
    run(root, "git", "commit", "-qm", message)


def make_website(root):
    root.mkdir()
    run(root, "git", "init", "-q")
    run(root, "git", "config", "user.name", "Test")
    run(root, "git", "config", "user.email", "test@example.invalid")
    for name, value in {
        "config/_default/languages.en.toml": 'title="Fixture"\n[params]\ndescription="Fixture"\n',
        "config/_default/hugo.toml": 'baseURL="https://example.invalid/"\n',
        "config/_default/params.toml": 'colorScheme="fire"\ndefaultAppearance="light"\n[header]\nlayout="hybrid"\n',
        "config/_default/menus.en.toml": 'main=[]\n',
        "content/contact.md": "Version one\n",
        "content/persons/example/photo.png": "\x89PNG\r\n\x1a\n\x00\x00binary fixture",
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    commit(root, "test: upstream one")


@pytest.mark.parametrize("layout", ["directory", "submodule"])
def test_populate_and_rerun_with_retained_data_and_changed_presentation(tmp_path, layout):
    if not shutil.which("datalad"):
        pytest.skip("Run in the engineering Pixi environment for DataLad coverage")
    www = tmp_path / "www"
    make_website(www)
    site = tmp_path / "site"
    run(tmp_path, "datalad", "create", "--no-annex", str(site))
    run(site, "git", "config", "user.name", "Test")
    run(site, "git", "config", "user.email", "test@example.invalid")
    (site / "pixi.toml").write_text('[workspace]\nname="fixture"\n')
    (site / "pixi.lock").write_text("fixture version one\n")
    capture = site / "sourcedata/downloaded/records.jsonl"
    capture.parent.mkdir(parents=True)
    capture.write_text(json.dumps({"pid": "ex:person", "schema_type": "xyzri:XYZPerson", "name": "One"}) + "\n")
    supplied = tmp_path / "supplied.jsonl"
    supplied.write_bytes(capture.read_bytes())
    capture.unlink()
    commit(site, "test: environment")
    # Replace only remote source resolution, so commands, conversion, file import,
    # DataLad recording, and rerun all execute their real implementations.
    commands = tmp_path / "bin"
    commands.mkdir()
    executable = commands / "orinoco-lite"
    executable.write_text(f'''#!{sys.executable}
import os
from pathlib import Path
from types import SimpleNamespace
from orinoco_lite import cli, upstream
upstream.resolve_resources = lambda: SimpleNamespace(root=Path("unused"))
upstream.resolve_presentation = lambda *args: Path(os.environ["TEST_WWW"])
raise SystemExit(cli.main())
''')
    executable.chmod(0o755)
    env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"], TEST_WWW=str(www))
    run(site, "orinoco-lite", "dev", "upstream", "populate", "--snapshot", str(supplied), "--site-layout", layout, env=env)
    supplied.unlink()
    ingestion = run(site, "git", "log", "--format=%B", "--grep=retain supplied pool capture")
    assert ingestion
    assert "DATALAD RUNCMD" not in ingestion
    history = run(site, "git", "log", "--format=%H").splitlines()
    runs = {}
    for sha in history:
        body = run(site, "git", "show", "-s", "--format=%B", sha)
        if "=== Do not change lines below ===" in body:
            record = json.loads(body.split("=== Do not change lines below ===\n", 1)[1].split("\n^^^", 1)[0])
            runs[record["cmd"]] = sha
            assert str(tmp_path) not in record["cmd"]
            assert "pixi.lock" in record["inputs"]
            assert not record["cmd"].startswith("cp ")
    conversion = next((command, sha) for command, sha in runs.items() if "jsonl-to-yaml" in command)
    imported = next((command, sha) for command, sha in runs.items() if "import-from-www" in command)
    assert "--force" in conversion[0]
    assert "--source" not in imported[0] and "--revision" not in imported[0]
    assert (site / "site-specific/.git").exists() == (layout == "submodule")
    # Identical inputs reproduce the content without acquisition.
    run(site, "datalad", "rerun", conversion[1], env=env)
    assert not run(site, "git", "status", "--porcelain")
    # The unchanged recorded import command resolves the newly selected source.
    (www / "content/contact.md").write_text("Version two\n")
    (www / "content/persons/example/photo.png").unlink()
    commit(www, "test: upstream two")
    (site / "pixi.lock").write_text("fixture version two\n")
    commit(site, "test: select second environment")
    run(site, "datalad", "rerun", imported[1], env=env)
    assert (site / "site-specific/content/contact.md").read_text() == "Version two\n"
    assert not (site / "site-specific/content/persons/example/photo.png").exists()
    # New data can pass through the same conversion run without changing commands.
    capture.write_text(json.dumps({"pid": "ex:person", "schema_type": "xyzri:XYZPerson", "name": "Two"}) + "\n")
    commit(site, "test: refresh input")
    run(site, "datalad", "rerun", conversion[1], env=env)
    rows = list((site / "site-specific/metadata/records").rglob("*.yaml"))
    assert len(rows) == 1 and "Two" in rows[0].read_text()
    assert not run(site, "git", "status", "--porcelain")


def test_setup_refuses_unpublished_candidate_before_creating_destination(tmp_path):
    commands = tmp_path / "bin"
    commands.mkdir()
    executable = commands / "orinoco-lite"
    executable.write_text('#!/bin/sh\necho "Cannot fetch package revision" >&2\nexit 2\n')
    executable.chmod(0o755)
    destination = tmp_path / "must-not-exist"
    engineering = Path(__file__).resolve().parents[1]
    result = subprocess.run(["bash", str(engineering / "tools/setup-upstream.sh"), str(destination),
                             "--template", str(engineering)], cwd=engineering,
                            env=dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"]),
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert not destination.exists()
    assert "Cannot fetch" in result.stderr
