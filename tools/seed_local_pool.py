#!/usr/bin/env python3
"""Load isolated upstream and CON records through the local Dump Things API."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "local-stack"
UPSTREAM_SNAPSHOT = STACK / "pool" / "public-thing.jsonl"
CON_RECORDS = ROOT / "build" / "con-projection" / "records.jsonl"
SEED_TOKEN = STACK / "seed-token"
SERVICE_URL = "http://127.0.0.1:8111"
CLASS_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
UPSTREAM_COLLECTIONS = ("upstream-public", "upstream-protected")
CON_COLLECTIONS = ("con-public", "con-protected")


def call(
    method: str,
    url: str,
    token: str,
    body: object | None = None,
) -> tuple[int, object | None]:
    headers = {"Accept": "application/json", "X-DumpThings-Token": token}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = Request(url, headers=headers, data=data, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if error.code == 404:
            return error.code, None
        raise RuntimeError(
            f"{method} {url} failed ({error.code}): {detail[:500]}"
        ) from error
    except URLError as error:
        raise RuntimeError(
            f"Could not reach local Dump Things service at {SERVICE_URL}: {error}"
        ) from error


def put_record(collection: str, class_name: str, record: dict, token: str) -> str:
    pid = record.get("pid")
    if not isinstance(pid, str):
        return "skipped"
    existing_status, existing = call(
        "GET",
        f"{SERVICE_URL}/{collection}/curated/record?{urlencode({'pid': pid})}",
        token,
    )
    if existing_status == 200:
        stored_record = dict(record)
        stored_record.pop("schema_type", None)
        if existing in (record, stored_record):
            return "unchanged"
    call(
        "POST",
        f"{SERVICE_URL}/{collection}/curated/record/{quote(class_name, safe='')}",
        token,
        record,
    )
    return "updated" if existing is not None else "created"


def load_manifest(path: Path) -> list[tuple[str, dict]]:
    """Load the stack JSONL envelope and reject ambiguous records."""
    records: list[tuple[str, dict]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise RuntimeError(f"{path}:{line_number}: blank JSONL line")
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"{path}:{line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(item, dict):
                raise RuntimeError(
                    f"{path}:{line_number}: expected a JSON object"
                )
            class_name = item.get("class_name")
            record = item.get("record")
            if not isinstance(class_name, str) or not CLASS_NAME.fullmatch(
                class_name
            ):
                raise RuntimeError(
                    f"{path}:{line_number}: invalid class_name {class_name!r}"
                )
            if not isinstance(record, dict):
                raise RuntimeError(
                    f"{path}:{line_number}: record must be a JSON object"
                )
            pid = record.get("pid")
            if not isinstance(pid, str) or not pid:
                raise RuntimeError(
                    f"{path}:{line_number}: record must have a string pid"
                )
            if pid in seen:
                raise RuntimeError(
                    f"{path}:{line_number}: duplicate record pid {pid!r}"
                )
            seen.add(pid)
            records.append((class_name, record))
    if not records:
        raise RuntimeError(f"{path}: manifest has no records")
    return records


def curated_pids(collection: str, token: str) -> set[str]:
    pids: set[str] = set()
    page = 1
    while True:
        query = urlencode({"page": page, "size": 100})
        url = f"{SERVICE_URL}/{collection}/curated/records/p/?{query}"
        status, payload = call("GET", url, token)
        if status != 200 or not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected paginated response from {url}")
        items = payload.get("items")
        if not isinstance(items, list):
            raise RuntimeError(f"Unexpected paginated response from {url}")
        for record in items:
            pid = record.get("pid") if isinstance(record, dict) else None
            if not isinstance(pid, str):
                raise RuntimeError(f"Record without a pid in {collection}")
            pids.add(pid)
        pages = int(payload.get("pages", 1))
        if page >= pages:
            return pids
        page += 1


def prune_collection(
    collection: str,
    expected_pids: set[str],
    token: str,
) -> int:
    stale = curated_pids(collection, token) - expected_pids
    for pid in sorted(stale):
        query = urlencode({"pid": pid})
        call(
            "DELETE",
            f"{SERVICE_URL}/{collection}/curated/record?{query}",
            token,
        )
    return len(stale)


def seed_manifest(
    path: Path,
    collections: tuple[str, str],
    token: str,
    label: str,
) -> dict[str, int]:
    records = load_manifest(path)
    counts = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "deleted": 0,
    }
    expected_pids = {record["pid"] for _, record in records}
    for collection in collections:
        counts["deleted"] += prune_collection(
            collection,
            expected_pids,
            token,
        )
    targets = " and ".join(collections)
    for index, (class_name, record) in enumerate(records, start=1):
        for collection in collections:
            result = put_record(collection, class_name, record, token)
            counts[result] += 1
        if index == 1 or index % 25 == 0 or index == len(records):
            print(
                f"Seeded {index}/{len(records)} {label} records into {targets}",
                flush=True,
            )
    return counts


def main() -> int:
    missing = [
        path
        for path in (UPSTREAM_SNAPSHOT, CON_RECORDS, SEED_TOKEN)
        if not path.exists()
    ]
    if missing:
        print("Run `pixi run prepare-local-stack` first.", file=sys.stderr)
        for path in missing:
            print(f"Missing required local-stack input: {path}", file=sys.stderr)
        return 1
    token = SEED_TOKEN.read_text(encoding="utf-8").strip()
    summary = {
        "upstream": seed_manifest(
            UPSTREAM_SNAPSHOT,
            UPSTREAM_COLLECTIONS,
            token,
            "upstream",
        ),
        "con": seed_manifest(CON_RECORDS, CON_COLLECTIONS, token, "CON"),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
