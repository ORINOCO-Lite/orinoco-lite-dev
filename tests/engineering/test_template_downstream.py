"""Exercise a selected template with replacement metadata through the public CLI."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

from copier import run_copy
import pytest


def test_downstream_replaces_starter_records_without_overrides(tmp_path):
    template = os.environ.get("ORINOCO_TEST_TEMPLATE")
    if not template:
        pytest.skip("Set ORINOCO_TEST_TEMPLATE to the template checkout to exercise")
    root = tmp_path / "downstream"
    run_copy(
        str(Path(template).resolve()), root, vcs_ref="HEAD", defaults=True,
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
