"""Semantic release driver entry point for a flattened consumer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .assets import load_assets
from .config import load_config_path
from .errors import OrinocoError
from .projection import verify_projection
from .validation import validate_workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        workspace = load_config_path(args.config)
        report = validate_workspace(workspace)
        assets, links = load_assets(workspace)
        report["assets"] = len(assets)
        report["asset_links"] = len(links)
        report["projection"] = verify_projection(workspace, args.runtime.resolve())
    except OrinocoError as error:
        print(f"orinoco validate: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
