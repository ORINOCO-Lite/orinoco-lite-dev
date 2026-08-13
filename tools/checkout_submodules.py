#!/usr/bin/env python3
"""Fully check out every pinned development submodule.

The static website build deliberately uses targeted shallow checkouts.  This
helper is for development checkouts, where every top-level and nested
submodule must have complete history and match its parent's recorded gitlink.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Iterable


class CheckoutError(RuntimeError):
    """Report a submodule checkout or verification failure."""


@dataclass(frozen=True)
class Gitlink:
    """One gitlink recorded by a parent repository."""

    parent: Path
    path: Path
    commit: str
    display_path: Path

    @property
    def checkout(self) -> Path:
        return self.parent / self.path


def git(
    repository: Path,
    *arguments: str,
    action: str | None = None,
) -> str:
    """Run Git in ``repository`` and return stripped standard output."""
    command = ["git", "-C", str(repository), *arguments]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout).strip()
        description = action or "Git command failed"
        if detail:
            raise CheckoutError(f"{description}: {detail}") from error
        raise CheckoutError(
            f"{description}: command exited with status {error.returncode}"
        ) from error
    return result.stdout.strip()


def repository_root(path: Path) -> Path:
    """Resolve ``path`` to the root of its containing Git worktree."""
    output = git(
        path.resolve(),
        "rev-parse",
        "--show-toplevel",
        action=f"Not a Git worktree: {path}",
    )
    return Path(output).resolve()


def recorded_gitlinks(repository: Path) -> list[tuple[Path, str]]:
    """Return all gitlink paths and commits recorded at ``HEAD``."""
    output = git(
        repository,
        "ls-tree",
        "-r",
        "-z",
        "HEAD",
        action=f"Unable to inspect gitlinks in {repository}",
    )
    links: list[tuple[Path, str]] = []
    for entry in output.split("\0"):
        if not entry:
            continue
        metadata, separator, name = entry.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise CheckoutError(
                f"Unable to parse gitlink inventory entry in {repository}: "
                f"{entry!r}"
            )
        mode, object_type, commit = fields
        if mode == "160000":
            if object_type != "commit":
                raise CheckoutError(
                    f"Gitlink {name!r} in {repository} has unexpected "
                    f"object type {object_type!r}"
                )
            links.append((Path(name), commit))
    return links


def is_initialized(checkout: Path) -> bool:
    """Return whether ``checkout`` is an initialized Git worktree."""
    if not (checkout / ".git").exists():
        return False
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    return Path(result.stdout.strip()).resolve() == checkout.resolve()


def is_shallow(checkout: Path) -> bool:
    """Return whether an initialized submodule has shallow history."""
    output = git(
        checkout,
        "rev-parse",
        "--is-shallow-repository",
        action=f"Unable to inspect submodule history at {checkout}",
    )
    if output not in {"true", "false"}:
        raise CheckoutError(
            f"Unexpected shallow-repository result at {checkout}: {output!r}"
        )
    return output == "true"


def walk_initialized(
    repository: Path,
    prefix: Path = Path(),
    visited: set[Path] | None = None,
) -> Iterable[Gitlink]:
    """Yield initialized gitlinks recursively from the current checkouts."""
    if visited is None:
        visited = set()
    resolved = repository.resolve()
    if resolved in visited:
        raise CheckoutError(f"Recursive submodule cycle reaches {repository}")
    visited.add(resolved)

    for path, commit in recorded_gitlinks(repository):
        link = Gitlink(repository, path, commit, prefix / path)
        if not is_initialized(link.checkout):
            continue
        yield link
        yield from walk_initialized(
            link.checkout,
            link.display_path,
            visited,
        )


def unshallow_initialized(repository: Path) -> int:
    """Unshallow every currently initialized recursive submodule."""
    count = 0
    for link in list(walk_initialized(repository)):
        if not is_shallow(link.checkout):
            continue
        print(f"Unshallowing {link.display_path}")
        git(
            link.checkout,
            "fetch",
            "--unshallow",
            action=f"Unable to unshallow {link.display_path}",
        )
        count += 1
    return count


def synchronize_submodules(repository: Path) -> None:
    """Copy recursive URLs from each checked-out ``.gitmodules`` file."""
    git(
        repository,
        "submodule",
        "sync",
        "--recursive",
        action="Unable to synchronize recursive submodule URLs",
    )


def update_submodules(repository: Path) -> None:
    """Initialize and detach every recursive submodule at its gitlink."""
    git(
        repository,
        "submodule",
        "update",
        "--init",
        "--recursive",
        "--checkout",
        "--no-recommend-shallow",
        action="Unable to check out every recorded recursive gitlink",
    )


def verify_submodules(repository: Path) -> int:
    """Verify initialization, full history, and exact recursive gitlinks."""
    errors: list[str] = []
    count = 0

    def verify(parent: Path, prefix: Path, ancestors: set[Path]) -> None:
        nonlocal count
        resolved = parent.resolve()
        if resolved in ancestors:
            errors.append(f"recursive submodule cycle reaches {prefix}")
            return
        descendants = {*ancestors, resolved}

        for path, expected in recorded_gitlinks(parent):
            display = prefix / path
            checkout = parent / path
            count += 1
            if not is_initialized(checkout):
                errors.append(f"{display}: not initialized")
                continue
            actual = git(
                checkout,
                "rev-parse",
                "HEAD",
                action=f"Unable to inspect {display}",
            )
            if actual != expected:
                errors.append(
                    f"{display}: expected {expected}, found {actual}"
                )
            if is_shallow(checkout):
                errors.append(f"{display}: repository is still shallow")
            verify(checkout, display, descendants)

    verify(repository, Path(), set())
    if errors:
        details = "\n".join(f"  - {error}" for error in errors)
        raise CheckoutError(f"Submodule verification failed:\n{details}")
    return count


def checkout_submodules(repository: Path) -> int:
    """Prepare and verify a complete recursive development checkout."""
    root = repository_root(repository)
    synchronize_submodules(root)
    unshallow_initialized(root)
    update_submodules(root)
    unshallow_initialized(root)
    synchronize_submodules(root)
    update_submodules(root)
    count = verify_submodules(root)
    print(f"Verified {count} recursive submodule gitlinks")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "repository",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="parent repository to prepare (default: this project)",
    )
    args = parser.parse_args()
    try:
        checkout_submodules(args.repository)
    except CheckoutError as error:
        print(f"checkout-submodules: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
