#!/usr/bin/env python3
"""Build an upstream Hugo source tree from the captured Pool snapshot."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import yaml

from orinoco_lite.config import load_workspace
from orinoco_lite.projection import render_projection
from orinoco_lite.release_schema import localize_schema

import prepare_upstream_snapshot


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "upstream-static"
WORKSPACE = BUILD / "workspace"
HUGO_SOURCE = BUILD / "hugo-source"
PRESENTATION = ROOT / "submodules" / "www-from-model"
SCHEMA_SOURCE = (
    ROOT
    / "submodules"
    / "things-schemas"
    / "src"
    / "demo-research-information"
    / "unreleased.yaml"
)
ENTITY_SECTIONS = (
    "datasets",
    "instruments",
    "objectives",
    "persons",
    "projects",
    "publications",
    "topics",
)


def _copy(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _write_workspace() -> None:
    storage = prepare_upstream_snapshot.ORINOCO_STORAGE
    records = storage / "metadata" / "records"
    annotations = storage / "metadata" / "overlays" / "annotations"
    _copy(records, WORKSPACE / "site-specific" / "metadata" / "records")
    _copy(
        annotations,
        WORKSPACE
        / "site-specific"
        / "metadata"
        / "overlays"
        / "annotations",
    )
    site = WORKSPACE / "site-specific"
    site.mkdir(parents=True, exist_ok=True)
    (site / "site.yaml").write_text(
        "version: 1\n"
        "identity:\n"
        "  title: Psychoinformatics\n"
        "  description: Metadata-based website of the Psychoinformatics group\n"
        "  base_url: http://127.0.0.1:8768/\n",
        encoding="utf-8",
    )
    contract_source = (
        ROOT
        / "packages"
        / "orinoco-lite"
        / "src"
        / "orinoco_lite"
        / "default_projection.yaml"
    ).read_text(encoding="utf-8")
    contract = yaml.safe_load(contract_source)
    rendered_classes = set(contract["pages"])
    stored_classes = {
        yaml.safe_load(path.read_text(encoding="utf-8"))["schema_type"]
        for path in records.rglob("*.yaml")
    }
    contract["unrendered_classes"] = sorted(stored_classes - rendered_classes)
    localized_contract = yaml.safe_dump(contract, sort_keys=False).replace(
        "presentation:", "presentation/"
    )
    (site / "projection.yaml").write_text(
        localized_contract, encoding="utf-8"
    )
    (WORKSPACE / "orinoco.yaml").write_text(
        "contract_version: 2\n"
        "paths:\n"
        "  records: site-specific/metadata/records\n",
        encoding="utf-8",
    )
    _copy(PRESENTATION / "page_templates", WORKSPACE / "presentation/page_templates")
    _copy(PRESENTATION / "code", WORKSPACE / "presentation/code")


def _stage_schema() -> Path:
    resources = BUILD / "resources"
    destination = resources / "schema"
    localize_schema(SCHEMA_SOURCE.parents[1], SCHEMA_SOURCE, destination)
    return resources


def _assemble(projection: Path) -> None:
    for surface in (
        "archetypes",
        "assets",
        "config",
        "layouts",
        "static",
        "themes",
    ):
        _copy(PRESENTATION / surface, HUGO_SOURCE / surface)
    content = PRESENTATION / "content"
    HUGO_SOURCE.joinpath("content").mkdir(parents=True, exist_ok=True)
    for child in sorted(content.iterdir()):
        if child.name not in ENTITY_SECTIONS:
            _copy(child, HUGO_SOURCE / "content" / child.name)
            continue
        section = HUGO_SOURCE / "content" / child.name
        section.mkdir(parents=True, exist_ok=True)
        for source in sorted(path for path in child.rglob("*") if path.is_file()):
            if source.name.startswith("_index.") and source.parent != child:
                continue
            _copy(source, section / source.relative_to(child))
    (HUGO_SOURCE / "static" / "graph.json").unlink(missing_ok=True)
    _copy(projection / "content", HUGO_SOURCE / "content")
    _copy(projection / "static", HUGO_SOURCE / "static")


def main() -> int:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    prepare_upstream_snapshot.main([])
    _write_workspace()
    resources = _stage_schema()
    workspace = load_workspace(WORKSPACE)
    projection = WORKSPACE / "generated" / "projection"
    report = render_projection(workspace, resources, projection)
    _assemble(projection)
    (BUILD / "projection-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Projected {report['records']} Pool records into {HUGO_SOURCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
