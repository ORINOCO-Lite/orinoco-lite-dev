"""Persist snapshots using the shared upstream Pool reader."""

from __future__ import annotations

import json
import os
from pathlib import Path

if __package__:
    from . import upstream_pool_diff
else:
    import upstream_pool_diff


DEFAULT_API = upstream_pool_diff.DEFAULT_API


def write_snapshot(
    destination: Path, *, api: str = DEFAULT_API
) -> tuple[int, dict[str, object]]:
    records, server = upstream_pool_diff.fetch_live(api)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            for pid in sorted(records):
                record = records[pid]
                schema_type = record.get("schema_type", "")
                class_name = (
                    schema_type.rsplit(":", 1)[-1]
                    if isinstance(schema_type, str)
                    else "Thing"
                )
                stream.write(
                    json.dumps(
                        {"class_name": class_name, "record": record},
                        sort_keys=True,
                    )
                    + "\n"
                )
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return len(records), server


def snapshot_fingerprint(path: Path) -> tuple[int, str]:
    records, digest = upstream_pool_diff.load_cache(path)
    return len(records), digest
