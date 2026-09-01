#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
# platforms = [
#   { platform = "osx-arm64", macos = "14.0" },
#   "linux-64",
# ]
#
# [tool.pixi.dependencies]
# python = ">=3.12,<3.13"
# git = ">=2.55.0,<3"
#
# [tool.pixi.target.linux-64.dependencies]
# git-annex = "==10.20260601"
#
# [tool.pixi.target.osx-arm64-macos-14-0.pypi-dependencies]
# git-annex = "==10.20260601"
# ///
"""Materialize selected Annex presentation payloads into the thin template."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
WEBSITE_GITLINK = PurePosixPath("submodules/www-from-model")
PRESENTATION_SURFACES = frozenset(
    {
        "archetypes",
        "assets",
        "config",
        "data",
        "i18n",
        "layouts",
        "page_templates",
        "static",
    }
)
GENERATED_OUTPUTS = frozenset({PurePosixPath("static/graph.json")})


class MaterializationError(RuntimeError):
    """Report an unsafe or incomplete presentation materialization."""


Runner = Callable[[Sequence[str]], str]


@dataclass(frozen=True)
class MaterializationResult:
    """Summary of a completed overlay replacement."""

    selected_commit: str
    asset_count: int
    destination: Path


def run_command(command: Sequence[str]) -> str:
    """Run a maintainer command and return stripped standard output."""
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        rendered = " ".join(str(item) for item in command)
        if detail:
            raise MaterializationError(f"{rendered} failed: {detail}")
        raise MaterializationError(
            f"{rendered} exited with status {result.returncode}"
        )
    return result.stdout.strip()


def git(repository: Path, *arguments: str, runner: Runner) -> str:
    """Run Git in ``repository``."""
    return runner(["git", "-C", str(repository), *arguments])


def linked_git(repository: Path, *arguments: str, runner: Runner) -> str:
    """Run Git against a checkout whose Git directory may be linked."""
    git_dir = git(
        repository,
        "rev-parse",
        "--absolute-git-dir",
        runner=runner,
    )
    work_tree = git(
        repository,
        "rev-parse",
        "--show-toplevel",
        runner=runner,
    )
    return runner(
        [
            "env",
            f"GIT_DIR={git_dir}",
            f"GIT_WORK_TREE={work_tree}",
            "git",
            *arguments,
        ]
    )


def git_annex(repository: Path, *arguments: str, runner: Runner) -> str:
    """Run Git Annex in a linked checkout."""
    return linked_git(repository, "annex", *arguments, runner=runner)


def selected_website_commit(
    engineering_root: Path,
    *,
    runner: Runner = run_command,
) -> str:
    """Read the website revision from the engineering repository gitlink."""
    output = git(
        engineering_root,
        "ls-tree",
        "HEAD",
        "--",
        WEBSITE_GITLINK.as_posix(),
        runner=runner,
    )
    fields = output.split()
    if len(fields) < 4 or fields[0:2] != ["160000", "commit"]:
        raise MaterializationError(
            f"{WEBSITE_GITLINK} is not a gitlink in {engineering_root}"
        )
    commit = fields[2]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise MaterializationError(
            f"Recorded website gitlink has an invalid commit: {commit!r}"
        )
    return commit


def _initialized_checkout(path: Path, *, runner: Runner) -> bool:
    try:
        root = git(path, "rev-parse", "--show-toplevel", runner=runner)
    except MaterializationError:
        return False
    return Path(root).resolve() == path.resolve()


def prepare_website_checkout(
    checkout: Path,
    expected_commit: str,
    *,
    runner: Runner = run_command,
) -> Path:
    """Verify a clean checkout of the gitlink-selected website."""
    selected = checkout.resolve()
    if not _initialized_checkout(selected, runner=runner):
        raise MaterializationError(
            f"Website checkout is not an initialized Git worktree: {selected}"
        )
    actual_commit = git(selected, "rev-parse", "HEAD", runner=runner)
    if actual_commit != expected_commit:
        raise MaterializationError(
            f"Website checkout should be {expected_commit}, found {actual_commit}"
        )
    status = linked_git(
        selected,
        "status",
        "--porcelain",
        "--untracked-files=all",
        runner=runner,
    )
    if status:
        raise MaterializationError(
            f"Website checkout has uncommitted changes: {selected}"
        )
    return selected


def _safe_repository_path(raw: str) -> PurePosixPath:
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise MaterializationError(f"Unsafe Annex path: {raw!r}")
    return path


def is_presentation_asset(path: PurePosixPath) -> bool:
    """Select Annex payloads on generic presentation surfaces."""
    return (
        len(path.parts) > 1
        and path.parts[0] in PRESENTATION_SURFACES
        and path not in GENERATED_OUTPUTS
    )


def discover_presentation_assets(
    website: Path,
    *,
    runner: Runner = run_command,
) -> tuple[PurePosixPath, ...]:
    """Discover every Annex-managed payload on a presentation surface."""
    output = git_annex(
        website,
        "find",
        "--json",
        "--json-error-messages",
        "--anything",
        runner=runner,
    )
    assets: set[PurePosixPath] = set()
    for line in output.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise MaterializationError(
                f"Git Annex returned invalid discovery JSON: {line!r}"
            ) from error
        if record.get("error-messages"):
            detail = "; ".join(str(item) for item in record["error-messages"])
            raise MaterializationError(f"Git Annex discovery failed: {detail}")
        raw_path = record.get("file")
        if not isinstance(raw_path, str):
            raise MaterializationError("Git Annex discovery omitted a file path")
        path = _safe_repository_path(raw_path)
        if not is_presentation_asset(path):
            continue
        assets.add(path)
    return tuple(sorted(assets))


def hydrate_and_verify(
    website: Path,
    assets: Sequence[PurePosixPath],
    *,
    runner: Runner = run_command,
) -> None:
    """Hydrate and checksum every required payload with Git Annex."""
    if not assets:
        return
    paths = [asset.as_posix() for asset in assets]
    git_annex(
        website,
        "get",
        "--",
        *paths,
        runner=runner,
    )
    git_annex(
        website,
        "fsck",
        "--",
        *paths,
        runner=runner,
    )


def _verify_copied_payload(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise MaterializationError(f"Materialized payload is not a file: {path}")
    if path.stat().st_size < 4096:
        content = path.read_bytes()
        if content.startswith((b"/annex/objects/", b".git/annex/objects/")):
            raise MaterializationError(
                f"Materialized payload is an Annex pointer, not content: {path}"
            )


def _copy_to_staging(
    website: Path,
    staging: Path,
    assets: Sequence[PurePosixPath],
) -> None:
    for asset in assets:
        source = website.joinpath(*asset.parts)
        if not source.exists() or not source.is_file():
            raise MaterializationError(
                f"Hydrated Annex payload is unavailable: {asset}"
            )
        destination = staging.joinpath(*asset.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as source_stream, destination.open("xb") as output:
            shutil.copyfileobj(source_stream, output)
        _verify_copied_payload(destination)


def _replace_upstream_overlay(
    overlay: Path,
    staging: Path,
) -> Path:
    destination = overlay / "upstream"
    if destination.is_symlink():
        raise MaterializationError(
            f"Refusing to replace symlinked materialized overlay: {destination}"
        )
    backup: Path | None = None
    try:
        if destination.exists():
            backup = Path(
                tempfile.mkdtemp(prefix=".upstream-backup-", dir=overlay)
            )
            backup.rmdir()
            destination.rename(backup)
        staging.rename(destination)
    except Exception:
        if backup is not None and backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    if backup is not None:
        shutil.rmtree(backup)
    return destination


def materialize(
    engineering_root: Path,
    template_root: Path,
    *,
    runner: Runner = run_command,
) -> MaterializationResult:
    """Build and safely install the selected ordinary-file asset overlay."""
    engineering_root = engineering_root.resolve()
    template_root = template_root.resolve()
    selected_commit = selected_website_commit(engineering_root, runner=runner)
    website = prepare_website_checkout(
        engineering_root.joinpath(*WEBSITE_GITLINK.parts),
        selected_commit,
        runner=runner,
    )
    assets = discover_presentation_assets(website, runner=runner)
    hydrate_and_verify(website, assets, runner=runner)
    if linked_git(
        website,
        "status",
        "--porcelain",
        "--untracked-files=all",
        runner=runner,
    ):
        raise MaterializationError(
            "Git Annex hydration left changes in the selected website worktree"
        )

    template_source = template_root / "copier-template"
    if template_source.is_symlink() or not template_source.is_dir():
        raise MaterializationError(
            f"Template Copier source is unavailable: {template_source}"
        )
    hidden = template_source / ".orinoco-lite"
    overlay = hidden / "materialized-presentation"
    for path in (hidden, overlay):
        if path.is_symlink():
            raise MaterializationError(
                f"Refusing to write through a symlinked template path: {path}"
            )
    overlay.mkdir(parents=True, exist_ok=True)
    license_path = overlay / "LICENSE"
    if license_path.is_symlink() or not license_path.is_file():
        raise MaterializationError(
            f"Materialized presentation overlay has no LICENSE: {license_path}"
        )

    staging = Path(tempfile.mkdtemp(prefix=".upstream-stage-", dir=overlay))
    try:
        _copy_to_staging(website, staging, assets)
        destination = _replace_upstream_overlay(overlay, staging)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return MaterializationResult(
        selected_commit=selected_commit,
        asset_count=len(assets),
        destination=destination,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "template",
        type=Path,
        help="orinoco-lite-template working tree to update",
    )
    parser.add_argument(
        "--engineering-root",
        type=Path,
        default=ROOT,
        help="engineering repository carrying the selected website gitlink",
    )
    args = parser.parse_args(argv)
    try:
        result = materialize(
            args.engineering_root,
            args.template,
        )
    except MaterializationError as error:
        parser.exit(1, f"materialize-presentation-assets: {error}\n")
    print(
        f"Materialized {result.asset_count} presentation assets from "
        f"{result.selected_commit} into {result.destination}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
