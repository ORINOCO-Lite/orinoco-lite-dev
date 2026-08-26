#!/usr/bin/env python3
"""Fetch or reuse the public pool and materialize its audited YAML snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

if __package__:
    from . import prepare_local_stack as source
    from . import upstream_orinoco_records
    from . import upstream_snapshot
else:  # Direct ``python tools/...`` use.
    import prepare_local_stack as source
    import upstream_orinoco_records
    import upstream_snapshot


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "upstream-stack"
POOL = STACK / "pool"
RAW_JSONL = POOL / "public-thing.jsonl"
POOL_MANIFEST = POOL / "manifest.json"
SNAPSHOT = STACK / "snapshot"
RECORDS = SNAPSHOT / "metadata" / "records"
CANONICAL_JSONL = SNAPSHOT / "records.jsonl"
SNAPSHOT_MANIFEST = SNAPSHOT / "manifest.json"
ORINOCO_STORAGE = SNAPSHOT / "orinoco-storage"


def configure_source() -> None:
    source.STACK = STACK
    source.SNAPSHOT = RAW_JSONL
    source.MANIFEST = POOL_MANIFEST


def prepare_raw(*, refresh: bool = False) -> tuple[int, str, dict]:
    configure_source()
    refresh = refresh or os.environ.get("REFRESH_UPSTREAM_POOL", "") == "1"
    if RAW_JSONL.exists() and POOL_MANIFEST.exists() and not refresh:
        pool_manifest = json.loads(POOL_MANIFEST.read_text(encoding="utf-8"))
        records, digest = source.snapshot_fingerprint(RAW_JSONL)
        if int(pool_manifest.get("record_count", -1)) != records:
            raise RuntimeError(
                "Cached upstream snapshot count does not match its manifest"
            )
        if pool_manifest.get("snapshot_sha256") != digest:
            raise RuntimeError(
                "Cached upstream snapshot digest does not match its manifest"
            )
        server = pool_manifest.get("source_server", {})
        if not isinstance(server, dict):
            server = {}
        print(
            f"Reusing {records} prepared upstream records "
            "(set REFRESH_UPSTREAM_POOL=1 to refresh)"
        )
        return records, digest, server

    records, server = source.write_snapshot()
    verified_records, digest = source.snapshot_fingerprint(RAW_JSONL)
    if verified_records != records:
        raise RuntimeError("New upstream snapshot failed its count check")
    return records, digest, server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="replace the verified cache with a fresh public-pool capture",
    )
    args = parser.parse_args(argv)
    POOL.mkdir(parents=True, exist_ok=True)
    records, raw_digest, server = prepare_raw(refresh=args.refresh)
    source_api = source.POOL_API
    upstream_snapshot.write_json(
        POOL_MANIFEST,
        {
            "record_count": records,
            "snapshot": str(RAW_JSONL.relative_to(ROOT)),
            "snapshot_sha256": raw_digest,
            "source_api": source_api,
            "source_class": "Thing",
            "source_collection": "public",
            "source_server": server,
        },
    )
    manifest = upstream_snapshot.materialize(
        RAW_JSONL,
        RECORDS,
        manifest_path=SNAPSHOT_MANIFEST,
        replace=True,
    )
    exported = upstream_snapshot.export_records(RECORDS, CANONICAL_JSONL)
    upstream_snapshot.compare_snapshots(
        upstream_snapshot.load_jsonl(RAW_JSONL),
        exported,
        expected_label="upstream API JSONL",
        actual_label="YAML-derived canonical JSONL",
    )
    storage = upstream_orinoco_records.project(
        RAW_JSONL,
        ORINOCO_STORAGE,
        replace=True,
    )
    canonical_digest = hashlib.sha256(CANONICAL_JSONL.read_bytes()).hexdigest()
    print(
        f"Prepared {manifest['record_count']} exact YAML records in {RECORDS}"
    )
    print(f"Raw JSONL SHA-256:       {raw_digest}")
    print(f"Canonical JSONL SHA-256: {canonical_digest}")
    print(f"Semantic SHA-256:        {manifest['records_semantic_sha256']}")
    print(
        "Orinoco storage view:    "
        f"{storage['annotation_companions']} companions / "
        f"{storage['annotation_assertions']} assertions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
