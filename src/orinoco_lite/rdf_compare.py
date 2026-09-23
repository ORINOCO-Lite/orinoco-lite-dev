"""Bounded RDF comparison using the selected PyOxigraph RDFC-1.0 API.

Canonicalization covers the entire dataset, including blank nodes shared across
named graphs. It compares RDF terms, without entailment or literal value folding.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

COMPARATOR = "rdf-dataset-rdfc-1.0-v2"
ATTRIBUTION_COMPARATOR = "rdf-source-record-rdfc-1.0-v1"
DEFAULT_TIMEOUT = 5.0
FORMATS = {".ttl": "turtle", ".nt": "n-triples", ".trig": "trig", ".nq": "n-quads"}


class RDFComparisonError(ValueError):
    """Comparison did not complete; this is neither equality nor inequality."""


def _worker(request: dict, timeout: float) -> dict:
    started = perf_counter()
    try:
        result = subprocess.run([sys.executable, "-m", __name__],
                                input=json.dumps(request), capture_output=True,
                                text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise RDFComparisonError(f"RDF comparison not evaluated: exceeded {timeout:g} seconds") from error
    if result.returncode:
        raise RDFComparisonError("RDF comparison not evaluated: " +
                                 (result.stderr.strip() or f"worker exited {result.returncode}"))
    response = json.loads(result.stdout)
    response["worker_seconds"] = perf_counter() - started
    return response


def compare_graphs(left: Path, right: Path, *, left_format: str | None = None,
                   right_format: str | None = None, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Compare complete outputs; no conversion metadata or record map is needed."""
    return _worker({"pairs": [{"left": str(left), "right": str(right),
                               "left_format": left_format, "right_format": right_format}]}, timeout)


def compare_records(pairs: list[dict], *, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Independent diagnostic comparison of original per-record RDF documents."""
    return _worker({"pairs": pairs}, timeout)


def _check_trig_inventory(path: Path) -> None:
    # Both selected quad loaders discard empty graph declarations. Compose the
    # existing RDFLib grammar with its sink interface to detect that unsupported
    # case, without storing triples, parsing syntax ourselves, or changing RDF.
    from rdflib import Graph
    from rdflib.plugins.parsers.notation3 import RDFSink
    from rdflib.plugins.parsers.trig import TrigSinkParser

    class Inventory(RDFSink):
        def __init__(self):
            super().__init__(Graph())
            self.declared = set()
            self.populated = set()

        def newGraph(self, identifier):
            self.declared.add(identifier)
            return super().newGraph(identifier)

        def makeStatement(self, quadruple, why=None):
            context = quadruple[0]
            if context is not None:
                self.populated.add(context.identifier)

    sink = Inventory()
    with path.open("rb") as stream:
        TrigSinkParser(sink, baseURI=path.resolve().as_uri(), turtle=True).loadStream(stream)
    empty = sink.declared - sink.populated - {sink.graph.identifier}
    if empty:
        raise ValueError("TriG contains empty named graphs, which the selected canonicalizer cannot represent")


def _compare(request: dict) -> dict:
    from pyoxigraph import CanonicalizationAlgorithm, Dataset, RdfFormat, parse
    import pyoxigraph

    formats = {"turtle": RdfFormat.TURTLE, "trig": RdfFormat.TRIG,
               "n-triples": RdfFormat.N_TRIPLES, "n-quads": RdfFormat.N_QUADS}
    rows = []
    timing = {"parse_seconds": 0.0, "canonicalize_seconds": 0.0, "compare_seconds": 0.0}
    for pair in request["pairs"]:
        started = perf_counter()
        datasets = []
        for side in ("left", "right"):
            path = pair.get(side)
            if path is None:
                datasets.append(Dataset())
                continue
            path = Path(path)
            name = pair.get(side + "_format") or FORMATS.get(path.suffix)
            if name not in formats:
                raise ValueError(f"Specify an RDF format for {path}")
            if name == "trig":
                _check_trig_inventory(path)
            datasets.append(Dataset(parse(path=path, format=formats[name],
                                          base_iri=path.resolve().as_uri())))
        timing["parse_seconds"] += perf_counter() - started
        started = perf_counter()
        for data in datasets:
            data.canonicalize(CanonicalizationAlgorithm.RDFC_1_0)
        timing["canonicalize_seconds"] += perf_counter() - started
        started = perf_counter()
        before, after = datasets
        same = before == after
        rows.append({"subject": pair.get("subject", "Complete RDF output"),
                     "equal": same, "before": len(before), "after": len(after),
                     "before_present": pair.get("left") is not None,
                     "after_present": pair.get("right") is not None})
        timing["compare_seconds"] += perf_counter() - started
    return {"comparisons": rows, "timing": timing, "engine": "PyOxigraph",
            "engine_version": pyoxigraph.__version__, "algorithm": "RDFC-1.0"}


if __name__ == "__main__":
    try:
        print(json.dumps(_compare(json.load(sys.stdin))))
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(2)
