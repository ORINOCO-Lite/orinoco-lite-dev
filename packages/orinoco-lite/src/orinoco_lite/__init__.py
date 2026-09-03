"""Public package metadata for Orinoco Lite."""

from __future__ import annotations

try:
    from importlib.metadata import version

    __version__ = version("orinoco-lite")
except Exception:  # pragma: no cover - source-tree fallback
    __version__ = "0.3.0rc1"

__all__ = ["__version__"]
