"""Location-independent static build driver for flattened consumers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from typing import Any, Sequence
from urllib.parse import urlsplit

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .assets import hydrate_asset_cache, load_assets, verify_asset
from .config import load_config_path
from .errors import ConfigurationError, DriverError, IntegrityError
from .editor import bind_editor
from .integrity import sha256_file
from .runtime import MANIFEST_NAME, load_runtime_manifest


HUGO_VERSION = re.compile(
    r"^hugo\s+v?(?P<version>[0-9]+(?:\.[0-9]+){2})"
    r"(?:-(?P<revision>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?P<variants>(?:\+[A-Za-z0-9.-]+)*)(?:\s|$)",
    re.IGNORECASE,
)


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    for candidate in sorted(source.rglob("*")):
        relative = candidate.relative_to(source)
        target = destination / relative
        if candidate.is_symlink():
            raise DriverError(f"Static source cannot contain symlinks: {candidate}")
        if candidate.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif candidate.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, target)


def _safe_destination(workspace, destination: Path) -> Path:
    if not destination.is_absolute():
        destination = workspace.root / destination
    resolved = destination.resolve(strict=False)
    build = workspace.path("build").resolve(strict=False)
    if build not in resolved.parents:
        raise ConfigurationError(f"Build destination must be below {build}: {resolved}")
    return resolved


def _assemble(workspace, runtime_root: Path, assembly: Path) -> dict[str, int]:
    framework = workspace.path("site") / "framework"
    for name in ("archetypes", "assets", "config", "layouts", "static", "themes"):
        _copy_tree(framework / name, assembly / name)
    _copy_tree(workspace.path("site") / "config", assembly / "config" / "con")
    # Consumer module mounts describe the ownership layout before flattening.
    # Copying that topology-only file would disable Hugo's implicit mounts and
    # point at paths that no longer exist inside the assembly.
    (assembly / "config" / "con" / "module.toml").unlink(missing_ok=True)
    _copy_tree(workspace.path("site") / "layouts", assembly / "layouts")
    _copy_tree(workspace.path("site") / "static", assembly / "static")
    _copy_tree(workspace.path("assets") / "files", assembly / "assets")
    _copy_tree(workspace.path("editorial"), assembly / "content")
    projection = workspace.path("generated") / "projection"
    _copy_tree(projection / "content", assembly / "content")
    _copy_tree(projection / "static", assembly / "static")
    _copy_tree(workspace.path("extensions") / "layouts", assembly / "layouts")
    _copy_tree(workspace.path("extensions") / "static", assembly / "static")
    _copy_tree(workspace.path("extensions") / "assets", assembly / "assets")
    for name in (
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "favicon.ico",
    ):
        (assembly / "static" / name).unlink(missing_ok=True)
    assets, links = load_assets(workspace)
    cache = workspace.path("build") / "asset-cache"
    hydrated = 0
    copied = 0
    copied_sources = 0
    destinations_by_source: dict[str, list[str]] = {}
    for destination, source in links.items():
        destinations_by_source.setdefault(source, []).append(destination)
    for source, asset in sorted(assets.items()):
        if asset.availability != "available":
            continue
        source_path = workspace.root.joinpath(*PurePosixPath(source).parts)
        if not source_path.is_file():
            source_path = cache / asset.sha256
            if not source_path.is_file():
                hydrate_asset_cache(source_path, asset)
                hydrated += 1
        verify_asset(source_path, asset)
        source_relative = PurePosixPath(source)
        if source_relative.parts[:2] != ("assets", "files"):
            raise DriverError(
                f"Asset source is outside the flattened assets/files contract: {source}"
            )
        assembled_source = assembly / "assets" / Path(*source_relative.parts[2:])
        assembled_source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, assembled_source)
        copied_sources += 1
        for destination in sorted(destinations_by_source.get(source, [])):
            destination_path = assembly / "consumer" / destination
            # Consumer paths are re-rooted into the Hugo assembly. Generated
            # content/static and site/static are mounted at their Hugo targets.
            destination_relative = PurePosixPath(destination)
            parts = destination_relative.parts
            if parts[:3] == ("generated", "projection", "content"):
                destination_path = assembly / "content" / Path(*parts[3:])
            elif parts[:3] == ("generated", "projection", "static"):
                destination_path = assembly / "static" / Path(*parts[3:])
            elif parts[:2] == ("site", "static"):
                destination_path = assembly / "static" / Path(*parts[2:])
            elif parts[:2] == ("assets", "files"):
                destination_path = assembly / "assets" / Path(*parts[2:])
            else:
                raise DriverError(f"Unsupported asset link destination: {destination}")
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination_path)
            copied += 1
    return {
        "copied_assets": copied_sources,
        "copied_links": copied,
        "hydrated_assets": hydrated,
    }


def _manifest(root: Path) -> list[str]:
    return [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file())
    ]


def _run(command: Sequence[str | Path], *, cwd: Path) -> str:
    try:
        result = subprocess.run(
            [str(item) for item in command],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise DriverError(f"Static build command is missing: {command[0]}") from error
    if result.returncode:
        raise DriverError((result.stderr or result.stdout).strip())
    return result.stdout


def _require_compatible_hugo(
    output: str,
    specifier: str,
    *,
    runtime_release: str,
) -> Version:
    match = HUGO_VERSION.match(output.strip())
    if match is None:
        raise DriverError(f"Could not determine Hugo version from: {output.strip()}")
    variants = {
        item.lower()
        for item in match.group("variants").split("+")
        if item
    }
    if "extended" not in variants:
        raise DriverError(f"Orinoco Lite requires Hugo Extended: {output.strip()}")
    version = Version(match.group("version"))
    if version not in SpecifierSet(specifier):
        raise DriverError(
            f"Orinoco runtime {runtime_release} requires Hugo {specifier}; "
            f"found {version}"
        )
    return version


def _preflight_hugo(runtime_root: Path, *, cwd: Path) -> Version:
    manifest = load_runtime_manifest(runtime_root / MANIFEST_NAME)
    output = _run(["hugo", "version"], cwd=cwd)
    return _require_compatible_hugo(
        output,
        str(manifest.compatibility["hugo"]),
        runtime_release=manifest.release,
    )


def build_site(
    config: Path,
    runtime_root: Path,
    destination: Path,
    base_url: str,
) -> dict[str, Any]:
    workspace = load_config_path(config)
    runtime_root = runtime_root.resolve()
    destination = _safe_destination(workspace, destination)
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError("Build base URL must be an absolute HTTP(S) URL")
    base_url = base_url.rstrip("/") + "/"
    _preflight_hugo(runtime_root, cwd=workspace.root)
    assembly = workspace.path("build") / "assembly"
    if assembly.exists():
        shutil.rmtree(assembly)
    assembly.mkdir(parents=True)
    asset_report = _assemble(workspace, runtime_root, assembly)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "hugo",
            "--minify",
            "--cleanDestinationDir",
            "--environment",
            "con",
            "--source",
            assembly,
            "--destination",
            destination,
            "--baseURL",
            base_url,
        ],
        cwd=workspace.root,
    )
    adapter = runtime_root / "drivers" / "adapt_pages.py"
    if adapter.is_file():
        graph_script = destination / "graph.js"
        # Historical annex pointers are not executable website resources.
        # The generic fallback keeps graph pages functional without requiring
        # git-annex and remains compatible with the adapter's fetch contract.
        if graph_script.is_file():
            graph_source = graph_script.read_text(encoding="utf-8").strip()
            if graph_source.startswith("/annex/objects/"):
                graph_script.write_text(
                    "fetch('/graph.json').then(response => response.json())"
                    ".then(data => { window.orinocoGraph = data; });\n",
                    encoding="utf-8",
                )
        _run(
            [
                sys.executable,
                adapter,
                destination,
                "--base-path",
                parsed.path or "/",
                "--edit-url",
                f"{base_url}edit/",
            ],
            cwd=workspace.root,
        )
    editor_report = bind_editor(
        workspace,
        runtime_root,
        destination / "edit",
    )
    entries = _manifest(destination)
    digest = hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest()
    report = {
        "assets": asset_report,
        "base_url": base_url,
        "editor": editor_report,
        "files": len(entries),
        "manifest_sha256": digest,
        "version": 1,
    }
    (destination.parent / f"{destination.name}-manifest.sha256").write_text(
        "\n".join(entries) + "\n", encoding="utf-8"
    )
    (destination.parent / f"{destination.name}-build.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args(argv)
    try:
        report = build_site(args.config, args.runtime, args.destination, args.base_url)
    except (ConfigurationError, DriverError, IntegrityError) as error:
        print(f"orinoco build: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
