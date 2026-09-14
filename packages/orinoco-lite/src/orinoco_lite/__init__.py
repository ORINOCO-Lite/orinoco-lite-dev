"""Public package metadata for Orinoco Lite."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib
import subprocess

try:
    __version__ = version("orinoco-lite")
except PackageNotFoundError:  # Release preparation before package installation.
    manifest = Path(__file__).resolve().parents[2] / "pyproject.toml"
    __version__ = tomllib.loads(manifest.read_text(encoding="utf-8"))["project"]["version"]


def source_description() -> str:
    """Describe the source checkout when running from one."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "release/package-resources.yaml").is_file() and (parent / ".git").exists():
            try:
                commit = subprocess.check_output(
                    ["git", "-C", str(parent), "rev-parse", "--short", "HEAD"],
                    text=True, stderr=subprocess.DEVNULL,
                ).strip()
            except (OSError, subprocess.CalledProcessError):
                commit = "unknown commit"
            return f"development checkout @ {commit}"
    return "installed package"

__all__ = ["__version__"]
