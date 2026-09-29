from pathlib import Path
import subprocess

import pytest
import tomllib

from orinoco_lite import cli


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def repository(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")


@pytest.mark.parametrize("annexed", [False, True])
def test_site_export_requires_selected_committed_inputs_and_preserves_metadata(tmp_path, annexed):
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
        "content/persons/_index.md": "Authored section\n",
        "content/persons/person/portrait.svg": "<svg/>\n",
        "assets/img/logo.png": "identity image",
        "layouts/ignored.html": "Hugo framework",
    }
    for name, text in files.items():
        path = website / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    if annexed:
        git(website, "annex", "init", "test source")
        git(website, "annex", "add", "content/persons/person/portrait.svg")
    git(website, "add", ".")
    git(website, "commit", "-qm", "test: website snapshot")
    revision = git(website, "rev-parse", "HEAD")
    git(engineering, "update-index", "--add", "--cacheinfo", f"160000,{revision},submodules/www-from-model")
    git(engineering, "commit", "-qm", "test: select website snapshot")
    media_remote = website
    if annexed:
        clone = tmp_path / "plain-git-clone"
        subprocess.run(["git", "clone", str(website), str(clone)], check=True)
        website = clone
        git(website, "config", "user.name", "Test")
        git(website, "config", "user.email", "test@example.invalid")
        git(website, "remote", "remove", "origin")
        assert not (website / "content/persons/person/portrait.svg").exists()
    (website / "content/contact.md").write_text("Uncommitted change\n")
    destination = tmp_path / "site-specific"
    destination.mkdir()
    (destination / "metadata").mkdir()
    (destination / "metadata/keep.yaml").write_text("authored: true\n")
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text("# Keep this comment\n[tool.other]\nanswer = 42\n[tool.orinoco.operations]\ntemplate_updates = true\n[tool.orinoco.site.identity]\ncustom = 'preserved'\n")
    command = ["--root", str(tmp_path), "dev", "upstream", "import-from-www", "--source", str(website),
               "--revision", revision, "--destination", str(destination)]
    if annexed:
        command += ["--media-remote", str(media_remote)]
    # Do not silently import uncommitted edits under a committed source identity.
    with pytest.raises(SystemExit, match="2"):
        cli.main(command)
    assert not (destination / "site.yaml").exists()
    git(website, "checkout", "--", "content/contact.md")
    assert cli.main(command) == 0
    document = tomllib.loads(manifest.read_text())
    site = document["tool"]["orinoco"]["site"]
    assert document["tool"]["orinoco"]["operations"]["template_updates"] is True
    assert document["tool"]["other"]["answer"] == 42
    assert site["identity"]["custom"] == "preserved"
    assert "# Keep this comment" in manifest.read_text()
    assert site["identity"]["title"] == "Captured site"
    assert (destination / "content/contact.md").read_text() == "Committed editorial content\n"
    assert not (destination / "content/_index.md").exists()
    assert not (destination / "content/persons/person/_index.md").exists()
    assert (destination / "content/persons/_index.md").read_text() == "Authored section\n"
    assert not (destination / "content/persons/person/portrait.svg").is_symlink()
    assert (destination / "content/persons/person/portrait.svg").read_text() == "<svg/>\n"
    assert (destination / "assets/img/logo.png").read_text() == "identity image"
    assert not (destination / "layouts").exists()
    assert (destination / "metadata/keep.yaml").read_text() == "authored: true\n"
    obsolete = destination / "static/obsolete.txt"
    obsolete.parent.mkdir(parents=True, exist_ok=True)
    obsolete.write_text("obsolete file\n")
    before = {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
    with pytest.raises(SystemExit, match="2"):
        cli.main(command)
    assert {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()} == before
    assert cli.main(command + ["--force"]) == 0
    assert not obsolete.exists()
    assert (destination / "metadata/keep.yaml").read_text() == "authored: true\n"
    # A deliberate homepage override does not enable importing generated entity pages.
    assert cli.main(command + ["--force", "--include-homepage"]) == 0
    assert (destination / "content/_index.md").read_text() == "Generated home page\n"
    assert not (destination / "content/persons/person/_index.md").exists()
    assert cli.main(command + ["--force"]) == 0
    assert not (destination / "content/_index.md").exists()
    with pytest.raises(SystemExit, match="2"):
        cli.main(command + ["--destination", str(website)])


def test_missing_annex_payload_does_not_modify_destination(tmp_path):
    from orinoco_lite.site_inputs import import_site_inputs
    from orinoco_lite.errors import DriverError
    source = tmp_path / "source"
    repository(source)
    (source / "content").mkdir()
    media = source / "content/image.png"
    media.write_bytes(b"retained media")
    git(source, "annex", "init", "missing media")
    git(source, "annex", "add", "content/image.png")
    git(source, "commit", "-qm", "test: media")
    git(source, "annex", "drop", "--force", "content/image.png")
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "keep").write_text("unchanged")
    with pytest.raises(DriverError, match="Annex media operation failed"):
        import_site_inputs(source, destination, config_path=tmp_path / "pyproject.toml", retrieve_media=True)
    assert list(destination.iterdir()) == [destination / "keep"]
    assert (destination / "keep").read_text() == "unchanged"


def test_import_refuses_deletion_without_overwrite_conflict(tmp_path, monkeypatch):
    from orinoco_lite import site_inputs
    from orinoco_lite.errors import DriverError
    monkeypatch.setattr(site_inputs, "selected_site_files", lambda *a, **kw: {})
    monkeypatch.setattr(site_inputs, "site_settings", lambda *a: {})
    destination = tmp_path / "site-specific"
    old = destination / "content/obsolete.md"
    old.parent.mkdir(parents=True)
    old.write_text("keep until forced\n")
    manifest = tmp_path / "pyproject.toml"
    manifest.write_text("[tool.orinoco]\n")
    with pytest.raises(DriverError, match="--force"):
        site_inputs.import_site_inputs(tmp_path / "source", destination, config_path=manifest)
    assert old.read_text() == "keep until forced\n"
    assert not (destination / "site.yaml").exists()
    site_inputs.import_site_inputs(tmp_path / "source", destination, config_path=manifest, force=True)
    assert not old.exists()
    assert "site" in tomllib.loads(manifest.read_text())["tool"]["orinoco"]


def test_upstream_checkout_preserves_dirty_input_and_rejects_unregistered_destination(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from orinoco_lite import upstream
    from orinoco_lite.errors import ConfigurationError
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    source, root = tmp_path / "source", tmp_path / "site"
    for path in (source, root):
        repository(path)
        (path / "input").write_text("recorded\n")
        git(path, "add", ".")
        git(path, "commit", "-qm", "test: initial")
    git(source, "remote", "add", "origin", source.as_uri())
    monkeypatch.setattr(upstream, "resolve_resources", lambda: SimpleNamespace(root=tmp_path))
    monkeypatch.setattr(upstream, "resolve_www_from_model", lambda *_: source)
    upstream.checkout_upstream(root)
    git(root, "add", ".")
    git(root, "commit", "-qm", "test: select website")
    (root / "sourcedata/www-from-model/input").write_text("unfinished work\n")
    before = git(root / "sourcedata/www-from-model", "rev-parse", "HEAD")
    with pytest.raises(ConfigurationError, match="changes"):
        upstream.checkout_upstream(root)
    assert (root / "sourcedata/www-from-model/input").read_text() == "unfinished work\n"
    assert git(root / "sourcedata/www-from-model", "rev-parse", "HEAD") == before
    other = tmp_path / "other-site"
    repository(other)
    (other / "sourcedata").mkdir()
    (other / "sourcedata/www-from-model").write_text("existing input\n")
    git(other, "add", ".")
    with pytest.raises(ConfigurationError, match="not one submodule"):
        upstream.checkout_upstream(other)
    (other / "sourcedata/www-from-model").unlink()
    (other / "sourcedata/www-from-model").symlink_to(source, target_is_directory=True)
    with pytest.raises(ConfigurationError, match="inside the downstream"):
        upstream.checkout_upstream(other)
