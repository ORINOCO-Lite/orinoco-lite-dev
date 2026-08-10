#!/usr/bin/env python3
"""Load the prepared upstream snapshot through the local Dump Things API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "local-stack"
SNAPSHOT = STACK / "pool" / "public-thing.jsonl"
EDITOR_TOKEN = STACK / "editor-token"
SERVICE_URL = "http://127.0.0.1:8111"


def call(method: str, url: str, token: str, body: object | None = None) -> tuple[int, object | None]:
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
        raise RuntimeError(f"{method} {url} failed ({error.code}): {detail[:500]}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach local Dump Things service at {SERVICE_URL}: {error}") from error


def put_record(collection: str, class_name: str, record: dict, token: str) -> str:
    pid = record.get("pid")
    if not isinstance(pid, str):
        return "skipped"
    existing_status, existing = call(
        "GET",
        f"{SERVICE_URL}/{collection}/curated/record?{urlencode({'pid': pid})}",
        token,
    )
    if existing_status == 200 and existing == record:
        return "unchanged"
    call(
        "POST",
        f"{SERVICE_URL}/{collection}/curated/record/{class_name}",
        token,
        record,
    )
    return "updated" if existing is not None else "created"


def main() -> int:
    if not SNAPSHOT.exists() or not EDITOR_TOKEN.exists():
        print("Run `pixi run prepare-local-stack` first.", file=sys.stderr)
        return 1
    token = EDITOR_TOKEN.read_text(encoding="utf-8").strip()
    counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    total = sum(1 for _ in SNAPSHOT.open(encoding="utf-8"))
    for index, line in enumerate(SNAPSHOT.open(encoding="utf-8"), start=1):
        item = json.loads(line)
        record = item["record"]
        class_name = item["class_name"]
        for collection in ("public", "protected"):
            result = put_record(collection, class_name, record, token)
            counts[result] += 1
        if index == 1 or index % 25 == 0 or index == total:
            print(f"Seeded {index}/{total} records into public and protected", flush=True)
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
