"""Refresh or verify the deterministic consumer-owned projection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import load_config_path
from .errors import OrinocoError
from .projection import update_projection, verify_projection


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("action", choices=("update", "verify"))
    args = parser.parse_args(argv)
    try:
        workspace = load_config_path(args.config)
        if args.action == "update":
            report = update_projection(workspace, args.resources.resolve())
        else:
            report = verify_projection(workspace, args.resources.resolve())
    except OrinocoError as error:
        parser.exit(1, f"orinoco projection: {error}\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
