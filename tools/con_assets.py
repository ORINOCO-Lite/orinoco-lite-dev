#!/usr/bin/env python3
"""Hydrate the manifest-declared assets for the clean migration."""

from __future__ import annotations

import hashlib
from pathlib import Path
import os
import shutil
import subprocess
import sys
from typing import Any, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml


ROOT = Path(__file__).resolve().parents[1]
SITE = Path(
    os.environ.get(
        "CON_SITE_ROOT",
        ROOT / "submodules" / "centerforopenneuroscience.org",
    )
).resolve()
UPSTREAM = Path(
    os.environ.get(
        "UPSTREAM_SITE_ROOT",
        ROOT / "submodules" / "www-from-model",
    )
).resolve()
ASSET_MANIFEST = SITE / "profiles" / "con" / "assets.yaml"
BASELINE_MANIFEST = (
    ROOT
    / "provenance"
    / "upstream-psychoinformatics"
    / "baseline.yaml"
)
CACHE = ROOT / "build" / "con-assets"
PORTRAIT = CACHE / "yaroslav-halchenko.jpg"


class AssetError(RuntimeError):
    """Report a manifest, retrieval, or checksum failure."""


def run(
    arguments: Sequence[str | Path],
    *,
    action: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(argument) for argument in arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise AssetError(f"{action} failed ({result.returncode}): {detail}")
    return result


def git(repository: Path, *arguments: str, action: str) -> str:
    return run(
        ["git", "-C", repository, *arguments], action=action
    ).stdout.strip()


def annex(repository: Path, *arguments: str, action: str) -> str:
    return git(
        repository,
        "-c",
        f"core.worktree={repository.resolve()}",
        "annex",
        *arguments,
        action=action,
    )


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssetError(f"Asset manifest is absent: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssetError(f"Asset manifest must be a mapping: {path}")
    return value


def annex_from_url(
    repository: Path,
    name: str,
    url: str,
    *arguments: str,
    action: str,
) -> str:
    """Use a normal annex remote without persisting Git configuration."""
    return git(
        repository,
        "-c",
        f"core.worktree={repository.resolve()}",
        "-c",
        f"remote.{name}.url={url}",
        "-c",
        f"remote.{name}.fetch=+refs/heads/*:refs/remotes/{name}/*",
        "annex",
        *arguments,
        action=action,
    )


def verify_annex_runtime() -> None:
    """Require the platform-specific annex version recorded by the trial."""
    baseline = load_yaml(BASELINE_MANIFEST)
    toolchain = baseline.get("toolchain", {})
    if not isinstance(toolchain, dict):
        raise AssetError("Invalid upstream toolchain baseline")
    expected = (
        toolchain.get("local_git_annex")
        if sys.platform == "darwin"
        else "10.20260601"
    )
    if not isinstance(expected, str):
        raise AssetError("The expected git-annex version is not recorded")
    output = run(
        ["git-annex", "version"], action="Inspect the git-annex runtime"
    ).stdout
    first_line = output.splitlines()[0] if output else ""
    actual = first_line.removeprefix("git-annex version: ")
    if actual != expected:
        raise AssetError(
            f"Expected git-annex {expected} on {sys.platform}, found "
            f"{actual or first_line!r}"
        )


def hydrate_upstream() -> None:
    """Hydrate upstream asset/static pointers from their own annex remote."""
    baseline = load_yaml(BASELINE_MANIFEST)
    website = baseline.get("website", {})
    annex_info = baseline.get("annex", {})
    if not isinstance(website, dict) or not isinstance(annex_info, dict):
        raise AssetError("Invalid upstream annex baseline manifest")
    commit = website.get("annex_metadata_commit")
    url = website.get("upstream_repository")
    if not isinstance(commit, str) or not isinstance(url, str):
        raise AssetError("Upstream annex provenance is incomplete")

    missing_before = annex(
        UPSTREAM,
        "find",
        "assets",
        "static",
        "--not",
        "--in=here",
        action="Inspect upstream annex availability",
    )
    if missing_before:
        name = "clean-migration-upstream"
        remote_ref = f"refs/remotes/{name}/git-annex"
        git(
            UPSTREAM,
            "fetch",
            "--no-write-fetch-head",
            "--depth",
            "1",
            url,
            f"+{commit}:{remote_ref}",
            action="Fetch pinned upstream annex metadata",
        )
        try:
            annex(UPSTREAM, "init", action="Initialize upstream annex")
            annex_from_url(
                UPSTREAM,
                name,
                url,
                "get",
                "--from",
                name,
                "assets",
                "static",
                action="Hydrate upstream Hugo assets",
            )
        finally:
            git(
                UPSTREAM,
                "update-ref",
                "-d",
                remote_ref,
                action="Remove temporary upstream annex ref",
            )
    missing_after = annex(
        UPSTREAM,
        "find",
        "assets",
        "static",
        "--not",
        "--in=here",
        action="Verify upstream annex availability",
    )
    if missing_after:
        raise AssetError(
            "Required upstream annex paths remain unavailable:\n"
            f"{missing_after}"
        )
    expected_total = annex_info.get("worktree_files")
    if expected_total != 39:
        raise AssetError(
            f"Unexpected upstream annex manifest count: {expected_total}"
        )


def file_digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_file(path: Path, spec: dict[str, Any]) -> None:
    if not path.is_file():
        raise AssetError(f"Required asset is absent: {path}")
    size = spec.get("size")
    if size is not None and path.stat().st_size != int(size):
        raise AssetError(
            f"{path}: expected {size} bytes, found {path.stat().st_size}"
        )
    for algorithm in ("md5", "sha256"):
        expected = spec.get(algorithm)
        if expected and file_digest(path, algorithm) != expected:
            raise AssetError(f"{path}: {algorithm} digest does not match")


def hydrate_portrait() -> Path:
    """Retrieve the legacy portrait key without mixing website annex state."""
    manifest = load_yaml(ASSET_MANIFEST)
    remote = manifest.get("annex_remote", {})
    assets = manifest.get("assets", {})
    if not isinstance(remote, dict) or not isinstance(assets, dict):
        raise AssetError("CON asset manifest is incomplete")
    destination = remote.get("destination")
    key = remote.get("required_key")
    name = remote.get("name")
    url = remote.get("repository")
    object_url = remote.get("object_url")
    if not all(
        isinstance(value, str)
        for value in (destination, key, name, url, object_url)
    ):
        raise AssetError("Legacy annex remote declaration is incomplete")
    spec = assets.get(destination)
    if not isinstance(spec, dict) or spec.get("annex_key") != key:
        raise AssetError("Portrait asset and annex remote key disagree")

    CACHE.mkdir(parents=True, exist_ok=True)
    if PORTRAIT.is_file():
        verify_file(PORTRAIT, spec)
        return PORTRAIT

    if not object_url.startswith(url):
        raise AssetError("Portrait object URL is outside its read-only remote")
    temporary = CACHE / ".yaroslav-halchenko.download"
    request = Request(object_url, headers={"User-Agent": "clean-migration/1"})
    try:
        with urlopen(request, timeout=120) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
    except (OSError, URLError) as error:
        if temporary.exists():
            temporary.unlink()
        raise AssetError(
            f"Could not hydrate portrait key {key} from {name}: {error}"
        ) from error
    try:
        verify_file(temporary, spec)
        os.replace(temporary, PORTRAIT)
    finally:
        if temporary.exists():
            temporary.unlink()
    return PORTRAIT


def verify_git_assets() -> None:
    manifest = load_yaml(ASSET_MANIFEST)
    assets = manifest.get("assets", {})
    if not isinstance(assets, dict):
        raise AssetError("CON asset entries must be a mapping")
    for relative, spec in sorted(assets.items()):
        if not isinstance(relative, str) or not isinstance(spec, dict):
            raise AssetError("Invalid CON asset entry")
        if spec.get("storage") == "git-annex":
            continue
        verify_file(SITE / relative, spec)


def hydrate_all() -> Path:
    verify_annex_runtime()
    verify_git_assets()
    hydrate_upstream()
    return hydrate_portrait()


def main() -> int:
    try:
        portrait = hydrate_all()
        print(f"Hydrated manifest assets; portrait cache: {portrait}")
    except AssetError as error:
        print(f"clean-migration assets: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
