"""Prepare or verify the manifest-driven downstream asset cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Sequence

from .assets import hydrate_asset_cache, load_assets, verify_asset
from .config import load_config_path
from .errors import OrinocoError


def manage_assets(config: Path, action: str) -> dict[str, int]:
    workspace = load_config_path(config)
    assets, _ = load_assets(workspace)
    cache = workspace.path("build") / "asset-cache"
    hydrated = 0
    verified = 0
    for source, asset in sorted(assets.items()):
        if asset.availability != "available":
            continue
        source_path = workspace.root.joinpath(*PurePosixPath(source).parts)
        if source_path.is_file():
            verify_asset(source_path, asset)
        else:
            source_path = cache / asset.sha256
            if action == "hydrate" and not source_path.is_file():
                hydrate_asset_cache(source_path, asset)
                hydrated += 1
            verify_asset(source_path, asset)
        verified += 1
    return {"hydrated": hydrated, "verified": verified}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("action", choices=("hydrate", "verify"))
    args = parser.parse_args(argv)
    try:
        report = manage_assets(args.config, args.action)
    except OrinocoError as error:
        parser.exit(1, f"orinoco assets: {error}\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
