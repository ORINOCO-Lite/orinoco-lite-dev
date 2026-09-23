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
def test_populate_and_rerun_with_retained_data_and_changed_presentation(tmp_path, layout, monkeypatch):
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "test@example.invalid")
    if not shutil.which("datalad"):
        pytest.skip("Run in the engineering Pixi environment for DataLad coverage")
    www = tmp_path / "www"
    make_website(www)
    site = tmp_path / "site"
    run(tmp_path, "datalad", "create", "--no-annex", str(site))
    run(site, "git", "config", "user.name", "Test")
    run(site, "git", "config", "user.email", "test@example.invalid")
    (site / "pixi.toml").write_text('[workspace]\nname="fixture"\n[pypi-dependencies]\norinoco-lite="*"\n')
    (site / "pixi.lock").write_text("fixture version one\n")
    dump = site / "sourcedata/downloaded/records.jsonl"
    dump.parent.mkdir(parents=True)
    dump.write_text(json.dumps({"pid": "ex:person", "schema_type": "xyzri:XYZPerson", "name": "One"}) + "\n")
    supplied = tmp_path / "supplied.jsonl"
    supplied.write_bytes(dump.read_bytes())
    dump.unlink()
    manifest = dump.with_name(dump.name + ".manifest.json")
    if layout == "submodule":
        manifest.write_text('{"source": "previous dump"}\n')
    else:
        supplied.with_name(supplied.name + ".manifest.json").write_text('{"source": "supplied dump"}\n')
    note = dump.parent / "notes.txt"
    note.write_text("saved note\n")
    commit(site, "test: environment")
    note.write_text("unfinished note edit\n")
    scratch = dump.parent / "scratch.txt"
    scratch.write_text("untracked work\n")
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
    run(site, "orinoco-lite", "dev", "upstream", "populate", "--dump", str(supplied), "--site-layout", layout, env=env)
    supplied.unlink()
    ingestion = run(site, "git", "log", "--format=%B", "--grep=retain supplied records dump")
    assert ingestion
    assert "DATALAD RUNCMD" not in ingestion
    ingestion_commit = run(site, "git", "log", "-1", "--format=%H", "--grep=retain supplied records dump")
    assert set(run(site, "git", "show", "--format=", "--name-only", ingestion_commit).splitlines()) == {
        "sourcedata/downloaded/records.jsonl", "sourcedata/downloaded/records.jsonl.manifest.json",
    }
    assert manifest.exists() == (layout == "directory")
    assert run(site, "git", "show", "HEAD:sourcedata/downloaded/notes.txt") == "saved note"
    assert note.read_text() == "unfinished note edit\n"
    assert not run(site, "git", "ls-files", "--", "sourcedata/downloaded/scratch.txt")
    assert scratch.read_text() == "untracked work\n"
    # Reuse accepts unrelated dirty files and still performs site import.
    (www / "content/contact.md").write_text("Reused dump import\n")
    commit(www, "test: update site before dump reuse")
    run(site, "orinoco-lite", "dev", "upstream", "populate", "--reuse-dump", env=env)
    assert (site / "site-specific/content/contact.md").read_text() == "Reused dump import\n"
    assert note.read_text() == "unfinished note edit\n"
    assert scratch.read_text() == "untracked work\n"
    note.write_text("saved note\n")
    scratch.unlink()
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
    assert "--force" in imported[0]
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
    dump.write_text(json.dumps({"pid": "ex:person", "schema_type": "xyzri:XYZPerson", "name": "Two"}) + "\n")
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


@pytest.mark.parametrize("selection", ["untracked-manifest", "untracked-lock", "modified", "staged"])
def test_population_requires_saved_pixi_files_before_writes(tmp_path, selection):
    run(tmp_path, "git", "init", "-q")
    run(tmp_path, "git", "config", "user.name", "Test")
    run(tmp_path, "git", "config", "user.email", "test@example.invalid")
    manifest, lock = tmp_path / "pixi.toml", tmp_path / "pixi.lock"
    manifest.write_text('[workspace]\nname="fixture"\n[pypi-dependencies]\norinoco-lite="*"\n')
    lock.write_text("saved lock\n")
    tracked = (lock if selection == "untracked-manifest" else
               manifest if selection == "untracked-lock" else None)
    if tracked:
        run(tmp_path, "git", "add", tracked.name)
        run(tmp_path, "git", "commit", "-qm", "test: partially saved selection")
    else:
        commit(tmp_path, "test: saved selection")
        lock.write_text("modified lock\n")
        if selection == "staged":
            run(tmp_path, "git", "add", "pixi.lock")
    before = run(tmp_path, "git", "status", "--porcelain")
    result = subprocess.run(["orinoco-lite", "dev", "upstream", "populate", "--reuse-dump"], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Record the package selection and lock" in result.stderr
    assert run(tmp_path, "git", "status", "--porcelain") == before
    assert not (tmp_path / "site-specific").exists()
    assert not (tmp_path / "sourcedata").exists()


@pytest.mark.parametrize("state", ["untracked", "modified", "staged", "staged-new", "staged-restored"])
def test_reuse_requires_saved_capture_before_writes(tmp_path, state):
    run(tmp_path, "git", "init", "-q")
    run(tmp_path, "git", "config", "user.name", "Test")
    run(tmp_path, "git", "config", "user.email", "test@example.invalid")
    (tmp_path / "pixi.toml").write_text('[workspace]\nname="fixture"\n[pypi-dependencies]\norinoco-lite="*"\n')
    (tmp_path / "pixi.lock").write_text("saved lock\n")
    dump = tmp_path / "source data/downloaded/records.jsonl"
    dump.parent.mkdir(parents=True)
    if state not in {"untracked", "staged-new"}:
        dump.write_text("saved dump\n")
    commit(tmp_path, "test: saved inputs")
    dump.write_text("unsaved dump\n")
    if state.startswith("staged"):
        run(tmp_path, "git", "add", str(dump))
    if state == "staged-restored":
        dump.write_text("saved dump\n")
    before = run(tmp_path, "git", "status", "--porcelain")
    head = run(tmp_path, "git", "rev-parse", "HEAD")
    result = subprocess.run(["orinoco-lite", "dev", "upstream", "populate", "--reuse-dump",
                             "--directory", "source data"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert 'datalad save -m "chore: retain records dump" -- source\\ data/downloaded/records.jsonl' in result.stderr
    assert run(tmp_path, "git", "status", "--porcelain") == before
    assert run(tmp_path, "git", "rev-parse", "HEAD") == head
    assert not (tmp_path / "site-specific").exists()


@pytest.mark.parametrize("manifest", [
    '[workspace]\nname="engineering"\n',
    '[pypi-dependencies]\norinoco-lite={path=".",editable=true}\n',
    '[pypi-dependencies]\norinoco-lite={path="./",editable=true}\n',
    'invalid TOML',
])
def test_population_rejects_non_downstream_before_writes(tmp_path, manifest):
    script = Path(__file__).resolve().parents[1] / "scripts/orinoco-lite-populate-upstream.sh"
    (tmp_path / "pixi.toml").write_text(manifest)
    (tmp_path / "pixi.lock").write_text("lock\n")
    before = set(tmp_path.iterdir())
    result = subprocess.run(["bash", str(script)], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert "Populate requires an Orinoco Lite downstream" in result.stderr
    assert "pixi run setup-upstream" in result.stderr
    assert set(tmp_path.iterdir()) == before
