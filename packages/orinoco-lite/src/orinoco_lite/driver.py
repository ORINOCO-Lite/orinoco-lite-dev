"""Invoke commands only from a digest-verified runtime manifest."""

from __future__ import annotations

import os
from pathlib import Path
import string
import subprocess
import sys
from typing import Mapping, Sequence

from .config import EngineLock, WorkspaceConfig, development_engine_root
from .errors import DriverError, IntegrityError
from .runtime import RuntimeReport, load_runtime_manifest


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
RUNTIME_SAFETY_ENVIRONMENT = {
    # The runtime is verified before every command and must remain immutable.
    "PYTHONDONTWRITEBYTECODE": "1",
}


def _expand_token(token: str, values: Mapping[str, str]) -> str:
    formatter = string.Formatter()
    for _, field, format_spec, conversion in formatter.parse(token):
        if field is None:
            continue
        if field not in values or format_spec or conversion:
            raise IntegrityError(f"Runtime command uses an unsupported placeholder: {field}")
    try:
        return token.format_map(values)
    except (KeyError, ValueError) as error:
        raise IntegrityError(f"Runtime command token cannot be expanded: {token}") from error


def driver_environment(
    workspace: WorkspaceConfig,
    runtime: RuntimeReport,
    *,
    additions: Mapping[str, str] | None = None,
) -> dict[str, str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if name in PASSTHROUGH_ENVIRONMENT
    }
    environment.update(workspace.environment())
    environment["ORINOCO_RUNTIME_ROOT"] = str(runtime.root)
    engine_paths = [str(runtime.root / "engine")]
    development_root = development_engine_root()
    if development_root is not None:
        development_source = development_root / "packages/orinoco-lite/src"
        engine_paths.insert(0, str(development_source))
        environment["ORINOCO_UNSAFE_DEVELOPMENT_RUNTIME"] = "1"
        environment["ORINOCO_CANDIDATE_ENGINE_ROOT"] = str(development_root)
    environment["PYTHONPATH"] = os.pathsep.join(engine_paths)
    if additions:
        environment.update(additions)
    environment.update(RUNTIME_SAFETY_ENVIRONMENT)
    return environment


def invoke_driver(
    action: str,
    workspace: WorkspaceConfig,
    lock: EngineLock,
    runtime: RuntimeReport,
    *,
    values: Mapping[str, str] | None = None,
    extra_arguments: Sequence[str] = (),
    environment: Mapping[str, str] | None = None,
) -> int:
    """Invoke a reviewed runtime driver without a shell."""

    manifest = load_runtime_manifest(runtime.root / "runtime-manifest.json")
    driver_name = workspace.driver_name(action)
    try:
        template = manifest.commands[driver_name]
    except KeyError as error:
        raise DriverError(
            f"Runtime {runtime.release} does not provide the {driver_name!r} driver"
        ) from error
    substitutions = {
        "base_url": workspace.base_url,
        "build": str(workspace.path("build")),
        "config": str(workspace.config_path),
        "lock": str(workspace.lock_path),
        "python": sys.executable,
        "root": str(workspace.root),
        "runtime": str(runtime.root),
    }
    if values:
        substitutions.update(values)
    command = [_expand_token(token, substitutions) for token in template]
    command.extend(str(argument) for argument in extra_arguments)
    try:
        result = subprocess.run(
            command,
            cwd=workspace.root,
            env=driver_environment(workspace, runtime, additions=environment),
            check=False,
        )
    except FileNotFoundError as error:
        raise DriverError(
            f"Runtime driver {driver_name!r} requires a missing command: {command[0]}"
        ) from error
    if result.returncode < 0:
        raise DriverError(f"Runtime driver {driver_name!r} terminated by signal")
    return result.returncode
