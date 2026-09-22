from __future__ import annotations

import argparse
from datetime import datetime
import json
from unittest.mock import Mock

import pytest

from orinoco_lite import pool_capture, upstream_snapshot


API = "https://pool.example.test/api"
PID = "example:record"


def main(arguments):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="records_command", required=True)
    pool_capture.register_capture(commands)
    args = parser.parse_args(arguments)
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
    destination = tmp_path / "downloaded/records.jsonl"
    manifest = tmp_path / "downloaded/records.jsonl.manifest.json"
    return destination, manifest, fetch


def test_cli_captures_exact_records_then_reuses_without_fetching(capture, monkeypatch):
    destination, manifest_path, fetch = capture
    monkeypatch.setenv("UPSTREAM_POOL_API", "https://ignored.example.test/api")
    monkeypatch.setenv("REFRESH_UPSTREAM_POOL", "1")
    expected = record()
    expected["extra"] = {"ordered": [2, 1, 2], "text": "ü", "optional": None}
    fetch.return_value = ({PID: expected}, {"version": "fixture"})

    assert main(["get", "--directory", str(destination.parent.parent)]) == 0
    fetch.assert_called_once_with(pool_capture.DEFAULT_API)
    assert json.loads(destination.read_text()) == expected
    assert upstream_snapshot.load_jsonl(destination)[0].record == expected
    manifest = json.loads(manifest_path.read_text())
    assert datetime.fromisoformat(manifest["captured_at"]).utcoffset().total_seconds() == 0
    assert datetime.fromisoformat(manifest["capture_started_at"]) <= datetime.fromisoformat(manifest["captured_at"])
    assert manifest["completeness"]["atomic_snapshot"] is False
    assert "concurrent edits" in manifest["completeness"]["limitations"]
    before = (destination.read_bytes(), manifest_path.read_bytes())

    assert main(["get", "--directory", str(destination.parent.parent)]) == 0
    assert fetch.call_count == 1
    assert (destination.read_bytes(), manifest_path.read_bytes()) == before
    assert set(destination.parent.iterdir()) == {destination, manifest_path}


def test_default_path_downloads_reuses_and_force_replaces(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetch = Mock(return_value=({PID: record()}, {}))
    monkeypatch.setattr(pool_capture, "fetch_live", fetch)

    assert main(["get"]) == 0
    destination = tmp_path / "upstream-diffing/downloaded/records.jsonl"
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
    assert main(["get", "--directory", str(destination.parent.parent), "--api", API + "/"]) == 0
    fetch.assert_called_once_with(API)
    fetch.return_value = ({PID: record(name="Changed")}, {"version": "new"})
    other_api = "https://other.example.test/api"

    assert main(["get", "--directory", str(destination.parent.parent), "--force", "--api", other_api]) == 0

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
def test_invalid_capture_is_not_fetched_or_rewritten(capture, damage, message, capsys):
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
        main(["get", "--directory", str(destination.parent.parent), "--api", API])

    assert error.value.code == 2
    assert message in capsys.readouterr().err
    fetch.assert_not_called()
    assert destination.read_bytes() == before
    assert (manifest_path.read_bytes() if manifest_path.exists() else None) == manifest_before
    assert main(["get", "--directory", str(destination.parent.parent), "--api", API, "--force"]) == 0
    fetch.assert_called_once_with(API)


def test_failed_force_preserves_existing_capture(capture):
    destination, manifest_path, fetch = capture
    pool_capture.capture(destination)
    before = (destination.read_bytes(), manifest_path.read_bytes())
    # A response with a PID but no schema class cannot become a usable capture.
    fetch.return_value = ({PID: {"pid": PID}}, {})

    with pytest.raises(pool_capture.CaptureError, match="schema_type"):
        pool_capture.capture(destination, force=True)

    assert (destination.read_bytes(), manifest_path.read_bytes()) == before
    assert set(destination.parent.iterdir()) == {destination, manifest_path}


def test_failed_manifest_replacement_leaves_capture_fail_closed(capture, monkeypatch):
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


def test_upstream_reader_preserves_records_and_order(monkeypatch):
    from dump_things_pyclient import communicate
    from contextlib import nullcontext

    session = object()
    monkeypatch.setattr(communicate, "get_session", lambda: nullcontext(session))
    monkeypatch.setattr(communicate, "server", lambda api, **kwargs: {"version": "fixture"})
    rows = [record("example:z"), record("example:a")]
    reader = Mock(return_value=iter((row, index + 1, 2, 1, 2) for index, row in enumerate(rows)))
    monkeypatch.setattr(communicate, "collection_read_records_of_class", reader)

    captured, server = pool_capture.fetch_live(API)

    assert list(captured.values()) == rows
    assert server == {"version": "fixture"}
    reader.assert_called_once_with(service_url=API, collection="public", class_name="Thing", session=session)


@pytest.mark.parametrize("rows,message", [
    ([(record(), 1, 1, 2, 2), (record(), 1, 1, 2, 2)], "duplicate PID"),
    ([(record(), 1, 1, 2, 2)], "incomplete"),
    ([], "empty"),
    ([(record(), 1, 2, 1, 2), (record("example:other"), 2, 3, 1, 3)], "totals changed"),
])
def test_upstream_stream_must_be_complete_and_unique(monkeypatch, rows, message):
    monkeypatch.setattr(pool_capture.communicate, "server", lambda *args, **kwargs: {})
    monkeypatch.setattr(pool_capture.communicate, "collection_read_records_of_class", lambda **kwargs: iter(rows))
    with pytest.raises(pool_capture.CaptureError, match=message):
        pool_capture.fetch_live(API)


def test_upstream_failure_preserves_existing_capture(tmp_path, monkeypatch):
    from requests import HTTPError

    destination = tmp_path / "records.jsonl"
    reader = Mock(return_value=iter([(record(), 1, 1, 100, 1)]))
    monkeypatch.setattr(pool_capture.communicate, "server", lambda *args, **kwargs: {})
    monkeypatch.setattr(pool_capture.communicate, "collection_read_records_of_class", reader)
    pool_capture.capture(destination, api=API)
    manifest = destination.with_name("records.jsonl.manifest.json")
    before = (destination.read_bytes(), manifest.read_bytes())
    reader.side_effect = HTTPError("service unavailable")
    with pytest.raises(pool_capture.CaptureError, match="retrieval failed"):
        pool_capture.capture(destination, api=API, force=True)
    assert (destination.read_bytes(), manifest.read_bytes()) == before


def test_capture_orders_and_serializes_upstream_cli_jsonl(tmp_path):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from click.testing import CliRunner
    from dump_things_pyclient.commands.dtc_plugins.get_records import cli

    rows = [record("example:z"), record("example:a", name="ü")]

    class Service(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = ({"version": "fixture"} if self.path == "/server" else
                       {"items": rows, "page": 1, "pages": 1, "size": 100, "total": 2})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Service) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            api = f"http://127.0.0.1:{server.server_port}"
            upstream = CliRunner().invoke(cli, [api, "public", "--class", "Thing", "--page-size", "100"])
            assert upstream.exit_code == 0, upstream.output
            destination = tmp_path / "records.jsonl"
            pool_capture.capture(destination, api=api)
            # Independently reproduce the documented final acquisition step
            # with the standard library, not the project comparison serializer.
            downloaded = [json.loads(line) for line in upstream.stdout.splitlines()]
            downloaded.sort(key=lambda row: (row["schema_type"].split(":")[-1], row["pid"]))
            expected = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                         separators=(",", ":")) + "\n" for row in downloaded)
            assert destination.read_text() == expected
            assert [item.record for item in upstream_snapshot.load_jsonl(destination)] == list(reversed(rows))
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("api", ["file:///tmp/source", "https://user:secret@example.test/api", "https://example.test/api?token=secret"])
def test_capture_does_not_store_credentials_or_accept_non_service_urls(tmp_path, monkeypatch, api):
    monkeypatch.setattr(pool_capture, "fetch_live", lambda *args: pytest.fail("must not fetch invalid source"))
    with pytest.raises(pool_capture.CaptureError, match="HTTP|credentials"):
        pool_capture.capture(tmp_path / "capture.jsonl", api=api)
    assert not list(tmp_path.iterdir())


def test_public_upstream_cli_accepts_explicit_output(tmp_path, monkeypatch):
    from orinoco_lite import cli
    monkeypatch.chdir(tmp_path)
    fetch = Mock(return_value=({PID: record()}, {}))
    monkeypatch.setattr(pool_capture, "fetch_live", fetch)
    assert cli.main(["dev", "records", "get", "--output", "custom/pool.jsonl"]) == 0
    assert upstream_snapshot.load_jsonl(tmp_path / "custom/pool.jsonl")[0].record == record()
    assert (tmp_path / "custom/pool.jsonl.manifest.json").is_file()
    assert not (tmp_path / "upstream-diffing").exists()
