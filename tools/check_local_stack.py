#!/usr/bin/env python3
"""Check the four-collection clean-migration local stack contract."""

from __future__ import annotations

import html
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult, parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

import yaml


ROOT = Path(__file__).resolve().parents[1]
SITE = Path(
    os.environ.get(
        "CON_SITE_ROOT",
        ROOT / "submodules" / "centerforopenneuroscience.org",
    )
).resolve()
STACK = ROOT / "build" / "local-stack"
UPSTREAM_SNAPSHOT = STACK / "pool" / "public-thing.jsonl"
CON_RECORDS = ROOT / "build" / "con-projection" / "records.jsonl"
CON_SITE = ROOT / "build" / "con-site"
EDITOR_TOKEN = STACK / "editor-token"
SEED_TOKEN = STACK / "seed-token"
SERVICE_URL = "http://127.0.0.1:8111"
EDITOR_URL = "http://127.0.0.1:3000/"
COLLECTIONS = {
    "upstream-public",
    "upstream-protected",
    "con-public",
    "con-protected",
}
LEGACY_COLLECTIONS = ("public", "protected")
EDIT_LINK = re.compile(r"href=(?:\"(?P<double>[^\"]+)\"|'(?P<single>[^']+)')")
PROBE_CLASS = "XYZProject"
LEGACY_PROBE_PID = "xyzrins:projects/_clean-migration-write-probe"
PROBE_PID_PREFIX = f"{LEGACY_PROBE_PID}-"
CON_PERSON_PID = "xyzrins:persons/yaroslav-halchenko"
REPRESENTATIVE_EDIT_PIDS = frozenset(
    {
        CON_PERSON_PID,
        "xyzrins:projects/datalad",
    }
)
PROJECTION_CONTRACT = SITE / "profiles" / "con" / "projection.yaml"
EDIT_QUERY_KEYS = frozenset({"sh:NodeShape", "pid", "edit"})


def request_json(
    method: str,
    url: str,
    token: str | None,
    body: object | None = None,
    *,
    missing_ok: bool = False,
) -> object | None:
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["X-DumpThings-Token"] = token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = Request(url, headers=headers, data=data, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
    except HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {url} failed ({error.code}): {detail[:500]}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach {url}: {error}") from error
    return json.loads(raw) if raw else None


def expect_rejected(
    method: str,
    url: str,
    token: str | None,
    body: object,
) -> None:
    """Require an API request to fail for lack of write permission."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token is not None:
        headers["X-DumpThings-Token"] = token
    request = Request(
        url,
        headers=headers,
        data=json.dumps(body).encode("utf-8"),
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except HTTPError as error:
        error.read()
        if error.code in {401, 403}:
            return
        raise RuntimeError(
            f"Unauthorized probe returned unexpected status {error.code}: {url}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach {url}: {error}") from error
    raise RuntimeError(f"Unauthorized write unexpectedly succeeded: {url}")


def read_text(url: str) -> str:
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def normalize_record(record: dict) -> dict:
    """Match the service's omission of a top-level class discriminator."""
    normalized = dict(record)
    normalized.pop("schema_type", None)
    return normalized


def manifest_records(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                item = json.loads(line)
                record = item["record"]
                pid = record["pid"]
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                raise RuntimeError(
                    f"{path}:{line_number}: invalid stack JSONL envelope"
                ) from error
            if not isinstance(record, dict):
                raise RuntimeError(f"{path}:{line_number}: record must be an object")
            if not isinstance(pid, str) or not pid:
                raise RuntimeError(f"{path}:{line_number}: record pid must be a string")
            if pid in records:
                raise RuntimeError(
                    f"{path}:{line_number}: duplicate record pid {pid!r}"
                )
            records[pid] = normalize_record(record)
    if not records:
        raise RuntimeError(f"{path}: manifest has no records")
    return records


def manifest_envelopes(path: Path) -> dict[str, dict]:
    """Load the generated service envelopes, retaining their class names."""
    envelopes: dict[str, dict] = {}
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                item = json.loads(line)
                class_name = item["class_name"]
                record = item["record"]
                pid = record["pid"]
            except (json.JSONDecodeError, KeyError, TypeError) as error:
                raise RuntimeError(
                    f"{path}:{line_number}: invalid stack JSONL envelope"
                ) from error
            if not isinstance(class_name, str) or not class_name:
                raise RuntimeError(f"{path}:{line_number}: class_name must be a string")
            if not isinstance(record, dict) or not isinstance(pid, str) or not pid:
                raise RuntimeError(
                    f"{path}:{line_number}: record and pid must be valid"
                )
            schema_type = record.get("schema_type")
            if schema_type != f"xyzri:{class_name}":
                raise RuntimeError(
                    f"{path}:{line_number}: class_name {class_name!r} does not "
                    f"match schema_type {schema_type!r}"
                )
            if pid in envelopes:
                raise RuntimeError(
                    f"{path}:{line_number}: duplicate record pid {pid!r}"
                )
            envelopes[pid] = item
    if not envelopes:
        raise RuntimeError(f"{path}: manifest has no records")
    return envelopes


def expected_edit_pids(
    records_path: Path = CON_RECORDS,
    projection_path: Path = PROJECTION_CONTRACT,
) -> frozenset[str]:
    """Derive the editable route closure from records and render policy."""
    try:
        contract = yaml.safe_load(projection_path.read_text(encoding="utf-8"))
        render = contract["render"]
        pages = render["pages"]
        homepage_pid = render["homepage"]["pid"]
    except (OSError, KeyError, TypeError, yaml.YAMLError) as error:
        raise RuntimeError(
            f"Invalid CON projection contract: {projection_path}"
        ) from error
    if not isinstance(pages, dict) or not pages:
        raise RuntimeError("CON projection contract declares no rendered classes")
    rendered_types = set(pages)
    if not all(
        isinstance(schema_type, str) and schema_type.startswith("xyzri:")
        for schema_type in rendered_types
    ):
        raise RuntimeError("CON rendered class designators must be xyzri CURIEs")
    if not isinstance(homepage_pid, str) or not homepage_pid:
        raise RuntimeError("CON projection homepage pid is invalid")

    envelopes = manifest_envelopes(records_path)
    expected = frozenset(
        pid
        for pid, item in envelopes.items()
        if item["record"]["schema_type"] in rendered_types
    )
    if homepage_pid not in expected:
        raise RuntimeError(f"CON homepage {homepage_pid!r} is not a rendered record")
    missing_smoke = REPRESENTATIVE_EDIT_PIDS - expected
    if missing_smoke:
        raise RuntimeError(
            "Representative CON edit fixtures are not rendered: "
            f"{sorted(missing_smoke)!r}"
        )
    return expected


def curated_records(collection: str, token: str) -> dict[str, dict]:
    records: dict[str, dict] = {}
    page = 1
    while True:
        query = urlencode({"page": page, "size": 100})
        url = f"{SERVICE_URL}/{collection}/curated/records/p/?{query}"
        payload = request_json("GET", url, token)
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise RuntimeError(f"Unexpected paginated response from {url}")
        for record in payload["items"]:
            pid = record.get("pid") if isinstance(record, dict) else None
            if not isinstance(pid, str):
                raise RuntimeError(f"Record without a pid in {collection}")
            if pid in records:
                raise RuntimeError(f"Duplicate record {pid!r} in {collection}")
            records[pid] = normalize_record(record)
        pages = int(payload.get("pages", 1))
        if page >= pages:
            return records
        page += 1


def record_digest(record: dict) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def describe_difference(
    expected: dict[str, dict],
    actual: dict[str, dict],
) -> str:
    missing = sorted(expected.keys() - actual.keys())[:3]
    extra = sorted(actual.keys() - expected.keys())[:3]
    changed = [
        (
            pid,
            record_digest(expected[pid])[:12],
            record_digest(actual[pid])[:12],
        )
        for pid in sorted(expected.keys() & actual.keys())
        if expected[pid] != actual[pid]
    ][:3]
    return f"missing={missing!r}, extra={extra!r}, changed={changed!r}"


def check_seed_separation(token: str) -> dict[str, int]:
    upstream = manifest_records(UPSTREAM_SNAPSHOT)
    con = manifest_records(CON_RECORDS)
    expected = {
        "upstream-public": upstream,
        "upstream-protected": upstream,
        "con-public": con,
        "con-protected": con,
    }
    counts: dict[str, int] = {}
    for collection, expected_records in expected.items():
        actual = curated_records(collection, token)
        if actual != expected_records:
            difference = describe_difference(expected_records, actual)
            raise RuntimeError(f"Curated records differ in {collection}: {difference}")
        counts[collection] = len(actual)
    return counts


def check_no_legacy_collection_stores() -> None:
    legacy = [
        STACK / "store" / collection
        for collection in LEGACY_COLLECTIONS
        if (STACK / "store" / collection).exists()
    ]
    if legacy:
        raise RuntimeError(f"Obsolete local collection stores remain: {legacy}")


def check_editor_ui() -> None:
    config = read_text(f"{EDITOR_URL}config.yaml")
    external = read_text(f"{EDITOR_URL}config_default_xyzri.yaml")
    service_url = f"{SERVICE_URL}/con-protected/"
    if config.count(service_url) != 2:
        raise RuntimeError(
            "SHACL Vue must use con-protected for both read and write URLs"
        )
    for forbidden in (
        f"{SERVICE_URL}/con-public/",
        f"{SERVICE_URL}/upstream-public/",
        f"{SERVICE_URL}/upstream-protected/",
        "https://pool.psychoinformatics.de/api/",
    ):
        if forbidden in config:
            raise RuntimeError(f"SHACL Vue unexpectedly references {forbidden!r}")
    for required in (
        "use_service: true",
        "use_token: true",
        "http://127.0.0.1:8122/git-annex",
    ):
        if required not in config:
            raise RuntimeError(f"SHACL Vue configuration is missing {required!r}")
    for required in ("xyzrins:", "dlschemas_owl.ttl", "data_url: ''"):
        if required not in external:
            raise RuntimeError(
                f"SHACL Vue external configuration is missing {required!r}"
            )


def check_static_edit_links(
    expected_pids: frozenset[str] | None = None,
) -> int:
    if expected_pids is None:
        expected_pids = expected_edit_pids()
    links: list[tuple[str, SplitResult, dict[str, list[str]]]] = []
    for path in sorted(CON_SITE.rglob("*.html")):
        source = path.read_text(encoding="utf-8")
        for match in EDIT_LINK.finditer(source):
            link = html.unescape(match.group("double") or match.group("single"))
            parsed = urlsplit(link)
            query = parse_qs(parsed.query, keep_blank_values=True)
            if (
                parsed.hostname == "127.0.0.1"
                and parsed.port == 3000
                or "edit" in query
                or "sh:NodeShape" in query
            ):
                links.append((link, parsed, query))
    if not links:
        raise RuntimeError(f"No edit links found in generated CON site: {CON_SITE}")
    linked_pids: list[str] = []
    for link, parsed, query in links:
        if (
            parsed.scheme != "http"
            or parsed.netloc != "127.0.0.1:3000"
            or parsed.path != "/"
            or parsed.fragment
            or set(query) != EDIT_QUERY_KEYS
            or query.get("sh:NodeShape") != ["dlthings:Thing"]
            or len(query.get("pid", [])) != 1
            or query.get("edit") != ["true"]
        ):
            raise RuntimeError(
                "CON static edit link does not use the credential-free local "
                f"CON editor contract: {link}"
            )
        linked_pids.append(query["pid"][0])
    actual_pids = set(linked_pids)
    if actual_pids != expected_pids or len(linked_pids) != len(expected_pids):
        raise RuntimeError(
            "CON static edit links do not match the rendered record set: "
            f"expected={sorted(expected_pids)!r}, "
            f"actual={sorted(linked_pids)!r}"
        )
    return len(links)


def incoming_record(
    collection: str,
    token: str,
    pid: str,
) -> object | None:
    query = urlencode({"pid": pid})
    url = f"{SERVICE_URL}/{collection}/incoming/local-editor/record?{query}"
    return request_json("GET", url, token, missing_ok=True)


def curated_record(
    collection: str,
    token: str | None,
    pid: str,
) -> object | None:
    query = urlencode({"pid": pid})
    url = f"{SERVICE_URL}/{collection}/curated/record?{query}"
    return request_json("GET", url, token, missing_ok=True)


def check_anonymous_con_read() -> None:
    """Require the editor's default identity to read curated CON records."""
    query = urlencode({"pid": CON_PERSON_PID, "format": "json"})
    url = f"{SERVICE_URL}/con-protected/record?{query}"
    record = request_json("GET", url, None)
    if not isinstance(record, dict) or record.get("pid") != CON_PERSON_PID:
        raise RuntimeError(
            "Anonymous con-protected read did not return the curated "
            f"CON person {CON_PERSON_PID!r}"
        )


def delete_incoming_record(collection: str, token: str, pid: str) -> None:
    query = urlencode({"pid": pid})
    url = f"{SERVICE_URL}/{collection}/incoming/local-editor/record?{query}"
    request_json("DELETE", url, token, missing_ok=True)


def incoming_probe_pids(collection: str, token: str) -> set[str]:
    """Find every reserved probe left by an interrupted acceptance run."""
    found: set[str] = set()
    page = 1
    while True:
        query = urlencode({"page": page, "size": 100})
        url = f"{SERVICE_URL}/{collection}/incoming/local-editor/records/p/?{query}"
        payload = request_json("GET", url, token, missing_ok=True)
        if payload is None:
            return found
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise RuntimeError(f"Unexpected paginated incoming response from {url}")
        for record in payload["items"]:
            pid = record.get("pid") if isinstance(record, dict) else None
            if not isinstance(pid, str):
                raise RuntimeError(f"Incoming record without a pid in {collection}")
            if pid == LEGACY_PROBE_PID or pid.startswith(PROBE_PID_PREFIX):
                found.add(pid)
        pages = int(payload.get("pages", 1))
        if page >= pages:
            return found
        page += 1


def prove_write_isolation(editor_token: str, seed_token: str) -> None:
    canonical_pids = set(manifest_envelopes(CON_RECORDS))
    collisions = sorted(
        pid
        for pid in canonical_pids
        if pid == LEGACY_PROBE_PID or pid.startswith(PROBE_PID_PREFIX)
    )
    if collisions:
        raise RuntimeError(
            f"Canonical records use the reserved acceptance PID namespace: {collisions}"
        )
    probe_pid = f"{PROBE_PID_PREFIX}{uuid.uuid4().hex}"
    probe = {"pid": probe_pid, "schema_type": "xyzri:XYZProject"}
    url = f"{SERVICE_URL}/con-protected/record/{PROBE_CLASS}"
    cleanup_pids = {LEGACY_PROBE_PID, probe_pid}
    for collection in COLLECTIONS:
        cleanup_pids.update(incoming_probe_pids(collection, seed_token))
    try:
        for stale_pid in sorted(cleanup_pids):
            for collection in COLLECTIONS:
                delete_incoming_record(collection, seed_token, stale_pid)
        for collection in sorted(COLLECTIONS):
            boundary_url = f"{SERVICE_URL}/{collection}/record/{PROBE_CLASS}"
            expect_rejected("POST", boundary_url, None, probe)
        for collection in sorted(COLLECTIONS - {"con-protected"}):
            boundary_url = f"{SERVICE_URL}/{collection}/record/{PROBE_CLASS}"
            expect_rejected("POST", boundary_url, editor_token, probe)

        request_json("POST", url, editor_token, probe)
        incoming = {
            collection: incoming_record(collection, seed_token, probe_pid)
            for collection in COLLECTIONS
        }
        protected_record = incoming["con-protected"]
        if (
            not isinstance(protected_record, dict)
            or protected_record.get("pid") != probe_pid
        ):
            raise RuntimeError(
                "Editor write did not land in con-protected/incoming/local-editor"
            )
        leaked = {
            collection: record
            for collection, record in incoming.items()
            if collection != "con-protected" and record is not None
        }
        if leaked:
            raise RuntimeError(f"Editor write leaked into incoming areas: {leaked}")
        curated = {
            collection: curated_record(collection, seed_token, probe_pid)
            for collection in COLLECTIONS
        }
        if any(record is not None for record in curated.values()):
            raise RuntimeError(f"Editor write leaked into curated areas: {curated}")
    finally:
        for stale_pid in sorted(cleanup_pids):
            for collection in COLLECTIONS:
                delete_incoming_record(collection, seed_token, stale_pid)


def main() -> int:
    required = (
        EDITOR_TOKEN,
        SEED_TOKEN,
        UPSTREAM_SNAPSHOT,
        CON_RECORDS,
        CON_SITE,
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing local-stack inputs: {missing}")
    editor_token = EDITOR_TOKEN.read_text(encoding="utf-8").strip()
    seed_token = SEED_TOKEN.read_text(encoding="utf-8").strip()
    server = request_json("GET", f"{SERVICE_URL}/server", seed_token)
    if not isinstance(server, dict):
        raise RuntimeError("Unexpected local Dump Things server response")
    names = {item["name"] for item in server["collections"]}
    if names != COLLECTIONS:
        raise RuntimeError(f"Unexpected local collections: {sorted(names)}")
    check_no_legacy_collection_stores()
    counts = check_seed_separation(seed_token)
    check_anonymous_con_read()
    check_editor_ui()
    edit_links = check_static_edit_links()
    prove_write_isolation(editor_token, seed_token)
    print(
        "Local clean-migration stack healthy: "
        f"{counts['upstream-public']} upstream records, "
        f"{counts['con-public']} CON records, {edit_links} CON edit links"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Local stack check failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
