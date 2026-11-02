"""Move depiction files between downstream inputs and Hugo page bundles."""

import os
from pathlib import Path

from .errors import ConfigurationError
from .progress import progress


KINDS = {"portrait", "logo", "depiction"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}


def _files(content: Path):
    if content.is_symlink():
        raise ConfigurationError(f"Content directory must not be a symlink: {content}")
    for path in sorted(content.rglob("*")):
        relative = path.relative_to(content)
        if ".git" in relative.parts or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path.is_file() or path.is_symlink():
            yield path, relative


def _flat_moves(content: Path):
    return [(path, path.parent.parent / f"{path.parent.name}_{path.name}")
            for path, relative in _files(content)
            if len(relative.parts) == 3 and path.stem in KINDS]


def _move_files(moves):
    # Check every destination before moving anything, including dangling links.
    for source, target in moves:
        if target.exists() or target.is_symlink():
            raise ConfigurationError(f"Cannot move {source}: destination already exists: {target}")
        if any(parent.is_symlink() for parent in (*source.parents, *target.parents)):
            raise ConfigurationError(f"Cannot move a depiction through a symlink: {source}")
    try:
        for source, target in moves:
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                # Locked Annex files can be moved without fetching their payload.
                link = source.readlink()
                if not link.is_absolute():
                    link = Path(os.path.relpath(source.parent / link, target.parent))
                target.symlink_to(link)
                source.unlink()
            else:
                source.rename(target)
        for parent in {source.parent for source, _ in moves}:
            if not any(parent.iterdir()):
                parent.rmdir()
    except OSError as error:
        raise ConfigurationError(f"Could not move depiction files: {error}") from error
    return len(moves)


@progress("Moving depiction files")
def flatten_depictions(content: Path) -> int:
    """Move section/entity/portrait.ext to section/entity_portrait.ext.

    Also handles logo and depiction images. Leaves other files and nonempty
    directories in place. Does not fetch content, stage changes, or commit.
    """
    if content.is_symlink() or not content.is_dir():
        raise ConfigurationError(f"Content must be an existing regular directory: {content}")
    return _move_files(_flat_moves(content.resolve()))


def validate_depictions(content: Path) -> None:
    moves = _flat_moves(content)
    if moves:
        source, target = moves[0]
        raise ConfigurationError(
            f"Depiction files must use flat paths: {source} belongs at {target}. "
            "Run `orinoco-lite flatten-depictions` from the website repository."
        )


def bundle_depictions(content: Path) -> None:
    """Place flat images into page bundles in the disposable Hugo assembly."""
    moves = []
    for path, relative in _files(content):
        entity, separator, kind = path.stem.rpartition("_")
        if len(relative.parts) == 2 and separator and entity not in {"", ".", ".."} and kind in KINDS:
            moves.append((path, path.parent / entity / f"{kind}{path.suffix}"))
    _move_files(moves)
