#!/usr/bin/env python3
"""Prepare exact or current-worktree inputs for upstream integration tasks."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Literal


CheckoutMode = Literal["recorded", "worktree"]


class UpstreamCheckoutError(RuntimeError):
    """Report an unsafe or incomplete scoped checkout."""


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise UpstreamCheckoutError(
            f"git {' '.join(arguments)} failed in {repository}: {detail}"
        )
    return result.stdout.strip()


def initialized(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    return (
        result.returncode == 0
        and Path(result.stdout.strip()).resolve() == path.resolve()
    )


def recorded_commit(parent: Path, relative: Path) -> str:
    entry = git(parent, "ls-tree", "HEAD", "--", str(relative))
    fields = entry.split()
    if len(fields) < 3 or fields[0] != "160000" or fields[1] != "commit":
        raise UpstreamCheckoutError(
            f"{relative} is not a gitlink recorded by {parent}"
        )
    return fields[2]


def prepare_gitlink(
    parent: Path,
    relative: Path,
    *,
    display: Path,
    mode: CheckoutMode,
) -> Path:
    checkout = parent / relative
    expected = recorded_commit(parent, relative)
    exists = initialized(checkout)

    if exists and mode == "recorded":
        status = git(checkout, "status", "--porcelain", "--untracked-files=all")
        if status:
            raise UpstreamCheckoutError(
                f"Recorded mode will not replace modified checkout {display}; "
                "use worktree mode to test it"
            )

    if not exists or mode == "recorded":
        git(parent, "submodule", "sync", "--", str(relative))
        git(
            parent,
            "submodule",
            "update",
            "--init",
            "--checkout",
            "--depth",
            "1",
            "--",
            str(relative),
        )

    if not initialized(checkout):
        raise UpstreamCheckoutError(f"Required checkout is unavailable: {display}")

    actual = git(checkout, "rev-parse", "HEAD")
    if mode == "recorded" and actual != expected:
        raise UpstreamCheckoutError(
            f"{display} should be {expected}, but is {actual}"
        )
    dirty = bool(
        git(checkout, "status", "--porcelain", "--untracked-files=all")
    )
    state = "modified" if dirty else "clean"
    source = "recorded" if mode == "recorded" else "current worktree"
    print(f"Using {source} {display} at {actual} ({state})")
    return checkout
