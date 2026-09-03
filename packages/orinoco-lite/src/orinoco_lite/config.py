"""Downstream workspace and release-lock contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
from pathlib import Path, PurePosixPath
import os
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

import yaml

from .errors import ConfigurationError


CONFIG_CONTRACT_VERSION = 2
LOCK_CONTRACT_VERSION = 1
SITE_DATA_VERSION = 1
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DRIVER_NAME = re.compile(r"^[a-z][a-z0-9]*(?:[-.][a-z0-9]+)*$")
GITHUB_REPOSITORY = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})/[A-Za-z0-9_.-]{1,100}$"
)
REVIEW_APP_NAME_SUFFIX = " source metadata review"
REVIEW_APP_NAME_MAXIMUM = 256
DEFAULT_CURATION_SERVICE = "https://orinoco-curation-review.pages.dev"
MAX_REPOSITORY_PATH_LENGTH = 1_024

DEFAULT_PATHS: dict[str, str] = {
    "records": "site-specific/metadata/records",
    "editorial": "site-specific/content",
    "site": "site-specific",
    "generated": "generated",
    "extensions": "extensions",
    "build": "build",
}

DIRECTORY_PATHS = {
    "records",
    "editorial",
    "site",
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
    if (
        len(value) > MAX_REPOSITORY_PATH_LENGTH
        or value != value.strip()
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ConfigurationError(f"{label} must be a normalized relative path")
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


def _browser_text_length(value: str) -> int:
    """Return the UTF-16 code-unit length used by browser string contracts."""

    try:
        return len(value.encode("utf-16-le")) // 2
    except UnicodeEncodeError as error:
        raise ConfigurationError("Text configuration must be valid Unicode") from error


def _review_app_name(site_name: str) -> str:
    """Return the site-owned review title accepted by the static browser shell."""

    if not site_name or site_name != site_name.strip():
        raise ConfigurationError(
            "site-specific/site.yaml identity.title must be a non-empty "
            "unpadded string"
        )
    value = f"{site_name}{REVIEW_APP_NAME_SUFFIX}"
    if (
        _browser_text_length(value) > REVIEW_APP_NAME_MAXIMUM
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ConfigurationError(
            "site-specific/site.yaml identity.title must produce a one-line "
            "source-review application name of at most 256 browser characters"
        )
    return value


def _load_site_data(path: Path) -> dict[str, Any]:
    """Load the declarative authority for public site identity."""

    value = _load_mapping(path, "Site-specific data")
    if value.get("version") != SITE_DATA_VERSION:
        raise ConfigurationError(
            f"site-specific/site.yaml version must be {SITE_DATA_VERSION}"
        )
    identity = value.get("identity")
    if not isinstance(identity, dict):
        raise ConfigurationError("site-specific/site.yaml requires identity")
    normalized_identity = dict(identity)
    for field in ("title", "description"):
        item = identity.get(field)
        if (
            not isinstance(item, str)
            or not item
            or item != item.strip()
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in item)
        ):
            raise ConfigurationError(
                f"site-specific/site.yaml identity.{field} must be a non-empty "
                "one-line string"
            )
        _browser_text_length(item)
        normalized_identity[field] = item
    base_url = _absolute_http_url(
        identity.get("base_url"),
        "site-specific/site.yaml identity.base_url",
        https_only=False,
    )
    if urlsplit(base_url).query:
        raise ConfigurationError(
            "site-specific/site.yaml identity.base_url cannot contain a query"
        )
    normalized_identity["base_url"] = base_url.rstrip("/") + "/"
    normalized = dict(value)
    normalized["identity"] = normalized_identity
    _review_app_name(normalized_identity["title"])
    return normalized


def _canonical_origin_host(hostname: str, label: str) -> str:
    """Return a browser-compatible canonical host without credentials or port."""

    if "%" in hostname:
        raise ConfigurationError(f"{label} has a non-canonical host")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if re.fullmatch(r"[0-9.]+", hostname):
            # WHATWG URLs reinterpret abbreviated and legacy numeric IPv4
            # spellings. Reject them rather than emitting an origin that the
            # browser silently changes.
            raise ConfigurationError(f"{label} has a non-canonical host")
        try:
            ascii_hostname = hostname.encode("ascii").decode("ascii").lower()
        except UnicodeError as error:
            raise ConfigurationError(
                f"{label} host must use its ASCII browser form"
            ) from error
        if not ascii_hostname or not re.fullmatch(r"[a-z0-9._-]+", ascii_hostname):
            raise ConfigurationError(f"{label} has an invalid host")
        if any(
            re.fullmatch(r"0x[0-9a-f]+", part)
            for part in ascii_hostname.rstrip(".").split(".")
        ):
            raise ConfigurationError(f"{label} has a non-canonical host")
        return ascii_hostname
    if isinstance(address, ipaddress.IPv6Address):
        return f"[{address.compressed}]"
    return str(address)


def _curation_service_origin(value: object, label: str) -> str:
    """Return a credential-free HTTPS origin, with loopback HTTP for development."""

    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ConfigurationError(f"{label} must be an absolute origin")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ConfigurationError(f"{label} is invalid") from error
    hostname = parsed.hostname
    canonical_host = (
        _canonical_origin_host(hostname, label) if hostname is not None else None
    )
    loopback = parsed.scheme == "http" and canonical_host in {
        "127.0.0.1",
        "localhost",
    }
    if (
        (parsed.scheme != "https" and not loopback)
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(
            f"{label} must be a credential-free HTTPS origin "
            "(or a loopback development origin)"
        )
    default_port = 443 if parsed.scheme == "https" else 80
    authority = canonical_host
    if port is not None and port != default_port:
        authority = f"{authority}:{port}"
    origin = f"{parsed.scheme}://{authority}"
    if len(origin) > 256:
        raise ConfigurationError(f"{label} must be at most 256 characters")
    return origin


def github_repository(value: object, label: str) -> str:
    """Return one exact GitHub owner/repository build coordinate."""

    if (
        not isinstance(value, str)
        or not GITHUB_REPOSITORY.fullmatch(value)
        or ".." in value
    ):
        raise ConfigurationError(f"{label} must use GitHub owner/repository form")
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
    site_data: Mapping[str, Any] = field(default_factory=dict)
    repository: str | None = None
    curation_service: str = DEFAULT_CURATION_SERVICE

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
class EngineLock:
    """Resolved immutable package pin from ``orinoco.lock``."""

    path: Path
    distribution: str
    engine_version: str
    engine_url: str
    engine_sha256: str
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
    """Load and resolve a version-2 downstream workspace."""

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

    site_data = _load_site_data(
        _inside(resolved_root, paths["site"], "paths.site") / "site.yaml"
    )
    identity = site_data["identity"]
    site_name = identity["title"]
    base_url = identity["base_url"]

    site = raw.get("site", {})
    if not isinstance(site, dict):
        raise ConfigurationError("orinoco.yaml site must be a mapping")
    unknown_site = sorted(set(site) - {"repository", "curation_service"})
    if unknown_site:
        raise ConfigurationError(
            "orinoco.yaml contains public site identity; move these site fields to "
            "site-specific/site.yaml: " + ", ".join(unknown_site)
        )
    repository_value = site.get("repository")
    service_value = site.get("curation_service")
    repository: str | None = None
    curation_service = _curation_service_origin(
        service_value if service_value is not None else DEFAULT_CURATION_SERVICE,
        "orinoco.yaml site.curation_service",
    )
    if repository_value is not None:
        repository = github_repository(
            repository_value,
            "orinoco.yaml site.repository",
        )

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
        site_name=site_name,
        base_url=base_url,
        site_data=site_data,
        paths=paths,
        command_aliases=normalized_aliases,
        raw=raw,
        repository=repository,
        curation_service=curation_service,
    )


def load_config_path(path: Path) -> WorkspaceConfig:
    """Load an explicitly named configuration file in its parent workspace."""

    path = path.resolve()
    return load_workspace(path.parent, config_name=path.name)


def load_lock(path: Path) -> EngineLock:
    """Load a strict immutable package lock."""

    raw = _load_mapping(path, "Orinoco lock")
    if raw.get("lock_version") != LOCK_CONTRACT_VERSION:
        raise ConfigurationError(
            f"orinoco.lock lock_version must be {LOCK_CONTRACT_VERSION}"
        )
    engine = raw.get("engine")
    if not isinstance(engine, dict):
        raise ConfigurationError("orinoco.lock requires an engine mapping")
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

    return EngineLock(
        path=path.resolve(),
        distribution=distribution,
        engine_version=engine_version,
        engine_url=engine_url,
        engine_sha256=engine_digest,
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


def development_engine_root() -> Path | None:
    """Resolve the explicitly selected local engineering working tree."""

    if not development_runtime_allowed():
        return None
    root_value = os.environ.get("ORINOCO_CANDIDATE_ENGINE_ROOT")
    if root_value is None:
        return None
    root = Path(root_value).resolve()
    source = root / "packages/orinoco-lite/src"
    if not (source / "orinoco_lite/__init__.py").is_file():
        raise ConfigurationError(
            "ORINOCO_CANDIDATE_ENGINE_ROOT does not contain "
            "packages/orinoco-lite/src/orinoco_lite"
        )
    return root


def development_engine_source() -> Path | None:
    """Resolve the explicitly selected local engine source for development."""

    root = development_engine_root()
    if root is None:
        return None
    source = root / "packages/orinoco-lite/src"
    return source


def development_editor_shell() -> Path | None:
    """Resolve the editor shell built for a local engine candidate."""

    if development_engine_root() is None:
        return None
    shell_value = os.environ.get("ORINOCO_CANDIDATE_EDITOR_SHELL")
    if shell_value is None:
        raise ConfigurationError(
            "Local engine candidate has no editor shell; run it through the "
            "downstream candidate command"
        )
    shell = Path(shell_value).resolve()
    if not shell.is_dir() or not (shell / "index.html").is_file():
        raise ConfigurationError(
            "ORINOCO_CANDIDATE_EDITOR_SHELL does not contain a built editor"
        )
    return shell
