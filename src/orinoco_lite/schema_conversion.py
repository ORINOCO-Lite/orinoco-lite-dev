"""Locked construction of the pinned semantic conversion pair."""

from __future__ import annotations

from pathlib import Path
import sys
from threading import RLock
from typing import Any

from rdflib import Graph, Literal, URIRef


# Dump Things 6.3.6 retries in increments of 1,000 and therefore succeeds at
# 2,000 for the pinned schema. Keep the same reviewed ceiling locally, but do
# not let that dependency's fallback leak a process-wide setting to callers.
PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT = 2000
_MODEL_BUILD_LOCK = RLock()


class _SourceLexicalRdfReader:
    """Keep the captured at_time marker through the upstream RDF loader."""

    def __init__(self, converter: Any):
        self.converter = converter

    def convert(self, data: str, target_class: str) -> dict:
        # The pinned JSON model and RDF writer preserve this source value, but
        # RDFLib cannot convert its datetime lexical form. The upstream RDF
        # loader then drops it. Adapt only the reader's transient graph: stored
        # records, emitted RDF, the schema, and SHACL constraints stay unchanged.
        graph = Graph().parse(data=data, format="turtle")
        predicate = URIRef("https://concepts.datalad.org/s/things/v2/at_time")
        datatype = URIRef("https://concepts.datalad.org/s/things/v2/w3ctr-datetime")
        markers = [
            (subject, predicate, value)
            for subject, value in graph.subject_objects(predicate)
            if isinstance(value, Literal)
            and value.datatype == datatype
            and str(value) == "-"
        ]
        for subject, predicate, value in markers:
            graph.remove((subject, predicate, value))
            graph.add((subject, predicate, Literal("-")))
        if markers:
            data = graph.serialize(format="turtle")
        return self.converter.convert(data, target_class)


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
                _SourceLexicalRdfReader(
                    FormatConverter(str(schema), Format.ttl, Format.json)
                ),
            )
        finally:
            if sys.getrecursionlimit() != previous_limit:
                sys.setrecursionlimit(previous_limit)
