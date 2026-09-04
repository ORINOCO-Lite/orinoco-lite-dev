"""Invoke the drivers supplied by the installed Python package."""

from __future__ import annotations

import os
from pathlib import Path
import string
import subprocess
import sys
from typing import Mapping, Sequence

from .config import PackageLock, WorkspaceConfig, development_package_root
from .errors import DriverError, IntegrityError
from .resources import PackageResources


PASSTHROUGH_ENVIRONMENT = {
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_FILE",
    "TMPDIR",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
}
COMMANDS = {
    "validate": ("orinoco_lite.validate_resources",),
    "projection-update": ("orinoco_lite.projection_cli", "update"),
    "projection-verify": ("orinoco_lite.projection_cli", "verify"),
    "build": ("orinoco_lite.site", "--destination", "{destination}", "--base-url", "{base_url}"),
    "editor-apply": ("orinoco_lite.editor", "--bundle", "{bundle}"),
}


def _expand_token(token: str, values: Mapping[str, str]) -> str:
    formatter = string.Formatter()
    for _, field, format_spec, conversion in formatter.parse(token):
        if field is None:
            continue
        if field not in values or format_spec or conversion:
            raise IntegrityError(f"Package command uses an unsupported placeholder: {field}")
    try:
        return token.format_map(values)
    except (KeyError, ValueError) as error:
        raise IntegrityError(f"Package command token cannot be expanded: {token}") from error


def driver_environment(
    workspace: WorkspaceConfig,
    resources: PackageResources,
    *,
    additions: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if name in PASSTHROUGH_ENVIRONMENT
    }
    environment.update(workspace.environment())
    development_root = development_package_root()
    if development_root is not None:
        development_source = development_root / "packages/orinoco-lite/src"
        environment["PYTHONPATH"] = str(development_source)
        environment["ORINOCO_UNSAFE_DEVELOPMENT_PACKAGE"] = "1"
        environment["ORINOCO_CANDIDATE_PACKAGE_ROOT"] = str(development_root)
        editor_shell = os.environ.get("ORINOCO_CANDIDATE_EDITOR_SHELL")
        if editor_shell is not None:
            environment["ORINOCO_CANDIDATE_EDITOR_SHELL"] = editor_shell
    if additions:
        environment.update(additions)
    return environment


def invoke_driver(
    action: str,
    workspace: WorkspaceConfig,
    lock: PackageLock,
    resources: PackageResources,
    *,
    values: Mapping[str, str] | None = None,
    extra_arguments: Sequence[str] = (),
    environment: Mapping[str, str] | None = None,
) -> int:
    """Invoke a package driver without a shell."""

    try:
        module, *arguments = COMMANDS[action]
        template = ["{python}", "-m", module, "--config", "{config}", "--resources", "{resources}", *arguments]
    except KeyError as error:
        raise DriverError(
            f"Orinoco Lite does not provide the {action!r} driver"
        ) from error
    substitutions = {
        "base_url": workspace.base_url,
        "build": str(workspace.path("build")),
        "config": str(workspace.config_path),
        "lock": str(workspace.lock_path),
        "python": sys.executable,
        "root": str(workspace.root),
        "resources": str(resources.root),
    }
    if values:
        substitutions.update(values)
    command = [_expand_token(token, substitutions) for token in template]
    command.extend(str(argument) for argument in extra_arguments)
    try:
        result = subprocess.run(
            command,
            cwd=workspace.root,
            env=driver_environment(workspace, resources, additions=environment),
            check=False,
        )
    except FileNotFoundError as error:
        raise DriverError(
            f"Package driver {action!r} requires a missing command: {command[0]}"
        ) from error
    if result.returncode < 0:
        raise DriverError(f"Package driver {action!r} terminated by signal")
    return result.returncode
