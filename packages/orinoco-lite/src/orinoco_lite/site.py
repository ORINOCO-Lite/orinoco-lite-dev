"""Location-independent static build driver for flattened consumers."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Sequence
from urllib.parse import unquote, urlsplit

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .config import development_package_root, github_repository, load_config_path
from .errors import ConfigurationError, DriverError, IntegrityError
from .editor import bind_editor
from .integrity import sha256_file
from .projection import load_contract
from .presentation import resolve_presentation
from .review import bind_review
from . import __version__

HUGO_REQUIREMENT = ">=0.161,<0.162"


HUGO_VERSION = re.compile(
    r"^hugo\s+v?(?P<version>[0-9]+(?:\.[0-9]+){2})"
    r"(?:-(?P<revision>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?P<variants>(?:\+[A-Za-z0-9.-]+)*)(?:\s|$)",
    re.IGNORECASE,
)
PRESENTATION_SURFACES = (
    "archetypes",
    "assets",
    "config",
    "data",
    "i18n",
    "layouts",
    "static",
)
SITE_IDENTITY_IMAGE_SUFFIXES = {
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}


def _copy_tree(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise DriverError(f"Static source cannot be a symlink: {source}")
    if not source.is_dir():
        return
    for candidate in sorted(source.rglob("*")):
        relative = candidate.relative_to(source)
        if ".git" in relative.parts:
            continue
        target = destination / relative
        if candidate.is_symlink():
            raise DriverError(f"Static source cannot contain symlinks: {candidate}")
        if candidate.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif candidate.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, target)


def _copy_file(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if source.is_symlink() or not source.is_file():
        raise DriverError(f"Presentation source is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _is_annex_pointer(path: Path) -> bool:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        return False
    try:
        value = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return False
    return value.startswith("/annex/objects/")


def _reject_annex_pointers(root: Path) -> None:
    pointers = [
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if _is_annex_pointer(path)
    ]
    if pointers:
        raise DriverError(
            "Materialized presentation assets are missing for upstream Annex "
            "content: " + ", ".join(pointers[:10])
        )


def _remove_upstream_identity_images(static_root: Path) -> None:
    """Leave root-level site identity images to the theme or downstream."""

    if not static_root.is_dir():
        return
    for path in static_root.iterdir():
        if path.is_file() and path.suffix.lower() in SITE_IDENTITY_IMAGE_SUFFIXES:
            path.unlink()


def _copy_upstream_section_frontmatter(source: Path, destination: Path) -> None:
    """Retain section presentation parameters without importing editorial bodies."""

    if source.is_symlink():
        raise DriverError(f"Upstream content root cannot be a symlink: {source}")
    if not source.is_dir():
        return
    for path in sorted(source.glob("*/_index.md")):
        if path.is_symlink() or not path.is_file():
            raise DriverError(f"Upstream section metadata is not a file: {path}")
        try:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        except UnicodeDecodeError as error:
            raise DriverError(f"Upstream section metadata is not UTF-8: {path}") from error
        if not lines or lines[0].strip() != "---":
            raise DriverError(f"Upstream section has no YAML front matter: {path}")
        closing = next(
            (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
            None,
        )
        if closing is None:
            raise DriverError(f"Upstream section front matter is unclosed: {path}")
        target = destination / path.parent.name / "_index.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(lines[: closing + 1]).rstrip() + "\n", encoding="utf-8")


def _render_template_tree(
    source: Path,
    destination: Path,
    *,
    site_data: dict[str, Any],
) -> None:
    """Render one small presentation-adapter tree from structured site data."""

    if source.is_symlink():
        raise DriverError(f"Presentation template root cannot be a symlink: {source}")
    if not source.is_dir():
        return
    environment = Environment(
        loader=FileSystemLoader(source),
        autoescape=False,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    environment.filters["json_string"] = lambda value: json.dumps(
        value, ensure_ascii=False
    )

    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise DriverError(f"Presentation template cannot be a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file() or path.suffix != ".j2":
            raise DriverError(
                f"Presentation template tree contains unsupported content: {path}"
            )
        relative = path.relative_to(source)
        target = destination / relative.with_suffix("")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            rendered = environment.get_template(relative.as_posix()).render(
                site=site_data
            )
        except Exception as error:
            raise DriverError(
                f"Could not render presentation template {path}: {error}"
            ) from error
        target.write_text(rendered, encoding="utf-8")


def _render_site_surfaces(
    workspace,
    adapter: Path,
    presentation_root: Path,
    assembly: Path,
) -> None:
    site_data = workspace.site_data
    projection = load_contract(workspace, presentation_root)
    record_prefix = site_data.get("record_prefix", projection.route_prefix)
    if record_prefix != projection.route_prefix:
        raise ConfigurationError(
            "Structured site record_prefix must match projection routing.strip_prefix"
        )

    for source_name, destination in (
        ("config-templates", assembly / "config" / "con"),
        ("static-templates", assembly / "static"),
    ):
        _render_template_tree(
            adapter / source_name,
            destination,
            site_data=site_data,
        )


def _safe_destination(workspace, destination: Path) -> Path:
    if not destination.is_absolute():
        destination = workspace.root / destination
    resolved = destination.resolve(strict=False)
    build = workspace.path("build").resolve(strict=False)
    if build not in resolved.parents:
        raise ConfigurationError(f"Build destination must be below {build}: {resolved}")
    return resolved


def _assemble(
    workspace,
    resources_root: Path,
    assembly: Path,
    *,
    presentation: Path | None = None,
) -> None:
    presentation = presentation or resolve_presentation(workspace.root, resources_root)
    upstream = presentation
    theme = upstream / "themes" / "congo"
    adapter = workspace.root / ".orinoco-lite" / "presentation"
    materialized = (
        workspace.root
        / ".orinoco-lite"
        / "materialized-presentation"
        / "upstream"
    )

    for name in PRESENTATION_SURFACES:
        _copy_tree(theme / name, assembly / "themes" / "congo" / name)
    _copy_file(theme / "theme.toml", assembly / "themes" / "congo" / "theme.toml")
    _copy_file(
        theme / "LICENSE",
        assembly / "static" / "LICENSES" / "congo-MIT.txt",
    )

    for name in PRESENTATION_SURFACES:
        _copy_tree(upstream / name, assembly / name)
        _copy_tree(materialized / name, assembly / name)
        if name == "static":
            _remove_upstream_identity_images(assembly / "static")
        _copy_tree(adapter / name, assembly / name)
    _copy_upstream_section_frontmatter(upstream / "content", assembly / "content")

    materialized_license = materialized.parent / "LICENSE"
    if not materialized_license.is_file():
        raise DriverError(
            "The materialized presentation overlay has no LICENSE: "
            f"{materialized_license}"
        )
    _copy_file(
        materialized_license,
        assembly / "static" / "LICENSES" / "materialized-presentation.txt",
    )

    _copy_tree(workspace.path("site") / "config", assembly / "config" / "con")
    # Consumer module mounts describe the ownership layout before flattening.
    # Copying that topology-only file would disable Hugo's implicit mounts and
    # point at paths that no longer exist inside the assembly.
    (assembly / "config" / "con" / "module.toml").unlink(missing_ok=True)
    _render_site_surfaces(workspace, adapter, upstream, assembly)
    overrides = workspace.path("site") / "overrides"
    _copy_tree(overrides / "config", assembly / "config" / "con")
    _copy_tree(overrides / "layouts", assembly / "layouts")
    _copy_tree(overrides / "static", assembly / "static")
    _copy_tree(workspace.path("site") / "assets", assembly / "assets")
    _copy_tree(workspace.path("site") / "static", assembly / "static")
    _copy_tree(workspace.path("editorial"), assembly / "content")
    projection = workspace.path("generated") / "projection"
    _copy_tree(projection / "content", assembly / "content")
    _copy_tree(projection / "static", assembly / "static")
    _copy_file(
        theme / "LICENSE",
        assembly / "static" / "LICENSES" / "congo-MIT.txt",
    )
    _copy_file(
        materialized_license,
        assembly / "static" / "LICENSES" / "materialized-presentation.txt",
    )
    _reject_annex_pointers(assembly)


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
    package_version: str,
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
            f"Orinoco Lite {package_version} requires Hugo {specifier}; "
            f"found {version}"
        )
    return version


def _preflight_hugo(resources_root: Path, *, cwd: Path) -> Version:
    output = _run(["hugo", "version"], cwd=cwd)
    return _require_compatible_hugo(
        output,
        HUGO_REQUIREMENT,
        package_version=__version__,
    )


def _site_adapter(resources_root: Path) -> Path:
    """Select the released adapter or explicitly enabled package candidate."""

    package_root = development_package_root()
    if package_root is None:
        return resources_root / "drivers" / "adapt_pages.py"
    adapter = package_root / "tools" / "adapt_upstream_pages.py"
    if not adapter.is_file():
        raise IntegrityError(f"Package candidate has no site adapter: {adapter}")
    return adapter


def normalize_build_base_url(value: str) -> str:
    """Return an absolute public URL or a host-neutral root-relative path."""

    if not value or value != value.strip():
        raise ConfigurationError("Build base URL cannot be empty or padded")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigurationError(
                "Build base URL must use HTTP(S) or be a root-relative path"
            )
        if parsed.query or parsed.fragment:
            raise ConfigurationError(
                "Build base URL cannot contain a query or fragment"
            )
        return value.rstrip("/") + "/"

    decoded = unquote(value)
    if (
        decoded != value
        or not decoded.startswith("/")
        or decoded.startswith("//")
        or "?" in decoded
        or "#" in decoded
        or "\\" in decoded
        or any(character.isspace() or ord(character) < 0x20 for character in decoded)
    ):
        raise ConfigurationError(
            "Build base URL must use HTTP(S) or be a root-relative path"
        )
    parts = [part for part in decoded.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise ConfigurationError("Build base URL cannot contain path traversal")
    return "/" if not parts else f"/{'/'.join(parts)}/"


def build_site(
    config: Path,
    resources_root: Path,
    destination: Path,
    base_url: str,
    github_repository_coordinate: str | None = None,
) -> dict[str, Any]:
    workspace = load_config_path(config)
    resources_root = resources_root.resolve()
    destination = _safe_destination(workspace, destination)
    base_url = normalize_build_base_url(base_url)
    repository = (
        github_repository(
            github_repository_coordinate,
            "GitHub repository build coordinate",
        )
        if github_repository_coordinate is not None
        else workspace.repository
    )
    parsed = urlsplit(base_url)
    _preflight_hugo(resources_root, cwd=workspace.root)
    assembly = workspace.path("build") / "assembly"
    if assembly.exists():
        shutil.rmtree(assembly)
    assembly.mkdir(parents=True)
    _assemble(workspace, resources_root, assembly)
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
    adapter = _site_adapter(resources_root)
    if adapter.is_file():
        _run(
            [
                sys.executable,
                adapter,
                destination,
                "--base-path",
                parsed.path or base_url,
                "--edit-url",
                f"{base_url}edit/",
            ],
            cwd=workspace.root,
        )
    editor_report = bind_editor(
        workspace,
        resources_root,
        destination / "edit",
        repository=repository,
        service_origin=workspace.curation_service,
    )
    review_report = bind_review(
        workspace,
        resources_root,
        destination / "review",
        repository=repository,
        service_origin=workspace.curation_service,
    )
    entries = _manifest(destination)
    digest = hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest()
    report = {
        "base_url": base_url,
        "editor": editor_report,
        "files": len(entries),
        "manifest_sha256": digest,
        "review": review_report,
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
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args(argv)
    try:
        report = build_site(
            args.config,
            args.resources,
            args.destination,
            args.base_url,
            os.environ.get("ORINOCO_GITHUB_REPOSITORY"),
        )
    except (ConfigurationError, DriverError, IntegrityError) as error:
        print(f"orinoco build: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
