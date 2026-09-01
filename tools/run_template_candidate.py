#!/usr/bin/env python3
"""Run Milestone 8 against a fresh template with compact mock site inputs."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/template-candidate"


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"quick", "full"}:
        print("usage: run_template_candidate.py {quick|full}", file=sys.stderr)
        return 2
    template = Path(
        os.environ.get(
            "ORINOCO_TEMPLATE_CANDIDATE",
            ROOT.parent / "orinoco-lite-template",
        )
    ).resolve()
    command = (
        sys.executable,
        ROOT / "tools/downstream_development.py",
        "--downstream",
        FIXTURE,
        "--engine",
        ROOT,
        "--template",
        template,
        "--repository",
        "ORINOCO-Lite/template-architecture-proof",
        "--mode",
        sys.argv[1],
    )
    return subprocess.run([str(item) for item in command], cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
