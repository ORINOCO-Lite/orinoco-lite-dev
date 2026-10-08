"""Location-independent static build driver for flattened consumers."""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping
from copy import deepcopy
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
import tomlkit

from .progress import progress
from .config import github_repository, load_config_path
from .errors import ConfigurationError, DriverError, IntegrityError
from .editor import bind_editor
from .integrity import sha256_file
from .projection import load_contract
from .www_from_model import resolve_www_from_model
from .upstream_runtime import (
    HUGO_SURFACES, _copy_tree, _copy_file, _reject_annex_pointers, copy_hugo_runtime,
)
from .review import bind_review
from .resources import SOURCE_REPOSITORY, source_commit, source_description
from . import __version__

GITHUB_REPOSITORY_URL = "https://github.com/"
FOOTER_PARTIAL = """{{ with .Site.Data.orinoco_build }}
  {{ with .engine }}
    <p class="text-xs text-neutral-500 dark:text-neutral-400">
      Orinoco Lite {{ .version }}
      (<a class="hover:underline hover:decoration-primary-400 hover:text-primary-500" href="{{ .url }}">{{ .describe }}</a>)
      {{ with $.Site.Data.orinoco_build.content }}
        · content <a class="hover:underline hover:decoration-primary-400 hover:text-primary-500" href="{{ .url }}">{{ .describe }}</a>
      {{ end }}
      {{ with $.Site.Data.orinoco_build.built_at }} · built {{ . }}{{ end }}
    </p>
  {{ end }}
{{ end }}
"""


def _overlay_config(source: Path, destination: Path) -> None:
    """Apply authored TOML settings without dropping other selected tables."""
    if source.is_symlink():
        raise DriverError(f"Configuration source cannot be a symlink: {source}")
    if not source.is_dir():
        return

    def merge(base, override):
        for key, value in override.items():
            if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
                merge(base[key], value)
            else:
                base[key] = deepcopy(value)

    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise DriverError(f"Configuration override cannot be a symlink: {path}")
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        if target.is_file() and path.suffix == ".toml":
            try:
                document = tomlkit.parse(target.read_text())
                merge(document, tomlkit.parse(path.read_text()))
                target.write_text(tomlkit.dumps(document))
            except (ValueError, TypeError) as error:
                raise DriverError(f"Cannot apply TOML configuration override {path}: {error}") from error
        else:
            _copy_file(path, target)


def _render_template_tree(
    source: Path,
    destination: Path,
    *,
    site_data: dict[str, Any],
) -> None:
    """Render one small Hugo adaptation tree from structured site data."""

    if source.is_symlink():
        raise DriverError(f"Hugo adaptation template root cannot be a symlink: {source}")
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
            raise DriverError(f"Hugo adaptation template cannot be a symlink: {path}")
        if path.is_dir():
            continue
        if path.name == ".DS_Store" and path.is_file():
            continue
        if not path.is_file() or path.suffix != ".j2":
            raise DriverError(
                f"Hugo adaptation template tree contains unsupported content: {path}"
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
                f"Could not render Hugo adaptation template {path}: {error}"
            ) from error
        target.write_text(rendered, encoding="utf-8")


def _render_site_surfaces(
    workspace,
    adapter: Path,
    www_from_model_root: Path,
    assembly: Path,
) -> None:
    site_data = workspace.site_data
    projection = load_contract(workspace, www_from_model_root)
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


def _git_output(root: Path, *arguments: str) -> str | None:
    """Return one bounded Git value from an ordinary downstream checkout."""

    try:
        completed = subprocess.run(
            ("git", "-C", str(root), *arguments),
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    value = completed.stdout.strip()
    if completed.returncode or not value or "\n" in value or len(value) > 200:
        return None
    return value


def _build_timestamp(value: str | None) -> str | None:
    """Normalize an explicitly supplied UTC build timestamp for static output."""

    if value is None:
        return None
    if value != value.strip() or not value:
        raise ConfigurationError("Build timestamp must be a non-empty UTC ISO 8601 value")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ConfigurationError("Build timestamp must be a UTC ISO 8601 value") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ConfigurationError("Build timestamp must be a UTC ISO 8601 value")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _build_provenance(
    workspace,
    resources_root: Path,
    repository: str | None,
    build_timestamp: str | None,
) -> dict[str, Any]:
    """Return footer data derived from immutable release and checkout inputs."""

    engine_commit = source_commit(resources_root)
    provenance: dict[str, Any] = {
        "engine": {
            "describe": source_description(resources_root),
            "repository": SOURCE_REPOSITORY,
            "url": f"{SOURCE_REPOSITORY}/commit/{engine_commit}",
            "version": __version__,
        },
        "built_at": _build_timestamp(build_timestamp),
    }
    content_commit = _git_output(workspace.root, "rev-parse", "--verify", "HEAD^{commit}")
    content_description = _git_output(workspace.root, "describe", "--always")
    if (
        repository is not None
        and content_commit is not None
        and content_description is not None
    ):
        provenance["content"] = {
            "describe": content_description,
            "repository": repository,
            "url": f"{GITHUB_REPOSITORY_URL}{repository}/commit/{content_commit}",
        }
    return provenance


def _write_build_provenance_footer(assembly: Path, provenance: dict[str, Any]) -> None:
    """Install the package-owned footer while preserving a site extension."""

    data = assembly / "data" / "orinoco_build.json"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    partials = assembly / "layouts" / "_partials"
    partials.mkdir(parents=True, exist_ok=True)
    footer = partials / "extend-footer.html"
    if footer.exists():
        if footer.is_symlink() or not footer.is_file():
            raise DriverError(f"Site footer extension is not a regular file: {footer}")
        try:
            site_extension = footer.read_text(encoding="utf-8").rstrip() + "\n"
        except UnicodeDecodeError as error:
            raise DriverError(f"Site footer extension is not UTF-8: {footer}") from error
    else:
        site_extension = ""
    footer.write_text(site_extension + FOOTER_PARTIAL, encoding="utf-8")


def _safe_destination(workspace, destination: Path) -> Path:
    if not destination.is_absolute():
        destination = workspace.root / destination
    resolved = destination.resolve(strict=False)
    build = workspace.path("build").resolve(strict=False)
    if build not in resolved.parents:
        raise ConfigurationError(f"Build destination must be below {build}: {resolved}")
    for name in ("hugo-projection", "hugo-assembly", "hugo-cache", "hugo-resources"):
        reserved = (build / name).resolve(strict=False)
        if resolved == reserved or reserved in resolved.parents or resolved in reserved.parents:
            raise ConfigurationError(f"Build destination overlaps {name}: {resolved}")
    return resolved


@progress("Preparing the website")
def _assemble(
    workspace,
    resources_root: Path,
    assembly: Path,
    *,
    www_from_model: Path | None = None,
) -> None:
    from .annex_media import prepare_media, prepare_hugo_assets
    from .www_from_model import editable_package_checkout

    media = prepare_media(workspace)
    upstream = www_from_model or resolve_www_from_model(workspace.root, resources_root)
    theme = upstream / "themes" / "congo"
    adapter = workspace.root / ".orinoco-lite" / "hugo-adapter"
    upstream_media = (prepare_hugo_assets(
        upstream, editable=True,
        remote="https://hub.psychoinformatics.de/www/www-from-model.git",
    ) if editable_package_checkout() is not None else {})
    copy_hugo_runtime(upstream, assembly, media=upstream_media)
    for name in HUGO_SURFACES:
        _copy_tree(adapter / name, assembly / name)

    _copy_tree(workspace.path("site") / "config", assembly / "config" / "con")
    # Consumer module mounts describe the ownership layout before flattening.
    # Copying that topology-only file would disable Hugo's implicit mounts and
    # point at paths that no longer exist inside the assembly.
    (assembly / "config" / "con" / "module.toml").unlink(missing_ok=True)
    _render_site_surfaces(workspace, adapter, upstream, assembly)
    overrides = workspace.path("site") / "overrides"
    _overlay_config(overrides / "config", assembly / "config" / "con")
    _copy_tree(overrides / "layouts", assembly / "layouts")
    _copy_tree(overrides / "static", assembly / "static")
    _copy_tree(workspace.path("site") / "assets", assembly / "assets", media=media)
    _copy_tree(workspace.path("site") / "static", assembly / "static", media=media)
    projection = workspace.path("build") / "hugo-projection"
    _copy_tree(projection / "content", assembly / "content")
    _copy_tree(projection / "static", assembly / "static")
    _copy_tree(workspace.path("editorial"), assembly / "content")
    _copy_file(
        theme / "LICENSE",
        assembly / "static" / "LICENSES" / "congo-MIT.txt",
    )

    _reject_annex_pointers(assembly)


def _manifest(root: Path) -> list[str]:
    return [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file())
    ]


def _run(
    command: Sequence[str | Path], *, cwd: Path,
    environment: dict[str, str] | None = None,
) -> str:
    try:
        result = subprocess.run(
            [str(item) for item in command],
            cwd=cwd,
            env={**os.environ, **environment} if environment is not None else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise DriverError(f"Static build command is missing: {command[0]}") from error
    if result.returncode:
        raise DriverError((result.stderr or result.stdout).strip())
    return result.stdout


def _site_adapter(resources_root: Path) -> Path:
    """Select the released adapter or explicitly enabled package candidate."""

    return resources_root / "drivers" / "adapt_pages.py"


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
    build_timestamp: str | None = None,
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
    assembly = workspace.path("build") / "hugo-assembly"
    if assembly.exists():
        shutil.rmtree(assembly)
    assembly.mkdir(parents=True)
    _assemble(workspace, resources_root, assembly)
    _write_build_provenance_footer(
        assembly,
        _build_provenance(workspace, resources_root, repository, build_timestamp),
    )
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with progress("Building the site with Hugo"):
        _run(
            [
                "hugo",
                "--minify",
                "--cleanDestinationDir",
                "--cacheDir",
                workspace.path("build") / "hugo-cache",
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
            environment={"HUGO_RESOURCEDIR": str(workspace.path("build") / "hugo-resources")},
        )
    adapter = _site_adapter(resources_root)
    with progress("Preparing editing and review pages"):
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
    parser.add_argument("--build-timestamp")
    parser.add_argument("--json", action="store_true", help="print the build report as JSON")
    args = parser.parse_args(argv)
    try:
        report = build_site(
            args.config,
            args.resources,
            args.destination,
            args.base_url,
            os.environ.get("ORINOCO_GITHUB_REPOSITORY"),
            args.build_timestamp,
        )
    except (ConfigurationError, DriverError, IntegrityError) as error:
        print(f"orinoco-lite build: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"Built website in {args.destination} ({report['files']} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
