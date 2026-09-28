"""Canonical hashing helpers shared by release and resources code."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def tree_sha256(root: Path, *, annex_keys: dict[Path, str] | None = None) -> str:
    """Hash an exact regular-file tree including names and file digests."""

    digest = hashlib.sha256()
    annex_keys = annex_keys or {}
    for path in sorted(candidate for candidate in root.rglob("*")
                       if ".git" not in candidate.relative_to(root).parts
                       and (candidate.is_file() or candidate in annex_keys)):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(annex_keys[path].encode()).digest()
                      if path in annex_keys else bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()
