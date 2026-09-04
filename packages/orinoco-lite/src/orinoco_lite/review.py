"""Content-neutral binding for the downstream source-review shell."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from .config import WorkspaceConfig, _review_app_name, development_package_root
from .errors import ConfigurationError, DriverError


CONFIG_FORMAT = "orinoco-curation-review-config"
CONFIG_VERSION = 1


def _review_config(
    workspace: WorkspaceConfig,
    *,
    repository: str,
    service_origin: str,
) -> dict[str, Any]:
    if not repository:
        raise ConfigurationError(
            "Static source review requires a trusted GitHub repository build coordinate"
        )
    return {
        "app_name": _review_app_name(workspace.site_name),
        "format": CONFIG_FORMAT,
        "repository": repository,
        "service_origin": service_origin,
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
    resources_root: Path,
    destination: Path,
    *,
    repository: str | None = None,
    service_origin: str | None = None,
) -> dict[str, Any]:
    """Bind review using the repository supplied by the trusted site build."""

    resolved_repository = repository or workspace.repository
    resolved_service = service_origin or workspace.curation_service
    if resolved_repository is None:
        _remove_destination(destination)
        return {"enabled": False}

    candidate_root = development_package_root()
    shell = (
        candidate_root / "packages/curation-review-app/dist-review"
        if candidate_root is not None
        else resources_root / "review-shell"
    )
    if not shell.is_dir() or not (shell / "index.html").is_file():
        if candidate_root is not None:
            raise DriverError(
                "Local package candidate has no built static source-review shell; "
                "run its curation-review build"
            )
        raise DriverError("Package does not contain the static source-review shell")

    _remove_destination(destination)
    shutil.copytree(shell, destination)
    (destination / "config.json").write_text(
        json.dumps(
            _review_config(
                workspace,
                repository=resolved_repository,
                service_origin=resolved_service,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "enabled": True,
        "repository": resolved_repository,
        "service_origin": resolved_service,
    }
