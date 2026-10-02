"""Exercise a selected template with replacement metadata through the public CLI."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from copier import run_copy
import pytest
import yaml


def test_downstream_replaces_starter_records_without_overrides(tmp_path):
    selected = os.environ.get("ORINOCO_TEST_TEMPLATE")
    template = Path(selected) if selected else Path(__file__).resolve().parents[3] / "orinoco-lite-template"
    if not selected and not template.exists():
        pytest.skip("No sibling orinoco-lite-template checkout; set ORINOCO_TEST_TEMPLATE to select one")
    root = tmp_path / "downstream"
    run_copy(
        str(template.resolve()), root, vcs_ref="HEAD", defaults=True,
        data={"project_name": "Replacement Research", "project_slug": "replacement"},
    )
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    records = root / "site-specific/metadata/records"
    shutil.rmtree(records)
    fixture = Path(__file__).parents[1] / "fixtures/template-candidate/site-specific/metadata/records"
    shutil.copytree(fixture, records)
    original = {path.relative_to(records): path.read_bytes() for path in records.rglob("*.yaml")}

    # Use the active engineering package and the downstream's ordinary build path.
    for args in (("build", "--destination", "build/site", "--base-url", "/"),
                 ("verify-site", "build/site")):
        subprocess.run([sys.executable, "-m", "orinoco_lite", *args], cwd=root, check=True)

    site = root / "build/site"
    home = (site / "index.html").read_text()
    assert "Architecture Proof" in home
    assert "/persons/example-person/" in home
    for section, record, title in (
        ("persons", "example-person", "Example Person"),
        ("projects", "example-project", "Example Project"),
        ("publications", "example-publication", "Example Publication"),
    ):
        assert f"/{section}/" in home
        assert f"/{section}/{record}/" in (site / section / "index.html").read_text()
        assert title in (site / section / record / "index.html").read_text()
    person = (site / "persons/example-person/index.html").read_text()
    assert "/projects/example-project/" in person
    assert "/publications/example-publication/" in person
    assert "/persons/example-person/" in (site / "projects/example-project/index.html").read_text()
    assert "/persons/example-person/" in (site / "publications/example-publication/index.html").read_text()
    for page in site.rglob("*.html"):
        assert "starter-person" not in page.read_text()
        assert "starter-project" not in page.read_text()
        assert "starter-publication" not in page.read_text()
    assert {path.relative_to(records): path.read_bytes() for path in records.rglob("*.yaml")} == original


@pytest.mark.parametrize("annex", [False, True])
def test_shacl_workflow_commits_metadata_across_steps(tmp_path, annex):
    """Execute the template's validation and commit steps in an activated job."""
    selected = os.environ.get("ORINOCO_TEST_TEMPLATE")
    template = Path(selected) if selected else Path(__file__).resolve().parents[3] / "orinoco-lite-template"
    if not selected and not template.exists():
        pytest.skip("No sibling orinoco-lite-template checkout; set ORINOCO_TEST_TEMPLATE to select one")
    engineering = Path(__file__).resolve().parents[2]
    root = tmp_path / "source"
    run_copy(str(template.resolve()), root, vcs_ref="HEAD", defaults=True)
    workflow = yaml.safe_load((root / ".github/workflows/shacl-vue-proposal.yml").read_text())
    steps = {step["name"]: step for step in workflow["jobs"]["validate"]["steps"]}
    environment = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GITHUB_WORKSPACE": str(tmp_path), "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "outputs"), "PIXI_LOCKED": "true",
        "METADATA_REPOSITORY": "example/metadata", "CURATOR": "curator", "CURATOR_ID": "1",
        "AUTHOR_DATE": "2026-01-01T00:00:00Z",
    }

    def git(directory, *args):
        return subprocess.check_output(["git", "-C", str(directory), *args], env=environment, text=True).strip()

    # Keep the published media unavailable in the checkout under test. Validation
    # and ordinary metadata commits must not retrieve or rewrite its pointer.
    origin = tmp_path / "metadata-origin"
    shutil.move(root / "site-specific", origin)
    git(origin, "init", "-q", "-b", "main")
    git(origin, "config", "user.name", "Fixture")
    git(origin, "config", "user.email", "fixture@example.invalid")
    (origin / ".gitattributes").write_text("* annex.largefiles=nothing\n")
    if annex:
        git(origin, "annex", "init", "fixture")
        (origin / "static").mkdir(exist_ok=True)
        (origin / "static/media.dat").write_bytes(b"Unavailable media fixture\n")
        git(origin, "annex", "add", "--force-large", "static/media.dat")
        with (root / "pyproject.toml").open("a") as stream:
            stream.write("\n[tool.orinoco.media]\nannex = true\n")
    git(origin, "add", ".")
    git(origin, "commit", "-qm", "test: prepare site inputs")
    git(root, "init", "-q", "-b", "main")
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", str(origin), "site-specific")
    git(root, "config", "-f", ".gitmodules", "submodule.site-specific.url", "https://github.com/example/metadata.git")
    git(root, "add", ".")
    git(root, "commit", "-qm", "test: pin site inputs")
    environment["SOURCE_COMMIT"] = git(root, "rev-parse", "HEAD")
    site = root / "site-specific"
    metadata_base = git(site, "rev-parse", "HEAD")
    record = next((site / "metadata/records").rglob("*.yaml"))
    value = yaml.safe_load(record.read_text())
    value["description"] = "Metadata changed by the workflow regression test."
    record.write_text(yaml.safe_dump(value, sort_keys=False))

    # setup-pixi activates via this public Pixi API. Use the engineering package
    # as the trusted environment so this test also exercises package candidates.
    activated = json.loads(subprocess.check_output(
        ["pixi", "shell-hook", "--manifest-path", str(engineering / "pixi.toml"), "--json"],
        text=True, env=environment,
    ))["environment_variables"]
    # Hide ambient Annex (pytest itself runs inside Pixi). Only job activation
    # may make it available to plain Git in subsequent workflow steps.
    trap = tmp_path / "no-annex"
    trap.mkdir()
    marker = trap / "invoked"
    executable = trap / "git-annex"
    executable.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\necho "Annex missing from job environment" >&2\nexit 127\n')
    executable.chmod(0o755)
    environment["PATH"] = str(trap) + os.pathsep + environment["PATH"]
    if steps["Install the trusted locked Pixi environment"]["with"].get("activate-environment"):
        environment.update(activated)
    if not annex:
        # An ordinary downstream must never invoke Annex even when it is
        # available in the engineering environment used to run this test.
        environment["PATH"] = str(trap) + os.pathsep + environment["PATH"]

    for name in ("Validate the materialized joined graph",
                 "Create the equivalent attributed human metadata commit"):
        subprocess.run(["bash", "-e", "-c", steps[name]["run"]], cwd=engineering, env=environment, check=True)
    (tmp_path / "proposal").symlink_to(root, target_is_directory=True)
    environment["HEAD_SHA"] = git(root, "rev-parse", "HEAD")
    subprocess.run(
        ["bash", "-e", "-c", steps["Validate the exact canonical joined metadata graph"]["run"]],
        cwd=engineering, env=environment, check=True,
    )
    assert git(site, "diff", "--name-only", metadata_base, "HEAD") == record.relative_to(site).as_posix()
    assert git(root, "diff", "--name-only", environment["SOURCE_COMMIT"], "HEAD") == "site-specific"
    assert git(site, "show", "-s", "--format=%an <%ae>") == "curator <1+curator@users.noreply.github.com>"
    assert git(root, "status", "--porcelain") == ""
    assert not marker.exists()
    if annex:
        assert (site / "static/media.dat").is_symlink()
        assert not (site / "static/media.dat").exists()
