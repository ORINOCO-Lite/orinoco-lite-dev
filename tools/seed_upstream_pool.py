#!/usr/bin/env python3
"""Seed only the upstream public/protected pair in the local service."""

from __future__ import annotations

from pathlib import Path

import seed_local_pool as shared
import upstream_snapshot


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "upstream-stack"
YAML_JSONL = STACK / "snapshot" / "records.jsonl"
PUBLIC_STORE = STACK / "store" / "public" / "curated"
PROTECTED_STORE = STACK / "store" / "protected" / "curated"


def main() -> int:
    snapshot = STACK / "pool" / "public-thing.jsonl"
    token_path = STACK / "seed-token"
    missing = [
        path for path in (snapshot, YAML_JSONL, token_path) if not path.exists()
    ]
    if missing:
        raise RuntimeError(f"Missing prepared upstream inputs: {missing}")
    token = token_path.read_text(encoding="utf-8").strip()
    public_counts = shared.seed_manifest(
        snapshot,
        ("public",),
        token,
        "upstream JSONL",
    )
    upstream_snapshot.verify(snapshot, PUBLIC_STORE, upstream_store=True)

    protected_counts = shared.seed_manifest(
        YAML_JSONL,
        ("protected",),
        token,
        "YAML-derived upstream",
    )
    upstream_snapshot.verify(YAML_JSONL, PROTECTED_STORE, upstream_store=True)
    upstream_snapshot.compare_snapshots(
        upstream_snapshot.load_jsonl(snapshot),
        upstream_snapshot.load_jsonl(YAML_JSONL),
        expected_label="raw upstream JSONL",
        actual_label="YAML-derived JSONL",
    )
    print(
        shared.json.dumps(
            {
                "upstream": {
                    "public_from_jsonl": public_counts,
                    "protected_from_yaml": protected_counts,
                    "roundtrip": "exact",
                }
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
