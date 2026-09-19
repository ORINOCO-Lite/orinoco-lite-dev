from copy import deepcopy
import json
from pathlib import Path
import socket
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

from orinoco_lite import upstream_snapshot
from orinoco_lite.upstream_service import (
    local_service,
    put_record,
    seed_manifest,
    verify_service_snapshot,
)


@pytest.fixture
def schema():
    selected = (
        Path(__file__).resolve().parents[2]
        / "submodules/things-schemas/src/demo-research-information/unreleased.yaml"
    )
    if not selected.is_file():
        pytest.fail("Initialize the selected Things Schema before the service integration test")
    return selected


def available_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def captured_records():
    return [
        {
            "class_name": "XYZPublication",
            "record": {
                "pid": "https://example.org/publication",
                "schema_type": "xyzri:XYZPublication",
                "title": "Mémoire — 日本語",
                "about": [
                    "https://example.org/b", "https://example.org/a",
                    "https://example.org/b",
                ],
                "generated_by": [
                    {
                        "object": "https://example.org/project",
                        "at_time": "2024-05-01",
                        "schema_type": "dlthings:Generation",
                    },
                    {
                        "object": "https://example.org/project",
                        "at_time": "2023-01",
                        "schema_type": "dlthings:Generation",
                    },
                ],
            },
        },
        {
            "class_name": "XYZProject",
            "record": {
                "pid": "https://example.org/project",
                "schema_type": "xyzri:XYZProject",
                "title": "München",
                "started": {"at_time": "2023-01", "schema_type": "dlthings:Start"},
            },
        },
    ]


def assert_stopped(url):
    with pytest.raises((URLError, TimeoutError, ConnectionError)):
        urlopen(f"{url}/server", timeout=1)


def test_real_service_preserves_records_and_stops_after_success(tmp_path, schema):
    capture = tmp_path / "source.jsonl"
    records = captured_records()
    capture.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    with local_service(tmp_path / "service", schema, port=available_port()) as service:
        with pytest.raises(HTTPError) as rejection:
            urlopen(f"{service.url}/public/curated/records/p/", timeout=1)
        assert rejection.value.code in {401, 403}
        counts = seed_manifest(
            capture, ("public",), service.token, "fixture", service_url=service.url,
        )
        assert counts["created"] == 2
        assert verify_service_snapshot(
            capture, "public", service.token, service_url=service.url,
        ) == 2
        # Check the stored representation too, including its class mapping.
        upstream_snapshot.verify(
            capture, service.store / "public/curated", upstream_store=True,
        )

        changed = deepcopy(records[0]["record"])
        changed["title"] = "Changed title"
        put_record(
            "public", "XYZPublication", changed, service.token,
            service_url=service.url,
        )
        with pytest.raises(upstream_snapshot.SnapshotError, match="JSON record differs"):
            verify_service_snapshot(
                capture, "public", service.token, service_url=service.url,
            )
    assert_stopped(service.url)


def test_real_service_stops_when_comparison_fails(tmp_path, schema):
    capture = tmp_path / "source.jsonl"
    capture.write_text(json.dumps(captured_records()[0]) + "\n", encoding="utf-8")
    with pytest.raises(upstream_snapshot.SnapshotError, match="snapshot PID mismatch"):
        with local_service(tmp_path / "service", schema, port=available_port()) as service:
            verify_service_snapshot(
                capture, "public", service.token, service_url=service.url,
            )
    assert_stopped(service.url)
