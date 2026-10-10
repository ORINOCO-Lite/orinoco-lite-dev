"""Validate Git records and project them through the selected upstream workflow."""
from __future__ import annotations

import hashlib
from importlib.metadata import distributions
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

from .annotations import annotation_root
from .config import WorkspaceConfig
from .errors import ConfigurationError, DriverError
from .integrity import canonical_json_bytes, sha256_file, tree_sha256
from .progress import progress
from .records import joined_records, stored_records
from .schema_conversion import build_format_converters, concise_date_warning
from .www_from_model import resolve_www_from_model

PROJECTION_CONTROL_SIDECAR = ".gitattributes"
FORBIDDEN_BRIDGE_PREDICATES = {
    "dcterms:contributor", "dcterms:creator", "dcterms:relation",
    "schema:about", "schema:member", "schema:memberOf", "schema:subjectOf",
}


def reject_projection_override(workspace: WorkspaceConfig) -> None:
    path = workspace.path("site") / "projection.yaml"
    if path.exists() or path.is_symlink():
        raise ConfigurationError(
            f"Unsupported projection override: {path}. Remove this file; "
            "selection and rendering now follow the pinned German www-from-model "
            "workflow. Keep editorial grouping in site-specific/content."
        )


def _www_from_model_root(workspace, resources_root):
    reject_projection_override(workspace)
    return resolve_www_from_model(workspace.root, resources_root)


def _records(workspace, schema=None):
    records = stored_records(workspace) if schema is None else joined_records(workspace, schema)
    return records, {record["pid"] for record in records}


def _nested_schema_types(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        if isinstance(value.get("schema_type"), str):
            yield value["schema_type"]
        for item in value.values():
            yield from _nested_schema_types(item)
    elif isinstance(value, list):
        for item in value:
            yield from _nested_schema_types(item)


def _record_stream(records):
    return "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                   for record in sorted(records, key=lambda r: (r["schema_type"], r["pid"])))


@progress("Validating metadata with the upstream schema")
def validate_semantics(workspace, resources_root, www_from_model_root=None):
    from linkml_runtime import SchemaView
    from .upstream_projection import homepage_pid, render_graph
    reject_projection_override(workspace)
    presentation = www_from_model_root or _www_from_model_root(workspace, resources_root)
    schema = resources_root / "schema/demo-research-information/unreleased.yaml"
    records, pids = _records(workspace, schema)
    if not pids or len(pids) != len(records):
        raise DriverError("Projection metadata PIDs must be unique and non-empty")
    if homepage_pid(presentation) not in pids:
        raise DriverError("Upstream homepage is not a metadata record")
    view = SchemaView(str(schema))
    accepted = {str(view.get_uri(name, expand=False)) for name in view.all_classes()}
    try:
        (writer,) = build_format_converters(schema, writer_only=True)
    except Exception as error:
        raise DriverError("Could not initialize semantic schema conversion") from error
    with concise_date_warning():
        for record in records:
            pid = record["pid"]
            for schema_type in _nested_schema_types(record):
                if schema_type not in accepted:
                    raise DriverError(f"{pid}: unknown CURIE schema type {schema_type}")
            for attribute in record.get("attributes", []):
                if isinstance(attribute, dict) and attribute.get("predicate") in FORBIDDEN_BRIDGE_PREDICATES:
                    raise DriverError(f"{pid}: relationship encoded as AttributeSpecification")
            try:
                writer.convert(record, record["schema_type"].rsplit(":", 1)[-1])
            except Exception as error:
                raise DriverError(f"{pid}: JSON/RDF schema validation failed: {error}") from error
    # The upstream graph producer owns graph selection and missing-target behavior.
    graph = json.loads(render_graph(_record_stream(stored_records(workspace)), presentation))
    return {"records": len(records), "graph_nodes": len(graph["nodes"]),
            "graph_edges": len(graph["edges"])}


@progress("Checking projection inputs")
def _projection_cache_key(
    workspace: WorkspaceConfig,
    presentation: Path,
    resources_root: Path,
) -> str | None:
    """Hash projection inputs, not editorial content or deployment settings."""
    roots = [
        workspace.path("records"),
        annotation_root(workspace),
        presentation / ".forgejo/workflows/update-from-pool.yaml",
        presentation / "page_templates",
        presentation / "code",
        resources_root / "schema",
    ]
    roots.extend(sorted(Path(__file__).parent.glob("*.py")))
    digest = hashlib.sha256()
    installed = list(distributions())
    digest.update(canonical_json_bytes({
        "format": 3,
        "python": list(sys.version_info[:3]),
        "dependencies": sorted((d.metadata["Name"], d.version) for d in installed),
    }))
    # Editable dependency versions do not change with working-tree edits.
    # Git supplies their source file set, including new, non-ignored files.
    # The package itself is covered by the Python and resource roots above.
    for dependency in sorted(installed, key=lambda d: d.metadata["Name"]):
        if dependency.metadata["Name"].lower().replace("_", "-") == "orinoco-lite":
            continue
        raw = dependency.read_text("direct_url.json")
        if not raw:
            continue
        source = json.loads(raw)
        if not source.get("dir_info", {}).get("editable"):
            continue
        url = urlsplit(source["url"])
        checkout = Path(unquote(url.path))
        if url.scheme != "file" or not checkout.is_dir():
            return None
        try:
            files = subprocess.run(
                ["git", "-C", str(checkout), "ls-files", "-z", "--cached",
                 "--others", "--exclude-standard"],
                capture_output=True, check=False,
            )
        except OSError:
            return None
        if files.returncode:
            return None  # Unenumerated editable sources must never reuse validation.
        digest.update(dependency.metadata["Name"].encode() + b"\0")
        for name in sorted(set(files.stdout.split(b"\0")) - {b""}):
            path = checkout / os.fsdecode(name)
            if path.is_dir():
                return None  # Nested source repositories need their own enumeration.
            digest.update(name + b"\0")
            digest.update(sha256_file(path).encode() if path.is_file() else b"missing")
            digest.update(b"\0")
    for root in roots:
        if root.is_file():
            digest.update(b"file\0" + root.read_bytes() + b"\0")
        elif root.is_dir():
            digest.update(b"tree\0" + tree_sha256(root).encode() + b"\0")
        else:
            digest.update(b"missing\0")
    return digest.hexdigest()


@progress("Projecting records with the upstream workflow and temporary Pool")
def render_projection(workspace, resources_root, output, *, records_input=None,
                      www_from_model_root=None):
    from .upstream_projection import run_upstream
    if records_input is not None:
        from .record_stages import _check_record_input
        _check_record_input(records_input)
    reject_projection_override(workspace)
    presentation = www_from_model_root or _www_from_model_root(workspace, resources_root)
    if records_input is None:
        report = validate_semantics(workspace, resources_root, presentation)
        records, pids = _records(workspace)
        joined, joined_pids = _records(workspace, resources_root / "schema/demo-research-information/unreleased.yaml")
        if pids != joined_pids:
            raise DriverError("Joined projection changed the metadata record inventory")
    else:
        from .record_stages import _check_record_input
        from .upstream_snapshot import load_jsonl
        _check_record_input(records_input)
        records = [item.record for item in load_jsonl(records_input)]
        joined = records
        report = {"records": len(records)}
    with tempfile.TemporaryDirectory(prefix="orinoco-projection-input-") as temporary:
        source = Path(temporary) / "records.jsonl"
        source.write_text(_record_stream(joined))
        result = run_upstream(source, presentation, output, resources_root=resources_root)
    # Retain complete records in the Pool and exported record stream.
    (output / "records.jsonl").write_text(_record_stream(joined))
    return {**report, "pages": result["pages"]}


def _cached_projection_report(workspace, key):
    if key is None:
        return None
    destination = workspace.path("build") / "hugo-projection"
    if destination.is_dir():
        try:
            saved = json.loads((destination.parent / ".projection-cache.json").read_text(encoding="utf-8"))
            if (saved["key"] == key
                    and saved["output"] == tree_sha256(destination)
                    and isinstance(saved["report"], dict)):
                return saved["report"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return None


def validate_inputs(workspace, resources_root, *, no_cache=False):
    """Check semantic inputs without generating a projection or website."""
    www_from_model = _www_from_model_root(workspace, resources_root)

    if not no_cache:
        report = _cached_projection_report(
            workspace, _projection_cache_key(workspace, www_from_model, resources_root),
        )
        if report is not None:
            print("Reusing unchanged semantic validation", file=sys.stderr)
            return report
    return validate_semantics(workspace, resources_root, www_from_model)


def update_projection(
    workspace: WorkspaceConfig, resources_root: Path, *, no_cache: bool = False,
) -> dict[str, Any]:
    destination = workspace.path("build") / "hugo-projection"
    destination.parent.mkdir(parents=True, exist_ok=True)
    www_from_model = _www_from_model_root(workspace, resources_root)
    key = None if no_cache else _projection_cache_key(workspace, www_from_model, resources_root)
    cache = destination.parent / ".projection-cache.json"
    if not no_cache:
        report = _cached_projection_report(workspace, key)
        if report is not None:
            print("Reusing unchanged projection (including semantic validation)", file=sys.stderr)
            return report
    staging = Path(
        tempfile.mkdtemp(prefix=".projection-staging-", dir=destination.parent)
    )
    backup = Path(
        tempfile.mkdtemp(prefix=".projection-backup-", dir=destination.parent)
    )
    backup.rmdir()
    moved_original = False
    installed = False
    preserve_backup = False
    try:
        report = render_projection(workspace, resources_root, staging)
        control_sidecar = destination / PROJECTION_CONTROL_SIDECAR
        if control_sidecar.exists() or control_sidecar.is_symlink():
            if control_sidecar.is_symlink() or not control_sidecar.is_file():
                raise DriverError(
                    "Projection control sidecar must be a regular file: "
                    f"{control_sidecar}"
                )
            shutil.copyfile(control_sidecar, staging / PROJECTION_CONTROL_SIDECAR)
        historical = destination / "provenance"
        if historical.is_dir():
            shutil.copytree(historical, staging / "provenance")
        if destination.exists():
            os.replace(destination, backup)
            moved_original = True
        os.replace(staging, destination)
        installed = True
    except BaseException as install_error:
        try:
            if installed and destination.exists():
                shutil.rmtree(destination)
            if moved_original and backup.exists():
                os.replace(backup, destination)
        except BaseException as rollback_error:
            preserve_backup = backup.exists()
            recovery = str(backup) if preserve_backup else "unavailable"
            raise DriverError(
                "Projection installation and rollback both failed; "
                f"the original is preserved at {recovery}"
            ) from rollback_error
        raise install_error
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists() and not preserve_backup:
            shutil.rmtree(backup)
    # This is disposable cache state, never a canonical input or publication record.
    try:
        if key is None:
            cache.unlink(missing_ok=True)
        else:
            cache.write_bytes(canonical_json_bytes({
                "key": key, "output": tree_sha256(destination), "report": report,
            }))
    except OSError:
        pass
    return report
