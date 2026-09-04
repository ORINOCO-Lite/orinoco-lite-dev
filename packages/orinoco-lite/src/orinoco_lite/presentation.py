"""Resolve the exact upstream presentation selected by engineering Git."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Sequence

from .config import development_package_root
from .errors import IntegrityError
from .resources import SOURCE_REPOSITORY, source_commit


_GIT_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_PRESENTATION_GITLINK = "submodules/www-from-model"


def _git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        {
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    return environment


def _git(
    repository: Path,
    arguments: Sequence[str],
    *,
    operation: str,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    command = [
        "git",
        "-c",
        "core.quotepath=false",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "core.fsmonitor=false",
        "-C",
        os.fspath(repository),
        *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=_git_environment(),
        )
    except OSError as error:
        raise IntegrityError(f"Git could not {operation}: {error}") from error
    if check and completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        if not detail:
            detail = f"Git exited with status {completed.returncode}"
        raise IntegrityError(f"Git could not {operation}: {detail}")
    return completed


def _git_text(repository: Path, arguments: Sequence[str], *, operation: str) -> str:
    try:
        return _git(repository, arguments, operation=operation).stdout.decode(
            "utf-8", "strict"
        ).strip()
    except UnicodeDecodeError as error:
        raise IntegrityError(
            f"Git returned non-UTF-8 data while it tried to {operation}"
        ) from error


def _repository_head(repository: Path, *, label: str) -> str:
    if repository.is_symlink() or not repository.is_dir():
        raise IntegrityError(f"{label} is not an ordinary Git worktree: {repository}")
    top = _git_text(
        repository,
        ("rev-parse", "--show-toplevel"),
        operation=f"inspect {label.lower()}",
    )
    if Path(top).resolve() != repository.resolve():
        raise IntegrityError(f"{label} is not a standalone Git worktree: {repository}")
    commit = _git_text(
        repository,
        ("rev-parse", "--verify", "HEAD^{commit}"),
        operation=f"read {label.lower()} HEAD",
    )
    if _GIT_COMMIT.fullmatch(commit) is None:
        raise IntegrityError(f"{label} HEAD is not a full lowercase Git commit")
    return commit


def _selected_presentation_commit(engineering: Path, commit: str) -> str:
    output = _git_text(
        engineering,
        ("ls-tree", "--full-tree", commit, "--", _PRESENTATION_GITLINK),
        operation="read the selected presentation Gitlink",
    )
    match = re.fullmatch(
        rf"160000 commit (?P<commit>[0-9a-f]{{40}})\t{re.escape(_PRESENTATION_GITLINK)}",
        output,
    )
    if match is None:
        raise IntegrityError(
            f"Engineering commit must select {_PRESENTATION_GITLINK} as one Gitlink"
        )
    return match.group("commit")


def _verify_checkout(engineering: Path, expected_commit: str) -> Path:
    actual_commit = _repository_head(engineering, label="Cached engineering checkout")
    if actual_commit != expected_commit:
        raise IntegrityError(
            f"Cached engineering checkout is {actual_commit}, expected {expected_commit}"
        )
    selected_commit = _selected_presentation_commit(engineering, expected_commit)
    presentation = engineering / _PRESENTATION_GITLINK
    if presentation.is_symlink() or not presentation.is_dir():
        raise IntegrityError("Selected presentation submodule is not initialized")
    if (
        _repository_head(presentation, label="Selected presentation checkout")
        != selected_commit
    ):
        raise IntegrityError("Selected presentation checkout does not match its Gitlink")

    status = _git(
        engineering,
        ("submodule", "status", "--recursive", "--", _PRESENTATION_GITLINK),
        operation="verify the presentation dependency closure",
    ).stdout
    try:
        lines = status.decode("utf-8", "strict").splitlines()
    except UnicodeDecodeError as error:
        raise IntegrityError("Git returned non-UTF-8 submodule status") from error
    if not lines or any(not line.startswith(" ") for line in lines):
        raise IntegrityError(
            "Presentation dependencies are missing or do not match their Gitlinks"
        )
    dirty = _git(
        engineering,
        (
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--ignore-submodules=none",
        ),
        operation="verify presentation checkout cleanliness",
    ).stdout
    if dirty:
        raise IntegrityError("Cached presentation dependency closure is not clean")
    return presentation.resolve()


def _clone_checkout(repository: str, commit: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    _git(
        destination.parent,
        (
            "clone",
            "--quiet",
            "--no-local",
            "--no-checkout",
            "--origin",
            "origin",
            "--",
            repository,
            os.fspath(destination),
        ),
        operation=f"clone {repository}",
    )
    _git(
        destination,
        ("checkout", "--quiet", "--detach", "--force", commit),
        operation=f"check out engineering commit {commit}",
    )
    _git(
        destination,
        (
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "update",
            "--quiet",
            "--init",
            "--recursive",
            "--checkout",
            "--",
            _PRESENTATION_GITLINK,
        ),
        operation="resolve the presentation dependency closure",
    )
    return _verify_checkout(destination, commit)


def _cache_name(repository: str, commit: str) -> str:
    repository_id = hashlib.sha256(repository.encode("utf-8")).hexdigest()[:16]
    return f"engineering-{repository_id}-{commit}"


def _remove_cache_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _ensure_checkout(
    cache: Path,
    *,
    repository: str,
    commit: str,
) -> Path:
    destination = cache / _cache_name(repository, commit)
    mismatch: IntegrityError | None = None
    if destination.exists() or destination.is_symlink():
        try:
            return _verify_checkout(destination, commit)
        except IntegrityError as error:
            mismatch = error

    cache.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".engineering-", dir=cache))
    fresh = temporary / "checkout"
    try:
        presentation = _clone_checkout(repository, commit, fresh)
        relative_presentation = presentation.relative_to(fresh)
        if destination.exists() or destination.is_symlink():
            _remove_cache_path(destination)
        os.replace(fresh, destination)
    except Exception as error:
        if mismatch is not None:
            raise IntegrityError(
                f"Cached presentation failed verification ({mismatch}); "
                f"repair failed: {error}"
            ) from error
        if isinstance(error, IntegrityError):
            raise
        raise IntegrityError(f"Could not resolve presentation: {error}") from error
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    _verify_checkout(destination, commit)
    return (destination / relative_presentation).resolve()


def _package_source(resources_root: Path) -> tuple[str, str]:
    return SOURCE_REPOSITORY, source_commit(resources_root)


def resolve_presentation(workspace: Path, resources_root: Path | None = None) -> Path:
    """Return the presentation checkout selected by the package source commit."""

    workspace = workspace.resolve()
    if workspace.is_symlink() or not workspace.is_dir():
        raise IntegrityError(f"Presentation workspace is not a directory: {workspace}")
    candidate = development_package_root()
    if candidate is not None:
        candidate = candidate.resolve()
        engineering_repository = os.fspath(candidate)
        engineering_commit = _repository_head(
            candidate, label="Candidate engineering source"
        )
    else:
        if resources_root is None:
            raise IntegrityError(
                "Presentation resolution requires package resources outside "
                "candidate mode"
            )
        engineering_repository, engineering_commit = _package_source(
            resources_root
        )
    return _ensure_checkout(
        workspace / ".orinoco" / "presentation",
        repository=engineering_repository,
        commit=engineering_commit,
    )
