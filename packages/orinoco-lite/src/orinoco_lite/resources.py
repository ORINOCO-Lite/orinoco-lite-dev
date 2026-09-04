"""Locate the resources installed as part of the Orinoco Lite package."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

from . import __version__
from .config import PackageLock, WorkspaceConfig, development_package_root
from .errors import ConfigurationError, IntegrityError

SOURCE_REPOSITORY = "https://github.com/ORINOCO-Lite/orinoco-lite-dev"
SOURCE_COMMIT_NAME = "source-commit.txt"


@dataclass(frozen=True)
class PackageResources:
    root: Path


def load_resources(root: Path) -> PackageResources:
    """Locate bundled data; the installed wheel owns its integrity boundary."""

    root = root.resolve()
    if not root.is_dir():
        raise IntegrityError(
            "orinoco-lite package resources are absent; install a released wheel "
            "or stage candidate resources"
        )
    return PackageResources(root=root)


def require_package_version(lock: PackageLock) -> None:
    if lock.package_version != __version__ and development_package_root() is None:
        raise ConfigurationError(
            f"orinoco.lock requires orinoco-lite {lock.package_version}, "
            f"but {__version__} is installed"
        )


def resolve_resources(
    _workspace: WorkspaceConfig, lock: PackageLock
) -> PackageResources:
    require_package_version(lock)
    candidate = os.environ.get("ORINOCO_CANDIDATE_RESOURCE_ROOT")
    if candidate and development_package_root() is not None:
        return load_resources(Path(candidate))
    return load_resources(Path(__file__).parent / "_resources")


def source_commit(root: Path) -> str:
    """Read the source commit whose Gitlink selects the presentation."""

    try:
        commit = (root / SOURCE_COMMIT_NAME).read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as error:
        raise IntegrityError("Package source commit is missing") from error
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise IntegrityError("Package source commit must be an exact lowercase Git SHA")
    return commit
