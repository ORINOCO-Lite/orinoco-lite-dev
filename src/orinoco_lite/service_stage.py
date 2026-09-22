"""Retained JSON round-trips through a disposable filesystem-backed Pool."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import tempfile
from dump_things_pyclient import communicate

from .errors import ConfigurationError
from . import upstream_snapshot
from .upstream_service import local_service
from .stage_reports import artifact_digest, write_json, write_operation


def register(subparsers) -> None:
    from .diagnostics import options
    parser = subparsers.add_parser("roundtrip", help="upload records to a temporary Pool and read them back",
        description="Upload the selected existing JSONL records to a temporary Pool and download them. Retain output under STATE-pool-jsonl/. Existing output requires --force.")
    options(parser)
    parser.add_argument("source_state", nargs="?", default="yaml-jsonl", choices=("downloaded", "yaml-jsonl"), help="input records (default: yaml-jsonl)")


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
            with communicate.get_session() as session:
                for item in expected:
                    communicate.curated_write_record(service.url, "public", item.class_name,
                        item.record, token=service.token, session=session)
                totals = None
                seen = set()
                with partial.open("w", encoding="utf-8") as stream:
                    for record, _page, pages, _size, total in communicate.collection_read_records_of_class(
                            service.url, "public", "Thing", token=service.token, session=session):
                        if totals is None:
                            totals = (pages, total)
                        if totals != (pages, total):
                            raise ConfigurationError("Service pagination totals changed during read-back")
                        pid = record.get("pid") if isinstance(record, dict) else None
                        if not isinstance(pid, str) or pid in seen:
                            raise ConfigurationError("Service returned a missing or duplicate PID")
                        seen.add(pid)
                        returned.append(record)
                        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                if totals is None or len(returned) != totals[1]:
                    raise ConfigurationError("Service read-back is empty or incomplete")
        # Validate syntax/identity. Preservation itself belongs to records diff.
        upstream_snapshot.load_jsonl(partial)
        os.replace(partial, output)
        diagnostics.update(status="complete", returned_records=len(returned))
        write_operation(output, operation="records.roundtrip", inputs={"records": source},
                        context={"schema_sha256": artifact_digest(schema), "service": "dump-things-service",
                                 "transport": "selected upstream client"})
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
    from .diagnostics import directory, record_path, prepare_output
    from .record_stages import _check_record_input
    source = record_path(directory(args), args.source_state)
    _check_record_input(source)
    upstream_snapshot.load_jsonl(source)
    output = prepare_output(directory(args) / f"{args.source_state}-pool-jsonl", args.force)
    try:
        result = roundtrip(source, output / "records.jsonl", scratch=output / "diagnostics")
    except (RuntimeError, OSError, ValueError) as error:
        raise ConfigurationError(f"Service round-trip failed: {error}") from error
    print(f"Returned {result['returned_records']} records (jsonl): {output / 'records.jsonl'}")
    print(f"Service diagnostics: {output / 'diagnostics'}")
    return 0
