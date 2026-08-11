#!/usr/bin/env python3
"""Assemble and build the backend-free clean-migration website."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Sequence
from urllib.parse import urlsplit

import yaml

from con_assets import AssetError, hydrate_all
from con_projection import (
    BUILD_ROOT,
    CANONICAL_PIDS,
    COMMITTED,
    EXPECTED_GRAPH_EDGES,
    PROFILE_ROOT,
    ProjectionError,
    ROOT,
    ROOT_PID,
    SITE,
    UPSTREAM,
    load_yaml,
    safe_reset,
    stack_records,
    validate_projection,
    verify_declared_pins,
    verify_manifest,
)


ASSEMBLY = ROOT / "build" / "con-hugo"
DEFAULT_DESTINATION = ROOT / "build" / "con-site"
DEFAULT_BASE_URL = "http://127.0.0.1:8767/"
DEFAULT_EDIT_URL = "http://127.0.0.1:3000/"
ENTITY_SECTIONS = {
    "datasets",
    "instruments",
    "objectives",
    "organizations",
    "persons",
    "projects",
    "publications",
    "topics",
}
EXPECTED_ENTITY_ROUTES = {
    "instruments/datalad",
    "persons/yaroslav-halchenko",
    "projects/datalad",
    "publications/datalad-joss-2021",
}


class BuildError(RuntimeError):
    """Report a static assembly or site acceptance failure."""


def run(
    arguments: Sequence[str | Path],
    *,
    action: str,
    environment: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        [str(argument) for argument in arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise BuildError(f"{action} failed ({result.returncode}): {detail}")
    return result.stdout


def safe_destination(path: Path) -> Path:
    resolved = path.resolve()
    build = (ROOT / "build").resolve()
    temporary_roots = {Path("/tmp").resolve(), Path("/private/tmp").resolve()}
    if build not in resolved.parents and not any(
        temporary in resolved.parents for temporary in temporary_roots
    ):
        raise BuildError(
            f"Destination must be below {build} or a temporary directory: "
            f"{resolved}"
        )
    return resolved


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        symlinks=False,
        ignore=shutil.ignore_patterns(".git", ".DS_Store"),
    )


def overlay_assets(portrait: Path) -> None:
    manifest = yaml.safe_load(
        (PROFILE_ROOT / "assets.yaml").read_text(encoding="utf-8")
    )
    portrait_target = (
        ASSEMBLY
        / "profiles"
        / "con"
        / "assets"
        / "img"
        / "yaroslav-halchenko.jpg"
    )
    portrait_target.parent.mkdir(parents=True, exist_ok=True)
    if portrait_target.exists() or portrait_target.is_symlink():
        portrait_target.unlink()
    shutil.copy2(portrait, portrait_target)
    link_groups = {
        "projection_links": "profiles/con/projection/content/",
        "static_links": "profiles/con/static/",
    }
    for group, prefix in link_groups.items():
        links = manifest.get(group, {}) if isinstance(manifest, dict) else {}
        if not isinstance(links, dict):
            raise BuildError(f"profiles/con/assets.yaml {group} is invalid")
        for destination_name, source_name in sorted(links.items()):
            if not isinstance(destination_name, str) or not isinstance(
                source_name, str
            ):
                raise BuildError("Asset links must be string mappings")
            if not destination_name.startswith(prefix):
                raise BuildError(
                    f"Asset destination is outside {prefix}: {destination_name}"
                )
            destination = ASSEMBLY / destination_name
            declared_source = ASSEMBLY / source_name
            source = (
                portrait_target
                if declared_source.name == "yaroslav-halchenko.jpg"
                else declared_source
            )
            if not source.is_file():
                raise BuildError(f"Projected asset source is absent: {source}")
            if destination.exists() or destination.is_symlink():
                destination.unlink()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def remove_transport_overrides() -> None:
    """Exclude upstream graph and branding that the CON profile replaces."""
    names = {
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "apple-touch-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "favicon.ico",
        "graph.json",
        "mstile-150x150.png",
        "site.webmanifest",
    }
    roots = (ASSEMBLY / "static", ASSEMBLY / "themes" / "congo" / "static")
    for root in roots:
        for name in names:
            path = root / name
            if path.exists() or path.is_symlink():
                path.unlink()
    for name in ("fzj.svg", "hhu.svg"):
        path = ASSEMBLY / "assets" / "img" / name
        if path.exists() or path.is_symlink():
            path.unlink()


def assemble_source(portrait: Path) -> None:
    safe_reset(ASSEMBLY)
    for name in ("archetypes", "config", "layouts"):
        copy_tree(SITE / name, ASSEMBLY / name)
    # The sibling checkout is only a hydration transport for unchanged annexed
    # assets and the initialized theme. Its Git trees are checked against SITE.
    for name in ("assets", "static", "themes"):
        copy_tree(UPSTREAM / name, ASSEMBLY / name)
    copy_tree(SITE / "config" / "con", ASSEMBLY / "config" / "con")
    copy_tree(PROFILE_ROOT, ASSEMBLY / "profiles" / "con")
    remove_transport_overrides()
    overlay_assets(portrait)


def manifest_entries(root: Path) -> list[str]:
    return [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"{path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != ".DS_Store"
    ]


def manifest_digest(entries: list[str]) -> str:
    return hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest()


def graph_contract(site: Path) -> None:
    graph_path = site / "graph.json"
    if not graph_path.is_file():
        raise BuildError("Static artifact has no graph.json")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if {node.get("id") for node in nodes} != CANONICAL_PIDS:
        raise BuildError("Static graph nodes do not match the clean slice")
    pairs = {(edge.get("source"), edge.get("target")) for edge in edges}
    if pairs != EXPECTED_GRAPH_EDGES:
        raise BuildError("Static graph edges do not match native relationships")


def entity_routes(site: Path) -> set[str]:
    routes: set[str] = set()
    for section in ENTITY_SECTIONS:
        root = site / section
        if not root.is_dir():
            continue
        for path in root.rglob("index.html"):
            relative = path.parent.relative_to(site).as_posix()
            if relative != section:
                routes.add(relative)
    return routes


def verify_site(site: Path, base_url: str, portrait: Path) -> dict[str, Any]:
    required = {
        "index.html",
        "graph.js",
        "graph.json",
        "site.webmanifest",
        "apple-touch-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "explore/index.html",
        "mstile-150x150.png",
        "instruments/datalad/index.html",
        "persons/yaroslav-halchenko/index.html",
        "projects/datalad/index.html",
        "publications/datalad-joss-2021/index.html",
    }
    missing = sorted(path for path in required if not (site / path).is_file())
    if missing:
        raise BuildError(f"Static CON artifact is missing routes/assets: {missing}")
    if (site / "organizations" / "ror-04tfhh831" / "index.html").exists():
        raise BuildError("The graph-only CON organization gained a detail page")
    routes = entity_routes(site)
    if routes != EXPECTED_ENTITY_ROUTES:
        raise BuildError(
            "German or unexpected entity routes leaked into the CON artifact: "
            f"{sorted(routes)}"
        )
    graph_contract(site)

    homepage = (site / "index.html").read_text(encoding="utf-8")
    if "Center for Open Neuroscience" not in homepage:
        raise BuildError("Homepage branding does not identify CON")
    if "con-logo.png" not in homepage:
        raise BuildError("Homepage does not use the CON logo")
    upstream_branding = {
        "https://www.fz-juelich.de/",
        "https://www.medizin.hhu.de/",
    }
    leaked_links = sorted(link for link in upstream_branding if link in homepage)
    forbidden_assets = {
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "img/fzj.svg",
        "img/hhu.svg",
    }
    leaked_assets = sorted(
        name for name in forbidden_assets if (site / name).exists()
    )
    if leaked_links or leaked_assets:
        raise BuildError(
            "Upstream institutional branding leaked into the CON artifact: "
            f"links={leaked_links}, assets={leaked_assets}"
        )
    base_path = urlsplit(base_url).path or "/"
    expected_explore = f"{base_path.rstrip('/')}/explore"
    unquoted_homepage = homepage.replace('"', "").replace("'", "")
    if f"href={expected_explore}" not in unquoted_homepage:
        raise BuildError(
            "Homepage Explore link does not target the local static route"
        )
    expected_logo = hashlib.sha256(
        (PROFILE_ROOT / "assets" / "img" / "con-logo.png").read_bytes()
    ).hexdigest()
    if not any(
        path.is_file()
        and hashlib.sha256(path.read_bytes()).hexdigest() == expected_logo
        for path in site.rglob("*")
    ):
        raise BuildError("The committed CON logo is absent from the site")
    manifest = json.loads((site / "site.webmanifest").read_text(encoding="utf-8"))
    if manifest.get("name") != "Center for Open Neuroscience":
        raise BuildError("The static web manifest does not identify CON")
    if "Congo" in json.dumps(manifest):
        raise BuildError("Upstream Congo branding leaked into the web manifest")
    for name in (
        "apple-touch-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "mstile-150x150.png",
    ):
        if hashlib.sha256((site / name).read_bytes()).hexdigest() != expected_logo:
            raise BuildError(f"Static CON branding is stale: {name}")
    person = (site / "persons" / "yaroslav-halchenko" / "index.html")
    person_text = person.read_text(encoding="utf-8")
    if "Yaroslav" not in person_text:
        raise BuildError("Person page does not identify Yaroslav")
    if not any(
        path.is_file()
        and hashlib.sha256(path.read_bytes()).hexdigest()
        == hashlib.sha256(portrait.read_bytes()).hexdigest()
        for path in (site / "persons" / "yaroslav-halchenko").rglob("*")
    ):
        raise BuildError("The hydrated Yaroslav portrait is absent from the site")

    audit = run(
        [
            sys.executable,
            ROOT / "tools" / "adapt_upstream_pages.py",
            site,
            "--base-path",
            base_path,
            "--edit-url",
            os.environ.get("SHACL_VUE_URL", DEFAULT_EDIT_URL),
            "--check-only",
        ],
        action="Audit static CON base-path links",
    )
    entries = manifest_entries(site)
    return {
        "base_url": base_url,
        "entity_routes": sorted(routes),
        "files": len(entries),
        "manifest_sha256": manifest_digest(entries),
        "path_audit": audit.strip(),
    }


def build_site(destination: Path, base_url: str) -> dict[str, Any]:
    destination = safe_destination(destination)
    try:
        verify_declared_pins(load_yaml(PROFILE_ROOT / "profile.yaml"))
        verify_manifest(COMMITTED)
        records = [
            json.loads(line)
            for line in (COMMITTED / "records.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        validate_projection(records, COMMITTED)
        stack_records(records, BUILD_ROOT / "records.jsonl")
        portrait = hydrate_all()
    except (ProjectionError, AssetError) as error:
        raise BuildError(str(error)) from error
    assemble_source(portrait)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["HUGO_ENVIRONMENT"] = "con"
    version = run(["hugo", "version"], action="Inspect Hugo version")
    if "hugo v0.154.5" not in version or "extended" not in version:
        raise BuildError(f"Unexpected Hugo runtime: {version.strip()}")
    run(
        [
            "hugo",
            "--minify",
            "--cleanDestinationDir",
            "--environment",
            "con",
            "--source",
            ASSEMBLY,
            "--destination",
            destination,
            "--baseURL",
            base_url,
        ],
        environment=environment,
        action="Build the backend-free CON site",
    )
    base_path = urlsplit(base_url).path or "/"
    run(
        [
            sys.executable,
            ROOT / "tools" / "adapt_upstream_pages.py",
            destination,
            "--base-path",
            base_path,
            "--edit-url",
            os.environ.get("SHACL_VUE_URL", DEFAULT_EDIT_URL),
        ],
        action="Adapt generated CON paths and edit links",
    )
    report = verify_site(destination, base_url, portrait)
    report_path = destination.parent / f"{destination.name}-build.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = destination.parent / f"{destination.name}-manifest.sha256"
    manifest_path.write_text(
        "\n".join(manifest_entries(destination)) + "\n",
        encoding="utf-8",
    )
    return report


def compare_builds(
    first: Path,
    second: Path,
    base_url: str,
) -> dict[str, Any]:
    first_report = build_site(first, base_url)
    second_report = build_site(second, base_url)
    first_entries = manifest_entries(first)
    second_entries = manifest_entries(second)
    if first_entries != second_entries:
        raise BuildError("Two clean static builds are not byte-identical")
    return {
        "first": first_report,
        "second": second_report,
        "byte_identical": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(os.environ.get("DESTINATION", DEFAULT_DESTINATION)),
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument(
        "--repeat-destination",
        type=Path,
        help="also build here and require byte-identical output",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/") + "/"
    try:
        if args.repeat_destination:
            report = compare_builds(
                args.destination,
                args.repeat_destination,
                base_url,
            )
        else:
            report = build_site(args.destination, base_url)
        print(json.dumps(report, sort_keys=True))
    except BuildError as error:
        print(f"clean-migration build: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
