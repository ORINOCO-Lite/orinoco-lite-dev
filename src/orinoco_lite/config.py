"""Downstream workspace configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

import tomllib

from .errors import ConfigurationError


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
    "extensions": "extensions",
    "build": "build",
}
FIXED_PATHS = frozenset({"site", "build"})

DIRECTORY_PATHS = {
    "records",
    "editorial",
    "site",
    "extensions",
    "build",
}


def parse_configuration(text: str) -> dict[str, Any]:
    """Read the downstream tool table without interpreting other TOML sections."""
    try:
        document = tomllib.loads(text)
        value = document.get("tool", {}).get("orinoco")
    except (ValueError, AttributeError) as error:
        raise ConfigurationError("pyproject.toml must contain valid TOML configuration") from error
    if not isinstance(value, dict):
        raise ConfigurationError("pyproject.toml requires [tool.orinoco] configuration")
    return value


def read_configuration(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError(f"Configuration is missing or is not a regular file: {path}")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ConfigurationError(f"Configuration is unexpectedly large: {path}")
    try:
        return parse_configuration(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise ConfigurationError(f"Configuration is not readable UTF-8: {path}") from error


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
            "pyproject.toml tool.orinoco.site.identity.title must be a non-empty "
            "unpadded string"
        )
    value = f"{site_name}{REVIEW_APP_NAME_SUFFIX}"
    if (
        _browser_text_length(value) > REVIEW_APP_NAME_MAXIMUM
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ConfigurationError(
            "pyproject.toml tool.orinoco.site.identity.title must produce a one-line "
            "source-review application name of at most 256 browser characters"
        )
    return value


def _load_site_data(value: object) -> dict[str, Any]:
    """Validate the public site settings from the runtime manifest."""
    if not isinstance(value, dict):
        raise ConfigurationError("pyproject.toml requires [tool.orinoco.site]")
    identity = value.get("identity")
    if not isinstance(identity, dict):
        raise ConfigurationError("pyproject.toml tool.orinoco.site requires identity")
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
                f"pyproject.toml tool.orinoco.site.identity.{field} must be a non-empty "
                "one-line string"
            )
        _browser_text_length(item)
        normalized_identity[field] = item
    base_url = _absolute_http_url(
        identity.get("base_url"),
        "pyproject.toml tool.orinoco.site.identity.base_url",
        https_only=False,
    )
    if urlsplit(base_url).query:
        raise ConfigurationError(
            "pyproject.toml tool.orinoco.site.identity.base_url cannot contain a query"
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
    site_name: str
    base_url: str
    paths: Mapping[str, str]
    raw: Mapping[str, Any]
    site_data: Mapping[str, Any] = field(default_factory=dict)
    repository: str | None = None
    annex_media: bool = False
    curation_service: str = DEFAULT_CURATION_SERVICE

    def path(self, name: str) -> Path:
        try:
            relative = self.paths[name]
        except KeyError as error:
            raise ConfigurationError(f"Unknown workspace path: {name}") from error
        return _inside(self.root, relative, f"paths.{name}")

    def environment(self) -> dict[str, str]:
        """Return the stable environment understood by released drivers."""

        values = {
            "ORINOCO_ROOT": str(self.root),
            "ORINOCO_CONFIG": str(self.config_path),
        }
        for name in sorted(self.paths):
            variable = "ORINOCO_" + name.upper().replace("-", "_") + "_ROOT"
            values[variable] = str(self.path(name))
        return values


def find_workspace_root(start: Path | None = None) -> Path:
    """Find the nearest ancestor with a downstream ``tool.orinoco`` table."""

    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        manifest = candidate / "pyproject.toml"
        if manifest.is_file():
            try:
                document = tomllib.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, ValueError) as error:
                raise ConfigurationError(f"Cannot read TOML configuration: {manifest}") from error
            tool = document.get("tool", {})
            if isinstance(tool, dict) and "orinoco" in tool:
                return candidate
    raise ConfigurationError(
        f"Could not find tool.orinoco in pyproject.toml at or above {current}; pass --root explicitly"
    )


def validate_operations(operations: object) -> dict[str, bool]:
    """Validate explicit operation opt-ins; missing keys remain disabled."""
    allowed = {"shacl_materialization", "automated_curation", "template_updates", "preview_editing"}
    if (not isinstance(operations, dict) or
            any(key not in allowed or type(value) is not bool for key, value in operations.items())):
        raise ConfigurationError("pyproject.toml tool.orinoco.operations must map known operation names to true or false")
    return operations


def load_workspace(
    root: Path | None = None,
    *,
    config_name: str = "pyproject.toml",
) -> WorkspaceConfig:
    """Load and resolve a downstream workspace."""

    resolved_root = find_workspace_root(root) if root is None else root.resolve()
    if not resolved_root.is_dir():
        raise ConfigurationError(f"Workspace root is not a directory: {resolved_root}")
    config_relative = _relative_path(config_name, "configuration path")
    config_path = _inside(resolved_root, config_relative, "configuration path")
    raw = read_configuration(config_path)

    path_values = raw.get("paths", {})
    if not isinstance(path_values, dict) or not all(
        isinstance(key, str) for key in path_values
    ):
        raise ConfigurationError("pyproject.toml paths must be a mapping")
    unknown_paths = sorted(set(path_values) - set(DEFAULT_PATHS))
    if unknown_paths:
        raise ConfigurationError(
            f"pyproject.toml has unknown path keys: {', '.join(unknown_paths)}"
        )
    fixed_paths = sorted(set(path_values) & FIXED_PATHS)
    if fixed_paths:
        raise ConfigurationError(
            "pyproject.toml cannot override package-owned paths: "
            + ", ".join(fixed_paths)
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
            "pyproject.toml paths must be distinct: "
            + "; ".join(", ".join(names) for names in collisions)
        )
    for name, value in paths.items():
        _inside(resolved_root, value, f"paths.{name}")

    site_data = _load_site_data(raw.get("site"))
    identity = site_data["identity"]
    site_name = identity["title"]
    base_url = identity["base_url"]
    validate_operations(raw.get("operations", {}))
    service = raw.get("service", {})
    github = raw.get("github", {})
    if not isinstance(service, dict) or not isinstance(github, dict):
        raise ConfigurationError("tool.orinoco.service and tool.orinoco.github must be tables")
    repository_value = github.get("repository")
    repository = None if repository_value is None else github_repository(
        repository_value, "tool.orinoco.github.repository")
    curation_service = _curation_service_origin(
        service.get("url", DEFAULT_CURATION_SERVICE), "tool.orinoco.service.url")

    media = raw.get("media", {})
    if (not isinstance(media, dict) or set(media) - {"annex"}
            or not isinstance(media.get("annex", False), bool)):
        raise ConfigurationError("pyproject.toml tool.orinoco.media accepts only annex = true or false")

    workspace = WorkspaceConfig(
        root=resolved_root,
        config_path=config_path,
        site_name=site_name,
        base_url=base_url,
        site_data=site_data,
        paths=paths,
        raw=raw,
        repository=repository,
        annex_media=media.get("annex", False),
        curation_service=curation_service,
    )
    from .annotations import annotation_root

    annotation_root(workspace)
    return workspace


def load_config_path(path: Path) -> WorkspaceConfig:
    """Load an explicitly named configuration file in its parent workspace."""

    path = path.resolve()
    return load_workspace(path.parent, config_name=path.name)
