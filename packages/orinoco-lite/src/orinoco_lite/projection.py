"""Generic semantic validation and deterministic flattened-site projection."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence

from jinja2 import Environment, FileSystemLoader
from linkml_runtime import SchemaView
import yaml

from .annotations import (
    PAV_IMPORTED_BY,
    PAV_IMPORTED_FROM,
    annotation_semantic_view,
    annotation_root,
    assertion_sha256,
)
from .config import WorkspaceConfig
from .errors import ConfigurationError, DriverError
from .integrity import sha256_file
from .records import joined_records, stored_records
from .schema_conversion import build_format_converters


MANIFEST_HEADER = "# orinoco-lite projection manifest v3"
PROJECTION_ALGORITHM = "orinoco-projection-v3"
PROJECTION_CONTROL_SIDECAR = ".gitattributes"
FORBIDDEN_BRIDGE_PREDICATES = {
    "dcterms:contributor",
    "dcterms:creator",
    "dcterms:relation",
    "schema:about",
    "schema:member",
    "schema:memberOf",
    "schema:subjectOf",
}
SEMANTIC_IDENTIFIER_FIELDS = {
    "about",
    "alternate_of",
    "annotation_tag",
    "associated_with",
    "attributed_to",
    "broad_mappings",
    "creator",
    "defined_by",
    "delegated_by",
    "depends_on",
    "derived_from",
    "exact_mappings",
    "generated_by",
    "influenced_by",
    "kind",
    "narrow_mappings",
    "object",
    "part_of",
    "pid",
    "predicate",
    "quoted_from",
    "related_mappings",
    "revision_of",
    "roles",
    "rules",
    "schema_type",
    "specialization_of",
    "unit",
}


def _is_projection_control_sidecar(output: Path, path: Path) -> bool:
    """Recognize the one reviewed, non-generated projection control file."""

    return (
        not path.is_symlink()
        and path.is_file()
        and path.relative_to(output).as_posix() == PROJECTION_CONTROL_SIDECAR
    )


def _is_historical_provenance(output: Path, path: Path) -> bool:
    """Identify only the preserved top-level projection evidence directory."""

    relative = path.relative_to(output)
    return bool(relative.parts) and relative.parts[0] == "provenance"


@dataclass(frozen=True)
class RenderPolicy:
    template: Path
    select: Mapping[str, Mapping[str, Any]]
    inline: tuple[str, ...]
    reverse_injections: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ProjectionContract:
    path: Path
    route_prefix: str
    homepage_pid: str
    homepage: RenderPolicy
    pages: Mapping[str, RenderPolicy]
    unrendered_classes: frozenset[str]
    graph_producer: Path
    graph_node_classes: frozenset[str]
    relationship_fields: tuple[str, ...]
    missing_reference_targets: str
    missing_graph_targets: str
    editor_record_scope: str


def _relative(workspace: WorkspaceConfig, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ConfigurationError(f"{label} must be a repository-relative POSIX path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != value:
        raise ConfigurationError(f"{label} must be a normalized safe path")
    path = workspace.root.joinpath(*relative.parts)
    root = workspace.root.resolve()
    resolved = path.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ConfigurationError(f"{label} escapes the consumer repository")
    return path


def load_contract(workspace: WorkspaceConfig) -> ProjectionContract:
    path = workspace.path("site") / "projection.yaml"
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Projection contract is invalid: {path}") from error
    if not isinstance(value, dict) or value.get("version") != 2:
        raise ConfigurationError("Projection contract must be version 2")
    homepage = value.get("homepage")
    pages = value.get("pages")
    unrendered = value.get("unrendered_classes")
    graph = value.get("graph")
    routing = value.get("routing")
    references = value.get("references", {"missing_targets": "preserve"})
    editor = value.get("editor", {"record_scope": "all"})
    if (
        not isinstance(homepage, dict)
        or not isinstance(pages, dict)
        or not pages
        or not isinstance(unrendered, list)
        or not isinstance(graph, dict)
        or not isinstance(routing, dict)
        or not isinstance(references, dict)
        or not isinstance(editor, dict)
        or set(routing) != {"strip_prefix"}
        or set(references) != {"missing_targets"}
        or set(editor) != {"record_scope"}
    ):
        raise ConfigurationError("Projection contract sections are malformed")
    route_prefix = routing.get("strip_prefix")
    homepage_pid = homepage.get("pid")
    node_classes = graph.get("node_classes")
    relationships = graph.get("relationship_fields")
    missing_graph_targets = graph.get("missing_external_targets", "drop")
    if (
        not isinstance(homepage_pid, str)
        or not isinstance(route_prefix, str)
        or not route_prefix
        or not isinstance(node_classes, list)
        or not isinstance(relationships, list)
        or references.get("missing_targets") not in {"preserve", "reject"}
        or missing_graph_targets not in {"drop", "reject"}
        or editor.get("record_scope") not in {"all", "editable"}
        or not all(isinstance(item, str) and item for item in node_classes)
        or not all(isinstance(item, str) and item for item in relationships)
        or not all(isinstance(item, str) and item for item in unrendered)
    ):
        raise ConfigurationError("Projection identity/graph policy is malformed")
    def policy(raw: object, label: str) -> RenderPolicy:
        if not isinstance(raw, dict):
            raise ConfigurationError(f"{label} must be a declarative render policy")
        unknown = set(raw) - {
            "pid",
            "template",
            "select",
            "inline",
            "reverse_injections",
        }
        if unknown:
            raise ConfigurationError(f"{label} has unknown operations: {sorted(unknown)}")
        select = raw.get("select", {})
        inline = raw.get("inline", [])
        reverse = raw.get("reverse_injections", [])
        if not isinstance(select, dict) or set(select) - {"linked_from", "links_to"}:
            raise ConfigurationError(f"{label}.select is unsupported")
        if len(select) > 1 or not all(isinstance(item, dict) for item in select.values()):
            raise ConfigurationError(f"{label}.select must contain at most one operator")
        for operator, arguments in select.items():
            required = {"pid", "field"}
            permitted = required | ({"recursive"} if operator == "links_to" else set())
            if (
                set(arguments) - permitted
                or not required <= set(arguments)
                or not isinstance(arguments.get("pid"), str)
                or not isinstance(arguments.get("field"), str)
                or (
                    "recursive" in arguments
                    and not isinstance(arguments["recursive"], bool)
                )
            ):
                raise ConfigurationError(f"{label}.select.{operator} is malformed")
        if not isinstance(inline, list) or not all(
            isinstance(item, str)
            and item
            and all(component for component in item.split("::"))
            for item in inline
        ):
            raise ConfigurationError(f"{label}.inline is malformed")
        normalized_reverse: list[tuple[str, str]] = []
        if not isinstance(reverse, list):
            raise ConfigurationError(f"{label}.reverse_injections is malformed")
        for item in reverse:
            if (
                not isinstance(item, dict)
                or set(item) != {"from", "to"}
                or not all(isinstance(item[key], str) and item[key] for key in item)
            ):
                raise ConfigurationError(f"{label}.reverse_injections is malformed")
            normalized_reverse.append((item["from"], item["to"]))
        return RenderPolicy(
            template=_relative(workspace, raw.get("template"), f"{label}.template"),
            select=select,
            inline=tuple(inline),
            reverse_injections=tuple(normalized_reverse),
        )

    page_policies: dict[str, RenderPolicy] = {}
    for schema_type, raw_policy in pages.items():
        if not isinstance(schema_type, str) or not schema_type:
            raise ConfigurationError("Projection page class is malformed")
        page_policies[schema_type] = policy(raw_policy, f"pages.{schema_type}")
    contract = ProjectionContract(
        path=path,
        route_prefix=route_prefix,
        homepage_pid=homepage_pid,
        homepage=policy(homepage, "homepage"),
        pages=page_policies,
        unrendered_classes=frozenset(unrendered),
        graph_producer=_relative(workspace, graph.get("producer"), "graph.producer"),
        graph_node_classes=frozenset(node_classes),
        relationship_fields=tuple(relationships),
        missing_reference_targets=references["missing_targets"],
        missing_graph_targets=missing_graph_targets,
        editor_record_scope=editor["record_scope"],
    )
    for required in [
        contract.homepage.template,
        contract.graph_producer,
        *(policy.template for policy in contract.pages.values()),
    ]:
        if required.is_symlink() or not required.is_file():
            raise ConfigurationError(f"Projection input is missing: {required}")
    return contract


def _nested_schema_types(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        schema_type = value.get("schema_type")
        if isinstance(schema_type, str):
            yield schema_type
        for child in value.values():
            yield from _nested_schema_types(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nested_schema_types(child)


def _relationship_targets(record: Mapping[str, Any], field: str) -> Iterable[str]:
    values = record.get(field, [])
    if values is None:
        return
    if not isinstance(values, list):
        values = [values]
    for value in values:
        if isinstance(value, dict) and value.get("object") is None:
            # LinkML permits a qualified relationship object to carry context
            # (for example, a role) without asserting its optional target.
            continue
        target = value.get("object") if isinstance(value, dict) else value
        targets = target if isinstance(target, list) else [target]
        if not all(isinstance(item, str) and item for item in targets):
            raise DriverError(f"{record.get('pid')}: malformed {field} target")
        yield from targets


def _targetless_relationship_contexts(
    record: Mapping[str, Any],
    field: str,
) -> int:
    """Count qualified relationship contexts with no optional object target."""

    values = record.get(field, [])
    if values is None:
        return 0
    if not isinstance(values, list):
        values = [values]
    return sum(
        isinstance(value, Mapping) and value.get("object") is None
        for value in values
    )


def _record_links(
    record: Mapping[str, Any], fields: Sequence[str]
) -> Iterable[tuple[str, str]]:
    """Yield every reference recognized by the Lite projection contract."""

    for field in fields:
        yield from ((field, target) for target in _relationship_targets(record, field))
        values = record.get(field, [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if isinstance(value, dict):
                roles = value.get("roles", [])
                if not isinstance(roles, list):
                    roles = [roles]
                for role in roles:
                    if not isinstance(role, str) or not role:
                        raise DriverError(f"{record.get('pid')}: malformed {field}.roles")
                    yield f"{field}.roles", role
    for field in ("kind", "rules"):
        values = record.get(field, [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            target = value.get("object") if isinstance(value, dict) else value
            if not isinstance(target, str) or not target:
                raise DriverError(f"{record.get('pid')}: malformed {field} target")
            yield field, target
    identifiers = record.get("identifiers", [])
    if not isinstance(identifiers, list):
        identifiers = [identifiers]
    for identifier in identifiers:
        if not isinstance(identifier, dict) or "creator" not in identifier:
            continue
        creators = identifier["creator"]
        if not isinstance(creators, list):
            creators = [creators]
        for creator in creators:
            if not isinstance(creator, str) or not creator:
                raise DriverError(f"{record.get('pid')}: malformed identifiers.creator")
            yield "identifiers.creator", creator


def _all_links(
    record: Mapping[str, Any], fields: Sequence[str]
) -> Iterable[tuple[str, str]]:
    """Yield every reference governed by explicit local-closure policy."""

    yield from _record_links(record, fields)


def _semantic_identifier_view(
    value: Any,
    namespaces: Any | None,
    *,
    identifier_value: bool = False,
) -> Any:
    """Expand recognized CURIE values while retaining ordinary literals."""

    if namespaces is None:
        return deepcopy(value)
    if isinstance(value, Mapping):
        return {
            key: _semantic_identifier_view(
                item,
                namespaces,
                identifier_value=key in SEMANTIC_IDENTIFIER_FIELDS,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _semantic_identifier_view(
                item,
                namespaces,
                identifier_value=identifier_value,
            )
            for item in value
        ]
    if isinstance(value, str) and identifier_value:
        try:
            expanded = namespaces.uri_for(value)
        except (KeyError, ValueError):
            return value
        return str(expanded) if expanded is not None else value
    return deepcopy(value)


def _native_fingerprint(
    value: Any,
    *,
    exclude_root_pid: bool = False,
    namespaces: Any | None = None,
) -> Counter[tuple[str, str]]:
    def unordered(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: unordered(item) for key, item in value.items()}
        if isinstance(value, list):
            items = [unordered(item) for item in value]
            return sorted(
                items,
                key=lambda item: json.dumps(
                    item,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
        return value

    result: Counter[tuple[str, str]] = Counter()
    if isinstance(value, dict):
        schema_type = value.get("schema_type")
        if isinstance(schema_type, str) and schema_type.startswith("dlthings:"):
            semantic = annotation_semantic_view(value)
            if exclude_root_pid:
                semantic.pop("pid", None)
            semantic = _semantic_identifier_view(semantic, namespaces)
            semantic = unordered(semantic)
            result[
                (
                    schema_type,
                    json.dumps(semantic, sort_keys=True, separators=(",", ":")),
                )
            ] += 1
        for child in value.values():
            result.update(_native_fingerprint(child, namespaces=namespaces))
    elif isinstance(value, list):
        for child in value:
            result.update(_native_fingerprint(child, namespaces=namespaces))
    return result


def _same_identifier(namespaces: Any, left: Any, right: Any) -> bool:
    """Compare CURIE/full-URI spellings without weakening raw storage checks."""

    if not isinstance(left, str) or not isinstance(right, str):
        return False

    def expand(value: str) -> str:
        try:
            expanded = namespaces.uri_for(value)
        except (KeyError, ValueError):
            return value
        return str(expanded) if expanded is not None else value

    return expand(left) == expand(right)


def _machine_pav_fingerprint(
    value: Any,
    namespaces: Any | None = None,
) -> Counter[tuple[str, str]]:
    """Bind every joined machine PAV pair to its annotation-free assertion."""

    result: Counter[tuple[str, str]] = Counter()
    if isinstance(value, dict):
        annotations = value.get("annotations")
        if isinstance(annotations, dict) and {
            PAV_IMPORTED_BY,
            PAV_IMPORTED_FROM,
        } <= set(annotations):
            machine = {
                tag: annotations[tag]
                for tag in (PAV_IMPORTED_BY, PAV_IMPORTED_FROM)
            }
            result[
                (
                    assertion_sha256(
                        _semantic_identifier_view(value, namespaces)
                    ),
                    json.dumps(
                        _semantic_identifier_view(machine, namespaces),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                )
            ] += 1
        for child in value.values():
            result.update(_machine_pav_fingerprint(child, namespaces))
    elif isinstance(value, list):
        for child in value:
            result.update(_machine_pav_fingerprint(child, namespaces))
    return result


def _records(
    workspace: WorkspaceConfig,
    schema: Path | None = None,
) -> tuple[list[dict[str, Any]], set[str]]:
    records = (
        stored_records(workspace)
        if schema is None
        else joined_records(workspace, schema)
    )
    return records, {item["pid"] for item in records}


def validate_semantics(
    workspace: WorkspaceConfig,
    runtime_root: Path,
) -> dict[str, Any]:
    contract = load_contract(workspace)
    schema = runtime_root / "schema/demo-research-information/unreleased.yaml"
    records, record_pids = _records(workspace, schema)
    by_pid = {record["pid"]: record for record in records}
    if len(by_pid) != len(records) or not record_pids:
        raise DriverError("Projection metadata PIDs must be unique and non-empty")
    homepage = by_pid.get(contract.homepage_pid)
    if homepage is None:
        raise DriverError("Projection homepage is not a metadata record")
    declared_classes = set(contract.pages) | set(contract.unrendered_classes)
    record_classes = {record["schema_type"] for record in records}
    if not record_classes <= declared_classes:
        raise DriverError(
            "Projection class policy differs from the metadata inventory: "
            f"declared={sorted(declared_classes)}, actual={sorted(record_classes)}"
        )
    schema_view = SchemaView(str(schema))
    accepted = {
        str(schema_view.get_uri(name, expand=False))
        for name in schema_view.all_classes()
    }
    try:
        to_ttl, to_json = build_format_converters(schema)
    except Exception as error:
        raise DriverError("Could not initialize semantic schema conversion") from error
    namespaces = schema_view.namespaces()
    rdf_identifier_normalizations = 0
    missing_references: Counter[str] = Counter()
    missing_reference_targets: set[str] = set()
    targetless_relationships: Counter[str] = Counter()
    for record in records:
        pid = record["pid"]
        for schema_type in _nested_schema_types(record):
            if schema_type.startswith(("http://", "https://")) or schema_type not in accepted:
                raise DriverError(f"{pid}: unknown CURIE schema type {schema_type}")
        for attribute in record.get("attributes", []):
            if isinstance(attribute, dict) and attribute.get("predicate") in FORBIDDEN_BRIDGE_PREDICATES:
                raise DriverError(f"{pid}: relationship encoded as AttributeSpecification")
        links = (
            _record_links(record, contract.relationship_fields)
            if contract.missing_reference_targets == "preserve"
            else _all_links(record, contract.relationship_fields)
        )
        for field, target in links:
            if target not in by_pid:
                if contract.missing_reference_targets == "reject":
                    raise DriverError(f"{pid}: dangling {field} target {target}")
                missing_references[field] += 1
                missing_reference_targets.add(target)
        for field in contract.relationship_fields:
            targetless_relationships[field] += _targetless_relationship_contexts(
                record, field
            )
        try:
            class_name = record["schema_type"].rsplit(":", 1)[-1]
            restored = to_json.convert(to_ttl.convert(record, class_name), class_name)
        except Exception as error:
            raise DriverError(f"{pid}: JSON/RDF/JSON schema validation failed: {error}") from error
        before = Counter(_nested_schema_types(record))
        after = Counter(_nested_schema_types(restored))
        restored_pid = restored.get("pid")
        if not _same_identifier(namespaces, pid, restored_pid):
            raise DriverError(f"{pid}: schema round trip changed record identity")
        if restored_pid != pid:
            rdf_identifier_normalizations += 1
        if (
            any(after[item] < count for item, count in before.items())
            or _native_fingerprint(
                restored,
                exclude_root_pid=True,
                namespaces=namespaces,
            )
            != _native_fingerprint(
                record,
                exclude_root_pid=True,
                namespaces=namespaces,
            )
            or _machine_pav_fingerprint(restored, namespaces)
            != _machine_pav_fingerprint(record, namespaces)
        ):
            raise DriverError(f"{pid}: schema round trip changed native semantics")
    graph_nodes = {
        pid
        for pid in record_pids
        if by_pid[pid]["schema_type"] in contract.graph_node_classes
    }
    graph_edges: set[tuple[str, str]] = set()
    dropped_graph_edges: set[tuple[str, str]] = set()
    dropped_graph_edges_by_field: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for pid in graph_nodes:
        for field in contract.relationship_fields:
            for target in _relationship_targets(by_pid[pid], field):
                if target not in graph_nodes:
                    if contract.missing_graph_targets == "reject":
                        raise DriverError(
                            f"{pid}: graph target does not materialize: {target}"
                        )
                    dropped_graph_edges.add((pid, target))
                    dropped_graph_edges_by_field[field].add((pid, target))
                    continue
                graph_edges.add((pid, target))
    report = {
        "records": len(records),
        "graph_nodes": len(graph_nodes),
        "graph_edges": len(graph_edges),
    }
    if contract.missing_reference_targets == "preserve":
        report["preserved_reference_targets"] = sum(missing_references.values())
        report["preserved_reference_unique_targets"] = len(
            missing_reference_targets
        )
        report["preserved_references_by_field"] = dict(
            sorted(missing_references.items())
        )
    if contract.missing_graph_targets == "drop":
        report["dropped_graph_edges"] = len(dropped_graph_edges)
        report["dropped_graph_edges_by_field"] = {
            field: len(edges)
            for field, edges in sorted(dropped_graph_edges_by_field.items())
        }
    if any(targetless_relationships.values()):
        report["targetless_relationship_contexts"] = sum(
            targetless_relationships.values()
        )
        report["targetless_relationship_contexts_by_field"] = {
            field: count
            for field, count in sorted(targetless_relationships.items())
            if count
        }
    if rdf_identifier_normalizations:
        report["rdf_identifier_normalizations"] = rdf_identifier_normalizations
    return report


def _toyaml(value: Any) -> str:
    return yaml.safe_dump(value, sort_keys=False, default_flow_style=False)


def _inline(value: Any, by_pid: Mapping[str, dict[str, Any]]) -> Any:
    """Resolve terminal PID strings with pinned query-things semantics."""

    if isinstance(value, str):
        if value and ":" in value:
            resolved = by_pid.get(value)
            if resolved is not None:
                return deepcopy(resolved)
        return value
    if isinstance(value, list):
        return [_inline(item, by_pid) for item in value]
    return value


def _walk_inline(
    container: Any,
    path: tuple[str, ...],
    by_pid: Mapping[str, dict[str, Any]],
) -> None:
    """Walk arbitrary dict/list nesting without discarding unmatched values."""

    if not path:
        return
    key = path[0]
    if isinstance(container, dict) and key in container:
        value = container[key]
        if len(path) == 1:
            container[key] = _inline(value, by_pid)
        elif isinstance(value, dict):
            _walk_inline(value, path[1:], by_pid)
        elif isinstance(value, list):
            for item in value:
                _walk_inline(item, path[1:], by_pid)
    elif isinstance(container, list):
        for item in container:
            _walk_inline(item, path, by_pid)


def _incoming(
    records: Sequence[dict[str, Any]], target: str, field: str
) -> list[dict[str, Any]]:
    return [
        deepcopy(record)
        for record in records
        if target in set(_relationship_targets(record, field))
    ]


def _apply_inline(
    record: dict[str, Any], operation: str, by_pid: Mapping[str, dict[str, Any]]
) -> None:
    _walk_inline(record, tuple(operation.split("::")), by_pid)


def _render_record(
    record: dict[str, Any],
    policy: RenderPolicy,
    by_pid: Mapping[str, dict[str, Any]],
    records: Sequence[dict[str, Any]],
) -> str:
    rec = deepcopy(record)
    for source_field, target_field in policy.reverse_injections:
        rec[target_field] = _incoming(records, rec["pid"], source_field)
    for operation in policy.inline:
        _apply_inline(rec, operation, by_pid)
    environment = Environment(
        loader=FileSystemLoader(policy.template.parent),
        autoescape=False,
        keep_trailing_newline=True,
    )
    environment.filters["toyaml"] = _toyaml
    loaded = environment.get_template(policy.template.name)
    props = {
        "__pid_curie_reference": rec["pid"].split(":", 1)[1],
        "__rec": rec,
        **rec,
    }
    try:
        return loaded.render(**props)
    except Exception as error:
        raise DriverError(f"Could not render {record['pid']}: {error}") from error


def _matches_policy(
    record: Mapping[str, Any],
    policy: RenderPolicy,
    by_pid: Mapping[str, dict[str, Any]],
) -> bool:
    if not policy.select:
        return True
    if "linked_from" in policy.select:
        arguments = policy.select["linked_from"]
        source = by_pid.get(arguments["pid"])
        if source is None:
            raise DriverError(f"Projection selector source is missing: {arguments['pid']}")
        return record["pid"] in set(_relationship_targets(source, arguments["field"]))
    arguments = policy.select["links_to"]
    target = arguments["pid"]
    field = arguments["field"]
    recursive = arguments.get("recursive", False)

    def links(candidate: Mapping[str, Any], visited: set[str]) -> bool:
        for linked_pid in _relationship_targets(candidate, field):
            if linked_pid == target:
                return True
            if recursive and linked_pid not in visited and linked_pid in by_pid:
                if links(by_pid[linked_pid], {*visited, linked_pid}):
                    return True
        return False

    return links(record, {record["pid"]})


def _projection_inputs(workspace: WorkspaceConfig, contract: ProjectionContract) -> list[Path]:
    roots = [
        workspace.path("records"),
        contract.path,
        workspace.path("site") / "projection-templates",
        workspace.path("site") / "projection-tools",
    ]
    annotations = annotation_root(workspace)
    if annotations.exists():
        roots.append(annotations)
    paths: list[Path] = []
    for root in roots:
        if root.is_file():
            paths.append(root)
        elif root.is_dir():
            paths.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and not any(
                    part.startswith(".") for part in path.relative_to(root).parts
                )
                and "__pycache__" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}
                and not path.is_symlink()
            )
    return sorted(set(paths))


def _schema_closure_digest(runtime_root: Path) -> str:
    """Digest the localized semantic schema closure, not just its entrypoint."""

    schema_root = runtime_root / "schema"
    inventory_path = schema_root / "source-inventory.json"
    try:
        inventory_bytes = inventory_path.read_bytes()
        inventory = json.loads(inventory_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise DriverError("Runtime schema source inventory is missing or invalid") from error
    sources = inventory.get("sources") if isinstance(inventory, dict) else None
    if not isinstance(sources, list) or not sources:
        raise DriverError("Runtime schema source inventory has no source closure")
    paths: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for source in sources:
        relative = source.get("localized_path") if isinstance(source, dict) else None
        if not isinstance(relative, str) or not relative or relative in seen:
            raise DriverError("Runtime schema source inventory is malformed")
        posix = PurePosixPath(relative)
        if posix.is_absolute() or posix.as_posix() != relative or ".." in posix.parts:
            raise DriverError("Runtime schema source inventory contains an unsafe path")
        path = schema_root.joinpath(*posix.parts)
        if path.is_symlink() or not path.is_file():
            raise DriverError(f"Runtime schema closure source is missing: {relative}")
        seen.add(relative)
        paths.append((relative, path))
    entrypoint = inventory.get("entrypoint")
    if not isinstance(entrypoint, str) or entrypoint not in seen:
        raise DriverError("Runtime schema entrypoint is absent from its source closure")
    digest = hashlib.sha256()
    digest.update(b"orinoco-schema-closure-v1\0")
    digest.update(inventory_bytes)
    for relative, path in sorted(paths):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _route_for_pid(pid: str, prefix: str) -> str:
    if not pid.startswith(prefix):
        raise DriverError(f"Renderable record PID is outside routing.strip_prefix: {pid}")
    route = pid.removeprefix(prefix).strip("/")
    if not route or any(part in {"", ".", ".."} for part in route.split("/")):
        raise DriverError(f"Renderable record has an unsafe route: {pid}")
    return route


def projection_manifest(
    workspace: WorkspaceConfig,
    runtime_root: Path,
    output: Path,
) -> str:
    contract = load_contract(workspace)
    lines: list[str] = []
    for path in _projection_inputs(workspace, contract):
        lines.append(
            f"{sha256_file(path)}  input:{path.relative_to(workspace.root).as_posix()}"
        )
    closure_digest = _schema_closure_digest(runtime_root)
    lines.append(f"{closure_digest}  pin:schema-closure@{closure_digest}")
    lines.append(
        f"{hashlib.sha256((PROJECTION_ALGORITHM + chr(10)).encode()).hexdigest()}  "
        f"pin:algorithm@{PROJECTION_ALGORITHM}"
    )
    for path in sorted(output.rglob("*")):
        if (
            path.is_file()
            and path.name != "SHA256SUMS"
            and not _is_historical_provenance(output, path)
            and not _is_projection_control_sidecar(output, path)
        ):
            lines.append(
                f"{sha256_file(path)}  output:{path.relative_to(output).as_posix()}"
            )
    return "\n".join([MANIFEST_HEADER, *sorted(lines)]) + "\n"


def render_projection(
    workspace: WorkspaceConfig,
    runtime_root: Path,
    output: Path,
) -> dict[str, Any]:
    semantic = validate_semantics(workspace, runtime_root)
    contract = load_contract(workspace)
    records, record_pids = _records(workspace)
    schema = runtime_root / "schema/demo-research-information/unreleased.yaml"
    machine_records, machine_pids = _records(workspace, schema)
    if machine_pids != record_pids:
        raise DriverError("Joined projection changed the metadata record inventory")
    by_pid = {record["pid"]: record for record in records}
    if output.exists():
        shutil.rmtree(output)
    (output / "content").mkdir(parents=True)
    (output / "static").mkdir()
    public_jsonl = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in sorted(
            records, key=lambda item: (item["schema_type"], item["pid"])
        )
    )
    machine_jsonl = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in sorted(
            machine_records, key=lambda item: (item["schema_type"], item["pid"])
        )
    )
    (output / "records.jsonl").write_text(machine_jsonl, encoding="utf-8")
    for pid in sorted(record_pids):
        record = by_pid[pid]
        schema_type = record["schema_type"]
        if pid == contract.homepage_pid:
            policy = contract.homepage
            destination = output / "content" / "_index.md"
        elif schema_type in contract.pages:
            policy = contract.pages[schema_type]
            if not _matches_policy(record, policy, by_pid):
                continue
            route = _route_for_pid(pid, contract.route_prefix)
            destination = output / "content" / route / "_index.md"
        else:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            _render_record(record, policy, by_pid, records), encoding="utf-8"
        )
    graph_result = subprocess.run(
        [sys.executable, str(contract.graph_producer)],
        input=public_jsonl,
        capture_output=True,
        text=True,
        check=False,
    )
    if graph_result.returncode or (
        graph_result.stderr.strip() and contract.missing_graph_targets == "reject"
    ):
        raise DriverError(f"Projection graph failed: {graph_result.stderr.strip()}")
    try:
        graph = json.loads(graph_result.stdout)
    except json.JSONDecodeError as error:
        raise DriverError("Projection graph producer emitted invalid JSON") from error
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    edges = graph.get("edges") if isinstance(graph, dict) else None
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise DriverError("Projection graph must contain node and edge arrays")
    expected_nodes = {
        pid
        for pid in record_pids
        if by_pid[pid]["schema_type"] in contract.graph_node_classes
    }
    expected_edges = {
        (pid, target)
        for pid in expected_nodes
        for field in contract.relationship_fields
        for target in _relationship_targets(by_pid[pid], field)
        if target in expected_nodes
    }
    actual_nodes = {node.get("id") for node in nodes if isinstance(node, dict)}
    actual_edges = {
        (edge.get("source"), edge.get("target"))
        for edge in edges
        if isinstance(edge, dict)
    }
    if (
        actual_nodes != expected_nodes
        or len(nodes) != len(expected_nodes)
        or actual_edges != expected_edges
        or len(edges) != len(expected_edges)
    ):
        raise DriverError("Projection graph differs from the declared native closure")
    (output / "static" / "graph.json").write_text(
        graph_result.stdout.rstrip("\n") + "\n", encoding="utf-8"
    )
    (output / "SHA256SUMS").write_text(
        projection_manifest(workspace, runtime_root, output), encoding="utf-8"
    )
    return {**semantic, "pages": len(list((output / "content").rglob("*.md")))}


def verify_projection(workspace: WorkspaceConfig, runtime_root: Path) -> dict[str, Any]:
    output = workspace.path("generated") / "projection"
    ledger = output / "SHA256SUMS"
    if not ledger.is_file():
        raise DriverError(
            "Projection ledger is missing; run `orinoco projection update`"
        )
    expected = projection_manifest(workspace, runtime_root, output)
    if ledger.read_text(encoding="utf-8") != expected:
        raise DriverError(
            "Projection output is stale; run `orinoco projection update`"
        )
    with tempfile.TemporaryDirectory(prefix="orinoco-projection-") as temporary:
        candidate = Path(temporary) / "projection"
        rendered = render_projection(workspace, runtime_root, candidate)
        expected_files = {
            path.relative_to(output).as_posix(): path
            for path in output.rglob("*")
            if path.is_file()
            and not _is_historical_provenance(output, path)
            and not _is_projection_control_sidecar(output, path)
        }
        candidate_files = {
            path.relative_to(candidate).as_posix(): path
            for path in candidate.rglob("*")
            if path.is_file()
        }
        changed = [
            name
            for name in sorted(set(expected_files) | set(candidate_files))
            if name not in expected_files
            or name not in candidate_files
            or expected_files[name].read_bytes() != candidate_files[name].read_bytes()
        ]
        if changed:
            raise DriverError(
                "Projection output does not match deterministic regeneration: "
                + ", ".join(changed[:10])
            )
    return {**rendered, "deterministic": True}


def update_projection(workspace: WorkspaceConfig, runtime_root: Path) -> dict[str, Any]:
    destination = workspace.path("generated") / "projection"
    destination.parent.mkdir(parents=True, exist_ok=True)
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
        report = render_projection(workspace, runtime_root, staging)
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
    return report
