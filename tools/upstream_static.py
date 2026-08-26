#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
# platforms = [
#   { platform = "osx-arm64", macos = "14.0" },
#   "linux-64",
# ]
#
# [tool.pixi.dependencies]
# python = ">=3.12,<3.13"
# hugo = "==0.161.1"
#
# [tool.pixi.target.linux-64.dependencies]
# git-annex = "==10.20260601"
#
# [tool.pixi.target.osx-arm64-macos-14-0.pypi-dependencies]
# git-annex = "==10.20260601"
# ///
"""Build or serve the pinned upstream Psychoinformatics static site.

Run this file through Pixi 0.76 or newer.  Its inline environment is isolated
from the engineering workspace, while the builder checks out the exact site
and theme gitlinks recorded by the current parent commit.
"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
from typing import Sequence

from upstream_checkout import (
    CheckoutMode,
    UpstreamCheckoutError,
    prepare_static_checkout,
)


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "build" / "upstream-local"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8768


class UpstreamStaticError(RuntimeError):
    """Report a checkout, build, or execution-boundary failure."""


def run(arguments: Sequence[str | Path], *, environment: dict[str, str]) -> None:
    result = subprocess.run(
        [str(argument) for argument in arguments],
        cwd=ROOT,
        env=environment,
    )
    if result.returncode:
        raise UpstreamStaticError(
            f"{' '.join(str(argument) for argument in arguments)} "
            f"failed with status {result.returncode}"
        )


def require_script_environment() -> None:
    """Reject direct Python execution that bypasses the locked Pixi script."""
    manifest = os.environ.get("PIXI_PROJECT_MANIFEST", "")
    if not manifest or Path(manifest).resolve() != Path(__file__).resolve():
        raise UpstreamStaticError(
            "Run with 'pixi run --frozen --script tools/upstream_static.py'"
        )
    for command in ("hugo", "git-annex"):
        result = subprocess.run(
            [command, "version"],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise UpstreamStaticError(
                f"The standalone Pixi environment does not provide {command}"
            )


def build(*, host: str, port: int, checkout: CheckoutMode) -> None:
    prepare_static_checkout(checkout)
    environment = os.environ.copy()
    environment.update(
        {
            "BASE_URL": f"http://{host}:{port}/",
            "DESTINATION": str(DESTINATION),
            "SHACL_VUE_URL": "https://pool.psychoinformatics.de/ui/",
        }
    )
    run([ROOT / "tools" / "build_upstream_site.sh"], environment=environment)


def serve(*, host: str, port: int, checkout: CheckoutMode) -> None:
    build(host=host, port=port, checkout=checkout)
    handler = partial(SimpleHTTPRequestHandler, directory=str(DESTINATION))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving the pinned upstream site at http://{host}:{port}/")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "serve"))
    parser.add_argument(
        "--checkout",
        choices=("recorded", "worktree"),
        default="recorded",
        help="restore recorded gitlinks or preserve current initialized worktrees",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    args = parser.parse_args(argv)
    try:
        require_script_environment()
        if args.command == "build":
            build(host=args.host, port=args.port, checkout=args.checkout)
        else:
            serve(host=args.host, port=args.port, checkout=args.checkout)
    except (UpstreamCheckoutError, UpstreamStaticError) as error:
        parser.exit(1, f"upstream-static: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
