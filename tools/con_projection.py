#!/usr/bin/env python3
"""Render and verify the committed clean-migration projection."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from typing import Any, Iterator, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

from dump_things_service import Format
from dump_things_service.converter import FormatConverter
from linkml_runtime import SchemaView


ROOT = Path(__file__).resolve().parents[1]
SITE = Path(
    os.environ.get(
        "CON_SITE_ROOT",
        ROOT / "submodules" / "centerforopenneuroscience.org",
    )
).resolve()
UPSTREAM = Path(
    os.environ.get(
        "UPSTREAM_SITE_ROOT",
        ROOT / "submodules" / "www-from-model",
    )
).resolve()
PROFILE_ROOT = SITE / "profiles" / "con"
PROFILE_PATH = PROFILE_ROOT / "profile.yaml"
PROJECTION_SPEC_PATH = PROFILE_ROOT / "projection.yaml"
COMMITTED = PROFILE_ROOT / "projection"
PROJECTION_ATTRIBUTES = COMMITTED / ".gitattributes"
SCHEMA = (
    ROOT
    / "submodules"
    / "things-schemas"
    / "src"
    / "demo-research-information"
    / "unreleased.yaml"
)
BUILD_ROOT = ROOT / "build" / "con-projection"
COLLECTION = "con-public"
READER_TOKEN = "con-projection-reader"
VALIDATOR_TOKEN = "con-projection-validator"

ROOT_PID = "xyzrins:."
CANONICAL_PIDS = {
    ROOT_PID,
    "ror:04tfhh831",
    "xyzrins:persons/yaroslav-halchenko",
    "xyzrins:projects/datalad",
    "xyzrins:publications/datalad-joss-2021",
    "xyzrins:instruments/datalad",
}
REFERENCE_PIDS = {
    "marcrel:led",
    "marcrel:aut",
    "obo:IAO_0000010",
    "bibo:AcademicArticle",
}
REQUIRED_NATIVE_TYPES = {
    "dlthings:Association",
    "dlthings:Attribution",
    "dlthings:Generation",
    "dlthings:DOI",
    "dlthings:ISSN",
}
FORBIDDEN_BRIDGE_PREDICATES = {
    "dcterms:contributor",
    "dcterms:creator",
    "dcterms:relation",
    "schema:about",
    "schema:member",
    "schema:memberOf",
    "schema:subjectOf",
}
EXPECTED_GRAPH_EDGES = {
    (ROOT_PID, "ror:04tfhh831"),
    (ROOT_PID, "xyzrins:persons/yaroslav-halchenko"),
    ("xyzrins:projects/datalad", ROOT_PID),
    (
        "xyzrins:projects/datalad",
        "xyzrins:persons/yaroslav-halchenko",
    ),
    (
        "xyzrins:publications/datalad-joss-2021",
        "xyzrins:persons/yaroslav-halchenko",
    ),
    (
        "xyzrins:publications/datalad-joss-2021",
        "xyzrins:projects/datalad",
    ),
    ("xyzrins:instruments/datalad", "xyzrins:projects/datalad"),
}


class ProjectionError(RuntimeError):
    """Report a fail-closed clean-migration contract violation."""


@dataclass(frozen=True)
class SourceRecord:
    """One canonical or reference record and its declared top-level class."""

    class_name: str
    record: dict[str, Any]
    path: Path
    category: str


def run(
    arguments: Sequence[str | Path],
    *,
    input_text: str | None = None,
    environment: dict[str, str] | None = None,
    cwd: Path = ROOT,
    action: str,
) -> str:
    """Run a command and return stdout with a useful failure message."""
    command = [str(argument) for argument in arguments]
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        input=input_text,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ProjectionError(
            f"{action} failed ({result.returncode}): {detail}"
        )
    return result.stdout


def git_commit(repository: Path) -> str:
    return run(
        ["git", "-C", repository, "rev-parse", "HEAD"],
        action=f"Inspect {repository.name} checkout",
    ).strip()


def git_tree_object(repository: Path, expression: str) -> str:
    return run(
        ["git", "-C", repository, "rev-parse", expression],
        action=f"Inspect {repository.name} tree object {expression}",
    ).strip()


def require_clean_checkout(repository: Path, label: str) -> None:
    status = run(
        [
            "git",
            "-C",
            repository,
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        action=f"Inspect the {label} worktree",
    ).strip()
    if status:
        raise ProjectionError(
            f"The pinned {label} worktree has changes:\n{status}"
        )


def verify_transport_trees() -> None:
    """Require the hydrated sibling to match the rebased site's payload trees."""
    for path in ("assets", "static", "themes/congo"):
        site_object = git_tree_object(SITE, f"HEAD:{path}")
        transport_object = git_tree_object(UPSTREAM, f"HEAD:{path}")
        if site_object != transport_object:
            raise ProjectionError(
                "The upstream hydration checkout differs from the rebased "
                f"site for {path}: {site_object} != {transport_object}"
            )


def verify_declared_pins(profile: dict[str, Any]) -> None:
    """Require the profile provenance to match the checked-out gitlinks."""
    schema = profile.get("schema", {})
    components = profile.get("components", {})
    if not isinstance(schema, dict) or not isinstance(components, dict):
        raise ProjectionError("Profile schema/components must be mappings")
    exact = {
        "schema.commit": (
            schema.get("commit"),
            ROOT / "submodules" / "things-schemas",
        ),
        "components.dump_things.commit": (
            components.get("dump_things", {}).get("commit"),
            ROOT / "submodules" / "dump-things-service",
        ),
        "components.dump_things_client.commit": (
            components.get("dump_things_client", {}).get("commit"),
            ROOT / "submodules" / "dump-things-pyclient",
        ),
        "components.qri.commit": (
            components.get("qri", {}).get("commit"),
            ROOT / "submodules" / "query-things",
        ),
        "components.graph.commit": (
            components.get("graph", {}).get("commit"),
            ROOT / "submodules" / "things-graph-renderer",
        ),
    }
    for label, (declared, repository) in exact.items():
        actual = git_commit(repository)
        if declared != actual:
            raise ProjectionError(
                f"{label} declares {declared!r}, but the gitlink is {actual}"
            )
        require_clean_checkout(repository, label.removesuffix(".commit"))

    declared_congo = components.get("congo", {}).get("commit")
    actual_congo = git_tree_object(SITE, "HEAD:themes/congo")
    if declared_congo != actual_congo:
        raise ProjectionError(
            "components.congo.commit declares "
            f"{declared_congo!r}, but the site gitlink is {actual_congo}"
        )

    declared_upstream = components.get("www_from_model", {}).get("commit")
    if not isinstance(declared_upstream, str):
        raise ProjectionError("Profile does not declare www-from-model commit")
    result = subprocess.run(
        [
            "git",
            "-C",
            str(SITE),
            "merge-base",
            "--is-ancestor",
            declared_upstream,
            "HEAD",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise ProjectionError(
            "The declared true upstream commit is not an ancestor of the "
            f"clean site checkout: {declared_upstream}"
        )
    commit_count = int(
        run(
            [
                "git",
                "-C",
                SITE,
                "rev-list",
                "--count",
                f"{declared_upstream}..HEAD",
            ],
            action="Count clean-migration website commits",
        ).strip()
    )
    if commit_count != 2:
        raise ProjectionError(
            "The clean site must have exactly two commits above its declared "
            f"base, found {commit_count}"
        )
    changed_paths = run(
        [
            "git",
            "-C",
            SITE,
            "diff",
            "--name-only",
            f"{declared_upstream}..HEAD",
        ],
        action="Inspect the clean-migration website overlay",
    ).splitlines()
    unexpected = [
        path
        for path in changed_paths
        if path not in {".gitmodules", "UPSTREAM.md"}
        and not path.startswith(("config/con/", "profiles/con/"))
    ]
    if unexpected:
        raise ProjectionError(
            "The clean site changed upstream-owned paths: "
            + ", ".join(unexpected)
        )
    require_clean_checkout(UPSTREAM, "www-from-model hydration transport")
    verify_transport_trees()
    build = profile.get("build", {})
    if not isinstance(build, dict) or build.get("metadata_collection") != COLLECTION:
        raise ProjectionError(
            f"Profile build.metadata_collection must be {COLLECTION!r}"
        )


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProjectionError(f"Required YAML file is absent: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProjectionError(f"Expected a YAML mapping: {path}")
    return value


def safe_reset(path: Path) -> None:
    """Replace one named build directory and nothing outside build state."""
    resolved = path.resolve()
    build = (ROOT / "build").resolve()
    if build not in resolved.parents or resolved == build:
        raise ProjectionError(f"Refusing to replace non-build path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def source_records(root: Path, category: str) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for path in sorted(root.rglob("*.yaml")):
        if path.name == ".dumpthings.yaml":
            continue
        relative = path.relative_to(root)
        if len(relative.parts) < 2:
            raise ProjectionError(
                f"Record is not stored below a class directory: {path}"
            )
        class_name = relative.parts[0]
        record = load_yaml(path)
        if not isinstance(record.get("pid"), str):
            raise ProjectionError(f"Record has no string PID: {path}")
        expected_type = f"xyzri:{class_name}"
        if record.get("schema_type") != expected_type:
            raise ProjectionError(
                f"{path}: expected top-level schema_type {expected_type!r}"
            )
        records.append(SourceRecord(class_name, record, path, category))
    if not records:
        raise ProjectionError(f"No records found below {root}")
    return records


def nested_schema_types(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        schema_type = value.get("schema_type")
        if isinstance(schema_type, str):
            result.append(schema_type)
        for child in value.values():
            result.extend(nested_schema_types(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(nested_schema_types(child))
    return result


def native_value_fingerprint(value: Any) -> Counter[tuple[str, str]]:
    """Capture the native relationship and identifier values that must survive."""
    result: Counter[tuple[str, str]] = Counter()
    if isinstance(value, dict):
        schema_type = value.get("schema_type")
        if schema_type in REQUIRED_NATIVE_TYPES:
            payload = {
                key: value[key]
                for key in (
                    "object",
                    "roles",
                    "notation",
                    "at_location",
                    "at_time",
                )
                if key in value
            }
            result[(schema_type, json.dumps(payload, sort_keys=True))] += 1
        for child in value.values():
            result.update(native_value_fingerprint(child))
    elif isinstance(value, list):
        for child in value:
            result.update(native_value_fingerprint(child))
    return result


def accepted_schema_types(schema: Path) -> set[str]:
    view = SchemaView(str(schema))
    return {
        str(view.get_uri(name, expand=False))
        for name in view.all_classes()
    }


def linked_values(record: dict[str, Any]) -> Iterator[tuple[str, str]]:
    for field in (
        "about",
        "associated_with",
        "attributed_to",
        "generated_by",
        "part_of",
    ):
        values = record.get(field, [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            target = value.get("object") if isinstance(value, dict) else value
            if isinstance(target, list):
                for item in target:
                    if isinstance(item, str):
                        yield field, item
            elif isinstance(target, str):
                yield field, target
            if isinstance(value, dict):
                roles = value.get("roles", [])
                if not isinstance(roles, list):
                    roles = [roles]
                for role in roles:
                    if isinstance(role, str):
                        yield f"{field}.roles", role
    for field in ("kind", "rules"):
        values = record.get(field, [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            target = value.get("object") if isinstance(value, dict) else value
            if isinstance(target, str):
                yield field, target


def validate_record_contract(records: list[SourceRecord]) -> None:
    canonical = {
        record.record["pid"]
        for record in records
        if record.category == "canonical"
    }
    references = {
        record.record["pid"]
        for record in records
        if record.category == "reference"
    }
    if canonical != CANONICAL_PIDS:
        raise ProjectionError(
            "Canonical PID closure differs from the reviewed six records: "
            f"{sorted(canonical)}"
        )
    if references != REFERENCE_PIDS:
        raise ProjectionError(
            "Reference PID closure differs from the reviewed four records: "
            f"{sorted(references)}"
        )
    unexpected = [
        record.path
        for record in records
        if record.category not in {"canonical", "reference"}
    ]
    if unexpected:
        raise ProjectionError(f"Unexpected non-source records: {unexpected}")

    by_pid = {record.record["pid"]: record for record in records}
    if len(by_pid) != len(records):
        raise ProjectionError("Record PIDs must be unique")
    accepted = accepted_schema_types(SCHEMA)
    observed_types: Counter[str] = Counter()
    for item in records:
        record = item.record
        for schema_type in nested_schema_types(record):
            if schema_type.startswith(("http://", "https://")):
                raise ProjectionError(
                    f"{record['pid']}: full-URI type designator is unsupported: "
                    f"{schema_type}"
                )
            if schema_type not in accepted:
                raise ProjectionError(
                    f"{record['pid']}: unknown CURIE type designator: "
                    f"{schema_type}"
                )
            observed_types[schema_type] += 1

        for attribute in record.get("attributes", []):
            if not isinstance(attribute, dict):
                continue
            if attribute.get("predicate") in FORBIDDEN_BRIDGE_PREDICATES:
                raise ProjectionError(
                    f"{record['pid']}: AttributeSpecification cannot encode "
                    f"relationship predicate {attribute.get('predicate')}"
                )
        for field, target in linked_values(record):
            if target not in by_pid:
                raise ProjectionError(
                    f"{record['pid']}: dangling {field} target {target}"
                )

    missing_types = REQUIRED_NATIVE_TYPES - set(observed_types)
    if missing_types:
        raise ProjectionError(
            f"Native CURIE fixture coverage is incomplete: {sorted(missing_types)}"
        )

    project = by_pid["xyzrins:projects/datalad"].record
    if project.get("part_of") != [ROOT_PID]:
        raise ProjectionError("DataLad must use upstream part_of: [xyzrins:.]")
    publication = by_pid[
        "xyzrins:publications/datalad-joss-2021"
    ].record
    if any(
        str(identifier.get("notation", "")).startswith("https://doi.org/")
        for identifier in publication.get("identifiers", [])
        if isinstance(identifier, dict)
    ):
        raise ProjectionError("The retired DOI URL PID is provenance, not identity")


def roundtrip_records(records: list[SourceRecord]) -> None:
    """Exercise every record through the pinned JSON/RDF conversion path."""
    to_ttl = FormatConverter(str(SCHEMA), Format.json, Format.ttl)
    to_json = FormatConverter(str(SCHEMA), Format.ttl, Format.json)
    for item in records:
        before = Counter(nested_schema_types(item.record))
        before_values = native_value_fingerprint(item.record)
        try:
            ttl = to_ttl.convert(item.record, item.class_name)
            restored = to_json.convert(ttl, item.class_name)
        except Exception as error:
            raise ProjectionError(
                f"{item.record['pid']}: JSON/RDF/JSON round trip failed: "
                f"{error}"
            ) from error
        after = Counter(nested_schema_types(restored))
        for schema_type, count in before.items():
            if after[schema_type] < count:
                raise ProjectionError(
                    f"{item.record['pid']}: round trip lost {schema_type}"
                )
        after_values = native_value_fingerprint(restored)
        if after_values != before_values:
            raise ProjectionError(
                f"{item.record['pid']}: round trip changed native relationship "
                "or identifier values"
            )

    association = next(
        item
        for item in records
        if "dlthings:Association" in nested_schema_types(item.record)
    )
    invalid = deepcopy(association.record)

    def expand_first(value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("schema_type") == "dlthings:Association":
                value["schema_type"] = (
                    "https://concepts.datalad.org/s/things/v2/Association"
                )
                return True
            return any(expand_first(child) for child in value.values())
        if isinstance(value, list):
            return any(expand_first(child) for child in value)
        return False

    if not expand_first(invalid):
        raise ProjectionError("No Association fixture was available")
    try:
        to_ttl.convert(invalid, association.class_name)
    except Exception:
        pass
    else:
        raise ProjectionError(
            "Pinned conversion unexpectedly accepted a full-URI discriminator"
        )


def write_record_store(records: list[SourceRecord], root: Path) -> Path:
    curated = root / COLLECTION / "curated"
    incoming = root / COLLECTION / "incoming"
    curated.mkdir(parents=True)
    incoming.mkdir(parents=True)
    (curated / ".dumpthings.yaml").write_text(
        yaml.safe_dump(
            {
                "type": "records",
                "version": 1,
                "schema": str(SCHEMA.resolve()),
                "format": "yaml",
                "idfx": "after-last-colon",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    by_class: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        by_class[record.class_name].append(record)
    for class_name, items in sorted(by_class.items()):
        destination = curated / class_name
        destination.mkdir()
        for index, item in enumerate(
            sorted(items, key=lambda value: value.record["pid"]), start=1
        ):
            output = destination / f"{index:02d}.yaml"
            output.write_text(
                yaml.safe_dump(
                    item.record,
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
    return root


def write_service_config(records: list[SourceRecord], root: Path) -> Path:
    # qri's upstream inject-links command queries the polymorphic Thing
    # endpoint, in addition to the concrete classes present in the slice.
    classes = sorted({"Thing", *(record.class_name for record in records)})
    config = {
        "type": "collections",
        "version": 2,
        "pid": "dump_things:clean_migration_projection",
        "collections": {
            COLLECTION: {
                "default_token": READER_TOKEN,
                "schema": str(SCHEMA.resolve()),
                "curated": f"{COLLECTION}/curated",
                "incoming": f"{COLLECTION}/incoming",
                "backend": {
                    "type": "record_dir+stl",
                    "mapping_method": "after-last-colon",
                },
                "auth_sources": [{"type": "config"}],
                "use_classes": classes,
            }
        },
        "tokens": {
            READER_TOKEN: {
                "user_id": READER_TOKEN,
                "representation": READER_TOKEN,
                "collections": {
                    COLLECTION: {
                        "mode": "READ_CURATED",
                        "incoming_label": "",
                    }
                },
            },
            VALIDATOR_TOKEN: {
                "user_id": VALIDATOR_TOKEN,
                "representation": VALIDATOR_TOKEN,
                "collections": {
                    COLLECTION: {
                        "mode": "WRITE_COLLECTION",
                        "incoming_label": "validation",
                    }
                },
            },
        },
        "admin_tokens": {},
    }
    path = root / "config.yaml"
    path.write_text(
        yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
    )
    return path


def free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def wait_for_service(url: str, process: subprocess.Popen[str]) -> None:
    for _ in range(480):
        if process.poll() is not None:
            raise ProjectionError(
                f"Ephemeral Dump Things exited with status {process.returncode}"
            )
        try:
            with urlopen(f"{url}/server", timeout=1):
                return
        except (URLError, TimeoutError):
            time.sleep(0.25)
    raise ProjectionError("Ephemeral Dump Things did not become ready")


@contextmanager
def dump_things_service(
    records: list[SourceRecord], state: Path
) -> Iterator[str]:
    store = write_record_store(records, state / "store")
    config = write_service_config(records, store)
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    log_path = state / "dump-things.log"
    environment = os.environ.copy()
    environment["DTS_ADMIN_TOKEN"] = "clean-migration-local-admin"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                "dump-things-service",
                str(store),
                "--config",
                str(config),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "WARNING",
            ],
            cwd=ROOT,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            wait_for_service(url, process)
            yield url
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)


def request_validation(
    url: str,
    item: SourceRecord,
    *,
    expected_status: int = 200,
) -> None:
    request = Request(
        f"{url}/{COLLECTION}/validate/record/{item.class_name}",
        data=json.dumps(item.record).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-DumpThings-Token": VALIDATOR_TOKEN,
        },
    )
    try:
        with urlopen(request, timeout=120) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
    if status != expected_status:
        raise ProjectionError(
            f"Live validation for {item.record['pid']} returned {status}, "
            f"expected {expected_status}"
        )


def live_negative_cases(url: str, records: list[SourceRecord]) -> None:
    association = next(
        item
        for item in records
        if "dlthings:Association" in nested_schema_types(item.record)
    )
    full_uri = deepcopy(association.record)
    unknown = deepcopy(association.record)

    def replace(value: Any, replacement: str) -> bool:
        if isinstance(value, dict):
            if value.get("schema_type") == "dlthings:Association":
                value["schema_type"] = replacement
                return True
            return any(replace(child, replacement) for child in value.values())
        if isinstance(value, list):
            return any(replace(child, replacement) for child in value)
        return False

    replace(
        full_uri,
        "https://concepts.datalad.org/s/things/v2/Association",
    )
    replace(unknown, "dlthings:NotARealAssociation")
    for record in (full_uri, unknown):
        request_validation(
            url,
            SourceRecord(
                association.class_name,
                record,
                association.path,
                "negative",
            ),
            expected_status=422,
        )


def service_export(
    url: str, records: list[SourceRecord], state: Path
) -> list[dict[str, Any]]:
    by_class: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        by_class[record.class_name].append(record)
        request_validation(url, record)
    live_negative_cases(url, records)

    environment = os.environ.copy()
    environment["DTC_TOKEN"] = VALIDATOR_TOKEN
    validation_log: list[str] = []
    for class_name, items in sorted(by_class.items()):
        stream = "".join(
            json.dumps(item.record, sort_keys=True) + "\n"
            for item in sorted(items, key=lambda value: value.record["pid"])
        )
        validation_log.append(
            run(
                ["dtc", "post-records", url, COLLECTION, class_name],
                input_text=stream,
                environment=environment,
                action=f"Validate {class_name} records through dtc",
            )
        )
    (state / "dtc-validation.log").write_text(
        "".join(validation_log), encoding="utf-8"
    )

    environment["DTC_TOKEN"] = READER_TOKEN
    exported = run(
        ["dtc", "get-records", url, COLLECTION],
        environment=environment,
        action="Export validated CON records through dtc",
    )
    parsed = [
        json.loads(line)
        for line in exported.splitlines()
        if line.strip()
    ]
    parsed.sort(key=lambda record: (record["schema_type"], record["pid"]))
    expected = {item.record["pid"] for item in records}
    actual = {record["pid"] for record in parsed}
    if actual != expected or len(parsed) != len(records):
        raise ProjectionError(
            "dtc export differs from the source closure: "
            f"expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return parsed


def qri_pipeline(
    commands: list[list[str | Path]],
    environment: dict[str, str],
    *,
    input_text: str | None = None,
    action: str,
) -> str:
    output = input_text
    for command in commands:
        output = run(
            command,
            input_text=output,
            environment=environment,
            action=action,
        )
    return output or ""


def render_qri(
    url: str,
    records: list[dict[str, Any]],
    output: Path,
    state: Path,
) -> None:
    stream = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    cache = state / "qri-cache.json"
    environment = os.environ.copy()
    environment.update(
        {
            "DUMPTHINGS_APIURL": url,
            "DUMPTHINGS_TOKEN": READER_TOKEN,
            "QRI_RECORD_CACHE": str(cache),
        }
    )
    qri_pipeline(
        [["qri", "cache"]],
        environment,
        input_text=stream,
        action="Cache the dtc export with qri",
    )

    content = output / "content"
    template = SITE / "page_templates"
    render_specs: list[tuple[str, list[list[str | Path]], Path]] = [
        (
            "person",
            [
                ["qri", "list", "--class", "xyzri:XYZPerson"],
                [
                    "qri",
                    "filter-linked-pid",
                    COLLECTION,
                    ROOT_PID,
                    "associated_with",
                ],
                [
                    "qri",
                    "inline-records",
                    "-c",
                    COLLECTION,
                    "-p",
                    "delegated_by",
                    "-p",
                    "delegated_by::roles",
                    "-p",
                    "identifiers::creator",
                ],
            ],
            template / "person.md.j2",
        ),
        (
            "project",
            [
                ["qri", "list", "--class", "xyzri:XYZProject"],
                [
                    "qri",
                    "filter-links-pid",
                    "--link",
                    "part_of",
                    ROOT_PID,
                    "--recursive",
                    "--collection",
                    COLLECTION,
                ],
                [
                    "qri",
                    "inject-links-pid",
                    "--link",
                    "generated_by",
                    "generated",
                    "-c",
                    COLLECTION,
                ],
                [
                    "qri",
                    "inject-links-pid",
                    "--link",
                    "part_of",
                    "parts",
                    "-c",
                    COLLECTION,
                ],
                [
                    "qri",
                    "inline-records",
                    "-c",
                    COLLECTION,
                    "-p",
                    "associated_with",
                    "-p",
                    "associated_with::roles",
                    "-p",
                    "influenced_by",
                    "-p",
                    "influenced_by::roles",
                    "-p",
                    "identifiers::creator",
                    "-p",
                    "part_of",
                ],
            ],
            template / "project.md.j2",
        ),
        (
            "publication",
            [
                ["qri", "list", "--class", "xyzri:XYZPublication"],
                [
                    "qri",
                    "inline-records",
                    "-p",
                    "about",
                    "-p",
                    "attributed_to",
                    "-c",
                    COLLECTION,
                ],
            ],
            template / "publication.md.j2",
        ),
        (
            "instrument",
            [
                ["qri", "list", "--class", "xyzri:XYZInstrument"],
                [
                    "qri",
                    "inline-records",
                    "-p",
                    "about",
                    "-p",
                    "attributed_to",
                    "-p",
                    "kind",
                    "-p",
                    "rules",
                    "-c",
                    COLLECTION,
                ],
            ],
            template / "instrument.md.j2",
        ),
    ]
    for name, commands, page_template in render_specs:
        selected = qri_pipeline(
            commands,
            environment,
            action=f"Select and inline the CON {name} projection",
        )
        output_template = str(content / "{__pid_curie_reference}" / "_index.md")
        qri_pipeline(
            [["qri", "render-record", page_template, output_template]],
            environment,
            input_text=selected,
            action=f"Render the CON {name} projection",
        )

    homepage = qri_pipeline(
        [
            ["qri", "list", "--pid", ROOT_PID],
            [
                "qri",
                "inject-links-pid",
                "--link",
                "generated_by",
                "generated",
                "-c",
                COLLECTION,
            ],
            [
                "qri",
                "inject-links-pid",
                "--link",
                "part_of",
                "parts",
                "-c",
                COLLECTION,
            ],
            [
                "qri",
                "inline-records",
                "-c",
                COLLECTION,
                "-p",
                "associated_with",
                "-p",
                "associated_with::roles",
                "-p",
                "influenced_by",
                "-p",
                "influenced_by::roles",
                "-p",
                "identifiers::creator",
                "-p",
                "part_of",
            ],
        ],
        environment,
        action="Select and inline the CON homepage projection",
    )
    qri_pipeline(
        [
            [
                "qri",
                "render-record",
                template / "homepage.md.j2",
                content / "_index.md",
            ]
        ],
        environment,
        input_text=homepage,
        action="Render the CON homepage projection",
    )

    all_records = run(
        ["qri", "list"],
        environment=environment,
        action="List qri records for the upstream graph",
    )
    graph = run(
        [sys.executable, SITE / "code" / "pool2graph.py"],
        input_text=all_records,
        environment=environment,
        action="Render the graph with upstream pool2graph.py",
    )
    graph_path = output / "static" / "graph.json"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(graph + "\n", encoding="utf-8")


def validate_projection(
    records: list[dict[str, Any]], output: Path
) -> dict[str, Any]:
    graph = json.loads((output / "static" / "graph.json").read_text())
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ProjectionError("Upstream graph output has no node/edge lists")
    node_pids = {node.get("id") for node in nodes}
    expected_nodes = CANONICAL_PIDS
    if node_pids != expected_nodes:
        raise ProjectionError(
            f"CON graph node closure differs: {sorted(node_pids)}"
        )
    edge_pairs = {(edge.get("source"), edge.get("target")) for edge in edges}
    if edge_pairs != EXPECTED_GRAPH_EDGES:
        raise ProjectionError(
            f"CON graph edge closure differs: {sorted(edge_pairs)}"
        )
    if len(records) != 10:
        raise ProjectionError(f"Expected 10 qri records, found {len(records)}")

    expected_pages = {
        "_index.md",
        "persons/yaroslav-halchenko/_index.md",
        "projects/datalad/_index.md",
        "publications/datalad-joss-2021/_index.md",
        "instruments/datalad/_index.md",
    }
    actual_pages = {
        path.relative_to(output / "content").as_posix()
        for path in (output / "content").rglob("*.md")
    }
    if actual_pages != expected_pages:
        raise ProjectionError(
            f"Unexpected qri page closure: {sorted(actual_pages)}"
        )
    if any("organizations/" in page for page in actual_pages):
        raise ProjectionError("The organization must remain graph-only")
    return {
        "records": len(records),
        "canonical_records": len(CANONICAL_PIDS),
        "reference_records": len(REFERENCE_PIDS),
        "generated_records": 0,
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "pages": len(actual_pages),
        "native_edges": sorted([list(pair) for pair in edge_pairs]),
    }


def files_below(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != ".DS_Store":
            yield path


def input_files() -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    site_roots = [
        SITE / "config" / "con",
        PROFILE_ROOT / "editorial",
        PROFILE_ROOT / "metadata",
        PROFILE_ROOT / "provenance",
        PROFILE_ROOT / "assets",
        PROFILE_ROOT / "static",
    ]
    for root in site_roots:
        for path in files_below(root):
            if path.name == "yaroslav-halchenko.jpg":
                continue
            entries.append(
                (f"site/{path.relative_to(SITE).as_posix()}", path)
            )
    for path in (PROFILE_PATH, PROJECTION_SPEC_PATH):
        entries.append((f"site/{path.relative_to(SITE).as_posix()}", path))
    assets_manifest = PROFILE_ROOT / "assets.yaml"
    entries.append(
        (
            f"site/{assets_manifest.relative_to(SITE).as_posix()}",
            assets_manifest,
        )
    )

    upstream_roots = [
        SITE / "config" / "_default",
        SITE / "layouts",
        SITE / "page_templates",
    ]
    for root in upstream_roots:
        for path in files_below(root):
            entries.append(
                (
                    f"upstream/{path.relative_to(SITE).as_posix()}",
                    path,
                )
            )
    graph = SITE / "code" / "pool2graph.py"
    entries.append(("upstream/code/pool2graph.py", graph))
    parent_inputs = (
        ROOT / "pixi.toml",
        ROOT / "pixi.lock",
        ROOT / "provenance" / "upstream-psychoinformatics" / "baseline.yaml",
        ROOT / "tools" / "adapt_upstream_pages.py",
        ROOT / "tools" / "build_con_site.py",
        ROOT / "tools" / "con_assets.py",
        ROOT / "tools" / "con_projection.py",
    )
    for path in parent_inputs:
        entries.append((f"parent/{path.relative_to(ROOT).as_posix()}", path))
    return sorted(set(entries), key=lambda item: item[0])


def declared_component_pins() -> list[tuple[str, str]]:
    profile = load_yaml(PROFILE_PATH)
    components = profile.get("components", {})
    if not isinstance(components, dict):
        raise ProjectionError("Profile components must be a mapping")
    upstream_base = components.get("www_from_model", {}).get("commit")
    if not isinstance(upstream_base, str):
        raise ProjectionError("Profile does not pin the upstream website base")
    return [
        ("www-from-model", upstream_base),
        (
            "things-schemas",
            git_commit(ROOT / "submodules" / "things-schemas"),
        ),
        (
            "dump-things-service",
            git_commit(ROOT / "submodules" / "dump-things-service"),
        ),
        (
            "dump-things-pyclient",
            git_commit(ROOT / "submodules" / "dump-things-pyclient"),
        ),
        (
            "query-things",
            git_commit(ROOT / "submodules" / "query-things"),
        ),
        (
            "things-graph-renderer",
            git_commit(ROOT / "submodules" / "things-graph-renderer"),
        ),
        (
            "congo",
            git_tree_object(SITE, "HEAD:themes/congo"),
        ),
    ]


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def projection_manifest(output: Path) -> str:
    lines = ["# clean-migration projection manifest v1"]
    for label, path in input_files():
        if not path.is_file():
            raise ProjectionError(f"Projection input is absent: {path}")
        lines.append(f"{digest_bytes(path.read_bytes())}  input:{label}")
    for name, commit in declared_component_pins():
        lines.append(
            f"{digest_bytes((commit + chr(10)).encode())}  pin:{name}@{commit}"
        )
    for path in files_below(output):
        if path.name == "SHA256SUMS" or path.name.startswith("qri-cache"):
            continue
        relative = path.relative_to(output).as_posix()
        lines.append(
            f"{digest_bytes(path.read_bytes())}  output:{relative}"
        )
    return "\n".join([lines[0], *sorted(lines[1:])]) + "\n"


def verify_manifest(output: Path) -> None:
    path = output / "SHA256SUMS"
    if not path.is_file():
        raise ProjectionError(f"Committed projection digest is absent: {path}")
    expected = projection_manifest(output)
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise ProjectionError(
            "The committed CON projection is stale; run "
            "`pixi run update-con-projection` after reviewing input changes"
        )


def stack_records(records: list[dict[str, Any]], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(
            json.dumps(
                {
                    "class_name": str(record["schema_type"]).rsplit(":", 1)[-1],
                    "record": record,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def render_projection(output: Path) -> dict[str, Any]:
    if not PROFILE_PATH.is_file() or not PROJECTION_SPEC_PATH.is_file():
        raise ProjectionError(
            "The clean-migration website profile is not checked out"
        )
    profile = load_yaml(PROFILE_PATH)
    verify_declared_pins(profile)
    canonical = source_records(
        PROFILE_ROOT / "metadata" / "records", "canonical"
    )
    references = source_records(
        PROFILE_ROOT / "metadata" / "reference", "reference"
    )
    all_records = canonical + references
    validate_record_contract(all_records)
    roundtrip_records(all_records)

    safe_reset(output)
    if not PROJECTION_ATTRIBUTES.is_file():
        raise ProjectionError(
            f"Projection storage policy is absent: {PROJECTION_ATTRIBUTES}"
        )
    shutil.copy2(PROJECTION_ATTRIBUTES, output / ".gitattributes")
    state = output / ".state"
    state.mkdir()
    with dump_things_service(all_records, state) as url:
        exported = service_export(url, all_records, state)
        (output / "records.jsonl").write_text(
            "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                for record in exported
            ),
            encoding="utf-8",
        )
        render_qri(url, exported, output, state)
    report = validate_projection(exported, output)
    shutil.rmtree(state)
    (output / "SHA256SUMS").write_text(
        projection_manifest(output), encoding="utf-8"
    )
    stack_records(exported, BUILD_ROOT / "records.jsonl")
    report_path = BUILD_ROOT / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def compare_trees(left: Path, right: Path) -> None:
    left_files = {
        path.relative_to(left).as_posix(): path for path in files_below(left)
    }
    right_files = {
        path.relative_to(right).as_posix(): path for path in files_below(right)
    }
    if left_files.keys() != right_files.keys():
        raise ProjectionError(
            "Projection file sets differ: "
            f"left={sorted(left_files)}, right={sorted(right_files)}"
        )
    changed = [
        name
        for name in left_files
        if left_files[name].read_bytes() != right_files[name].read_bytes()
    ]
    if changed:
        raise ProjectionError(
            f"Projection bytes differ for: {', '.join(sorted(changed))}"
        )


def replace_committed(candidate: Path) -> None:
    allowed = {
        ".gitattributes",
        "content",
        "records.jsonl",
        "static",
        "SHA256SUMS",
    }
    present = {path.name for path in candidate.iterdir()}
    if present != allowed:
        raise ProjectionError(
            f"Candidate projection paths are unexpected: {sorted(present)}"
        )
    COMMITTED.mkdir(parents=True, exist_ok=True)
    obsolete_records = COMMITTED / "records"
    if obsolete_records.exists():
        shutil.rmtree(obsolete_records)
    for name in sorted(allowed):
        source = candidate / name
        destination = COMMITTED / name
        if destination.is_dir():
            shutil.rmtree(destination)
        elif destination.exists() or destination.is_symlink():
            destination.unlink()
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument(
        "--output", type=Path, default=BUILD_ROOT / "candidate"
    )
    subparsers.add_parser("update")
    subparsers.add_parser("verify")
    subparsers.add_parser("check-snapshot")
    args = parser.parse_args()
    try:
        if args.command == "render":
            report = render_projection(args.output)
            print(json.dumps(report, sort_keys=True))
        elif args.command == "update":
            candidate = BUILD_ROOT / "update"
            render_projection(candidate)
            replace_committed(candidate)
            verify_manifest(COMMITTED)
            print(f"Updated committed projection at {COMMITTED}")
        elif args.command == "verify":
            first = BUILD_ROOT / "verify-first"
            second = BUILD_ROOT / "verify-second"
            render_projection(first)
            render_projection(second)
            compare_trees(first, second)
            compare_trees(first, COMMITTED)
            verify_manifest(COMMITTED)
            print("Projection rendered twice byte-identically and matches Git")
        elif args.command == "check-snapshot":
            verify_manifest(COMMITTED)
            records = [
                json.loads(line)
                for line in (COMMITTED / "records.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line
            ]
            validate_projection(records, COMMITTED)
            stack_records(records, BUILD_ROOT / "records.jsonl")
            print("Committed projection digest and closure are current")
    except ProjectionError as error:
        print(f"clean-migration projection: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
