#!/usr/bin/env python3
"""Restore clean-filter-equivalent annex changes without touching user edits."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import subprocess
from typing import Sequence


class AnnexStatusError(RuntimeError):
    """Report a worktree change that annex hydration cannot safely refresh."""


def git(repository: Path, *arguments: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise AnnexStatusError(
            f"git {' '.join(arguments)} failed in {repository}: {detail}"
        )
    return result.stdout


def status(repository: Path) -> bytes:
    return git(
        repository,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )


def status_paths(raw: bytes) -> set[bytes]:
    chunks = raw.rstrip(b"\0").split(b"\0") if raw else []
    paths: set[bytes] = set()
    index = 0
    while index < len(chunks):
        entry = chunks[index]
        if len(entry) < 4 or entry[2:3] != b" ":
            raise AnnexStatusError(f"Unexpected porcelain entry: {entry!r}")
        paths.add(entry[3:])
        if entry[:1] in {b"R", b"C"} or entry[1:2] in {b"R", b"C"}:
            index += 1
            if index >= len(chunks):
                raise AnnexStatusError("Incomplete rename in porcelain status")
            paths.add(chunks[index])
        index += 1
    return paths


def write_snapshot(repository: Path, destination: Path) -> None:
    payload = {
        "repository": str(repository.resolve()),
        "status": base64.b64encode(status(repository)).decode("ascii"),
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def refresh(repository: Path, snapshot: Path) -> None:
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    if Path(payload["repository"]) != repository.resolve():
        raise AnnexStatusError("Annex status snapshot belongs to another repository")
    before = base64.b64decode(payload["status"], validate=True)
    current = status(repository)
    new_paths = status_paths(current) - status_paths(before)
    for raw_path in sorted(new_paths):
        path = raw_path.decode("utf-8", errors="surrogateescape")
        index = git(repository, "rev-parse", f":{path}", check=False).strip()
        if not index:
            raise AnnexStatusError(
                f"Annex hydration created an untracked path: {path}"
            )
        worktree = git(repository, "hash-object", "--", path).strip()
        if worktree != index:
            raise AnnexStatusError(
                "Annex hydration changed tracked content rather than only its "
                f"clean-filter representation: {path}"
            )
        git(repository, "add", "--", path)
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "diff",
                "--cached",
                "--quiet",
                "HEAD",
                "--",
                path,
            ],
            capture_output=True,
        )
        if result.returncode:
            raise AnnexStatusError(f"Refreshing annex status staged a change: {path}")
    after = status(repository)
    if after != before:
        raise AnnexStatusError(
            "Annex hydration did not restore the exact pre-build worktree status"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("snapshot", "refresh"))
    parser.add_argument("repository", type=Path)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            write_snapshot(args.repository, args.snapshot)
        else:
            refresh(args.repository, args.snapshot)
    except (AnnexStatusError, KeyError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, f"restore-annex-status: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
