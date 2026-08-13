"""Downstream workspace and release-lock contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import os
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

import yaml

from .errors import ConfigurationError


CONFIG_CONTRACT_VERSION = 1
LOCK_CONTRACT_VERSION = 1
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DRIVER_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[-.][a-z0-9]+)*$")

DEFAULT_PATHS: dict[str, str] = {
    "canonical": "metadata/records",
    "reference": "metadata/reference",
    "provenance": "metadata/provenance",
    "editorial": "editorial",
    "assets": "assets",
    "site": "site",
    "integrations": "integrations",
    "generated": "generated",
    "extensions": "extensions",
    "build": "build",
}

DIRECTORY_PATHS = {
    "canonical",
    "reference",
    "provenance",
    "editorial",
    "assets",
    "site",
    "integrations",
    "generated",
    "extensions",
    "build",
}


def _load_mapping(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError(f"{label} is missing or is not a regular file: {path}")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ConfigurationError(f"{label} is unexpectedly large: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f"{label} is not valid UTF-8 YAML: {path}") from error
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ConfigurationError(f"{label} must be a YAML mapping: {path}")
    return value


def _relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ConfigurationError(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value.rstrip("/")
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ConfigurationError(f"{label} must be a normalized relative path")
    return path.as_posix()


def _absolute_http_url(value: object, label: str, *, https_only: bool) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{label} must be an absolute URL")
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError as error:
        raise ConfigurationError(f"{label} is invalid") from error
    schemes = {"https"} if https_only else {"http", "https"}
    if (
        parsed.scheme not in schemes
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        qualifier = "credential-free HTTPS" if https_only else "credential-free HTTP(S)"
        raise ConfigurationError(f"{label} must be a {qualifier} URL")
    return value


def _inside(root: Path, relative: str, label: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    resolved_root = root.resolve()
    resolved = candidate.resolve(strict=False)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ConfigurationError(f"{label} escapes the workspace root")
    return candidate


@dataclass(frozen=True)
class WorkspaceConfig:
    """Resolved public configuration for one single-repository site."""

    root: Path
    config_path: Path
    lock_path: Path
    site_name: str
    base_url: str
    paths: Mapping[str, str]
    command_aliases: Mapping[str, str]
    raw: Mapping[str, Any]

    def path(self, name: str) -> Path:
        try:
            relative = self.paths[name]
        except KeyError as error:
            raise ConfigurationError(f"Unknown workspace path: {name}") from error
        return _inside(self.root, relative, f"paths.{name}")

    def driver_name(self, action: str) -> str:
        return self.command_aliases.get(action, action)

    def environment(self) -> dict[str, str]:
        """Return the stable environment understood by released drivers."""

        values = {
            "ORINOCO_ROOT": str(self.root),
            "ORINOCO_CONFIG": str(self.config_path),
            "ORINOCO_LOCK": str(self.lock_path),
        }
        for name in sorted(self.paths):
            variable = "ORINOCO_" + name.upper().replace("-", "_") + "_ROOT"
            values[variable] = str(self.path(name))
        return values


@dataclass(frozen=True)
class RuntimePin:
    """One immutable runtime archive or development directory."""

    version: str
    url: str | None
    path: str | None
    sha256: str
    manifest_sha256: str


@dataclass(frozen=True)
class EngineLock:
    """Resolved engine/runtime pins from ``orinoco.lock``."""

    path: Path
    distribution: str
    engine_version: str
    engine_url: str
    engine_sha256: str
    runtime: RuntimePin
    raw: Mapping[str, Any]


def find_workspace_root(start: Path | None = None) -> Path:
    """Find the nearest ancestor containing ``orinoco.yaml``."""

    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "orinoco.yaml").is_file():
            return candidate
    raise ConfigurationError(
        f"Could not find orinoco.yaml at or above {current}; pass --root explicitly"
    )


def load_workspace(
    root: Path | None = None,
    *,
    config_name: str = "orinoco.yaml",
    lock_name: str = "orinoco.lock",
) -> WorkspaceConfig:
    """Load and resolve a version-1 downstream workspace."""

    resolved_root = find_workspace_root(root) if root is None else root.resolve()
    if not resolved_root.is_dir():
        raise ConfigurationError(f"Workspace root is not a directory: {resolved_root}")
    config_relative = _relative_path(config_name, "configuration path")
    lock_relative = _relative_path(lock_name, "lock path")
    config_path = _inside(resolved_root, config_relative, "configuration path")
    lock_path = _inside(resolved_root, lock_relative, "lock path")
    raw = _load_mapping(config_path, "Orinoco configuration")
    if raw.get("contract_version") != CONFIG_CONTRACT_VERSION:
        raise ConfigurationError(
            f"orinoco.yaml contract_version must be {CONFIG_CONTRACT_VERSION}"
        )

    site = raw.get("site")
    if not isinstance(site, dict):
        raise ConfigurationError("orinoco.yaml site must be a mapping")
    site_name = site.get("name")
    if not isinstance(site_name, str) or not site_name.strip():
        raise ConfigurationError("orinoco.yaml site.name must be a non-empty string")
    base_url = _absolute_http_url(
        site.get("base_url", "http://127.0.0.1:8767/"),
        "orinoco.yaml site.base_url",
        https_only=False,
    )
    if not base_url.endswith("/"):
        base_url += "/"

    path_values = raw.get("paths", {})
    if not isinstance(path_values, dict) or not all(
        isinstance(key, str) for key in path_values
    ):
        raise ConfigurationError("orinoco.yaml paths must be a mapping")
    unknown_paths = sorted(set(path_values) - set(DEFAULT_PATHS))
    if unknown_paths:
        raise ConfigurationError(
            f"orinoco.yaml has unknown path keys: {', '.join(unknown_paths)}"
        )
    paths = {
        name: _relative_path(path_values.get(name, default), f"paths.{name}")
        for name, default in DEFAULT_PATHS.items()
    }
    duplicates: dict[str, list[str]] = {}
    for name, value in paths.items():
        duplicates.setdefault(value, []).append(name)
    collisions = [names for names in duplicates.values() if len(names) > 1]
    if collisions:
        raise ConfigurationError(
            "orinoco.yaml paths must be distinct: "
            + "; ".join(", ".join(names) for names in collisions)
        )
    for name, value in paths.items():
        _inside(resolved_root, value, f"paths.{name}")

    runtime = raw.get("runtime", {})
    if not isinstance(runtime, dict):
        raise ConfigurationError("orinoco.yaml runtime must be a mapping")
    aliases = runtime.get("commands", {})
    if not isinstance(aliases, dict):
        raise ConfigurationError("orinoco.yaml runtime.commands must be a mapping")
    normalized_aliases: dict[str, str] = {}
    for public_name, driver_name in aliases.items():
        if (
            not isinstance(public_name, str)
            or not DRIVER_NAME.fullmatch(public_name)
            or not isinstance(driver_name, str)
            or not DRIVER_NAME.fullmatch(driver_name)
        ):
            raise ConfigurationError(
                "runtime.commands keys and values must be normalized driver names"
            )
        normalized_aliases[public_name] = driver_name

    return WorkspaceConfig(
        root=resolved_root,
        config_path=config_path,
        lock_path=lock_path,
        site_name=site_name.strip(),
        base_url=base_url,
        paths=paths,
        command_aliases=normalized_aliases,
        raw=raw,
    )


def load_config_path(path: Path) -> WorkspaceConfig:
    """Load an explicitly named configuration file in its parent workspace."""

    path = path.resolve()
    return load_workspace(path.parent, config_name=path.name)


def load_lock(path: Path) -> EngineLock:
    """Load a strict immutable package/runtime lock."""

    raw = _load_mapping(path, "Orinoco lock")
    if raw.get("lock_version") != LOCK_CONTRACT_VERSION:
        raise ConfigurationError(
            f"orinoco.lock lock_version must be {LOCK_CONTRACT_VERSION}"
        )
    engine = raw.get("engine")
    runtime = raw.get("runtime")
    if not isinstance(engine, dict) or not isinstance(runtime, dict):
        raise ConfigurationError("orinoco.lock requires engine and runtime mappings")
    distribution = engine.get("distribution")
    engine_version = engine.get("version")
    engine_url = engine.get("url")
    engine_digest = engine.get("sha256")
    if distribution != "orinoco-lite":
        raise ConfigurationError("orinoco.lock engine.distribution must be orinoco-lite")
    if not isinstance(engine_version, str) or not engine_version:
        raise ConfigurationError("orinoco.lock engine.version must be a string")
    engine_url = _absolute_http_url(
        engine_url, "orinoco.lock engine.url", https_only=True
    )
    if (
        not isinstance(engine_digest, str)
        or not SHA256.fullmatch(engine_digest)
        or set(engine_digest) == {"0"}
    ):
        raise ConfigurationError("orinoco.lock engine.sha256 must be lowercase SHA-256")
    wheel_name = PurePosixPath(urlsplit(engine_url).path).name
    expected_wheel_prefix = f"orinoco_lite-{engine_version.replace('-', '_')}-"
    if not wheel_name.startswith(expected_wheel_prefix) or not wheel_name.endswith(
        ".whl"
    ):
        raise ConfigurationError(
            "orinoco.lock engine.url must name the exact locked orinoco-lite wheel"
        )

    runtime_version = runtime.get("version")
    url = runtime.get("url")
    location = runtime.get("path")
    digest = runtime.get("sha256")
    manifest_digest = runtime.get("manifest_sha256")
    if not isinstance(runtime_version, str) or not runtime_version:
        raise ConfigurationError("orinoco.lock runtime.version must be a string")
    if (url is None) == (location is None):
        raise ConfigurationError("orinoco.lock runtime requires exactly one of url or path")
    if url is not None:
        url = _absolute_http_url(url, "orinoco.lock runtime.url", https_only=True)
    if location is not None:
        location = _relative_path(location, "orinoco.lock runtime.path")
    if (
        not isinstance(digest, str)
        or not SHA256.fullmatch(digest)
        or set(digest) == {"0"}
    ):
        raise ConfigurationError("orinoco.lock runtime.sha256 must be lowercase SHA-256")
    if (
        not isinstance(manifest_digest, str)
        or not SHA256.fullmatch(manifest_digest)
        or set(manifest_digest) == {"0"}
    ):
        raise ConfigurationError(
            "orinoco.lock runtime.manifest_sha256 must be lowercase SHA-256"
        )
    return EngineLock(
        path=path.resolve(),
        distribution=distribution,
        engine_version=engine_version,
        engine_url=engine_url,
        engine_sha256=engine_digest,
        runtime=RuntimePin(
            version=runtime_version,
            url=url,
            path=location,
            sha256=digest,
            manifest_sha256=manifest_digest,
        ),
        raw=raw,
    )


def load_workspace_lock(workspace: WorkspaceConfig) -> EngineLock:
    return load_lock(workspace.lock_path)


def development_runtime_allowed() -> bool:
    """Return whether an unhashed environment override is explicitly enabled.

    This is intentionally not used by normal commands. It exists so runtime
    authors can build dedicated tooling without accidentally weakening the
    downstream release path.
    """

    return os.environ.get("ORINOCO_UNSAFE_DEVELOPMENT_RUNTIME") == "1"
