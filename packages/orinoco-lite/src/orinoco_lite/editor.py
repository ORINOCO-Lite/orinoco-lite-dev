"""Content-neutral static editor binding and flattened review bundles."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence

import yaml

from .annotations import (
    companion_sources,
    reconcile_annotation_companion,
    validate_stored_record,
)
from .canonical import canonical_yaml
from .config import WorkspaceConfig, load_config_path
from .errors import ConfigurationError, DriverError
from .records import record_sources
from .schema_conversion import build_format_converters


CATALOG_FORMAT = "orinoco-static-record-sources"
BUNDLE_FORMAT = "orinoco-shacl-review-bundle"
VERSION = 2
MAX_BUNDLE_BYTES = 10 * 1024 * 1024
MAX_RECORDS = 50
APPLY_REPORT_FORMAT = "orinoco-editor-apply-report"
APPLY_REPORT_VERSION = 1
BUNDLE_RECORD_KEYS = {
    "pid",
    "rdf_turtle",
    "schema_type",
    "source_path",
    "source_sha256",
}


def _git_commit(root: Path) -> str:
    if not (root / ".git").exists():
        return "0" * 40
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD^{commit}"],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    if result.returncode:
        unborn = subprocess.run(
            ["git", "-C", str(root), "symbolic-ref", "--quiet", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if unborn.returncode == 0 and unborn.stdout.strip().startswith("refs/heads/"):
            return "0" * 40
    if result.returncode or len(value) != 40 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise DriverError("Could not resolve the consumer source commit")
    return value


def record_catalog(workspace: WorkspaceConfig) -> dict[str, Any]:
    """Return coordinates for records editable under the projection plan."""

    # Import here so projection and editor can share record loading without a
    # module cycle. Editability is declarative, never inferred from a second
    # filesystem category.
    from .projection import load_contract

    contract = load_contract(workspace)
    editable_classes = set(contract.pages) | set(contract.graph_node_classes)

    records = [
        {key: source[key] for key in ("path", "pid", "schema_type", "sha256")}
        for source in record_sources(workspace)
        if source["pid"] == contract.homepage_pid
        or source["schema_type"] in editable_classes
    ]
    return {
        "format": CATALOG_FORMAT,
        "records": records,
        "source_commit": _git_commit(workspace.root),
        "version": VERSION,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _editor_config(
    workspace: WorkspaceConfig,
    *,
    repository: str | None = None,
    service_origin: str | None = None,
) -> dict[str, Any]:
    resolved_repository = repository or workspace.repository
    resolved_service = service_origin or workspace.curation_service
    github_handoff = resolved_repository is not None
    config: dict[str, Any] = {
        "app_name": f"{workspace.site_name} metadata review",
        "class_url": "dlschemas_owl.ttl",
        "data_url": "records.ttl",
        "external_config_url": "config_default_xyzri.yaml",
        "front_page_content": (
            "Edit a public record, validate it, then download a review bundle. "
            + (
                "You may also explicitly propose the same bundle through GitHub. "
                if github_handoff
                else ""
            )
            + "This static editor receives no authentication credential."
        ),
        "page_title": f"{workspace.site_name} metadata review",
        "priority_classes": [
            {
                "class": "dlthings:Thing",
                "icon": "mdi-view-list",
                "include_subclasses": True,
                "title": "All",
            }
        ],
        "review_bundle_catalog": "data/record-sources.json",
        "review_bundle_mode": "patch-download",
        "shapes_url": "dlschemas_shacl.ttl",
        "use_default_classes": False,
        "use_default_data": False,
        "use_default_shapes": False,
        "use_service": False,
        "use_token": False,
    }
    if github_handoff:
        config["review_bundle_proposal"] = {
            "repository": resolved_repository,
            "service_origin": resolved_service,
        }
    return config


def _converters(schema: Path):
    if schema.is_symlink() or not schema.is_file():
        raise DriverError("Runtime does not contain the pinned editor schema")
    try:
        return build_format_converters(schema)
    except ImportError as error:
        raise DriverError(
            "The editor requires the locked dump-things-service conversion dependency"
        ) from error
    except Exception as error:
        raise DriverError("Could not load the pinned editor schema") from error


def _canonical_rdf(value: str, *, record_pid: str) -> str:
    try:
        from rdflib import BNode, Graph
        from rdflib.compare import to_canonical_graph

        graph = Graph()
        graph.parse(data=value, format="turtle")
        canonical = to_canonical_graph(graph)
        namespace = "r" + hashlib.sha256(record_pid.encode("utf-8")).hexdigest()[:24]
        relabeled = Graph()
        blank_nodes: dict[BNode, BNode] = {}

        def scoped(term):
            if not isinstance(term, BNode):
                return term
            return blank_nodes.setdefault(
                term,
                BNode(f"{namespace}_{term}"),
            )

        for subject, predicate, object_ in canonical:
            relabeled.add((scoped(subject), predicate, scoped(object_)))
        serialized = relabeled.serialize(format="nt")
    except Exception as error:
        raise DriverError("Could not canonicalize record RDF") from error
    return "\n".join(sorted(line for line in serialized.splitlines() if line.strip())) + "\n"


def _render_rdf_sources(
    sources: Sequence[Mapping[str, str]],
    converter: Any,
) -> tuple[dict[str, str], str]:
    per_record: dict[str, str] = {}
    combined_lines: set[str] = set()
    for source in sources:
        record = yaml.safe_load(source["content"])
        class_name = source["schema_type"].rsplit(":", 1)[-1]
        try:
            rendered = converter.convert(record, class_name)
            if not isinstance(rendered, str):
                raise TypeError("converter did not return Turtle")
            canonical = _canonical_rdf(rendered, record_pid=source["pid"])
            per_record[source["pid"]] = canonical
            combined_lines.update(canonical.splitlines())
        except Exception as error:
            raise DriverError(
                f"Could not bind editor RDF for {source['pid']}: {error}"
            ) from error
    combined = "\n".join(sorted(line for line in combined_lines if line.strip())) + "\n"
    return per_record, combined


def bind_editor(
    workspace: WorkspaceConfig,
    runtime_root: Path,
    destination: Path,
    *,
    repository: str | None = None,
    service_origin: str | None = None,
) -> dict[str, Any]:
    from .projection import load_contract

    shell = runtime_root / "editor-shell"
    if not shell.is_dir() or not (shell / "index.html").is_file():
        raise DriverError("Runtime does not contain the generic static editor shell")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(shell, destination)
    for name in (
        "dlschemas_owl.ttl",
        "dlschemas_shacl.ttl",
        "config_default_xyzri.yaml",
    ):
        source = runtime_root / "editor-schema" / name
        if not source.is_file():
            raise DriverError(f"Runtime editor schema resource is missing: {name}")
        shutil.copyfile(source, destination / name)

    contract = load_contract(workspace)
    all_sources = record_sources(workspace)
    catalog = record_catalog(workspace)
    if contract.editor_record_scope == "editable":
        editable_pids = {entry["pid"] for entry in catalog["records"]}
        sources = [source for source in all_sources if source["pid"] in editable_pids]
    else:
        sources = all_sources
    json_to_rdf, _ = _converters(
        runtime_root / "schema/demo-research-information/unreleased.yaml"
    )
    record_rdf, combined_rdf = _render_rdf_sources(sources, json_to_rdf)
    for entry in catalog["records"]:
        entry["rdf_turtle"] = record_rdf[entry["pid"]]
    (destination / "data").mkdir(exist_ok=True)
    _write_json(destination / "data/record-sources.json", catalog)
    _write_json(
        destination / "config.json",
        _editor_config(
            workspace,
            repository=repository,
            service_origin=service_origin,
        ),
    )
    (destination / "records.ttl").write_text(combined_rdf, encoding="utf-8")
    return {
        "catalog_format": CATALOG_FORMAT,
        "editable_records": len(catalog["records"]),
        "loaded_records": len(sources),
        "record_scope": contract.editor_record_scope,
        "source_commit": catalog["source_commit"],
        "source_records": len(all_sources),
        "version": VERSION,
    }


def _read_bundle(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BUNDLE_BYTES:
        raise DriverError("Review bundle must be a regular JSON file no larger than 10 MiB")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DriverError("Review bundle is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise DriverError("Review bundle must be a JSON object")
    if (
        value.get("format") != BUNDLE_FORMAT
        or value.get("version") != VERSION
        or not isinstance(value.get("source_commit"), str)
        or not isinstance(value.get("records"), list)
        or not 0 < len(value["records"]) <= MAX_RECORDS
    ):
        raise DriverError("Review bundle does not satisfy version 2")
    return value


def _git_status(root: Path) -> set[str]:
    if not (root / ".git").exists():
        return set()
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise DriverError("Could not inspect the consumer worktree status")
    entries = result.stdout.split("\0")
    changed: set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4 or entry[2] != " ":
            raise DriverError("Consumer worktree status is malformed")
        status = entry[:2]
        changed.add(entry[3:])
        if "R" in status or "C" in status:
            if index >= len(entries) or not entries[index]:
                raise DriverError("Consumer worktree rename status is malformed")
            changed.add(entries[index])
            index += 1
    return changed


def validate_bundle(
    workspace: WorkspaceConfig,
    runtime_root: Path,
    bundle: Mapping[str, Any],
) -> dict[Path, str]:
    catalog = record_catalog(workspace)
    if bundle["source_commit"] != catalog["source_commit"]:
        raise DriverError("Review bundle is stale for the current consumer commit")
    by_pid = {entry["pid"]: entry for entry in catalog["records"]}
    dirty = _git_status(workspace.root)
    companions = {
        source.record_path.resolve(): source
        for source in companion_sources(workspace)
    }
    _, rdf_to_json = _converters(
        runtime_root / "schema/demo-research-information/unreleased.yaml"
    )
    updates: dict[Path, str] = {}
    seen: set[str] = set()
    for item in bundle["records"]:
        if not isinstance(item, dict) or set(item) != BUNDLE_RECORD_KEYS:
            raise DriverError("Review bundle record has unexpected fields")
        pid = item.get("pid")
        if pid in seen:
            raise DriverError(f"Review bundle contains duplicate PID: {pid}")
        if not isinstance(pid, str):
            raise DriverError("Review bundle record PID must be a string")
        seen.add(pid)
        source = by_pid.get(pid)
        if source is None:
            raise DriverError(f"Review bundle PID is not in metadata/records: {pid}")
        source_path = item.get("source_path")
        relative = PurePosixPath(source_path) if isinstance(source_path, str) else None
        if (
            relative is None
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != source_path
            or source_path != source["path"]
        ):
            raise DriverError(f"Review bundle source path does not match {pid}")
        path = workspace.root.joinpath(*relative.parts)
        if source_path in dirty:
            raise DriverError(f"Metadata source has a conflicting local change: {source_path}")
        if item.get("source_sha256") != source["sha256"]:
            raise DriverError(f"Review bundle source digest is stale for {pid}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != item.get("source_sha256"):
            raise DriverError(f"Review bundle source digest is stale for {pid}")
        if item.get("schema_type") != source["schema_type"]:
            raise DriverError(f"Review bundle schema type does not match {pid}")
        rdf_turtle = item.get("rdf_turtle")
        if not isinstance(rdf_turtle, str) or not rdf_turtle.strip():
            raise DriverError(f"Review bundle RDF is missing for {pid}")
        try:
            # Parsing before schema conversion rejects malformed RDF without
            # permitting network retrieval or filesystem references.
            _canonical_rdf(rdf_turtle, record_pid=pid)
            class_name = source["schema_type"].rsplit(":", 1)[-1]
            record = rdf_to_json.convert(rdf_turtle, class_name)
        except Exception as error:
            raise DriverError(f"Review bundle RDF is invalid for {pid}: {error}") from error
        if not isinstance(record, dict):
            raise DriverError(f"Review bundle conversion failed for {pid}")
        if record.get("pid") != pid or record.get("schema_type") != source["schema_type"]:
            raise DriverError(f"Review bundle changed record identity: {pid}")
        validate_stored_record(record)
        updates[path] = canonical_yaml(record)

        companion = companions.get(path.resolve())
        if companion is not None:
            companion_relative = companion.path.relative_to(workspace.root).as_posix()
            if companion_relative in dirty:
                raise DriverError(
                    "Annotation companion has a conflicting local change: "
                    f"{companion_relative}"
                )
            reconciled = reconcile_annotation_companion(record, companion.value)
            rendered_companion = canonical_yaml(reconciled)
            if companion.path.read_text(encoding="utf-8") != rendered_companion:
                updates[companion.path] = rendered_companion
    return updates


def _atomic_apply(updates: Mapping[Path, str]) -> None:
    """Replace one or more records as a rollback-capable transaction."""

    staged: dict[Path, Path] = {}
    backups: dict[Path, bytes] = {}
    replaced: list[Path] = []
    try:
        for source, content in updates.items():
            backups[source] = source.read_bytes()
            descriptor, name = tempfile.mkstemp(
                prefix=f".{source.name}.", suffix=".staged", dir=source.parent
            )
            temporary = Path(name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            staged[source] = temporary
        for source in sorted(staged):
            os.replace(staged[source], source)
            replaced.append(source)
        for source, content in updates.items():
            if yaml.safe_load(source.read_text(encoding="utf-8")) != yaml.safe_load(content):
                raise DriverError(f"Canonical source post-write validation failed: {source}")
        for source in updates:
            directory = os.open(source.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except BaseException:
        for source in reversed(replaced):
            descriptor, name = tempfile.mkstemp(
                prefix=f".{source.name}.", suffix=".rollback", dir=source.parent
            )
            rollback = Path(name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(backups[source])
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(rollback, source)
            finally:
                rollback.unlink(missing_ok=True)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def apply_bundle_report(
    workspace: WorkspaceConfig,
    runtime_root: Path,
    path: Path,
    *,
    write: bool,
) -> dict[str, Any]:
    updates = validate_bundle(workspace, runtime_root, _read_bundle(path))
    chunks: list[str] = []
    for source, content in sorted(updates.items()):
        before = source.read_text(encoding="utf-8")
        relative = source.relative_to(workspace.root).as_posix()
        chunks.extend(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
            )
        )
    difference = "".join(chunks)
    if write:
        _atomic_apply(updates)
    changed_paths = [
        source.relative_to(workspace.root).as_posix()
        for source, content in sorted(updates.items())
        if source.read_text(encoding="utf-8") != content
    ]
    # After a successful write the source bytes now equal ``content``. Derive
    # changed paths from the reviewed diff in that mode instead.
    if write:
        changed_paths = [
            line.removeprefix("+++ b/").strip()
            for line in difference.splitlines()
            if line.startswith("+++ b/")
        ]
    return {
        "applied": write,
        "changed_paths": changed_paths,
        "diff": difference,
        "format": APPLY_REPORT_FORMAT,
        "validated_records": sum(
            1
            for source in updates
            if source == workspace.path("records")
            or workspace.path("records") in source.parents
        ),
        "version": APPLY_REPORT_VERSION,
    }


def apply_bundle(
    workspace: WorkspaceConfig,
    runtime_root: Path,
    path: Path,
    *,
    write: bool,
) -> str:
    """Compatibility API returning only the reviewed unified difference."""

    return apply_bundle_report(
        workspace, runtime_root, path, write=write
    )["diff"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        workspace = load_config_path(args.config)
        report = apply_bundle_report(
            workspace, args.runtime.resolve(), args.bundle, write=args.write
        )
    except (ConfigurationError, DriverError) as error:
        print(f"orinoco editor: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
