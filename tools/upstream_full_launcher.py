#!/usr/bin/env python3
"""Prepare full upstream gitlinks before running the engineering environment."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Sequence

from upstream_checkout import UpstreamCheckoutError, prepare_full_checkout


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "upstream_full.py"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "check", "test"))
    parser.add_argument("mode", choices=("recorded", "worktree"))
    args = parser.parse_args(argv)
    try:
        prepare_full_checkout(args.mode)
    except UpstreamCheckoutError as error:
        parser.exit(1, f"upstream-full: {error}\n")
    return subprocess.run(
        [sys.executable, str(SCRIPT), args.command, "--checkout", args.mode],
        cwd=ROOT,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
