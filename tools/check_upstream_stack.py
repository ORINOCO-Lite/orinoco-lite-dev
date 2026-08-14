#!/usr/bin/env python3
"""Check the isolated service-backed upstream deployment."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import uuid
from urllib.request import Request, urlopen

import check_local_stack as shared


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "upstream-stack"
SERVICE_URL = "http://127.0.0.1:8111"
EDITOR_URL = "http://127.0.0.1:3000/"
PROBE_CLASS = "XYZProject"
PROBE_PID_PREFIX = "xyzrins:projects/_upstream-write-probe-"


def read(url: str, token: str | None = None) -> bytes:
    headers = {"X-DumpThings-Token": token} if token else {}
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read()


def prove_write_isolation(editor_token: str, seed_token: str) -> None:
    probe_pid = f"{PROBE_PID_PREFIX}{uuid.uuid4().hex}"
    probe = {"pid": probe_pid, "schema_type": f"xyzri:{PROBE_CLASS}"}
    try:
        for collection in ("public", "protected"):
            url = f"{SERVICE_URL}/{collection}/record/{PROBE_CLASS}"
            shared.expect_rejected("POST", url, None, probe)
        shared.expect_rejected(
            "POST",
            f"{SERVICE_URL}/public/record/{PROBE_CLASS}",
            editor_token,
            probe,
        )
        shared.request_json(
            "POST",
            f"{SERVICE_URL}/protected/record/{PROBE_CLASS}",
            editor_token,
            probe,
        )
        incoming = shared.incoming_record("protected", seed_token, probe_pid)
        if not isinstance(incoming, dict) or incoming.get("pid") != probe_pid:
            raise RuntimeError(
                "Editor write did not land in protected/incoming/local-editor"
            )
        if shared.curated_record("protected", seed_token, probe_pid) is not None:
            raise RuntimeError("Editor write leaked into protected curated records")
    finally:
        shared.delete_incoming_record("protected", seed_token, probe_pid)


def main() -> int:
    seed_path = STACK / "seed-token"
    editor_path = STACK / "editor-token"
    snapshot = STACK / "pool" / "public-thing.jsonl"
    required = (seed_path, editor_path, snapshot, STACK / "ui")
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing upstream-stack inputs: {missing}")
    token = seed_path.read_text(encoding="utf-8").strip()
    editor_token = editor_path.read_text(encoding="utf-8").strip()
    server = json.loads(read(f"{SERVICE_URL}/server", token))
    names = {item["name"] for item in server["collections"]}
    if names != {"public", "protected"}:
        raise RuntimeError(f"Unexpected local collections: {sorted(names)}")

    expected = shared.manifest_records(snapshot)
    for collection in ("public", "protected"):
        actual = shared.curated_records(collection, token)
        if actual != expected:
            difference = shared.describe_difference(expected, actual)
            raise RuntimeError(
                f"Curated upstream records differ in {collection}: {difference}"
            )
    prove_write_isolation(editor_token, token)

    config = read(f"{EDITOR_URL}config.yaml").decode("utf-8")
    external = read(f"{EDITOR_URL}config_default_xyzri.yaml").decode("utf-8")
    for required_text in (
        "use_service: true",
        "use_token: true",
        f"{SERVICE_URL}/protected/",
        f"{SERVICE_URL}/public/",
        "http://127.0.0.1:8122/git-annex",
    ):
        if required_text not in config:
            raise RuntimeError(
                f"Upstream editor configuration is missing {required_text!r}"
            )
    for required_text in ("xyzrins:", "dlschemas_owl.ttl", "data_url: ''"):
        if required_text not in external:
            raise RuntimeError(
                f"Upstream editor schema config is missing {required_text!r}"
            )
    schema_data = read(f"{EDITOR_URL}dlschemas_data.ttl").decode("utf-8")
    schema_owl = read(f"{EDITOR_URL}dlschemas_owl.ttl").decode("utf-8")
    if " a xyzri:" in schema_data:
        raise RuntimeError("Editor schema data asset contains demo records")
    if "XYZDataset" not in schema_owl:
        raise RuntimeError("Editor OWL asset does not contain XYZDataset")
    read("http://127.0.0.1:8768/")
    print(
        "Service-backed upstream deployment healthy: "
        f"{len(expected)} records in each isolated collection"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Upstream stack check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
