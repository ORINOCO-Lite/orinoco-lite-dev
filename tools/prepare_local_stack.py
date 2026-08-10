#!/usr/bin/env python3
"""Prepare a local, service-backed copy of the upstream public pool.

The local editor is deliberately configured like the upstream deployment: the
UI reads and writes through Dump Things and receives the schema/configuration
from the pool-ui checkout.  This task only materializes runtime state under
``build/local-stack``; no records or credentials are committed to Git.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "local-stack"
SNAPSHOT = STACK / "pool" / "public-thing.jsonl"
MANIFEST = STACK / "pool" / "manifest.json"
SERVICE_CONFIG = STACK / "dumpthings.yaml"
EDITOR_TOKEN = STACK / "editor-token"
ADMIN_TOKEN = STACK / "admin-token"
POOL_API = os.environ.get("UPSTREAM_POOL_API", "https://pool.psychoinformatics.de/api").rstrip("/")
SCHEMA = ROOT / "submodules" / "things-schemas" / "src" / "demo-research-information" / "unreleased.yaml"


def request_json(url: str, *, timeout: int = 120) -> object:
    request = Request(url, headers={"Accept": "application/json"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == 3:
                raise RuntimeError(f"Could not fetch {url}: {error}") from error
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def token_file(path: Path) -> str:
    existing = path.read_text().strip() if path.exists() else ""
    if existing:
        return existing
    value = secrets.token_urlsafe(32)
    path.write_text(value + "\n")
    path.chmod(0o600)
    return value


def fetch_page(page: int, size: int = 100) -> dict:
    """Fetch one paginated Thing page, shrinking a page that exceeds the API limit."""
    while size >= 1:
        query = urlencode({"format": "json", "size": size, "page": page})
        url = f"{POOL_API}/public/records/p/Thing?{query}"
        try:
            result = request_json(url)
            if not isinstance(result, dict) or "items" not in result:
                raise RuntimeError(f"Unexpected response from {url}")
            return result
        except RuntimeError as error:
            if "413" not in str(error) or size == 1:
                raise
            size //= 2
    raise AssertionError("unreachable")


def write_snapshot() -> tuple[int, dict]:
    server = request_json(f"{POOL_API}/server")
    first = fetch_page(1)
    total = int(first["total"])
    pages = int(first["pages"])
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    records = 0
    seen: set[str] = set()
    with SNAPSHOT.open("w", encoding="utf-8") as output:
        for page in range(1, pages + 1):
            payload = first if page == 1 else fetch_page(page)
            for record in payload["items"]:
                pid = record.get("pid")
                if not isinstance(pid, str) or pid in seen:
                    continue
                schema_type = record.get("schema_type", "")
                class_name = schema_type.rsplit(":", 1)[-1] if isinstance(schema_type, str) else "Thing"
                output.write(json.dumps({"class_name": class_name, "record": record}, sort_keys=True) + "\n")
                seen.add(pid)
                records += 1
            print(f"Fetched pool page {page}/{pages} ({records}/{total} records)", flush=True)
    return records, server if isinstance(server, dict) else {}


def yaml_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_service_config(editor_token: str) -> None:
    store = STACK / "store"
    for collection in ("public", "protected"):
        (store / collection / "curated").mkdir(parents=True, exist_ok=True)
        (store / collection / "incoming").mkdir(parents=True, exist_ok=True)
    config = f"""type: collections
version: 2
collections:
  public:
    default_token: local_editor
    curated: public/curated
    incoming: public/incoming
    schema: {yaml_quote(str(SCHEMA))}
    auth_sources:
      - type: config
  protected:
    default_token: local_editor
    curated: protected/curated
    incoming: protected/incoming
    schema: {yaml_quote(str(SCHEMA))}
    auth_sources:
      - type: config
tokens:
  local_editor:
    user_id: local-editor
    representation: {yaml_quote(editor_token)}
    collections:
      public:
        mode: CURATOR
      protected:
        mode: CURATOR
"""
    SERVICE_CONFIG.write_text(config, encoding="utf-8")
    SERVICE_CONFIG.chmod(0o600)


def main() -> int:
    if not SCHEMA.exists():
        print(f"Missing local schema: {SCHEMA}", file=sys.stderr)
        return 1
    STACK.mkdir(parents=True, exist_ok=True)
    editor_token = token_file(EDITOR_TOKEN)
    token_file(ADMIN_TOKEN)
    refresh = os.environ.get("REFRESH_UPSTREAM_POOL", "") == "1"
    if SNAPSHOT.exists() and MANIFEST.exists() and not refresh:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        records = int(manifest["record_count"])
        server = manifest.get("source_server", {})
        print(f"Reusing {records} prepared upstream records (set REFRESH_UPSTREAM_POOL=1 to refresh)")
    else:
        records, server = write_snapshot()
    write_service_config(editor_token)
    MANIFEST.write_text(
        json.dumps(
            {
                "source_api": POOL_API,
                "source_collection": "public",
                "source_class": "Thing",
                "source_server": server,
                "record_count": records,
                "snapshot": str(SNAPSHOT.relative_to(ROOT)),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Prepared {records} upstream records in {SNAPSHOT}")
    print(f"Dump Things config: {SERVICE_CONFIG}")
    print(f"Editor token: {EDITOR_TOKEN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
