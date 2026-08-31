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
# nodejs = ">=22,<23"
# make = "==4.4.1"
#
# [tool.pixi.target.linux-64.dependencies]
# git-annex = "==10.20260601"
#
# [tool.pixi.target.osx-arm64-macos-14-0.pypi-dependencies]
# git-annex = "==10.20260601"
#
# [tool.pixi.pypi-dependencies]
# dump-things-service = { path = "../submodules/dump-things-service", editable = true }
# ///
"""Build and serve the pinned or current service-backed upstream stack."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
from typing import Sequence
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "build" / "upstream-stack"
LOGS = STACK / "logs"
POOL_UI = ROOT / "submodules" / "pool.psychoinformatics.de-ui"


class UpstreamFullError(RuntimeError):
    """Report a full-stack preparation or process failure."""


def require_script_environment() -> None:
    manifest = os.environ.get("PIXI_PROJECT_MANIFEST", "")
    if not manifest or Path(manifest).resolve() != Path(__file__).resolve():
        raise UpstreamFullError("Run through the serve-upstream Pixi task")
    for command in ("hugo", "git-annex", "node", "npm", "dump-things-service"):
        if shutil.which(command) is None:
            raise UpstreamFullError(f"Inline environment lacks {command}")


def run(arguments: Sequence[str | Path], *, environment: dict[str, str]) -> None:
    result = subprocess.run(
        [str(argument) for argument in arguments],
        cwd=ROOT,
        env=environment,
    )
    if result.returncode:
        raise UpstreamFullError(
            f"{' '.join(str(argument) for argument in arguments)} failed "
            f"with status {result.returncode}"
        )


def wait_for_url(name: str, url: str, processes: list[subprocess.Popen[bytes]]) -> None:
    for _ in range(120):
        failed = [process for process in processes if process.poll() is not None]
        if failed:
            raise UpstreamFullError(f"A child process exited while waiting for {name}")
        try:
            with urlopen(url, timeout=2):
                print(f"{name} is ready: {url}")
                return
        except Exception:
            time.sleep(1)
    raise UpstreamFullError(f"{name} did not become ready: {url}")


def start(
    name: str,
    arguments: Sequence[str | Path],
    *,
    environment: dict[str, str],
) -> subprocess.Popen[bytes]:
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / f"{name}.log"
    print(f"Starting {name} (log: {log_path})")
    stream = log_path.open("wb")
    try:
        process = subprocess.Popen(
            [str(argument) for argument in arguments],
            cwd=ROOT,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    finally:
        stream.close()
    return process


def prepare(environment: dict[str, str], checkout: str) -> None:
    run(["npm", "--prefix", POOL_UI / "shacl-vue", "ci"], environment=environment)
    run(["make", "-C", POOL_UI, "build-ui"], environment=environment)
    static_environment = environment.copy()
    static_environment.update(
        {
            "BASE_URL": "http://127.0.0.1:8768/",
            "DESTINATION": str(ROOT / "build" / "upstream-local"),
            "SHACL_VUE_URL": "http://127.0.0.1:3000/",
        }
    )
    run([ROOT / "tools" / "build_upstream_site.sh"], environment=static_environment)
    run([sys.executable, ROOT / "tools" / "prepare_upstream_stack.py"], environment=environment)
    provenance = {
        "checkout_mode": checkout,
        "parent": subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
    }
    (STACK / "checkout.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def serve(environment: dict[str, str], *, persistent: bool) -> None:
    processes: list[subprocess.Popen[bytes]] = []
    try:
        processes.append(
            start(
                "dump-things",
                [ROOT / "tools" / "serve_upstream_dumpthings.sh"],
                environment=environment,
            )
        )
        wait_for_url(
            "Dump Things",
            "http://127.0.0.1:8111/server",
            processes,
        )
        run(
            [sys.executable, ROOT / "tools" / "seed_upstream_pool.py"],
            environment=environment,
        )
        processes.append(
            start(
                "git-annex",
                [sys.executable, ROOT / "tools" / "serve_upstream_gitannex.py"],
                environment=environment,
            )
        )
        processes.append(
            start(
                "shacl-vue",
                [
                    sys.executable,
                    "-m",
                    "http.server",
                    "3000",
                    "--directory",
                    STACK / "ui",
                ],
                environment=environment,
            )
        )
        processes.append(
            start(
                "upstream-site",
                [
                    sys.executable,
                    "-m",
                    "http.server",
                    "8768",
                    "--directory",
                    ROOT / "build" / "upstream-local",
                ],
                environment=environment,
            )
        )
        wait_for_url("SHACL Vue", "http://127.0.0.1:3000/config.yaml", processes)
        wait_for_url("Upstream site", "http://127.0.0.1:8768/", processes)
        run(
            [sys.executable, ROOT / "tools" / "check_upstream_stack.py"],
            environment=environment,
        )
        if not persistent:
            return
        print("Service-backed upstream deployment: http://127.0.0.1:8768/")
        print("Press Ctrl-C to stop all services.")
        while all(process.poll() is None for process in processes):
            time.sleep(1)
        raise UpstreamFullError("A child process exited unexpectedly")
    finally:
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "check", "test"))
    parser.add_argument("--checkout", choices=("recorded", "worktree"), required=True)
    args = parser.parse_args(argv)
    try:
        require_script_environment()
        environment = os.environ.copy()
        if args.command == "test":
            run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "tests.test_upstream_stack_contract",
                    "-v",
                ],
                environment=environment,
            )
            return 0
        prepare(environment, args.checkout)
        serve(environment, persistent=args.command == "serve")
    except KeyboardInterrupt:
        return 130
    except UpstreamFullError as error:
        parser.exit(1, f"upstream-full: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
