"""Digest-verified materialization of site-owned downstream assets."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Mapping
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import yaml

from .config import WorkspaceConfig
from .errors import ConfigurationError, IntegrityError
from .integrity import sha256_file


MAX_ASSET_BYTES = 1024 * 1024 * 1024


@dataclass(frozen=True)
class Asset:
    source: str
    sha256: str
    size: int
    availability: str
    object_url: str | None


def _relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ConfigurationError(f"{label} must be a POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise ConfigurationError(f"{label} must be a normalized relative path")
    return path.as_posix()


def load_assets(workspace: WorkspaceConfig) -> tuple[dict[str, Asset], dict[str, str]]:
    path = workspace.path("assets") / "manifest.yaml"
    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Asset manifest is invalid: {path}") from error
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ConfigurationError("Asset manifest must be a version-1 mapping")
    entries = manifest.get("assets")
    if not isinstance(entries, dict):
        raise ConfigurationError("Asset manifest assets must be a mapping")
    assets: dict[str, Asset] = {}
    for name, value in entries.items():
        source = _relative(name, "Asset source")
        if not isinstance(value, dict):
            raise ConfigurationError(f"Asset declaration must be a mapping: {source}")
        digest = value.get("sha256")
        size = value.get("size")
        availability = value.get("availability")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(size, int)
            or size < 0
            or size > MAX_ASSET_BYTES
            or availability not in {"available", "unavailable", "absent-in-source"}
        ):
            raise ConfigurationError(f"Asset declaration is invalid: {source}")
        retrieval = value.get("retrieval")
        object_url = retrieval.get("object_url") if isinstance(retrieval, dict) else None
        if object_url is not None:
            parsed = urlsplit(object_url)
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise ConfigurationError(f"Asset retrieval URL is invalid: {source}")
        assets[source] = Asset(source, digest, size, availability, object_url)
    links: dict[str, str] = {}
    for group in ("projection_links", "static_links"):
        mapping = manifest.get(group, {})
        if not isinstance(mapping, dict):
            raise ConfigurationError(f"Asset manifest {group} must be a mapping")
        for destination, source in mapping.items():
            normalized_destination = _relative(destination, f"{group} destination")
            normalized_source = _relative(source, f"{group} source")
            if normalized_source not in assets:
                raise ConfigurationError(
                    f"Asset link references an undeclared source: {normalized_source}"
                )
            if normalized_destination in links:
                raise ConfigurationError(
                    f"Asset destination is declared twice: {normalized_destination}"
                )
            links[normalized_destination] = normalized_source
    return assets, links


def verify_asset(path: Path, asset: Asset) -> None:
    if path.is_symlink() or not path.is_file():
        raise IntegrityError(f"Asset is missing: {asset.source}")
    if path.stat().st_size != asset.size or sha256_file(path) != asset.sha256:
        raise IntegrityError(f"Asset failed integrity verification: {asset.source}")


def hydrate_asset_cache(path: Path, asset: Asset) -> None:
    if asset.object_url is None:
        raise IntegrityError(
            f"Asset {asset.source} is absent and has no read-only retrieval URL"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    temporary.unlink()
    request = Request(asset.object_url, headers={"User-Agent": "orinoco-lite-assets/1"})
    try:
        with urlopen(request, timeout=120) as response, temporary.open("xb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > asset.size or total > MAX_ASSET_BYTES:
                    raise IntegrityError(f"Asset download is too large: {asset.source}")
                output.write(chunk)
        verify_asset(temporary, asset)
        os.replace(temporary, path)
    except IntegrityError:
        temporary.unlink(missing_ok=True)
        raise
    except Exception as error:
        temporary.unlink(missing_ok=True)
        raise IntegrityError(f"Could not hydrate asset: {asset.source}") from error
