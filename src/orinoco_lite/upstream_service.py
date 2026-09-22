"""Reusable HTTP and temporary-service helpers for upstream Pool checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import os
import secrets
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from orinoco_lite import upstream_snapshot
import yaml


SERVICE_URL = "http://127.0.0.1:8111"


@dataclass(frozen=True)
class LocalService:
    """Connection to a disposable service and its retained scratch files."""

    url: str
    token: str
    store: Path


@contextmanager
def local_service(
    scratch: Path,
    schema: Path,
    *,
    port: int,
    timeout: float = 120,
    backend: str = "record_dir+stl",
) -> Iterator[LocalService]:
    """Start a fresh loopback Pool; stop it when the caller leaves the context.

    The selected environment must supply ``dump-things-service``. Scratch
    must be empty; its configuration, store, and log remain for inspection.
    """
    schema = schema.resolve(strict=True)
    if not schema.is_file():
        raise ValueError(f"Service schema is not a file: {schema}")
    if not 1 <= port <= 65535:
        raise ValueError("Service port must be between 1 and 65535")
    scratch.mkdir(parents=True, exist_ok=True)
    if any(scratch.iterdir()):
        raise ValueError(f"Service scratch directory is not empty: {scratch}")
    scratch = scratch.resolve()
    scratch.chmod(0o700)
    store = scratch / "store"
    store.mkdir()
    token = secrets.token_urlsafe(32)
    config = {
        "type": "collections",
        "version": 2,
        "collections": {
            "public": {
                "default_token": "local_reader",
                "curated": "public/curated",
                "incoming": "public/incoming",
                "schema": str(schema),
                "backend": {"type": backend},
                "auth_sources": [{"type": "config"}],
            },
        },
        "tokens": {
            "local_reader": {
                "user_id": "local-reader",
                "collections": {"public": {"mode": "READ_CURATED"}},
            },
            "local_seeder": {
                "user_id": "local-seeder",
                "representation": token,
                "collections": {"public": {"mode": "CURATOR"}},
            },
        },
    }
    config_path = scratch / "dumpthings.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    config_path.chmod(0o600)
    log_path = scratch / "service.log"
    connection = LocalService(f"http://127.0.0.1:{port}", token, store)
    environment = os.environ.copy()
    environment.pop("DTS_ADMIN_TOKEN", None)
    with log_path.open("wb") as stream:
        process = subprocess.Popen(
            [
                "dump-things-service", str(store), "--config", str(config_path),
                "--host", "127.0.0.1", "--port", str(port),
            ],
            cwd=scratch,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Local service exited with status {process.returncode}; "
                        f"see {log_path}"
                    )
                try:
                    request = Request(
                        f"{connection.url}/server",
                        headers={"X-DumpThings-Token": token},
                    )
                    with urlopen(request, timeout=1) as response:
                        server = json.load(response)
                    if {item["name"] for item in server["collections"]} == {"public"}:
                        # A bound service with this private token must answer;
                        # an unrelated listener must not be accepted as ready.
                        private_request = Request(
                            f"{connection.url}/public/curated/records/p/",
                            headers={"X-DumpThings-Token": token},
                        )
                        with urlopen(private_request, timeout=1):
                            pass
                        break
                except HTTPError as error:
                    if error.code in {401, 403}:
                        raise RuntimeError(
                            f"Port {port} did not accept the private service token; "
                            "another service may already be using it"
                        ) from error
                    raise RuntimeError(
                        f"Local service readiness failed with HTTP {error.code}; "
                        f"see {log_path}"
                    ) from error
                except (URLError, TimeoutError):
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError(f"Local service did not become ready; see {log_path}")
            yield connection
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def verify_service_snapshot(
    source: Path,
    collection: str,
    token: str,
    *,
    service_url: str = SERVICE_URL,
) -> int:
    """Require every captured PID, class, and JSON value to survive the service."""
    expected = upstream_snapshot.load_jsonl(source)
    actual = []
    page = 1
    while True:
        payload = request_json(
            "GET",
            f"{service_url}/{quote(collection, safe='')}/records/p/Thing?"
            f"{urlencode({'page': page, 'size': 100, 'format': 'json'})}",
            token,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise RuntimeError("Unexpected service snapshot response")
        for record in payload["items"]:
            schema_type = record.get("schema_type") if isinstance(record, dict) else None
            if not isinstance(schema_type, str) or ":" not in schema_type:
                raise RuntimeError(
                    "Service record is missing its class-qualified schema_type"
                )
            actual.append(upstream_snapshot.RecordEnvelope(
                schema_type.rsplit(":", 1)[-1], record,
            ))
        if page >= int(payload["pages"]):
            break
        page += 1
    upstream_snapshot.compare_snapshots(
        expected,
        actual,
        expected_label="source JSONL",
        actual_label="service records",
    )
    return len(actual)


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


def put_record(
    collection: str, class_name: str, record: dict, token: str,
    *, service_url: str = SERVICE_URL,
) -> str:
    pid = record.get("pid")
    if not isinstance(pid, str):
        return "skipped"
    query = urlencode({"pid": pid})
    existing = request_json(
        "GET",
        f"{service_url}/{collection}/curated/record?{query}",
        token,
        missing_ok=True,
    )
    stored = dict(record)
    stored.pop("schema_type", None)
    if existing in (record, stored):
        return "unchanged"
    request_json(
        "POST",
        f"{service_url}/{collection}/curated/record/{quote(class_name, safe='')}",
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


def curated_pids(
    collection: str, token: str, *, service_url: str = SERVICE_URL,
) -> set[str]:
    return set(curated_records(collection, token, service_url=service_url))


def prune_collection(
    collection: str, expected: set[str], token: str,
    *, service_url: str = SERVICE_URL,
) -> int:
    stale = curated_pids(collection, token, service_url=service_url) - expected
    for pid in sorted(stale):
        request_json(
            "DELETE",
            f"{service_url}/{collection}/curated/record?{urlencode({'pid': pid})}",
            token,
        )
    return len(stale)


def seed_manifest(
    path: Path,
    collections: Sequence[str],
    token: str,
    label: str,
    *, service_url: str = SERVICE_URL,
) -> dict[str, int]:
    records = load_manifest(path)
    counts = {key: 0 for key in ("created", "updated", "unchanged", "skipped")}
    counts["deleted"] = 0
    expected = {record["pid"] for _, record in records}
    for collection in collections:
        counts["deleted"] += prune_collection(collection, expected, token, service_url=service_url)
    for index, (class_name, record) in enumerate(records, start=1):
        for collection in collections:
            counts[put_record(
                collection, class_name, record, token, service_url=service_url
            )] += 1
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


def curated_records(
    collection: str, token: str, *, service_url: str = SERVICE_URL,
) -> dict[str, dict]:
    records: dict[str, dict] = {}
    page = 1
    while True:
        url = (
            f"{service_url}/{collection}/curated/records/p/?"
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


def incoming_record(
    collection: str, token: str, pid: str, *, service_url: str = SERVICE_URL,
) -> object | None:
    query = urlencode({"pid": pid})
    return request_json(
        "GET",
        f"{service_url}/{collection}/incoming/local-editor/record?{query}",
        token,
        missing_ok=True,
    )


def curated_record(
    collection: str, token: str | None, pid: str,
    *, service_url: str = SERVICE_URL,
) -> object | None:
    query = urlencode({"pid": pid})
    return request_json(
        "GET",
        f"{service_url}/{collection}/curated/record?{query}",
        token,
        missing_ok=True,
    )


def delete_incoming_record(
    collection: str, token: str, pid: str, *, service_url: str = SERVICE_URL,
) -> None:
    query = urlencode({"pid": pid})
    request_json(
        "DELETE",
        f"{service_url}/{collection}/incoming/local-editor/record?{query}",
        token,
        missing_ok=True,
    )
