#!/usr/bin/env python3
"""Compare the prepared upstream pool cache with the current public pool."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "build" / "upstream-stack" / "pool" / "public-thing.jsonl"
DEFAULT_MANIFEST = DEFAULT_CACHE.with_name("manifest.json")
DEFAULT_REPORT = DEFAULT_CACHE.with_name("live-diff.json")
DEFAULT_API = "https://pool.psychoinformatics.de/api"
MISSING = object()


class PoolDiffError(RuntimeError):
    """Report an invalid cache, live response, or comparison request."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_record(record: Mapping[str, object]) -> bytes:
    return (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()


def semantic_digest(records: Mapping[str, Mapping[str, object]]) -> str:
    digest = hashlib.sha256()
    for pid in sorted(records):
        digest.update(canonical_record(records[pid]))
    return digest.hexdigest()


def load_cache(path: Path) -> tuple[dict[str, dict[str, object]], str]:
    if not path.is_file():
        raise PoolDiffError(
            f"Prepared cache is missing: {path}. Run `pixi run check-upstream` "
            "or `pixi run serve-upstream` first."
        )
    records: dict[str, dict[str, object]] = {}
    file_digest = hashlib.sha256()
    with path.open("rb") as stream:
        for line_number, line in enumerate(stream, start=1):
            file_digest.update(line)
            if not line.strip():
                raise PoolDiffError(f"Cache {path}:{line_number} has a blank line")
            try:
                envelope = json.loads(line)
                record = envelope["record"]
                pid = record["pid"]
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                raise PoolDiffError(f"Cache {path}:{line_number} is invalid") from error
            if not isinstance(record, dict) or not isinstance(pid, str) or not pid:
                raise PoolDiffError(f"Cache {path}:{line_number} has an invalid record")
            if pid in records:
                raise PoolDiffError(f"Cache {path}:{line_number} repeats PID {pid!r}")
            records[pid] = record
    if not records:
        raise PoolDiffError(f"Cache {path} has no records")
    return records, file_digest.hexdigest()


def load_manifest(path: Path, cache: Path, count: int, digest: str) -> dict[str, object]:
    if not path.is_file():
        raise PoolDiffError(f"Prepared cache manifest is missing: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise PoolDiffError(f"Prepared cache manifest is invalid: {path}") from error
    if not isinstance(manifest, dict):
        raise PoolDiffError(f"Prepared cache manifest is not an object: {path}")
    if manifest.get("record_count") != count:
        raise PoolDiffError(
            "Prepared cache count does not match its manifest: "
            f"cache={count}, manifest={manifest.get('record_count')!r}"
        )
    expected_digest = manifest.get("snapshot_sha256")
    if expected_digest != digest:
        raise PoolDiffError(
            "Prepared cache digest does not match its manifest: "
            f"cache={digest}, manifest={expected_digest!r}"
        )
    declared = manifest.get("snapshot")
    try:
        relative = str(cache.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        relative = str(cache.resolve())
    if declared not in (relative, str(cache)):
        raise PoolDiffError(
            "Prepared cache path does not match its manifest: "
            f"cache={relative!r}, manifest={declared!r}"
        )
    return manifest


def request_json(url: str, *, timeout: int = 120) -> object:
    request = Request(url, headers={"Accept": "application/json"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code == 413:
                raise PoolDiffError(f"Could not fetch {url}: {error}") from error
            if attempt == 3:
                raise PoolDiffError(f"Could not fetch {url}: {error}") from error
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def fetch_page(
    api: str,
    page: int,
    size: int,
    fetch: Callable[[str], object],
) -> tuple[dict[str, object], int]:
    while size >= 1:
        query = urlencode({"format": "json", "size": size, "page": page})
        url = f"{api}/public/records/p/Thing?{query}"
        try:
            result = fetch(url)
        except PoolDiffError as error:
            if "413" not in str(error) or size == 1:
                raise
            size //= 2
            continue
        if not isinstance(result, dict) or "items" not in result:
            raise PoolDiffError(f"Unexpected live pool response from {url}")
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
            raise PoolDiffError("Live pool pagination metadata is invalid") from error
        with ThreadPoolExecutor(max_workers=workers) as executor:
            remainder = list(
                executor.map(
                    lambda page: fetch_page(api, page, size, fetch),
                    range(2, pages + 1),
                )
            )
        effective_sizes = [effective_size for _, effective_size in remainder]
        restart = any(effective_size != size for effective_size in effective_sizes)
        if restart:
            size = min(effective_sizes)
            continue
        payloads = [first, *(payload for payload, _ in remainder)]
        for payload in payloads[1:]:
            if int(payload.get("total", -1)) != total:
                raise PoolDiffError("Live pool changed while the diff was fetched")
        if not restart:
            break
    records: dict[str, dict[str, object]] = {}
    for page, payload in enumerate(payloads, start=1):
        items = payload.get("items")
        if not isinstance(items, list):
            raise PoolDiffError(f"Live pool page {page} has invalid items")
        for record in items:
            if not isinstance(record, dict):
                raise PoolDiffError(f"Live pool page {page} has a non-object record")
            pid = record.get("pid")
            if not isinstance(pid, str) or not pid or pid in records:
                raise PoolDiffError(
                    f"Live pool page {page} has an invalid or duplicate PID {pid!r}"
                )
            records[pid] = record
    if len(records) != total:
        raise PoolDiffError(
            f"Live pool snapshot is incomplete: expected {total}, fetched {len(records)}"
        )
    return records, server if isinstance(server, dict) else {}


def pointer_segment(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def value_changes(cache: object, live: object, path: str = "") -> list[dict[str, object]]:
    if cache == live:
        return []
    if isinstance(cache, dict) and isinstance(live, dict):
        changes: list[dict[str, object]] = []
        for key in sorted(set(cache) | set(live)):
            child = f"{path}/{pointer_segment(key)}"
            cached_value = cache.get(key, MISSING)
            live_value = live.get(key, MISSING)
            if cached_value is MISSING:
                changes.append(
                    {"path": child, "cache_present": False, "live": live_value}
                )
            elif live_value is MISSING:
                changes.append(
                    {"path": child, "cache": cached_value, "live_present": False}
                )
            else:
                changes.extend(value_changes(cached_value, live_value, child))
        return changes
    return [{"path": path or "/", "cache": cache, "live": live}]


def record_identity(record: Mapping[str, object]) -> dict[str, object]:
    return {
        "pid": record["pid"],
        "schema_type": record.get("schema_type"),
        "display_label": record.get("display_label"),
    }


def compare_records(
    cached: Mapping[str, dict[str, object]],
    live: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    cached_pids = set(cached)
    live_pids = set(live)
    added = [record_identity(live[pid]) for pid in sorted(live_pids - cached_pids)]
    removed = [
        record_identity(cached[pid]) for pid in sorted(cached_pids - live_pids)
    ]
    changed: list[dict[str, object]] = []
    unchanged = 0
    for pid in sorted(cached_pids & live_pids):
        changes = value_changes(cached[pid], live[pid])
        if not changes:
            unchanged += 1
            continue
        changed.append(
            {
                "pid": pid,
                "cache_schema_type": cached[pid].get("schema_type"),
                "live_schema_type": live[pid].get("schema_type"),
                "cache_display_label": cached[pid].get("display_label"),
                "live_display_label": live[pid].get("display_label"),
                "cache_sha256": sha256_bytes(canonical_record(cached[pid])),
                "live_sha256": sha256_bytes(canonical_record(live[pid])),
                "changes": changes,
            }
        )
    return {
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": unchanged,
            "different": bool(added or removed or changed),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def display_value(value: object, *, present: bool = True) -> str:
    if not present:
        return "<missing>"
    rendered = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return rendered if len(rendered) <= 120 else rendered[:117] + "..."


def display_change(change: Mapping[str, object]) -> str:
    cached = display_value(
        change.get("cache"), present=change.get("cache_present") is not False
    )
    live = display_value(
        change.get("live"), present=change.get("live_present") is not False
    )
    return f"{change['path']}: {cached} -> {live}"


def print_report(report: Mapping[str, object], limit: int) -> None:
    cache = report["cache"]
    live = report["live"]
    summary = report["summary"]
    assert isinstance(cache, dict) and isinstance(live, dict) and isinstance(summary, dict)
    print(
        "Upstream pool cache: "
        f"{cache['record_count']} records, {cache['semantic_sha256']}"
    )
    print(
        "Live public pool:    "
        f"{live['record_count']} records, {live['semantic_sha256']}"
    )
    print(
        "Diff: "
        f"+{summary['added']} -{summary['removed']} "
        f"~{summary['changed']} ={summary['unchanged']}"
    )
    remaining = limit
    for marker, section in (("+", "added"), ("-", "removed")):
        entries = report[section]
        assert isinstance(entries, list)
        for entry in entries:
            if remaining == 0:
                break
            assert isinstance(entry, dict)
            label = entry.get("display_label") or entry.get("schema_type") or "Thing"
            print(f"{marker} {entry['pid']} ({label})")
            remaining -= 1
    entries = report["changed"]
    assert isinstance(entries, list)
    for entry in entries:
        if remaining == 0:
            break
        assert isinstance(entry, dict)
        label = entry.get("live_display_label") or entry.get("cache_display_label")
        changes = entry["changes"]
        assert isinstance(changes, list)
        print(f"~ {entry['pid']} ({label or 'Thing'})")
        for change in changes[:8]:
            if isinstance(change, dict):
                print(f"    {display_change(change)}")
        if len(changes) > 8:
            print(f"    ... {len(changes) - 8} more changed fields")
        remaining -= 1
    hidden = int(summary["added"]) + int(summary["removed"]) + int(summary["changed"])
    hidden -= min(limit, hidden)
    if hidden > 0:
        print(f"... {hidden} more changed records; see the JSON report")
    print(f"Detailed report: {report['report_path']}")


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument(
        "--limit", type=int, default=25, help="maximum changed records to print"
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="parallel live-pool page requests"
    )
    parser.add_argument(
        "--check", action="store_true", help="exit 1 when the live pool differs"
    )
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit must be non-negative")
    if args.workers < 1:
        parser.error("--workers must be positive")
    try:
        cached, cache_file_digest = load_cache(args.cache)
        manifest = load_manifest(
            args.manifest, args.cache, len(cached), cache_file_digest
        )
        live, server = fetch_live(args.api, workers=args.workers)
        comparison = compare_records(cached, live)
        report: dict[str, object] = {
            "format": "orinoco-upstream-pool-diff",
            "version": 1,
            "source_api": args.api.rstrip("/"),
            "cache": {
                "path": str(args.cache),
                "manifest_path": str(args.manifest),
                "record_count": len(cached),
                "file_sha256": cache_file_digest,
                "semantic_sha256": semantic_digest(cached),
                "source_server": manifest.get("source_server", {}),
            },
            "live": {
                "record_count": len(live),
                "semantic_sha256": semantic_digest(live),
                "source_server": server,
            },
            **comparison,
            "report_path": str(args.report),
        }
        write_report(args.report, report)
        print_report(report, args.limit)
        summary = report["summary"]
        assert isinstance(summary, dict)
        return 1 if args.check and summary["different"] else 0
    except PoolDiffError as error:
        parser.exit(2, f"upstream-pool-diff: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
