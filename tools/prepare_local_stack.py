#!/usr/bin/env python3
"""Prepare the isolated local services used by the clean migration.

The German pool cache and the CON projection are kept in separate collection
pairs.  The local editor can write only to the CON incoming area.  This task
only materializes runtime state under ``build/local-stack``; no records or
credentials are committed to Git.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
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
SEED_TOKEN = STACK / "seed-token"
ADMIN_TOKEN = STACK / "admin-token"
POOL_UI_SOURCE = (
    ROOT / "submodules" / "pool.psychoinformatics.de-ui" / "dist" / "ui"
)
POOL_UI = STACK / "ui"
POOL_API = os.environ.get(
    "UPSTREAM_POOL_API", "https://pool.psychoinformatics.de/api"
).rstrip("/")
SCHEMA = (
    ROOT
    / "submodules"
    / "things-schemas"
    / "src"
    / "demo-research-information"
    / "unreleased.yaml"
)
COLLECTIONS = (
    "upstream-public",
    "upstream-protected",
    "con-public",
    "con-protected",
)
LEGACY_COLLECTIONS = ("public", "protected")


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
        path.chmod(0o600)
        return existing
    value = secrets.token_urlsafe(32)
    path.write_text(value + "\n")
    path.chmod(0o600)
    return value


def fetch_page(page: int, size: int = 100) -> tuple[dict, int]:
    """Fetch one paginated Thing page, shrinking a page that exceeds the API limit."""
    while size >= 1:
        query = urlencode({"format": "json", "size": size, "page": page})
        url = f"{POOL_API}/public/records/p/Thing?{query}"
        try:
            result = request_json(url)
            if not isinstance(result, dict) or "items" not in result:
                raise RuntimeError(f"Unexpected response from {url}")
            return result, size
        except RuntimeError as error:
            if "413" not in str(error) or size == 1:
                raise
            size //= 2
    raise AssertionError("unreachable")


def write_snapshot() -> tuple[int, dict]:
    server = request_json(f"{POOL_API}/server")
    size = 100
    while True:
        first, size = fetch_page(1, size)
        total = int(first["total"])
        pages = int(first["pages"])
        payloads = [first]
        restart = False
        for page in range(2, pages + 1):
            payload, effective_size = fetch_page(page, size)
            if effective_size != size:
                size = effective_size
                restart = True
                break
            if int(payload["total"]) != total:
                raise RuntimeError(
                    "Upstream pool changed while its snapshot was being fetched"
                )
            payloads.append(payload)
        if not restart:
            break
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    temporary = SNAPSHOT.with_name(f".{SNAPSHOT.name}.tmp-{os.getpid()}")
    records = 0
    seen: set[str] = set()
    try:
        with temporary.open("w", encoding="utf-8") as output:
            for page, payload in enumerate(payloads, start=1):
                for record in payload["items"]:
                    pid = record.get("pid")
                    if not isinstance(pid, str) or not pid:
                        raise RuntimeError(
                            "Upstream pool page "
                            f"{page} has a record without a pid"
                        )
                    if pid in seen:
                        raise RuntimeError(
                            f"Upstream pool pagination repeated pid {pid!r}"
                        )
                    schema_type = record.get("schema_type", "")
                    class_name = (
                        schema_type.rsplit(":", 1)[-1]
                        if isinstance(schema_type, str)
                        else "Thing"
                    )
                    envelope = {"class_name": class_name, "record": record}
                    output.write(json.dumps(envelope, sort_keys=True) + "\n")
                    seen.add(pid)
                    records += 1
                print(
                    f"Fetched pool page {page}/{pages} "
                    f"({records}/{total} records)",
                    flush=True,
                )
        if records != total:
            raise RuntimeError(
                "Upstream pool snapshot is incomplete: "
                f"expected {total} unique records, fetched {records}"
            )
        os.replace(temporary, SNAPSHOT)
    finally:
        if temporary.exists():
            temporary.unlink()
    return records, server if isinstance(server, dict) else {}


def snapshot_fingerprint(path: Path) -> tuple[int, str]:
    """Validate a cached JSONL snapshot and return its count and digest."""
    digest = hashlib.sha256()
    seen: set[str] = set()
    with path.open("rb") as stream:
        for line_number, line in enumerate(stream, start=1):
            digest.update(line)
            if not line.strip():
                raise RuntimeError(
                    f"Cached snapshot {path}:{line_number} has a blank line"
                )
            try:
                item = json.loads(line)
                pid = item["record"]["pid"]
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                raise RuntimeError(
                    f"Cached snapshot {path}:{line_number} is invalid"
                ) from error
            if not isinstance(pid, str) or not pid or pid in seen:
                raise RuntimeError(
                    f"Cached snapshot {path}:{line_number} has an invalid "
                    f"or duplicate pid {pid!r}"
                )
            seen.add(pid)
    if not seen:
        raise RuntimeError(f"Cached snapshot {path} has no records")
    return len(seen), digest.hexdigest()


def yaml_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def write_service_config(editor_token: str, seed_token: str) -> None:
    store = STACK / "store"
    for collection in COLLECTIONS:
        (store / collection / "curated").mkdir(parents=True, exist_ok=True)
        (store / collection / "incoming").mkdir(parents=True, exist_ok=True)
    config = f"""type: collections
version: 2
collections:
  upstream-public:
    default_token: local_reader
    curated: upstream-public/curated
    incoming: upstream-public/incoming
    schema: {yaml_quote(str(SCHEMA))}
    auth_sources:
      - type: config
  upstream-protected:
    default_token: local_reader
    curated: upstream-protected/curated
    incoming: upstream-protected/incoming
    schema: {yaml_quote(str(SCHEMA))}
    auth_sources:
      - type: config
  con-public:
    default_token: local_reader
    curated: con-public/curated
    incoming: con-public/incoming
    schema: {yaml_quote(str(SCHEMA))}
    auth_sources:
      - type: config
  con-protected:
    default_token: local_con_reader
    curated: con-protected/curated
    incoming: con-protected/incoming
    schema: {yaml_quote(str(SCHEMA))}
    auth_sources:
      - type: config
tokens:
  local_reader:
    user_id: local-reader
    collections:
      upstream-public:
        mode: READ_CURATED
      upstream-protected:
        mode: READ_CURATED
      con-public:
        mode: READ_CURATED
  local_con_reader:
    user_id: local-con-reader
    collections:
      con-protected:
        mode: READ_CURATED
  local_editor:
    user_id: local-editor
    representation: {yaml_quote(editor_token)}
    collections:
      con-protected:
        mode: WRITE_COLLECTION
        incoming_label: local-editor
  local_seeder:
    user_id: local-seeder
    representation: {yaml_quote(seed_token)}
    collections:
      upstream-public:
        mode: CURATOR
      upstream-protected:
        mode: CURATOR
      con-public:
        mode: CURATOR
      con-protected:
        mode: CURATOR
"""
    SERVICE_CONFIG.write_text(config, encoding="utf-8")
    SERVICE_CONFIG.chmod(0o600)


def reset_persisted_service_config() -> None:
    """Make the service import the generated config on its next start."""
    persisted = STACK / "store" / "__dump_things__"
    if persisted.exists():
        shutil.rmtree(persisted)


def remove_legacy_collection_stores() -> list[Path]:
    """Remove only obsolete two-collection runtime stores."""
    removed: list[Path] = []
    store = STACK / "store"
    for collection in LEGACY_COLLECTIONS:
        path = store / collection
        if path.exists():
            shutil.rmtree(path)
            removed.append(path)
    return removed


def prepare_pool_ui() -> None:
    """Copy the pinned UI and specialize both service URLs for CON."""
    source_config = POOL_UI_SOURCE / "config.yaml"
    if not source_config.exists():
        raise RuntimeError(f"Missing pinned pool UI configuration: {source_config}")
    if POOL_UI.exists():
        shutil.rmtree(POOL_UI)
    shutil.copytree(POOL_UI_SOURCE, POOL_UI)
    config_path = POOL_UI / "config.yaml"
    config = config_path.read_text(encoding="utf-8")
    replacements = {
        "http://127.0.0.1:8111/protected/": (
            "http://127.0.0.1:8111/con-protected/"
        ),
        "http://127.0.0.1:8111/public/": (
            "http://127.0.0.1:8111/con-protected/"
        ),
    }
    for original, replacement in replacements.items():
        if config.count(original) != 1:
            raise RuntimeError(
                "Pinned pool UI service contract changed: expected one "
                f"{original!r} in {source_config}"
            )
        config = config.replace(original, replacement)
    token_info = (
        "token_info: Please contact Michael Hanke at "
        "m.hanke@fz-juelich.de for credentials."
    )
    if config.count(token_info) != 1:
        raise RuntimeError(
            "Pinned pool UI token-information contract changed in "
            f"{source_config}"
        )
    config = config.replace(
        token_info,
        "token_info: 'Paste build/local-stack/editor-token when prompted.'",
    )
    config_path.write_text(config, encoding="utf-8")


def main() -> int:
    if not SCHEMA.exists():
        print(f"Missing local schema: {SCHEMA}", file=sys.stderr)
        return 1
    STACK.mkdir(parents=True, exist_ok=True)
    editor_token = token_file(EDITOR_TOKEN)
    seed_token = token_file(SEED_TOKEN)
    token_file(ADMIN_TOKEN)
    refresh = os.environ.get("REFRESH_UPSTREAM_POOL", "") == "1"
    if SNAPSHOT.exists() and MANIFEST.exists() and not refresh:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        expected_records = int(manifest["record_count"])
        records, snapshot_sha256 = snapshot_fingerprint(SNAPSHOT)
        if records != expected_records:
            raise RuntimeError(
                "Cached upstream snapshot count does not match its manifest: "
                f"expected {expected_records}, found {records}"
            )
        expected_sha256 = manifest.get("snapshot_sha256")
        if expected_sha256 is not None and expected_sha256 != snapshot_sha256:
            raise RuntimeError(
                "Cached upstream snapshot digest does not match its manifest"
            )
        server = manifest.get("source_server", {})
        print(
            f"Reusing {records} prepared upstream records "
            "(set REFRESH_UPSTREAM_POOL=1 to refresh)"
        )
    else:
        records, server = write_snapshot()
        verified_records, snapshot_sha256 = snapshot_fingerprint(SNAPSHOT)
        if verified_records != records:
            raise RuntimeError("New upstream snapshot failed its count check")
    removed = remove_legacy_collection_stores()
    write_service_config(editor_token, seed_token)
    reset_persisted_service_config()
    prepare_pool_ui()
    MANIFEST.write_text(
        json.dumps(
            {
                "source_api": POOL_API,
                "source_collection": "public",
                "source_class": "Thing",
                "source_server": server,
                "record_count": records,
                "snapshot": str(SNAPSHOT.relative_to(ROOT)),
                "snapshot_sha256": snapshot_sha256,
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
    print(f"Build-only seed token: {SEED_TOKEN}")
    print(f"CON editor UI: {POOL_UI}")
    if removed:
        print(
            "Removed obsolete local collection stores: "
            + ", ".join(str(path) for path in removed)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
