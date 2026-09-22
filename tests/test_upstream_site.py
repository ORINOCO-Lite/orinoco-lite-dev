from pathlib import Path
import subprocess

import pytest
import yaml

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
        "layouts/ignored.html": "presentation framework",
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
    command = ["dev", "upstream", "import-from-www", "--source", str(website),
               "--revision", revision, "--destination", str(destination)]
    if annexed:
        command += ["--media-remote", str(media_remote)]
    # Do not silently import uncommitted edits under a committed source identity.
    with pytest.raises(SystemExit, match="2"):
        cli.main(command)
    assert not (destination / "site.yaml").exists()
    git(website, "checkout", "--", "content/contact.md")
    assert cli.main(command) == 0
    site = yaml.safe_load((destination / "site.yaml").read_text())
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
    with pytest.raises(DriverError, match="retrieval failed"):
        import_site_inputs(source, destination, retrieve_media=True)
    assert list(destination.iterdir()) == [destination / "keep"]
    assert (destination / "keep").read_text() == "unchanged"
