"""Shared HTTP helpers for the isolated German upstream service stack."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import upstream_snapshot


SERVICE_URL = "http://127.0.0.1:8111"


def request_json(
    method: str,
    url: str,
    token: str | None,
    body: object | None = None,
    *,
    missing_ok: bool = False,
) -> object | None:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["X-DumpThings-Token"] = token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = Request(url, headers=headers, data=data, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {url} failed ({error.code}): {detail[:500]}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach {url}: {error}") from error


def expect_rejected(method: str, url: str, token: str | None, body: object) -> None:
    try:
        request_json(method, url, token, body)
    except RuntimeError as error:
        if "(401)" in str(error) or "(403)" in str(error):
            return
        raise
    raise RuntimeError(f"Unauthorized write unexpectedly succeeded: {url}")


def put_record(collection: str, class_name: str, record: dict, token: str) -> str:
    pid = record.get("pid")
    if not isinstance(pid, str):
        return "skipped"
    query = urlencode({"pid": pid})
    existing = request_json(
        "GET",
        f"{SERVICE_URL}/{collection}/curated/record?{query}",
        token,
        missing_ok=True,
    )
    stored = dict(record)
    stored.pop("schema_type", None)
    if existing in (record, stored):
        return "unchanged"
    request_json(
        "POST",
        f"{SERVICE_URL}/{collection}/curated/record/{quote(class_name, safe='')}",
        token,
        record,
    )
    return "updated" if existing is not None else "created"


def load_manifest(path: Path) -> list[tuple[str, dict]]:
    try:
        records = upstream_snapshot.load_jsonl(path)
    except upstream_snapshot.SnapshotError as error:
        raise RuntimeError(str(error)) from error
    return [(item.class_name, item.record) for item in records]


def curated_pids(collection: str, token: str) -> set[str]:
    return set(curated_records(collection, token))


def prune_collection(collection: str, expected: set[str], token: str) -> int:
    stale = curated_pids(collection, token) - expected
    for pid in sorted(stale):
        request_json(
            "DELETE",
            f"{SERVICE_URL}/{collection}/curated/record?{urlencode({'pid': pid})}",
            token,
        )
    return len(stale)


def seed_manifest(
    path: Path,
    collections: Sequence[str],
    token: str,
    label: str,
) -> dict[str, int]:
    records = load_manifest(path)
    counts = {key: 0 for key in ("created", "updated", "unchanged", "skipped")}
    counts["deleted"] = 0
    expected = {record["pid"] for _, record in records}
    for collection in collections:
        counts["deleted"] += prune_collection(collection, expected, token)
    for index, (class_name, record) in enumerate(records, start=1):
        for collection in collections:
            counts[put_record(collection, class_name, record, token)] += 1
        if index == 1 or index % 25 == 0 or index == len(records):
            print(f"Seeded {index}/{len(records)} {label} records", flush=True)
    return counts


def normalize_record(record: dict) -> dict:
    normalized = dict(record)
    normalized.pop("schema_type", None)
    return normalized


def manifest_records(path: Path) -> dict[str, dict]:
    return {
        item.record["pid"]: normalize_record(item.record)
        for item in upstream_snapshot.load_jsonl(path)
    }


def curated_records(collection: str, token: str) -> dict[str, dict]:
    records: dict[str, dict] = {}
    page = 1
    while True:
        url = (
            f"{SERVICE_URL}/{collection}/curated/records/p/?"
            f"{urlencode({'page': page, 'size': 100})}"
        )
        payload = request_json("GET", url, token)
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise RuntimeError(f"Unexpected paginated response from {url}")
        for record in payload["items"]:
            pid = record.get("pid") if isinstance(record, dict) else None
            if not isinstance(pid, str):
                raise RuntimeError(f"Record without a pid in {collection}")
            records[pid] = normalize_record(record)
        if page >= int(payload.get("pages", 1)):
            return records
        page += 1


def describe_difference(expected: dict[str, dict], actual: dict[str, dict]) -> str:
    def digest(record: dict) -> str:
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    missing = sorted(expected.keys() - actual.keys())[:3]
    extra = sorted(actual.keys() - expected.keys())[:3]
    changed = [
        (pid, digest(expected[pid]), digest(actual[pid]))
        for pid in sorted(expected.keys() & actual.keys())
        if expected[pid] != actual[pid]
    ][:3]
    return f"missing={missing!r}, extra={extra!r}, changed={changed!r}"


def incoming_record(collection: str, token: str, pid: str) -> object | None:
    query = urlencode({"pid": pid})
    return request_json(
        "GET",
        f"{SERVICE_URL}/{collection}/incoming/local-editor/record?{query}",
        token,
        missing_ok=True,
    )


def curated_record(collection: str, token: str | None, pid: str) -> object | None:
    query = urlencode({"pid": pid})
    return request_json(
        "GET",
        f"{SERVICE_URL}/{collection}/curated/record?{query}",
        token,
        missing_ok=True,
    )


def delete_incoming_record(collection: str, token: str, pid: str) -> None:
    query = urlencode({"pid": pid})
    request_json(
        "DELETE",
        f"{SERVICE_URL}/{collection}/incoming/local-editor/record?{query}",
        token,
        missing_ok=True,
    )
