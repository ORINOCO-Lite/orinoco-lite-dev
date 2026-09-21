from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

from orinoco_lite import pool_capture, upstream_snapshot


API = "https://pool.example.test/api"
PID = "example:record"


def main(arguments):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="records_command", required=True)
    pool_capture.register_capture(commands)
    args = parser.parse_args([*arguments, "--no-record"])
    try:
        return pool_capture.execute(args)
    except pool_capture.CaptureError as error:
        parser.error(str(error))


def record(pid=PID, name="Initial"):
    return {"pid": pid, "schema_type": "dlthings:Thing", "name": name}


@pytest.fixture
def capture(tmp_path, monkeypatch):
    fetch = Mock(return_value=({PID: record()}, {"version": "fixture"}))
    monkeypatch.setattr(pool_capture, "fetch_live", fetch)
    destination = tmp_path / "pool.jsonl"
    manifest = tmp_path / "pool.jsonl.manifest.json"
    return destination, manifest, fetch


def test_cli_captures_exact_records_then_reuses_without_fetching(capture, monkeypatch):
    destination, manifest_path, fetch = capture
    monkeypatch.setenv("UPSTREAM_POOL_API", "https://ignored.example.test/api")
    monkeypatch.setenv("REFRESH_UPSTREAM_POOL", "1")
    expected = record()
    expected["extra"] = {"ordered": [2, 1, 2], "text": "ü", "optional": None}
    fetch.return_value = ({PID: expected}, {"version": "fixture"})

    assert main(["get", str(destination)]) == 0
    fetch.assert_called_once_with(pool_capture.DEFAULT_API)
    assert upstream_snapshot.load_jsonl(destination)[0].record == expected
    manifest = json.loads(manifest_path.read_text())
    assert datetime.fromisoformat(manifest["captured_at"]).utcoffset().total_seconds() == 0
    assert datetime.fromisoformat(manifest["capture_started_at"]) <= datetime.fromisoformat(manifest["captured_at"])
    assert manifest["completeness"]["atomic_snapshot"] is False
    assert "concurrent edits" in manifest["completeness"]["limitations"]
    before = (destination.read_bytes(), manifest_path.read_bytes())

    assert main(["get", str(destination)]) == 0
    assert fetch.call_count == 1
    assert (destination.read_bytes(), manifest_path.read_bytes()) == before
    assert set(destination.parent.iterdir()) == {destination, manifest_path}


def test_default_path_downloads_reuses_and_force_replaces(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetch = Mock(return_value=({PID: record()}, {}))
    monkeypatch.setattr(pool_capture, "fetch_live", fetch)

    assert main(["get"]) == 0
    destination = tmp_path / "site-specific/sources/pool/records.jsonl"
    assert upstream_snapshot.load_jsonl(destination)[0].record == record()
    assert destination.with_name("records.jsonl.manifest.json").is_file()

    assert main(["get"]) == 0
    assert fetch.call_count == 1

    fetch.return_value = ({PID: record(name="Changed")}, {})
    assert main(["get", "--force"]) == 0
    assert fetch.call_count == 2
    assert upstream_snapshot.load_jsonl(destination)[0].record == record(name="Changed")


def test_force_replaces_capture_and_records_its_actual_origin(capture):
    destination, manifest_path, fetch = capture
    assert main(["get", str(destination), "--api", API + "/"]) == 0
    fetch.assert_called_once_with(API)
    fetch.return_value = ({PID: record(name="Changed")}, {"version": "new"})
    other_api = "https://other.example.test/api"

    assert main(["get", str(destination), "--force", "--api", other_api]) == 0

    fetch.assert_called_with(other_api)
    assert upstream_snapshot.load_jsonl(destination)[0].record == record(name="Changed")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["source_api"] == other_api
    assert manifest["source_server"] == {"version": "new"}


@pytest.mark.parametrize("damage, message", [
    ("missing", "no provenance manifest"),
    ("malformed", "Invalid Pool capture manifest"),
    ("not-object", "manifest is not an object"),
    ("unknown-origin", "use --force"),
    ("other-origin", "use --force"),
    ("count", "count does not match"),
    ("digest", "digest does not match"),
])
def test_invalid_cache_is_not_fetched_or_rewritten(capture, damage, message, capsys):
    destination, manifest_path, fetch = capture
    pool_capture.capture(destination, api=API)
    manifest = json.loads(manifest_path.read_text())
    if damage == "missing":
        manifest_path.unlink()
    elif damage == "malformed":
        manifest_path.write_text("{")
    elif damage == "not-object":
        manifest_path.write_text("[]")
    else:
        field, value = {
            "unknown-origin": ("source_api", None),
            "other-origin": ("source_api", "https://other.example.test/api"),
            "count": ("record_count", 2),
            "digest": ("snapshot_sha256", "0" * 64),
        }[damage]
        manifest[field] = value
        manifest_path.write_text(json.dumps(manifest))
    before = destination.read_bytes()
    manifest_before = manifest_path.read_bytes() if manifest_path.exists() else None
    fetch.reset_mock()

    with pytest.raises(SystemExit) as error:
        main(["get", str(destination), "--api", API])

    assert error.value.code == 2
    assert message in capsys.readouterr().err
    fetch.assert_not_called()
    assert destination.read_bytes() == before
    assert (manifest_path.read_bytes() if manifest_path.exists() else None) == manifest_before
    assert main(["get", str(destination), "--api", API, "--force"]) == 0
    fetch.assert_called_once_with(API)


def test_failed_force_preserves_existing_capture(capture):
    destination, manifest_path, fetch = capture
    pool_capture.capture(destination)
    before = (destination.read_bytes(), manifest_path.read_bytes())
    # A response with a PID but no schema class cannot become a usable capture.
    fetch.return_value = ({PID: {"pid": PID}}, {})

    with pytest.raises(pool_capture.CaptureError, match="invalid class_name"):
        pool_capture.capture(destination, force=True)

    assert (destination.read_bytes(), manifest_path.read_bytes()) == before
    assert set(destination.parent.iterdir()) == {destination, manifest_path}


def test_failed_manifest_replacement_leaves_cache_fail_closed(capture, monkeypatch):
    destination, manifest_path, fetch = capture
    pool_capture.capture(destination)
    fetch.return_value = ({PID: record(name="Changed")}, {})
    replace = pool_capture.os.replace

    def fail_manifest(source, target):
        if target == manifest_path:
            raise OSError("injected manifest replacement failure")
        return replace(source, target)

    monkeypatch.setattr(pool_capture.os, "replace", fail_manifest)
    with pytest.raises(pool_capture.CaptureError, match="manifest replacement failure"):
        pool_capture.capture(destination, force=True)

    fetch.reset_mock()
    with pytest.raises(pool_capture.CaptureError, match="digest does not match"):
        pool_capture.capture(destination)
    fetch.assert_not_called()


def test_capture_restarts_all_pages_when_a_later_page_needs_smaller_requests():
    records = [record(f"example:{index}") for index in range(105)]
    requests = []

    def fetch(url):
        if url.endswith("/server"):
            return {"version": "fixture"}
        query = parse_qs(urlparse(url).query)
        page, size = int(query["page"][0]), int(query["size"][0])
        requests.append((page, size))
        if page > 1 and size > 50:
            raise pool_capture.CaptureError("HTTP Error 413")
        start = (page - 1) * size
        return {"items": records[start:start + size], "total": len(records),
                "pages": math.ceil(len(records) / size)}

    captured, server = pool_capture.fetch_live(API, fetch=fetch, workers=1)

    assert list(captured.values()) == records
    assert server == {"version": "fixture"}
    assert (1, 100) in requests and (1, 50) in requests


@pytest.mark.parametrize("items,total,message", [
    ([record(), record()], 2, "duplicate PID"),
    ([record()], 2, "incomplete"),
])
def test_live_capture_rejects_duplicate_or_missing_records(items, total, message):
    def fetch(url):
        return {} if url.endswith("/server") else {"items": items, "total": total, "pages": 1}

    with pytest.raises(pool_capture.CaptureError, match=message):
        pool_capture.fetch_live(API, fetch=fetch)


@pytest.mark.parametrize("total,pages", [(True, 1), (1, "1"), (1, 2), (-1, 1)])
def test_live_capture_rejects_invalid_pagination(total, pages):
    def fetch(url):
        return {} if url.endswith("/server") else {"items": [record()], "total": total, "pages": pages}

    with pytest.raises(pool_capture.CaptureError, match="pagination|at least one"):
        pool_capture.fetch_live(API, fetch=fetch)


@pytest.mark.parametrize("change", [{"total": 100}, {"pages": 3}, {"page": 1}, {"size": 50}])
def test_live_capture_rejects_changed_paging_coordinates(change):
    def fetch(url):
        if url.endswith("/server"):
            return {}
        page = int(parse_qs(urlparse(url).query)["page"][0])
        payload = {"items": [record(f"example:{page}-{index}") for index in range(100 if page == 1 else 1)],
                   "total": 101, "pages": 2, "page": page, "size": 100}
        if page == 2:
            payload.update(change)
        return payload

    with pytest.raises(pool_capture.CaptureError, match="changed|pagination"):
        pool_capture.fetch_live(API, fetch=fetch, workers=1)


@pytest.mark.parametrize("api", ["file:///tmp/source", "https://user:secret@example.test/api", "https://example.test/api?token=secret"])
def test_capture_does_not_store_credentials_or_accept_non_service_urls(tmp_path, monkeypatch, api):
    monkeypatch.setattr(pool_capture, "fetch_live", lambda *args: pytest.fail("must not fetch invalid source"))
    with pytest.raises(pool_capture.CaptureError, match="HTTP|credentials"):
        pool_capture.capture(tmp_path / "capture.jsonl", api=api)
    assert not list(tmp_path.iterdir())
