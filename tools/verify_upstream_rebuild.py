#!/usr/bin/env python3
"""Verify the distinct boundaries of the snapshot-driven upstream rebuild."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from orinoco_lite.config import load_workspace
from orinoco_lite.records import joined_records

import adapt_upstream_pages
import prepare_upstream_snapshot
import upstream_orinoco_records
import upstream_snapshot
from project_upstream_static import BUILD, ENTITY_SECTIONS, HUGO_SOURCE, WORKSPACE


ROOT = Path(__file__).resolve().parents[1]
PROJECTION = WORKSPACE / "generated" / "projection"
SITE = ROOT / "build" / "upstream-local"
SCHEMA = BUILD / "resources" / "schema" / "demo-research-information" / "unreleased.yaml"


def _require_directory(path: Path) -> None:
    if not path.is_dir():
        raise RuntimeError(f"required rebuild directory does not exist: {path}")


def verify_records() -> None:
    """Verify both YAML representations against the captured Pool JSONL."""

    raw = prepare_upstream_snapshot.RAW_JSONL
    exact = upstream_snapshot.verify(raw, prepare_upstream_snapshot.RECORDS)
    semantic = upstream_orinoco_records.verify_projection(
        raw, prepare_upstream_snapshot.ORINOCO_STORAGE
    )
    if exact["record_count"] != semantic["record_count"]:
        raise RuntimeError("record inventory changed between storage representations")
    print(
        "Verified record fidelity: "
        f"{exact['record_count']} Pool records survive canonical YAML and "
        "Orinoco annotation split/join"
    )


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _nested_indexes(root: Path, section: str) -> set[Path]:
    section_root = root / "content" / section
    if not section_root.is_dir():
        return set()
    return {
        path.relative_to(root / "content")
        for path in section_root.rglob("_index.md")
        if path.parent != section_root
    }


def verify_projection() -> None:
    """Verify generated records, pages, and graph own the assembled entity layer."""

    for path in (PROJECTION, HUGO_SOURCE):
        _require_directory(path)
    workspace = load_workspace(WORKSPACE)
    expected_records = sorted(
        joined_records(workspace, SCHEMA),
        key=lambda item: (item["schema_type"], item["pid"]),
    )
    actual_records = _load_jsonl(PROJECTION / "records.jsonl")
    if actual_records != expected_records:
        raise RuntimeError("projection record stream differs from joined storage")

    projected_pages: set[Path] = set()
    assembled_pages: set[Path] = set()
    for section in ENTITY_SECTIONS:
        projected_pages.update(_nested_indexes(PROJECTION, section))
        assembled_pages.update(_nested_indexes(HUGO_SOURCE, section))
    if assembled_pages != projected_pages:
        raise RuntimeError(
            "assembled entity pages differ from the generated projection"
        )

    projected_graph = json.loads(
        (PROJECTION / "static" / "graph.json").read_text(encoding="utf-8")
    )
    assembled_graph = json.loads(
        (HUGO_SOURCE / "static" / "graph.json").read_text(encoding="utf-8")
    )
    if assembled_graph != projected_graph:
        raise RuntimeError("assembled graph differs from the generated projection")
    print(
        "Verified projection ownership: "
        f"{len(actual_records)} records, {len(projected_pages) + 1} pages, "
        f"{len(projected_graph['nodes'])} graph nodes"
    )


def verify_site(site: Path, base_path: str, edit_url: str) -> None:
    """Verify projected routes and adapted links in the rendered Hugo artifact."""

    for path in (PROJECTION, site):
        _require_directory(path)
    missing: list[str] = []
    for source in sorted((PROJECTION / "content").rglob("_index.md")):
        relative = source.relative_to(PROJECTION / "content")
        rendered = site / relative.parent / "index.html"
        if not rendered.is_file():
            missing.append(relative.parent.as_posix() or "/")
    if missing:
        raise RuntimeError(
            "rendered site is missing projected routes: " + ", ".join(missing[:10])
        )
    violations = adapt_upstream_pages.audit_site(
        site, base_path, edit_url
    )
    if violations:
        raise RuntimeError(
            f"rendered site has {len(violations)} adaptation violation(s): "
            + "; ".join(violations[:5])
        )
    page_count = len(list((PROJECTION / "content").rglob("_index.md")))
    print(f"Verified rendered site: {page_count} projected routes and adapted links")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("boundary", choices=("records", "projection", "site"))
    parser.add_argument("--site", type=Path, default=SITE)
    parser.add_argument("--base-path", default="/")
    parser.add_argument("--edit-url", default=adapt_upstream_pages.DEFAULT_EDIT_URL)
    args = parser.parse_args()
    if args.boundary == "records":
        verify_records()
    elif args.boundary == "projection":
        verify_projection()
    else:
        verify_site(args.site, args.base_path, args.edit_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
