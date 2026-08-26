#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
# platforms = [
#   { platform = "osx-arm64", macos = "14.0" },
#   "linux-64",
# ]
#
# [tool.pixi.dependencies]
# python = ">=3.12,<3.13"
# hugo = "==0.154.5"
#
# [tool.pixi.pypi-dependencies]
# orinoco-lite = { path = "../packages/orinoco-lite", editable = true }
# ///
"""Validate, build, and compare the generated upstream Orinoco fixture."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Sequence

from orinoco_lite.config import load_workspace, load_workspace_lock
from orinoco_lite.runtime import resolve_runtime
from orinoco_lite.validation import validate_workspace


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "upstream-stack"
FIXTURE = ROOT / "build" / "upstream-orinoco-site"
ORINOCO_SITE = FIXTURE / "build" / "site"
UPSTREAM_SITE = ROOT / "build" / "upstream-local"
REPORT = ROOT / "build" / "upstream-orinoco-comparison.json"


class CheckError(RuntimeError):
    """Report fixture validation, build, or comparison failures."""


def require_script_environment() -> None:
    manifest = os.environ.get("PIXI_PROJECT_MANIFEST", "")
    if not manifest or Path(manifest).resolve() != Path(__file__).resolve():
        raise CheckError("Run through the check-upstream-orinoco Pixi task")
    for executable in ("orinoco", "hugo"):
        if shutil.which(executable) is None:
            raise CheckError(f"Locked check environment lacks {executable}")


def released_runtime_probe(arguments: Sequence[str | Path]) -> dict[str, object]:
    """Exercise the fixture's release lock without making it the dev gate."""

    result = subprocess.run(
        [str(item) for item in arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    detail = (result.stderr or result.stdout).strip()
    return {
        "command": [str(item) for item in arguments],
        "diagnostic": detail[-2000:],
        "returncode": result.returncode,
        "status": "supported" if result.returncode == 0 else "unsupported",
    }


def released_engine_command(pixi_exe: str) -> list[str | Path]:
    """Run the engine installed by the generated repository's own lock."""

    return [
        pixi_exe,
        "run",
        "--frozen",
        "--manifest-path",
        FIXTURE / "pixi.toml",
        "orinoco",
        "--root",
        FIXTURE,
        "projection",
        "update",
    ]


def current_driver(arguments: Sequence[str | Path]) -> dict[str, object]:
    """Run one development driver in a fresh production-like interpreter."""

    started = time.monotonic()
    command = [sys.executable, *[str(item) for item in arguments]]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = round(time.monotonic() - started, 3)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise CheckError(
            f"{' '.join(command)} failed with status {result.returncode}: {detail}"
        )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    try:
        report = json.loads(lines[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise CheckError(
            f"{' '.join(command)} did not emit a JSON report"
        ) from error
    print(json.dumps(report, sort_keys=True))
    return {"elapsed_seconds": elapsed, "report": report}


def files(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        result[path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return result


def routes(root: Path) -> set[str]:
    result: set[str] = set()
    for path in root.rglob("index.html"):
        relative = path.relative_to(root)
        parent = relative.parent.as_posix()
        result.add("/" if parent == "." else f"/{parent}/")
    return result


def compare_sites() -> dict[str, object]:
    if not (UPSTREAM_SITE / "index.html").is_file():
        raise CheckError(f"upstream static comparison site is missing: {UPSTREAM_SITE}")
    upstream_files = files(UPSTREAM_SITE)
    orinoco_files = files(ORINOCO_SITE)
    common = upstream_files.keys() & orinoco_files.keys()
    upstream_routes = routes(UPSTREAM_SITE)
    orinoco_routes = routes(ORINOCO_SITE)
    graph = json.loads((ORINOCO_SITE / "graph.json").read_text(encoding="utf-8"))
    return {
        "byte_identical_common_files": sum(
            upstream_files[path] == orinoco_files[path] for path in common
        ),
        "common_files": len(common),
        "orinoco_files": len(orinoco_files),
        "orinoco_only_routes": sorted(orinoco_routes - upstream_routes),
        "orinoco_routes": len(orinoco_routes),
        "projection_graph_edges": len(graph["edges"]),
        "projection_graph_nodes": len(graph["nodes"]),
        "shared_routes": len(upstream_routes & orinoco_routes),
        "upstream_files": len(upstream_files),
        "upstream_only_routes": sorted(upstream_routes - orinoco_routes),
        "upstream_routes": len(upstream_routes),
    }


def console_summary(report: dict[str, object]) -> dict[str, object]:
    """Keep terminal output bounded while retaining the full file report."""

    summary = json.loads(json.dumps(report))
    routes = summary.pop("orinoco_only_routes", [])
    if isinstance(routes, list):
        summary["orinoco_only_route_count"] = len(routes)
        summary["orinoco_only_route_sample"] = routes[:10]
    return summary


def main() -> int:
    require_script_environment()
    required = (
        FIXTURE / "orinoco.yaml",
        FIXTURE / "orinoco.lock",
        STACK / "snapshot" / "manifest.json",
        UPSTREAM_SITE / "index.html",
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        raise CheckError(f"missing prepared inputs: {missing}")
    workspace = load_workspace(FIXTURE)
    lock = load_workspace_lock(workspace)
    runtime = resolve_runtime(workspace, lock)
    pixi_exe = os.environ.get("PIXI_EXE")
    if not pixi_exe:
        raise CheckError(
            "Locked check environment does not identify its Pixi executable"
        )
    release_probe = released_runtime_probe(released_engine_command(pixi_exe))
    structural = validate_workspace(workspace)
    common = [
        "-m",
        "orinoco_lite.projection_cli",
        "--config",
        FIXTURE / "orinoco.yaml",
        "--runtime",
        runtime.root,
    ]
    projection = current_driver([*common, "update"])
    verification = current_driver([*common, "verify"])
    build = current_driver(
        [
            "-m",
            "orinoco_lite.site",
            "--config",
            FIXTURE / "orinoco.yaml",
            "--runtime",
            runtime.root,
            "--destination",
            ORINOCO_SITE,
            "--base-url",
            "/",
        ]
    )
    report = compare_sites()
    report.update(
        {
            "development_engine": {
                "build": build,
                "projection": projection,
                "projection_verification": verification,
                "structural_records": structural["records"],
            },
            "released_runtime_probe": release_probe,
            "verified_release_runtime": {
                "files": runtime.files,
                "manifest_sha256": runtime.manifest_sha256,
                "release": runtime.release,
                "tree_sha256": runtime.tree_sha256,
            },
        }
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(console_summary(report), indent=2, sort_keys=True))
    print(f"Checked upstream Orinoco site: {ORINOCO_SITE}")
    print(f"Comparison report: {REPORT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as error:
        raise SystemExit(f"upstream-orinoco-check: {error}") from error
