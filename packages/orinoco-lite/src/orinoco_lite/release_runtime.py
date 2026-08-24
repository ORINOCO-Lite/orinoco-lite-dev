"""Assemble one deterministic Orinoco Lite runtime release archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .errors import OrinocoError
from .runtime import assemble_runtime


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args(argv)
    try:
        report = assemble_runtime(
            args.spec,
            args.output,
            force=args.force,
            source_commit=args.source_commit,
        )
    except OrinocoError as error:
        parser.exit(1, f"orinoco runtime release: {error}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
