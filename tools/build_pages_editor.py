#!/usr/bin/env python3
"""Build the credential-free SHACL Vue editor for the CON Pages preview."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Sequence

from dump_things_service import Format
from dump_things_service.converter import FormatConverter
from rdflib import Graph
from rdflib.compare import to_canonical_graph

from build_con_site import (
    BuildError,
    ROOT,
    manifest_digest,
    manifest_entries,
    safe_destination,
)
from con_projection import (
    SCHEMA,
    SITE,
    git_commit,
    load_projection_contract,
    source_closure,
    validate_record_contract,
)


UI = ROOT / "submodules" / "pool.psychoinformatics.de-ui"
DEFAULT_SOURCE = UI / "dist" / "ui"
DEFAULT_DESTINATION = ROOT / "build" / "pages-editor"
DEFAULT_REPEAT_DESTINATION = ROOT / "build" / "pages-editor-repeat"
TEXT_CONFIG = {
    "app_name": "CON metadata review",
    "app_theme": {
        "active_color": "#2b71b9",
        "hover_color": "#2b71b9",
        "link_color": "#7fa7d8",
        "logo": "logo.png",
        "panel_color": "#29343e",
        "visited_color": "#7fa7d8",
    },
    "class_url": "dlschemas_owl.ttl",
    "data_url": "records.ttl",
    "documentation_url": "",
    "external_config_url": "config_default_xyzri.yaml",
    "front_page_content": (
        "Edit a public CON record, save it in the form, then use the download "
        "button to create a review bundle. The browser has no write service "
        "or authentication credential."
    ),
    "page_title": "CON metadata review",
    "priority_classes": [
        {
            "class": "dlthings:Thing",
            "icon": "mdi-view-list",
            "include_subclasses": True,
            "title": "All",
        }
    ],
    "review_bundle_catalog": "record-sources.json",
    "review_bundle_mode": "patch-download",
    "shapes_url": "dlschemas_shacl.ttl",
    "source_code_url": "https://github.com/ORINOCO-Lite/orinoco-lite-dev",
    "use_default_classes": False,
    "use_default_data": False,
    "use_default_shapes": False,
    "use_service": False,
    "use_token": False,
}


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def copy_ui(source: Path, destination: Path) -> None:
    if not source.is_dir() or not (source / "index.html").is_file():
        raise BuildError("Built pool UI is missing index.html")
    for candidate in source.rglob("*"):
        if candidate.is_symlink():
            raise BuildError(
                f"Built pool UI contains a symlink: {candidate.relative_to(source)}"
            )
    shutil.copytree(source, destination)
    for name in (
        "config.json",
        "config.yaml",
        "config.yml",
        "dlschemas_data.ttl",
    ):
        destination.joinpath(name).unlink(missing_ok=True)
    for source_map in destination.rglob("*.map"):
        source_map.unlink()


def static_records_turtle() -> tuple[str, int]:
    contract = load_projection_contract()
    records = source_closure(contract)
    validate_record_contract(records, contract)
    converter = FormatConverter(str(SCHEMA), Format.json, Format.ttl)
    rendered: list[str] = []
    for source in sorted(records, key=lambda item: item.record["pid"]):
        try:
            turtle = converter.convert(source.record, source.class_name)
        except Exception as error:
            raise BuildError(
                f"Could not render editor RDF for {source.record['pid']}: {error}"
            ) from error
        rendered.append(turtle)
    return canonical_turtle(rendered), len(records)


def canonical_turtle(snippets: Sequence[str]) -> str:
    """Return deterministic RDF accepted by a Turtle parser.

    RDFLib's Turtle serializer can emit equivalent blank-node properties and
    repeated values in process-dependent order.  Canonical blank-node labels
    plus sorted N-Triples make the byte stream stable.  N-Triples is a strict
    subset of Turtle, so SHACL Vue can continue to load ``records.ttl``.
    """

    graph = Graph()
    for snippet in snippets:
        graph.parse(data=snippet, format="turtle")
    serialized = to_canonical_graph(graph).serialize(format="nt")
    lines = sorted(line for line in serialized.splitlines() if line.strip())
    return "\n".join(lines) + "\n"


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def build_editor(destination: Path, source: Path = DEFAULT_SOURCE) -> dict[str, Any]:
    destination = safe_destination(destination)
    if destination.exists():
        shutil.rmtree(destination)
    copy_ui(source.resolve(), destination)
    turtle, record_count = static_records_turtle()
    destination.joinpath("records.ttl").write_text(turtle, encoding="utf-8")
    write_json(destination / "config.json", TEXT_CONFIG)
    contract = {
        "authentication": "none",
        "backend": "none",
        "input_sha256": tree_digest(destination),
        "mode": "patch-download",
        "pool_ui_commit": git_commit(UI),
        "record_count": record_count,
        "schema_commit": git_commit(ROOT / "submodules" / "things-schemas"),
        "site_commit": git_commit(SITE),
        "version": 1,
    }
    write_json(destination / "editor-contract.json", contract)
    return contract


def build_pool_ui() -> None:
    """Build the pinned UI without reusing a previous distribution tree."""

    result = subprocess.run(
        ["make", "-C", str(UI), "build-ui"],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        raise BuildError(f"Pinned pool UI build failed ({result.returncode})")


def verify_editor_builds(
    destination: Path,
    repeat_destination: Path,
    source: Path = DEFAULT_SOURCE,
) -> dict[str, Any]:
    """Build the UI/editor twice independently and compare exact bytes."""

    if source.resolve() != DEFAULT_SOURCE.resolve():
        raise BuildError("Repeated editor verification requires the pinned UI source")
    build_pool_ui()
    first = build_editor(destination, source)
    first_entries = manifest_entries(destination)
    build_pool_ui()
    second = build_editor(repeat_destination, source)
    second_entries = manifest_entries(repeat_destination)
    if first_entries != second_entries:
        raise BuildError("Two independent static editor builds are not byte-identical")
    return {
        "byte_identical": True,
        "files": len(first_entries),
        "first": first,
        "manifest_sha256": manifest_digest(first_entries),
        "second": second,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--repeat-destination", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.repeat_destination is None:
        report = build_editor(args.destination, args.source)
    else:
        report = verify_editor_builds(
            args.destination,
            args.repeat_destination,
            args.source,
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
