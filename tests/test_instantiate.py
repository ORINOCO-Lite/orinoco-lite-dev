from pathlib import Path
import json
import subprocess

import pytest
import yaml

from orinoco_lite import instantiate, site_inputs
from orinoco_lite.errors import ConfigurationError


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def repository(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")


def test_snapshot_conversion_uses_committed_editorial_inputs(tmp_path):
    engineering = tmp_path / "engineering"
    repository(engineering)
    website = engineering / "submodules/www-from-model"
    repository(website)
    files = {
        "config/_default/languages.en.toml": 'title = "Captured site"\n[params]\ndescription = "Captured description"\n',
        "config/_default/hugo.toml": 'baseURL = "https://example.invalid/"\n',
        "config/_default/params.toml": 'colorScheme = "fire"\ndefaultAppearance = "light"\n[header]\nlayout = "hybrid"\n',
        "config/_default/menus.en.toml": '[[main]]\nname = "People"\npageRef = "persons"\n',
        "content/contact.md": "Committed editorial content\n",
        "content/_index.md": "Generated home page\n",
        "content/persons/person/_index.md": "Generated record page\n",
    }
    for name, text in files.items():
        path = website / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(website, "add", ".")
    git(website, "commit", "-qm", "test: website snapshot")
    revision = git(website, "rev-parse", "HEAD")
    git(engineering, "update-index", "--add", "--cacheinfo", f"160000,{revision},submodules/www-from-model")
    git(engineering, "commit", "-qm", "test: select website snapshot")
    (website / "content/contact.md").write_text("Uncommitted change\n")
    snapshot = tmp_path / "pool.jsonl"
    snapshot.write_text(json.dumps({"class_name": "XYZPerson", "record": {
        "pid": "xyzrins:person", "schema_type": "dlthings:XYZPerson", "name": "Snapshot person"}}) + "\n")
    destination = tmp_path / "site-specific"
    instantiate.snapshot_site(engineering, snapshot, destination)
    site = yaml.safe_load((destination / "site.yaml").read_text())
    assert site["identity"]["title"] == "Captured site"
    assert (destination / "content/contact.md").read_text() == "Committed editorial content\n"
    assert not (destination / "content/_index.md").exists()
    assert not (destination / "content/persons").exists()
    assert not (destination / "manifest.json").exists()
    records = list((destination / "metadata/records").rglob("*.yaml"))
    assert len(records) == 1
    assert yaml.safe_load(records[0].read_text())["name"] == "Snapshot person"
    snapshot.write_text("")
    assert yaml.safe_load(records[0].read_text())["name"] == "Snapshot person"


def test_force_does_not_remove_output_when_snapshot_is_missing(tmp_path, monkeypatch):
    engineering = tmp_path / "orinoco-lite-dev"
    (engineering / "release").mkdir(parents=True)
    (engineering / "release/package-resources.yaml").touch()
    template = tmp_path / "orinoco-lite-template"
    template.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (output / "keep.txt").write_text("keep")
    monkeypatch.setattr(instantiate, "__file__", str(engineering / "src/orinoco_lite/instantiate.py"))
    with pytest.raises(ConfigurationError, match="Cached pool snapshot is missing"):
        instantiate.setup(output, force=True)
    assert (output / "keep.txt").read_text() == "keep"


def test_setup_retains_original_capture_before_public_conversion(tmp_path, monkeypatch):
    engineering = tmp_path / "engineering"
    (engineering / "release").mkdir(parents=True)
    (engineering / "release/package-resources.yaml").touch()
    (engineering / "submodules/www-from-model/.git").mkdir(parents=True)
    template = tmp_path / "template"
    template.mkdir()
    source = tmp_path / "original.jsonl"
    raw = b'{"class_name":"Thing","record":{"pid":"example:one","schema_type":"dlthings:Thing"}}\n'
    source.write_bytes(raw)
    manifest = source.with_name(source.name + ".manifest.json")
    facts = b'{"captured_at":"2026-09-18T12:00:00+00:00"}\n'
    manifest.write_bytes(facts)
    destination = tmp_path / "downstream"
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        if "create" in args:
            destination.mkdir()

    monkeypatch.setattr(instantiate, "__file__", str(engineering / "src/orinoco_lite/instantiate.py"))
    monkeypatch.setattr(instantiate, "run", run)
    monkeypatch.setattr(instantiate, "git", lambda *args: "a" * 40)
    monkeypatch.setattr(site_inputs, "selected_site_files", lambda source: {})
    monkeypatch.setattr(instantiate, "enable", lambda *args: calls.append(("enable", *args)))
    instantiate.setup(destination, template=template, snapshot=source)
    retained = destination / "site-specific/sources/pool/original.jsonl"
    assert retained.read_bytes() == raw
    assert retained.with_name(retained.name + ".manifest.json").read_bytes() == facts
    convert = next(i for i, call in enumerate(calls) if "convert" in call)
    enabled = next(i for i, call in enumerate(calls) if call[0] == "enable")
    assert enabled < convert
    assert calls[convert][-2:] == (Path("site-specific/sources/pool/original.jsonl"), "site-specific")
    assert calls[-1][-6:] == ("dev", "inputs", "import", "site-specific",
                            "--presentation", ".orinoco-lite/dev/submodules/www-from-model")


def test_setup_rejects_unselected_maintainer_source_before_replacing_output(tmp_path, monkeypatch):
    engineering = tmp_path / "engineering"
    (engineering / "release").mkdir(parents=True)
    (engineering / "release/package-resources.yaml").touch()
    (engineering / "submodules/www-from-model/.git").mkdir(parents=True)
    template = tmp_path / "template"
    template.mkdir()
    snapshot = tmp_path / "capture.jsonl"
    snapshot.write_text("retained source")
    output = tmp_path / "output"
    output.mkdir()
    (output / "keep.txt").write_text("keep")
    monkeypatch.setattr(instantiate, "__file__", str(engineering / "src/orinoco_lite/instantiate.py"))
    monkeypatch.setattr(instantiate, "git", lambda root, *args: "a" * 40 if root == engineering else "b" * 40)
    with pytest.raises(ConfigurationError, match="does not match.*Gitlink"):
        instantiate.setup(output, template=template, snapshot=snapshot, force=True)
    assert (output / "keep.txt").read_text() == "keep"
