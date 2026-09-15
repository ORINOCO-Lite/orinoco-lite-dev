"""Locked construction of the pinned semantic conversion pair."""

from __future__ import annotations

from pathlib import Path
import sys
from threading import RLock
from typing import Any


# Dump Things 6.3.6 retries in increments of 1,000 and therefore succeeds at
# 2,000 for the pinned schema. Keep the same reviewed ceiling locally, but do
# not let that dependency's fallback leak a process-wide setting to callers.
PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT = 2000
_MODEL_BUILD_LOCK = RLock()


def build_format_converters(schema: Path) -> tuple[Any, Any]:
    """Build JSON/RDF converters without changing the caller's recursion limit."""

    from dump_things_service import Format
    from dump_things_service.converter import FormatConverter

    # LinkML expands the inlined, type-designated recursive Thing range to a
    # wide union of every descendant. Pydantic rebuilds that union deeply even
    # though the LinkML inheritance graph is acyclic, so isolate the temporary
    # process-global limit behind a lock until LinkML emits a named type alias.
    with _MODEL_BUILD_LOCK:
        previous_limit = sys.getrecursionlimit()
        try:
            if previous_limit < PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT:
                sys.setrecursionlimit(PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT)
            return (
                FormatConverter(str(schema), Format.json, Format.ttl),
                FormatConverter(str(schema), Format.ttl, Format.json),
            )
        finally:
            if sys.getrecursionlimit() != previous_limit:
                sys.setrecursionlimit(previous_limit)
