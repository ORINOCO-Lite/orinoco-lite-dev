#!/usr/bin/env python3
"""Run unittest suites and optionally reject every skipped test."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import unittest
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]


def load_suite(
    *, discover: Path | None, names: Sequence[str]
) -> unittest.TestSuite:
    loader = unittest.defaultTestLoader
    if discover is not None:
        return loader.discover(str(discover))
    return loader.loadTestsFromNames(list(names))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--discover",
        type=Path,
        help="discover tests below this directory instead of loading module names",
    )
    parser.add_argument(
        "--fail-on-skip",
        action="store_true",
        help="return failure when any test reports a skip",
    )
    parser.add_argument("tests", nargs="*", help="test modules or dotted test names")
    args = parser.parse_args(argv)
    if (args.discover is None) == (not args.tests):
        parser.error("provide either --discover or one or more test names")

    sys.path.insert(0, str(ROOT))
    result = unittest.TextTestRunner(verbosity=2).run(
        load_suite(discover=args.discover, names=args.tests)
    )
    if args.fail_on_skip and result.skipped:
        print("Strict test run rejected skipped tests:", file=sys.stderr)
        for test, reason in result.skipped:
            print(f"- {test}: {reason}", file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
