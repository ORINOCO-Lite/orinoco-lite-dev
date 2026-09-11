"""Locate the resources installed as part of the Orinoco Lite package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .errors import IntegrityError

SOURCE_REPOSITORY = "https://github.com/ORINOCO-Lite/orinoco-lite-dev"
SOURCE_COMMIT_NAME = "source-commit.txt"
SOURCE_DESCRIPTION_NAME = "source-description.txt"


@dataclass(frozen=True)
class PackageResources:
    root: Path


def load_resources(root: Path) -> PackageResources:
    """Locate bundled data; the installed wheel owns its integrity boundary."""

    root = root.resolve()
    if not root.is_dir():
        raise IntegrityError(
            "orinoco-lite package resources are absent; install a released wheel "
            "or build the package resources before installing from source"
        )
    return PackageResources(root=root)


def resolve_resources() -> PackageResources:
    """Use the resources belonging to the installed package."""

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


def source_description(root: Path) -> str:
    """Read the release-time ``git describe --always`` source identity."""

    try:
        description = (root / SOURCE_DESCRIPTION_NAME).read_text(
            encoding="utf-8"
        ).strip()
    except (OSError, UnicodeError) as error:
        raise IntegrityError("Package source description is missing") from error
    if (
        not description
        or "\n" in description
        or len(description) > 200
        or any(character.isspace() or ord(character) < 0x20 for character in description)
    ):
        raise IntegrityError("Package source description must be one bounded Git value")
    return description
