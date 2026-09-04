"""Public package metadata for Orinoco Lite."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib

try:
    __version__ = version("orinoco-lite")
except PackageNotFoundError:  # Release preparation before package installation.
    manifest = Path(__file__).resolve().parents[2] / "pyproject.toml"
    __version__ = tomllib.loads(manifest.read_text(encoding="utf-8"))["project"]["version"]

__all__ = ["__version__"]
