"""Prepare bundled Orinoco Lite resources for an editable checkout."""

from pathlib import Path

from .build_resources import build_resources
from .errors import ConfigurationError


def main() -> None:
    package = Path(__file__).resolve().parents[2]
    if not (package / "release/package-resources.yaml").is_file():
        raise ConfigurationError("Resource preparation requires an editable checkout. Run orinoco-lite dev enable first.")
    build_resources(package, Path(__file__).parent / "_resources")


if __name__ == "__main__":
    main()
