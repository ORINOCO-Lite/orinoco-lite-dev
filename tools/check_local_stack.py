#!/usr/bin/env python3
"""Check the local Dump Things and git-annex service contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "local-stack"


def get(url: str, token: str) -> bytes:
    request = Request(url, headers={"X-DumpThings-Token": token})
    with urlopen(request, timeout=30) as response:
        return response.read()


def main() -> int:
    token_path = STACK / "editor-token"
    if not token_path.exists():
        raise RuntimeError("Run `pixi run prepare-local-stack` first")
    token = token_path.read_text(encoding="utf-8").strip()
    server = json.loads(get("http://127.0.0.1:8111/server", token))
    names = {item["name"] for item in server["collections"]}
    if names != {"public", "protected"}:
        raise RuntimeError(f"Unexpected local collections: {sorted(names)}")
    public = json.loads(get("http://127.0.0.1:8111/public/records/XYZDataset?format=json", token))
    protected = json.loads(get("http://127.0.0.1:8111/protected/records/XYZDataset?format=json", token))
    if not public or len(public) != len(protected):
        raise RuntimeError("The local public/protected record views do not match")
    with urlopen("http://127.0.0.1:3000/config.yaml", timeout=30) as response:
        config = response.read().decode("utf-8")
    with urlopen("http://127.0.0.1:3000/config_default_xyzri.yaml", timeout=30) as response:
        external_config = response.read().decode("utf-8")
    for required in ("use_service: true", "http://127.0.0.1:8111/protected/", "http://127.0.0.1:8122/git-annex"):
        if required not in config:
            raise RuntimeError(f"Local pool UI configuration is missing {required!r}")
    for required in ("xyzrins:", "dlschemas_owl.ttl", "data_url: ''"):
        if required not in external_config:
            raise RuntimeError(f"Local pool UI external configuration is missing {required!r}")
    print(f"Local stack healthy: {len(public)} datasets visible through Dump Things")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Local stack check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
