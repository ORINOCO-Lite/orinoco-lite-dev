from __future__ import annotations

from datetime import datetime
import json
import math
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

from orinoco_lite import cli, pool_capture, upstream_snapshot


API = "https://pool.example.test/api"
PID = "example:record"


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

    assert cli.main(["dev", "capture", str(destination)]) == 0
    fetch.assert_called_once_with(pool_capture.DEFAULT_API)
    assert upstream_snapshot.load_jsonl(destination)[0].record == expected
    manifest = json.loads(manifest_path.read_text())
    assert datetime.fromisoformat(manifest["captured_at"]).utcoffset().total_seconds() == 0
    before = (destination.read_bytes(), manifest_path.read_bytes())

    assert cli.main(["dev", "capture", str(destination)]) == 0
    assert fetch.call_count == 1
    assert (destination.read_bytes(), manifest_path.read_bytes()) == before
    assert set(destination.parent.iterdir()) == {destination, manifest_path}


def test_refresh_replaces_capture_and_records_its_actual_origin(capture):
    destination, manifest_path, fetch = capture
    assert cli.main(["dev", "capture", str(destination), "--api", API + "/"]) == 0
    fetch.assert_called_once_with(API)
    fetch.return_value = ({PID: record(name="Changed")}, {"version": "new"})
    other_api = "https://other.example.test/api"

    assert cli.main(["dev", "capture", str(destination), "--refresh", "--api", other_api]) == 0

    fetch.assert_called_with(other_api)
    assert upstream_snapshot.load_jsonl(destination)[0].record == record(name="Changed")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["source_api"] == other_api
    assert manifest["source_server"] == {"version": "new"}


@pytest.mark.parametrize("damage, message", [
    ("missing", "no provenance manifest"),
    ("malformed", "Invalid Pool capture manifest"),
    ("not-object", "manifest is not an object"),
    ("unknown-origin", "use --refresh"),
    ("other-origin", "use --refresh"),
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
        cli.main(["dev", "capture", str(destination), "--api", API])

    assert error.value.code == 2
    assert message in capsys.readouterr().err
    fetch.assert_not_called()
    assert destination.read_bytes() == before
    assert (manifest_path.read_bytes() if manifest_path.exists() else None) == manifest_before
    assert cli.main(["dev", "capture", str(destination), "--api", API, "--refresh"]) == 0
    fetch.assert_called_once_with(API)


def test_failed_refresh_preserves_existing_capture(capture):
    destination, manifest_path, fetch = capture
    pool_capture.capture(destination)
    before = (destination.read_bytes(), manifest_path.read_bytes())
    # A response with a PID but no schema class cannot become a usable capture.
    fetch.return_value = ({PID: {"pid": PID}}, {})

    with pytest.raises(pool_capture.CaptureError, match="invalid class_name"):
        pool_capture.capture(destination, refresh=True)

    assert (destination.read_bytes(), manifest_path.read_bytes()) == before
    assert set(destination.parent.iterdir()) == {destination, manifest_path}


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
