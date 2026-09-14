"""Prepare bundled Orinoco Lite resources for an editable checkout."""

from pathlib import Path

from .build_resources import build_resources


def main() -> None:
    package = Path(__file__).resolve().parents[2].parent.parent
    build_resources(package, Path(__file__).parent / "_resources")


if __name__ == "__main__":
    main()
