"""Validate a consumer's semantic inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import load_config_path
from .errors import OrinocoError
from .validation import validate_workspace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        workspace = load_config_path(args.config)
        report = validate_workspace(workspace)
    except OrinocoError as error:
        print(f"orinoco-lite validate: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
