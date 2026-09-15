"""Build the generic downstream source-review shell and license inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any, Sequence

from .errors import DriverError
from .release_editor import _dependency_inventory, _run


def build_review_shell(
    application: Path,
    shell: Path,
    licenses: Path,
) -> dict[str, Any]:
    """Build one deterministic, unconfigured static review application."""

    if (
        application.is_symlink()
        or not (application / "package.json").is_file()
        or not (application / "package-lock.json").is_file()
        or not (application / "review/index.html").is_file()
    ):
        raise DriverError("Curation review application source is incomplete")
    _run(["npm", "ci", "--ignore-scripts"], application)
    _run(["npm", "run", "build:review"], application)
    built = application / "dist-review"
    if not (built / "index.html").is_file() or (built / "config.json").exists():
        raise DriverError("Static review build is missing or contains site configuration")
    if shell.exists():
        shutil.rmtree(shell)
    shutil.copytree(built, shell)
    if licenses.exists():
        shutil.rmtree(licenses)
    licenses.mkdir(parents=True)
    inventory = _dependency_inventory(
        application / "node_modules",
        licenses,
        component="review",
    )
    return {"dependencies": len(inventory["packages"]), "shell": str(shell)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application", type=Path, required=True)
    parser.add_argument("--shell", type=Path, required=True)
    parser.add_argument("--licenses", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_review_shell(
            args.application.resolve(),
            args.shell.resolve(),
            args.licenses.resolve(),
        )
    except DriverError as error:
        parser.exit(1, f"orinoco review release: {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
