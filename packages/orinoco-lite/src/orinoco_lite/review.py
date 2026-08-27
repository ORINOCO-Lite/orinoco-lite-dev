"""Content-neutral binding for the downstream source-review shell."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from .config import WorkspaceConfig, _review_app_name
from .errors import ConfigurationError, DriverError


CONFIG_FORMAT = "orinoco-curation-review-config"
CONFIG_VERSION = 1


def _review_config(workspace: WorkspaceConfig) -> dict[str, Any]:
    if workspace.repository is None or workspace.curation_service is None:
        raise ConfigurationError(
            "Static source review requires site.repository and "
            "site.curation_service"
        )
    return {
        "app_name": _review_app_name(workspace.site_name),
        "format": CONFIG_FORMAT,
        "repository": workspace.repository,
        "service_origin": workspace.curation_service,
        "version": CONFIG_VERSION,
    }


def _remove_destination(destination: Path) -> None:
    if destination.is_symlink() or (
        destination.exists() and not destination.is_dir()
    ):
        raise DriverError(
            f"Static source-review destination is not a directory: {destination}"
        )
    if destination.is_dir():
        shutil.rmtree(destination)


def bind_review(
    workspace: WorkspaceConfig,
    runtime_root: Path,
    destination: Path,
) -> dict[str, Any]:
    """Bind the review shell when GitHub curation is explicitly configured."""

    configured = (
        workspace.repository is not None and workspace.curation_service is not None
    )
    if (workspace.repository is None) != (workspace.curation_service is None):
        raise ConfigurationError(
            "site.repository and site.curation_service must be configured together"
        )
    if not configured:
        _remove_destination(destination)
        return {"enabled": False}

    shell = runtime_root / "review-shell"
    if not shell.is_dir() or not (shell / "index.html").is_file():
        raise DriverError("Runtime does not contain the static source-review shell")

    _remove_destination(destination)
    shutil.copytree(shell, destination)
    (destination / "config.json").write_text(
        json.dumps(
            _review_config(workspace),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "enabled": True,
        "repository": workspace.repository,
        "service_origin": workspace.curation_service,
    }
