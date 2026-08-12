"""Generic semantic validation and deterministic flattened-site projection."""

from __future__ import annotations

from collections import Counter
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

from .config import WorkspaceConfig
from .editor import _record_sources
from .errors import ConfigurationError, DriverError
from .integrity import sha256_file


MANIFEST_HEADER = "# orinoco-lite projection manifest v2"
PROJECTION_ALGORITHM = "orinoco-projection-v2"
FORBIDDEN_BRIDGE_PREDICATES = {
    "dcterms:contributor",
    "dcterms:creator",
    "dcterms:relation",
    "schema:about",
    "schema:member",
    "schema:memberOf",
    "schema:subjectOf",
}


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
    if (
        not isinstance(homepage, dict)
        or not isinstance(pages, dict)
        or not pages
        or not isinstance(unrendered, list)
        or not isinstance(graph, dict)
        or not isinstance(routing, dict)
        or set(routing) != {"strip_prefix"}
    ):
        raise ConfigurationError("Projection contract sections are malformed")
    route_prefix = routing.get("strip_prefix")
    homepage_pid = homepage.get("pid")
    node_classes = graph.get("node_classes")
    relationships = graph.get("relationship_fields")
    if (
        not isinstance(homepage_pid, str)
        or not isinstance(route_prefix, str)
        or not route_prefix
        or not isinstance(node_classes, list)
        or not isinstance(relationships, list)
        or graph.get("missing_external_targets") != "reject"
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
            isinstance(item, str) and item and item.count("::") <= 1
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
        target = value.get("object") if isinstance(value, dict) else value
        targets = target if isinstance(target, list) else [target]
        if not targets or not all(isinstance(item, str) and item for item in targets):
            raise DriverError(f"{record.get('pid')}: malformed {field} target")
        yield from targets


def _all_links(record: Mapping[str, Any], fields: Sequence[str]) -> Iterable[tuple[str, str]]:
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


def _native_fingerprint(value: Any) -> Counter[tuple[str, str]]:
    result: Counter[tuple[str, str]] = Counter()
    if isinstance(value, dict):
        schema_type = value.get("schema_type")
        if isinstance(schema_type, str) and schema_type.startswith("dlthings:"):
            result[(schema_type, json.dumps(value, sort_keys=True, separators=(",", ":")))] += 1
        for child in value.values():
            result.update(_native_fingerprint(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_native_fingerprint(child))
    return result


def _records(workspace: WorkspaceConfig) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    canonical_sources = _record_sources(workspace, "canonical")
    reference_sources = _record_sources(workspace, "reference")
    records = [yaml.safe_load(item["content"]) for item in [*canonical_sources, *reference_sources]]
    canonical = {item["pid"] for item in canonical_sources}
    reference = {item["pid"] for item in reference_sources}
    return records, canonical, reference


def validate_semantics(
    workspace: WorkspaceConfig,
    runtime_root: Path,
) -> dict[str, Any]:
    contract = load_contract(workspace)
    records, canonical, reference = _records(workspace)
    by_pid = {record["pid"]: record for record in records}
    if len(by_pid) != len(records) or not canonical:
        raise DriverError("Projection metadata PIDs must be unique and non-empty")
    homepage = by_pid.get(contract.homepage_pid)
    if homepage is None or contract.homepage_pid not in canonical:
        raise DriverError("Projection homepage is not a canonical record")
    declared_classes = set(contract.pages) | set(contract.unrendered_classes)
    record_classes = {record["schema_type"] for record in records}
    if not record_classes <= declared_classes:
        raise DriverError(
            "Projection class policy differs from the metadata inventory: "
            f"declared={sorted(declared_classes)}, actual={sorted(record_classes)}"
        )
    schema = runtime_root / "schema/demo-research-information/unreleased.yaml"
    schema_view = SchemaView(str(schema))
    accepted = {
        str(schema_view.get_uri(name, expand=False))
        for name in schema_view.all_classes()
    }
    try:
        from dump_things_service import Format
        from dump_things_service.converter import FormatConverter

        to_ttl = FormatConverter(str(schema), Format.json, Format.ttl)
        to_json = FormatConverter(str(schema), Format.ttl, Format.json)
    except Exception as error:
        raise DriverError("Could not initialize semantic schema conversion") from error
    adjacency: dict[str, set[str]] = {pid: set() for pid in by_pid}
    for record in records:
        pid = record["pid"]
        for schema_type in _nested_schema_types(record):
            if schema_type.startswith(("http://", "https://")) or schema_type not in accepted:
                raise DriverError(f"{pid}: unknown CURIE schema type {schema_type}")
        for attribute in record.get("attributes", []):
            if isinstance(attribute, dict) and attribute.get("predicate") in FORBIDDEN_BRIDGE_PREDICATES:
                raise DriverError(f"{pid}: relationship encoded as AttributeSpecification")
        for field, target in _all_links(record, contract.relationship_fields):
            if target not in by_pid:
                raise DriverError(f"{pid}: dangling {field} target {target}")
            adjacency[pid].add(target)
        try:
            class_name = record["schema_type"].rsplit(":", 1)[-1]
            restored = to_json.convert(to_ttl.convert(record, class_name), class_name)
        except Exception as error:
            raise DriverError(f"{pid}: JSON/RDF/JSON schema validation failed: {error}") from error
        before = Counter(_nested_schema_types(record))
        after = Counter(_nested_schema_types(restored))
        if any(after[item] < count for item, count in before.items()) or _native_fingerprint(restored) != _native_fingerprint(record):
            raise DriverError(f"{pid}: schema round trip changed native semantics")
    reachable = set(canonical)
    pending = list(canonical)
    while pending:
        source = pending.pop()
        for target in adjacency[source]:
            if target not in reachable:
                reachable.add(target)
                pending.append(target)
    if reference - reachable:
        raise DriverError(
            "Reference records are outside the canonical relationship closure: "
            + ", ".join(sorted(reference - reachable))
        )
    graph_nodes = {
        pid
        for pid in canonical
        if by_pid[pid]["schema_type"] in contract.graph_node_classes
    }
    graph_edges: set[tuple[str, str]] = set()
    for pid in graph_nodes:
        for field in contract.relationship_fields:
            for target in _relationship_targets(by_pid[pid], field):
                if target not in graph_nodes:
                    raise DriverError(f"{pid}: graph target does not materialize: {target}")
                graph_edges.add((pid, target))
    return {
        "canonical_records": len(canonical),
        "reference_records": len(reference),
        "graph_nodes": len(graph_nodes),
        "graph_edges": len(graph_edges),
        "records": len(records),
    }


def _toyaml(value: Any) -> str:
    return yaml.safe_dump(value, sort_keys=False, default_flow_style=False)


def _inline(value: Any, by_pid: Mapping[str, dict[str, Any]]) -> Any:
    scalar = not isinstance(value, list)
    values = [value] if scalar else value
    rendered = []
    for item in values:
        pid = item.get("object") if isinstance(item, dict) else item
        if isinstance(pid, list):
            replacement = [deepcopy(by_pid.get(one, one)) for one in pid]
        else:
            replacement = deepcopy(by_pid.get(pid, pid))
        if isinstance(item, dict):
            copy = deepcopy(item)
            copy["object"] = replacement
            rendered.append(copy)
        else:
            rendered.append(replacement)
    return rendered[0] if scalar and rendered else rendered


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
    parent, separator, child = operation.partition("::")
    if parent not in record:
        return
    if not separator:
        record[parent] = _inline(record[parent], by_pid)
        return
    values = record[parent]
    scalar = not isinstance(values, list)
    values = [values] if scalar else values
    rendered = []
    for value in values:
        copy = deepcopy(value)
        if not isinstance(copy, dict) or child not in copy:
            # Match the accepted qri inline operator: entries without the
            # requested PID-bearing child do not survive that operation.
            continue
        child_value = copy[child]
        child_scalar = not isinstance(child_value, list)
        child_values = [child_value] if child_scalar else child_value
        replacements = [deepcopy(by_pid.get(pid, pid)) for pid in child_values]
        copy[child] = replacements[0] if child_scalar and replacements else replacements
        rendered.append(copy)
    record[parent] = rendered[0] if scalar and rendered else rendered


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
        workspace.path("canonical"),
        workspace.path("reference"),
        contract.path,
        workspace.path("site") / "projection-templates",
        workspace.path("site") / "projection-tools",
    ]
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
        if path.is_file() and path.name != "SHA256SUMS" and "provenance" not in path.parts:
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
    records, canonical, _ = _records(workspace)
    by_pid = {record["pid"]: record for record in records}
    if output.exists():
        shutil.rmtree(output)
    (output / "content").mkdir(parents=True)
    (output / "static").mkdir()
    (output / "records.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in sorted(records, key=lambda item: (item["schema_type"], item["pid"]))),
        encoding="utf-8",
    )
    for pid in sorted(canonical):
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
        input=(output / "records.jsonl").read_text(encoding="utf-8"),
        capture_output=True,
        text=True,
        check=False,
    )
    if graph_result.returncode or graph_result.stderr.strip():
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
        for pid in canonical
        if by_pid[pid]["schema_type"] in contract.graph_node_classes
    }
    expected_edges = {
        (pid, target)
        for pid in expected_nodes
        for field in contract.relationship_fields
        for target in _relationship_targets(by_pid[pid], field)
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
            "Committed projection ledger is missing; run `orinoco projection update`"
        )
    expected = projection_manifest(workspace, runtime_root, output)
    if ledger.read_text(encoding="utf-8") != expected:
        raise DriverError(
            "Committed projection is stale; run `orinoco projection update` after review"
        )
    with tempfile.TemporaryDirectory(prefix="orinoco-projection-") as temporary:
        candidate = Path(temporary) / "projection"
        rendered = render_projection(workspace, runtime_root, candidate)
        expected_files = {
            path.relative_to(output).as_posix(): path
            for path in output.rglob("*")
            if path.is_file() and "provenance" not in path.parts
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
                "Committed projection does not match deterministic regeneration: "
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
