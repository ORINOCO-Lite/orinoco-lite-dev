"""Fetch a public Pool capture, or reuse it after checking its source and bytes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import OrinocoError


DEFAULT_API = "https://pool.psychoinformatics.de/api"


class CaptureError(OrinocoError):
    """The capture or live Pool response cannot be safely used."""


def load_cache(path: Path) -> tuple[dict[str, dict[str, object]], str]:
    from .upstream_snapshot import SnapshotError, load_jsonl

    try:
        records = load_jsonl(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, UnicodeError, SnapshotError) as error:
        raise CaptureError(f"Invalid Pool capture {path}: {error}") from error
    if not records:
        raise CaptureError(f"Pool capture has no records: {path}")
    return {item.pid: item.record for item in records}, digest


def request_json(url: str, *, timeout: int = 120) -> object:
    request = Request(url, headers={"Accept": "application/json"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            if (isinstance(error, HTTPError) and error.code == 413) or attempt == 3:
                raise CaptureError(f"Could not fetch {url}: {error}") from error
            time.sleep(2**attempt)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise CaptureError(f"Invalid JSON response from {url}") from error
    raise AssertionError("unreachable")


def fetch_page(
    api: str, page: int, size: int, fetch: Callable[[str], object]
) -> tuple[dict[str, object], int]:
    while size >= 1:
        query = urlencode({"format": "json", "size": size, "page": page})
        url = f"{api}/public/records/p/Thing?{query}"
        try:
            result = fetch(url)
        except CaptureError as error:
            if "413" not in str(error) or size == 1:
                raise
            size //= 2
            continue
        if not isinstance(result, dict) or "items" not in result:
            raise CaptureError(f"Unexpected Pool response from {url}")
        return result, size
    raise AssertionError("unreachable")


def fetch_live(
    api: str,
    *,
    fetch: Callable[[str], object] = request_json,
    workers: int = 8,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    api = api.rstrip("/")
    server = fetch(f"{api}/server")
    size = 100
    while True:
        first, size = fetch_page(api, 1, size, fetch)
        try:
            total = int(first["total"])
            pages = int(first["pages"])
        except (KeyError, TypeError, ValueError) as error:
            raise CaptureError("Pool pagination metadata is invalid") from error
        if total < 1 or pages < 1:
            raise CaptureError("Pool capture must contain at least one record")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            remainder = list(
                executor.map(
                    lambda page: fetch_page(api, page, size, fetch),
                    range(2, pages + 1),
                )
            )
        effective_sizes = [effective_size for _, effective_size in remainder]
        if any(effective_size != size for effective_size in effective_sizes):
            size = min(effective_sizes)
            continue
        payloads = [first, *(payload for payload, _ in remainder)]
        if any(payload.get("total") != first["total"] for payload in payloads[1:]):
            raise CaptureError("Pool changed while the capture was fetched")
        break
    records: dict[str, dict[str, object]] = {}
    for page, payload in enumerate(payloads, start=1):
        items = payload.get("items")
        if not isinstance(items, list):
            raise CaptureError(f"Pool page {page} has invalid items")
        for record in items:
            if not isinstance(record, dict):
                raise CaptureError(f"Pool page {page} has a non-object record")
            pid = record.get("pid")
            if not isinstance(pid, str) or not pid or pid in records:
                raise CaptureError(
                    f"Pool page {page} has an invalid or duplicate PID {pid!r}"
                )
            records[pid] = record
    if len(records) != total:
        raise CaptureError(
            f"Pool capture is incomplete: expected {total}, fetched {len(records)}"
        )
    return records, server if isinstance(server, dict) else {}


def capture(
    destination: Path, *, api: str = DEFAULT_API, refresh: bool = False
) -> dict:
    """Keep exact record values; publish only a complete, checked JSONL capture."""
    destination = destination.absolute()
    manifest_path = destination.with_name(destination.name + ".manifest.json")
    api = api.rstrip("/")
    if destination.exists() and not refresh:
        if not manifest_path.is_file():
            raise CaptureError(
                "Cached Pool capture has no provenance manifest; "
                "use --refresh to capture the requested API"
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CaptureError(
                f"Invalid Pool capture manifest: {manifest_path}"
            ) from error
        if not isinstance(manifest, dict):
            raise CaptureError(
                f"Pool capture manifest is not an object: {manifest_path}"
            )
        cached_api = manifest.get("source_api")
        if not isinstance(cached_api, str) or cached_api.rstrip("/") != api:
            raise CaptureError(
                f"Cached Pool capture is from {cached_api!r}, not {api!r}; "
                "use --refresh to capture the requested API"
            )
        records, digest = load_cache(destination)
        if manifest.get("record_count") != len(records):
            raise CaptureError("Cached Pool capture count does not match its manifest")
        if manifest.get("snapshot_sha256") != digest:
            raise CaptureError("Cached Pool capture digest does not match its manifest")
        print(
            f"Reusing {len(records)} records in {destination} "
            "(use --refresh to fetch again)"
        )
        return manifest

    records, server = fetch_live(api)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".pool-capture-", dir=destination.parent
        ) as temporary:
            raw = Path(temporary) / "capture.jsonl"
            with raw.open("w", encoding="utf-8") as stream:
                for pid in sorted(records):
                    record = records[pid]
                    schema_type = record.get("schema_type", "")
                    class_name = (
                        schema_type.rsplit(":", 1)[-1]
                        if isinstance(schema_type, str) else ""
                    )
                    stream.write(
                        json.dumps(
                            {"class_name": class_name, "record": record},
                            sort_keys=True,
                        ) + "\n"
                    )
            verified, digest = load_cache(raw)
            if len(verified) != len(records):
                raise CaptureError("New Pool capture failed its count check")
            manifest = {
                "record_count": len(records),
                "snapshot": destination.name,
                "snapshot_sha256": digest,
                "source_api": api,
                "source_class": "Thing",
                "source_collection": "public",
                "source_server": server,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }
            audit = Path(temporary) / "manifest.json"
            audit.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(raw, destination)
            os.replace(audit, manifest_path)
    except OSError as error:
        raise CaptureError(f"Could not save Pool capture {destination}: {error}") from error
    print(f"Captured {len(records)} records in {destination}")
    print(f"SHA-256: {digest}")
    return manifest
