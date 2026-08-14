#!/usr/bin/env python3
"""Seed only the upstream public/protected pair in the local service."""

from __future__ import annotations

from pathlib import Path

import seed_local_pool as shared


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "upstream-stack"


def main() -> int:
    snapshot = STACK / "pool" / "public-thing.jsonl"
    token_path = STACK / "seed-token"
    missing = [path for path in (snapshot, token_path) if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing prepared upstream inputs: {missing}")
    token = token_path.read_text(encoding="utf-8").strip()
    counts = shared.seed_manifest(
        snapshot,
        ("public", "protected"),
        token,
        "upstream",
    )
    print(shared.json.dumps({"upstream": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
