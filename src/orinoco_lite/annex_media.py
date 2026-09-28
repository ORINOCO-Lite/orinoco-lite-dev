"""Native Annex retrieval shared by site builds and upstream preparation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
import subprocess

from .errors import ConfigurationError, DriverError


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *arguments], cwd=repository,
                              capture_output=True, text=True)
    except FileNotFoundError as error:
        raise DriverError("Git is required to prepare Annex media") from error


def annex(repository: Path, *arguments: str, remote: str | None = None) -> str:
    config = ["-c", f"remote.orinoco-media.url={remote}"] if remote else []
    result = _git(repository, *config, "annex", *arguments)
    if result.returncode:
        raise DriverError(
            f"Annex media operation failed in {repository}: "
            f"{result.stdout.strip()} {result.stderr.strip()}"
        )
    return result.stdout.strip()


def annex_files(repository: Path, *, initialize: bool = False) -> dict[Path, str]:
    """Discover managed files, including unavailable and unlocked content."""
    result = _git(repository, "rev-parse", "--git-path", "annex")
    if result.returncode:
        return {}
    directory = Path(result.stdout.strip())
    if not directory.is_absolute():
        directory = repository / directory
    refs = _git(repository, "for-each-ref", "--format=%(refname)",
                "refs/heads/git-annex", "refs/remotes").stdout.splitlines()
    if not initialize and not directory.is_dir() and not any(ref.endswith("/git-annex") for ref in refs):
        return {}
    if not directory.is_dir():
        if initialize and not any(ref.endswith("/git-annex") for ref in refs):
            # Shallow CI submodule checkouts may omit the content-location branch.
            # Fetch only that branch; never advance the selected source commit.
            origin = _git(repository, "remote", "get-url", "origin")
            if origin.returncode == 0:
                result = _git(repository, "fetch", "origin",
                              "refs/heads/git-annex:refs/remotes/origin/git-annex")
                if result.returncode:
                    raise DriverError(f"Cannot fetch Annex storage configuration: {result.stderr.strip()}")
        annex(repository, "init")
    files = {}
    for line in annex(repository, "find", "--anything", "--json").splitlines():
        entry = json.loads(line)
        path = Path(entry["file"])
        if path.is_absolute() or ".." in path.parts:
            raise DriverError(f"Unsafe Annex media path: {path}")
        files[path] = entry["key"]
    return files


def retrieve_and_verify(
    repository: Path, files: dict[Path, str], *, remote: str | None = None,
    run_annex: Callable[..., str] | None = None,
) -> dict[Path, Path]:
    """Return verified object paths without replacing tracked representations."""
    if not files:
        return {}
    run = run_annex or (lambda *args: annex(repository, *args, remote=remote))
    names = [str(path) for path in files]
    source = ["--from", "orinoco-media"] if remote else []
    run("get", *source, "--", *names)
    # --from can skip unavailable files successfully. Resolve every required
    # key explicitly before allowing assembly to publish any pointer bytes.
    locations = {}
    for path, key in files.items():
        try:
            value = run("contentlocation", key)
        except DriverError as error:
            raise DriverError(f"Annex media is unavailable: {repository / path}") from error
        location = repository / value
        if not value or not location.is_file():
            raise DriverError(f"Annex media is unavailable: {repository / path}")
        locations[path] = location
    run("fsck", "--numcopies=1", "--", *names)
    return locations


def workspace_annex_files(workspace) -> dict[Path, str]:
    """Enforce the opted-in submodule and ordinary-Git input boundary."""
    if not workspace.annex_media:
        return {}
    site = workspace.path("site")
    entry = _git(workspace.root, "ls-files", "--stage", "--", "site-specific")
    if not entry.stdout.startswith("160000 ") or site.is_symlink():
        raise ConfigurationError("media.annex requires a site-specific Git submodule")
    files = annex_files(site, initialize=True)
    forbidden = [str(path) for path in files
                 if len(path.parts) < 2 or path.parts[0] not in {"assets", "static"}]
    if forbidden:
        raise ConfigurationError(
            "Records, configuration, and editorial content must remain in ordinary Git; "
            "Annex media is limited to assets/ and static/: " + ", ".join(forbidden)
        )
    return files


def prepare_media(workspace) -> dict[Path, Path]:
    site = workspace.path("site")
    return {site / path: location for path, location in
            retrieve_and_verify(site, workspace_annex_files(workspace)).items()}
