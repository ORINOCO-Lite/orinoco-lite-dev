"""Retained JSON round-trips through a disposable filesystem-backed Pool."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import tempfile
from urllib.parse import urlencode

from .errors import ConfigurationError
from . import upstream_snapshot
from .upstream_service import local_service, request_json, seed_manifest
from .stage_reports import artifact_digest, write_json, write_operation


def register(subparsers) -> None:
    parser = subparsers.add_parser("roundtrip", help="upload records to a temporary Pool and retain its returned records")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scratch", type=Path, help="empty directory for service logs and partial results")
    parser.add_argument("--no-record", action="store_true", help="generated diagnostic output is never committed")


def selected_schema() -> Path:
    from .resources import resolve_resources
    path = resolve_resources().root / "schema" / "src" / "demo-research-information" / "unreleased.yaml"
    if not path.is_file():
        # The bundled schema is the selected package schema, never a newer generated replacement.
        path = resolve_resources().root / "schema" / "demo-research-information" / "unreleased.yaml"
    if not path.is_file():
        raise ConfigurationError("Pinned Things Schema is missing; run dev prepare-resources")
    return path


def roundtrip(source: Path, output: Path, *, scratch: Path | None = None,
              schema: Path | None = None) -> dict:
    from .record_stages import _check_record_input

    source, output = source.resolve(), output.absolute()
    if source == output.resolve() or output.exists():
        raise ConfigurationError(f"Returned-record output must be new and distinct from input: {output}")
    _check_record_input(source)
    expected = upstream_snapshot.load_jsonl(source)
    schema = schema or selected_schema()
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = scratch or Path(tempfile.mkdtemp(prefix=output.stem + "-service-", dir=output.parent))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    returned = []
    partial = scratch / "returned.partial.jsonl"
    diagnostics = {"status": "failed", "input_records": len(expected), "returned_records": 0}
    try:
        with local_service(scratch, schema, port=port) as service:
            seed_manifest(source, ("public",), service.token, "round-trip", service_url=service.url)
            page, seen, total = 1, set(), None
            with partial.open("w", encoding="utf-8") as stream:
                while True:
                    payload = request_json("GET", service.url + "/public/records/p/Thing?" +
                                           urlencode({"page": page, "size": 100, "format": "json"}), service.token)
                    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                        raise ConfigurationError("Service returned an invalid page")
                    pages = payload.get("pages")
                    if type(pages) is not int or pages < 0 or (total is not None and total != pages):
                        raise ConfigurationError("Service pagination changed during the retained read-back")
                    total = pages
                    for record in payload["items"]:
                        if not isinstance(record, dict) or not isinstance(record.get("schema_type"), str) or ":" not in record["schema_type"]:
                            raise ConfigurationError("Returned record has no class-qualified schema_type")
                        if not isinstance(record.get("pid"), str) or record["pid"] in seen:
                            raise ConfigurationError("Service returned a missing or duplicate PID")
                        seen.add(record["pid"])
                        envelope = {"class_name": record["schema_type"].rsplit(":", 1)[-1], "record": record}
                        returned.append(envelope)
                        stream.write(json.dumps(envelope, ensure_ascii=False, allow_nan=False) + "\n")
                    if page >= pages:
                        break
                    page += 1
        # Validate syntax/identity. Preservation itself belongs to records diff.
        upstream_snapshot.load_jsonl(partial)
        os.replace(partial, output)
        diagnostics.update(status="complete", returned_records=len(returned))
        write_operation(output, operation="records.roundtrip", inputs={"records": source},
                        context={"schema_sha256": artifact_digest(schema), "service": "dump-things-service",
                                 "transport": "retained HTTP upload/read-back helpers"})
    except Exception as error:
        diagnostics.update(error=str(error), returned_records=len(returned))
        raise
    finally:
        write_json(scratch / "roundtrip.json", diagnostics)
        # The transient token has no use after shutdown and must not enter evidence bundles.
        config = scratch / "dumpthings.yaml"
        if config.exists():
            config.unlink()
    return diagnostics


def execute(args) -> int:
    try:
        result = roundtrip(args.source, args.output, scratch=args.scratch)
    except (RuntimeError, OSError, ValueError) as error:
        raise ConfigurationError(f"Service round-trip failed: {error}") from error
    print(f"Service round-trip retained {result['returned_records']} records at {args.output}")
    return 0
