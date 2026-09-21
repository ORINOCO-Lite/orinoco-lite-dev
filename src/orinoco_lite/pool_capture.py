"""Fetch a public Pool capture, or reuse it after checking its source and bytes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

from dump_things_pyclient import communicate
from requests import RequestException

from .errors import OrinocoError


DEFAULT_OUTPUT = Path("captures/records.jsonl")
DEFAULT_API = "https://pool.psychoinformatics.de/api"
COMPLETENESS_LIMIT = (
    "Reported pagination totals, record count, and unique PIDs were checked. "
    "The service does not provide an atomic snapshot; concurrent edits that preserve these "
    "checks can remain undetected."
)


class CaptureError(OrinocoError):
    """The capture or live Pool response cannot be safely used."""


def load_capture(path: Path) -> tuple[dict[str, dict[str, object]], str]:
    from .upstream_snapshot import SnapshotError, load_jsonl

    try:
        records = load_jsonl(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, UnicodeError, SnapshotError) as error:
        raise CaptureError(f"Invalid Pool capture {path}: {error}") from error
    if not records:
        raise CaptureError(f"Pool capture has no records: {path}")
    return {item.pid: item.record for item in records}, digest


def fetch_live(api: str) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """Use the pinned upstream reader; verify the returned stream before saving."""
    records = {}
    expected = None
    try:
        with communicate.get_session() as session:
            server = communicate.server(api, session=session)
            stream = communicate.collection_read_records_of_class(
                service_url=api, collection="public", class_name="Thing",
                session=session,
            )
            for record, _page, pages, _size, total in stream:
                if expected is None:
                    expected = (pages, total)
                if (pages, total) != expected:
                    raise CaptureError("Pool pagination totals changed during acquisition")
                pid = record.get("pid") if isinstance(record, dict) else None
                if not isinstance(pid, str) or not pid or pid in records:
                    raise CaptureError(f"Pool returned an invalid or duplicate PID {pid!r}")
                records[pid] = record
    except (RequestException, ValueError) as error:
        raise CaptureError(f"Upstream record retrieval failed: {error}") from error
    if expected is None or len(records) != expected[1]:
        raise CaptureError("Pool capture is empty or incomplete")
    return records, server


def capture(
    destination: Path, *, api: str = DEFAULT_API, force: bool = False
) -> dict:
    """Keep exact record values; publish only a complete, checked JSONL capture."""
    destination = destination.absolute()
    manifest_path = destination.with_name(destination.name + ".manifest.json")
    api = api.rstrip("/")
    source = urlsplit(api)
    if source.scheme not in {"http", "https"} or not source.hostname:
        raise CaptureError("The Pool API must be an HTTP or HTTPS service URL")
    if source.username or source.password or source.query or source.fragment:
        raise CaptureError("The public Pool API URL must not contain credentials, a query, or a fragment")
    if destination.exists() and not force:
        if not manifest_path.is_file():
            raise CaptureError(
                "Existing Pool capture has no provenance manifest; "
                "use --force to capture the requested API"
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CaptureError(
                f"Invalid Pool capture manifest: {manifest_path}"
            ) from error
        if not isinstance(manifest, dict):
            raise CaptureError(
                f"Pool capture manifest is not an object: {manifest_path}"
            )
        captured_api = manifest.get("source_api")
        if not isinstance(captured_api, str) or captured_api.rstrip("/") != api:
            raise CaptureError(
                f"Existing Pool capture is from {captured_api!r}, not {api!r}; "
                "use --force to capture the requested API"
            )
        records, digest = load_capture(destination)
        if manifest.get("record_count") != len(records):
            raise CaptureError("Existing Pool capture count does not match its manifest")
        if manifest.get("snapshot_sha256") != digest:
            raise CaptureError("Existing Pool capture digest does not match its manifest")
        print(
            f"Reusing {len(records)} records in {destination} "
            "(use --force to fetch again)"
        )
        return manifest

    started_at = datetime.now(timezone.utc).isoformat()
    records, server = fetch_live(api)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".pool-capture-", dir=destination.parent
        ) as temporary:
            raw = Path(temporary) / "capture.jsonl"
            with raw.open("w", encoding="utf-8") as stream:
                for record in records.values():
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            verified, digest = load_capture(raw)
            if len(verified) != len(records):
                raise CaptureError("New Pool capture failed its count check")
            manifest = {
                "schema_version": 1,
                "record_count": len(records),
                "snapshot": destination.name,
                "snapshot_sha256": digest,
                "source_api": api,
                "source_class": "Thing",
                "source_collection": "public",
                "source_server": server,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "capture_started_at": started_at,
                "completeness": {
                    "pagination_totals_checked": True,
                    "record_count_checked": True,
                    "unique_pids_checked": True,
                    "atomic_snapshot": False,
                    "limitations": COMPLETENESS_LIMIT,
                },
            }
            audit = Path(temporary) / "manifest.json"
            audit.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(raw, destination)
            os.replace(audit, manifest_path)
    except OSError as error:
        raise CaptureError(f"Could not save Pool capture {destination}: {error}") from error
    print(f"Captured {len(records)} records in {destination}")
    print(f"SHA-256: {digest}")
    print(COMPLETENESS_LIMIT)
    return manifest


def register_capture(commands: argparse._SubParsersAction) -> None:
    """Add ``get`` to the shared ``dev records`` command group."""
    parser = commands.add_parser(
        "get", help="capture public Pool records and their acquisition facts",
        description=("Download public Pool records to OUTPUT as JSON Lines, "
                     "with one record per line. "
                     "Save source information and verification details to OUTPUT.manifest.json. "
                     "Reuse an existing verified capture unless --force is supplied."),
    )
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT,
                        help="capture file (default: %(default)s)")
    parser.add_argument("--api", default=DEFAULT_API, help="public Pool API URL")
    parser.add_argument("--force", action="store_true", help="download again and replace the capture and its manifest")


def execute(args: argparse.Namespace) -> int:
    root = (getattr(args, "root", None) or Path.cwd()).resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    capture(output, api=args.api, force=args.force)
    return 0
