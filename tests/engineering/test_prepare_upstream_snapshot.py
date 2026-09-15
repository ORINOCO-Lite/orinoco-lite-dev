from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from orinoco_lite import upstream_snapshot
from tools import prepare_upstream_snapshot as preparation


API = "https://pool.example.test/api"
PID = "example:record"


@pytest.fixture
def capture(tmp_path, monkeypatch):
    for name, relative in {
        "ROOT": ".",
        "POOL": "pool",
        "RAW_JSONL": "pool/public-thing.jsonl",
        "POOL_MANIFEST": "pool/manifest.json",
        "RECORDS": "snapshot/metadata/records",
        "CANONICAL_JSONL": "snapshot/records.jsonl",
        "SNAPSHOT_MANIFEST": "snapshot/manifest.json",
        "ORINOCO_STORAGE": "snapshot/orinoco-storage",
    }.items():
        monkeypatch.setattr(preparation, name, tmp_path / relative)
    fetch = Mock(return_value=(
        {PID: {"pid": PID, "schema_type": "dlthings:Thing", "name": "Initial"}},
        {"version": "fixture"},
    ))
    monkeypatch.setattr(preparation.source.upstream_pool_diff, "fetch_live", fetch)
    return fetch


def test_cli_reuses_cache_and_regenerates_outputs_without_environment_controls(
    capture, monkeypatch
):
    monkeypatch.setenv("UPSTREAM_POOL_API", "https://ignored.example.test/api")
    monkeypatch.setenv("REFRESH_UPSTREAM_POOL", "1")
    assert preparation.main([]) == 0
    capture.assert_called_once_with(preparation.source.DEFAULT_API)
    generated = next(preparation.RECORDS.rglob("*.yaml"))
    generated.unlink()

    assert preparation.main([]) == 0

    assert capture.call_count == 1
    assert generated.is_file()
    assert upstream_snapshot.load_records_tree(preparation.RECORDS)[0].record[
        "name"
    ] == "Initial"


def test_cli_refresh_replaces_the_capture_and_derived_values(capture):
    assert preparation.main(["--api", API + "/"]) == 0
    capture.assert_called_once_with(API)
    capture.return_value = (
        {PID: {"pid": PID, "schema_type": "dlthings:Thing", "name": "Changed"}},
        {"version": "new"},
    )
    other_api = "https://other.example.test/api"

    assert preparation.main(["--refresh", "--api", other_api]) == 0

    capture.assert_called_with(other_api)
    assert capture.call_count == 2
    assert upstream_snapshot.load_records_tree(preparation.RECORDS)[0].record[
        "name"
    ] == "Changed"
    manifest = json.loads(preparation.POOL_MANIFEST.read_text())
    assert manifest["source_api"] == other_api
    assert manifest["source_server"] == {"version": "new"}


def test_missing_manifest_requires_explicit_refresh_without_replacing_capture(capture):
    assert preparation.main([]) == 0
    raw_before = preparation.RAW_JSONL.read_bytes()
    preparation.POOL_MANIFEST.unlink()
    capture.reset_mock()

    with pytest.raises(RuntimeError, match="no provenance manifest.*--refresh"):
        preparation.main([])

    capture.assert_not_called()
    assert preparation.RAW_JSONL.read_bytes() == raw_before
    assert not preparation.POOL_MANIFEST.exists()

    assert preparation.main(["--refresh"]) == 0
    capture.assert_called_once_with(preparation.source.DEFAULT_API)
    assert preparation.POOL_MANIFEST.is_file()


@pytest.mark.parametrize("cached_api", [API, None])
def test_other_or_unknown_origin_is_rejected_without_relabeling(capture, cached_api):
    assert preparation.main(["--api", API]) == 0
    manifest = json.loads(preparation.POOL_MANIFEST.read_text())
    manifest["source_api"] = cached_api
    preparation.POOL_MANIFEST.write_text(json.dumps(manifest))
    before = preparation.POOL_MANIFEST.read_bytes()
    raw_before = preparation.RAW_JSONL.read_bytes()
    capture.reset_mock()

    with pytest.raises(RuntimeError, match="use --refresh"):
        preparation.main(["--api", "https://other.example.test/api"])

    capture.assert_not_called()
    assert preparation.POOL_MANIFEST.read_bytes() == before
    assert preparation.RAW_JSONL.read_bytes() == raw_before
