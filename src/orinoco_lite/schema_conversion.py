"""Locked construction of the pinned semantic conversion pair."""

from __future__ import annotations

from contextlib import contextmanager
import logging
from pathlib import Path
import sys
from threading import RLock
from typing import Any


# Dump Things 6.3.6 retries in increments of 1,000 and therefore succeeds at
# 2,000 for the pinned schema. Keep the same reviewed ceiling locally, but do
# not let that dependency's fallback leak a process-wide setting to callers.
PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT = 2000
_MODEL_BUILD_LOCK = RLock()


def build_format_converters(schema: Path, *, writer_only: bool = False) -> tuple[Any, ...]:
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
            writer = FormatConverter(str(schema), Format.json, Format.ttl)
            if writer_only:
                return (writer,)
            return (
                writer,
                FormatConverter(str(schema), Format.ttl, Format.json),
            )
        finally:
            if sys.getrecursionlimit() != previous_limit:
                sys.setrecursionlimit(previous_limit)


@contextmanager
def concise_date_warning():
    """Summarize the known placeholder-date diagnostic during validation."""
    class DateWarningFilter(logging.Filter):
        reported = False

        def filter(self, record: logging.LogRecord) -> bool:
            error = record.exc_info[1] if record.exc_info else None
            if (
                record.getMessage().startswith(
                    "Failed to convert Literal lexical form to value. Datatype="
                    "https://concepts.datalad.org/s/things/v2/w3ctr-datetime,"
                )
                and isinstance(error, ValueError)
                and str(error) == (
                    "Invalid https://concepts.datalad.org/s/things/v2/"
                    "w3ctr-datetime format: -"
                )
            ):
                if self.reported:
                    return False
                self.reported = True
                record.msg = (
                    "Known issue: placeholder date '-' in metadata; "
                    "no action needed for now."
                )
                record.args = ()
                record.exc_info = None
                record.exc_text = None
            return True

    logger = logging.getLogger("rdflib.term")
    warning_filter = DateWarningFilter()
    logger.addFilter(warning_filter)
    try:
        yield
    finally:
        logger.removeFilter(warning_filter)
