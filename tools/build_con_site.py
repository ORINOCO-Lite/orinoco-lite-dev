#!/usr/bin/env python3
"""Assemble and build the backend-free clean-migration website."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Sequence
from urllib.parse import urlsplit

import yaml

from con_assets import (
    ASSET_MANIFEST,
    AssetError,
    hydrate_all_assets,
    load_yaml as load_asset_manifest,
    materialize_all_assets,
    upstream_annex_entries,
)
from con_projection import (
    BUILD_ROOT,
    COMMITTED,
    PROFILE_ROOT,
    ProjectionExpectations,
    ProjectionError,
    ROOT,
    SITE,
    SourceRecord,
    UPSTREAM,
    declared_component_pins,
    load_yaml,
    load_projection_contract,
    safe_reset,
    source_closure,
    stack_records,
    validate_record_contract,
    validate_projection,
    verify_declared_pins,
    verify_final_site_state,
    verify_manifest,
)


ASSEMBLY = ROOT / "build" / "con-hugo"
ASSEMBLY_SPEC = PROFILE_ROOT / "assembly.yaml"
PRESENTATION = PROFILE_ROOT / "presentation.yaml"
MENU_CONFIG = SITE / "config" / "con" / "menus.en.toml"
TAXONOMY_CONFIG = SITE / "config" / "_default" / "taxonomies.toml"
DEFAULT_DESTINATION = ROOT / "build" / "con-site"
DEFAULT_BASE_URL = "http://127.0.0.1:8767/"
DEFAULT_EDIT_URL = "http://127.0.0.1:3000/"
ENTITY_SECTIONS = {
    "datasets",
    "instruments",
    "objectives",
    "organizations",
    "persons",
    "projects",
    "publications",
    "topics",
}
MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown"}


class BuildError(RuntimeError):
    """Report a static assembly or site acceptance failure."""


@dataclass(frozen=True)
class PresentationGroup:
    """One named presentation group with its reviewed member order."""

    name: str
    members: tuple[str, ...]


@dataclass(frozen=True)
class PresentationContract:
    """Reviewed navigation and ordering derived from canonical records."""

    editorial_routes: frozenset[str]
    editorial_aliases: frozenset[str]
    people_groups: tuple[PresentationGroup, ...]
    project_categories: tuple[PresentationGroup, ...]
    people: tuple[str, ...]
    projects: tuple[str, ...]


def run(
    arguments: Sequence[str | Path],
    *,
    action: str,
    environment: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        [str(argument) for argument in arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise BuildError(f"{action} failed ({result.returncode}): {detail}")
    return result.stdout


def safe_destination(path: Path) -> Path:
    resolved = path.resolve()
    build = (ROOT / "build").resolve()
    temporary_roots = {Path("/tmp").resolve(), Path("/private/tmp").resolve()}
    if build not in resolved.parents and not any(
        temporary in resolved.parents for temporary in temporary_roots
    ):
        raise BuildError(
            f"Destination must be below {build} or a temporary directory: {resolved}"
        )
    return resolved


def copy_tree(
    source: Path,
    destination: Path,
    *,
    preserve_symlinks: bool = False,
) -> None:
    if not source.is_dir():
        return
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        symlinks=preserve_symlinks,
        ignore=shutil.ignore_patterns(".git", ".DS_Store"),
    )


def source_symlinks(root: Path) -> list[Path]:
    links: list[Path] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        kept: list[str] = []
        for name in names:
            path = current / name
            if path.is_symlink():
                raise BuildError(f"Source tree contains a directory symlink: {path}")
            kept.append(name)
        names[:] = kept
        links.extend(
            current / name for name in filenames if (current / name).is_symlink()
        )
    return sorted(links)


def reject_source_symlinks(root: Path) -> None:
    links = source_symlinks(root)
    if links:
        raise BuildError(f"Source tree contains an undeclared symlink: {links[0]}")


def validate_upstream_annex_symlinks(root: Path) -> None:
    """Permit only exact, hydrated annex pointers recorded by provenance."""
    allowed = upstream_annex_entries()
    for path in source_symlinks(root):
        relative = path.relative_to(UPSTREAM).as_posix()
        key = allowed.get(relative)
        target = os.readlink(path).replace("\\", "/")
        parts = PurePosixPath(target).parts
        if (
            key is None
            or len(parts) < 3
            or parts[-1] != key
            or parts[-2] != key
            or ".git/annex/objects/" not in target
            or not path.resolve().is_file()
        ):
            raise BuildError(f"Unverified upstream symlink cannot be copied: {path}")


def assembly_scope_path(value: str) -> tuple[str, Path, Path]:
    """Resolve one assembly input without following a nested symlink."""
    if value.startswith("upstream:"):
        label, root, relative = "upstream", SITE, value.removeprefix("upstream:")
    elif value.startswith("parent:"):
        label, root, relative = "parent", ROOT, value.removeprefix("parent:")
    else:
        label, root, relative = "site", SITE, value
    path = PurePosixPath(relative)
    if (
        not relative
        or relative.startswith("/")
        or "\\" in relative
        or ".." in path.parts
        or path.as_posix() != relative
    ):
        raise BuildError(f"Invalid assembly digest scope path: {value}")
    root = root.resolve()
    candidate = root.joinpath(*path.parts)
    if candidate != root and root not in candidate.parents:
        raise BuildError(f"Assembly digest scope escapes {label}: {value}")
    return label, root, candidate


def files_without_following_symlinks(root: Path) -> list[Path]:
    """List regular files and link pointers while rejecting link directories."""
    if root.is_symlink():
        return [root]
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise BuildError(f"Assembly digest input is absent: {root}")
    files: list[Path] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        kept: list[str] = []
        for name in sorted(names):
            path = current / name
            if name in {".git", ".DS_Store"}:
                continue
            if path.is_symlink():
                raise BuildError(
                    f"Assembly digest input contains a directory symlink: {path}"
                )
            kept.append(name)
        names[:] = kept
        for name in sorted(filenames):
            if name in {".git", ".DS_Store"}:
                continue
            path = current / name
            if not path.is_symlink() and not path.is_file():
                raise BuildError(f"Unsupported assembly digest input: {path}")
            files.append(path)
    return files


def assembly_input_bytes(path: Path) -> bytes:
    if path.is_symlink():
        return b"symlink\0" + os.readlink(path).encode("utf-8")
    return path.read_bytes()


def reject_output_symlink_ancestors(path: Path, root: Path) -> None:
    """Reject a link or non-directory on the path to a generated output."""
    lexical_root = Path(os.path.abspath(root))
    lexical_path = Path(os.path.abspath(path))
    canonical_root = root.resolve()
    for candidate_root in (lexical_root, canonical_root):
        try:
            relative = lexical_path.relative_to(candidate_root)
            break
        except ValueError:
            continue
    else:
        raise BuildError(f"Generated output escapes its root: {path}")
    root = canonical_root
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise BuildError(f"Generated output has a symlinked ancestor: {current}")
        if current.exists() and not current.is_dir():
            raise BuildError(f"Generated output ancestor is not a directory: {current}")


def assembly_manifest_path(
    specification: dict[str, Any] | None = None,
) -> Path:
    profile = load_yaml(PROFILE_ROOT / "profile.yaml")
    paths = profile.get("paths")
    if not isinstance(paths, dict):
        raise BuildError("profiles/con/profile.yaml paths must be a mapping")
    declared_spec = paths.get("assembly")
    declared_output = paths.get("assembly_digest")
    if not isinstance(declared_spec, str) or not isinstance(declared_output, str):
        raise BuildError("The CON profile must declare assembly paths")
    _, spec_root, spec_path = assembly_scope_path(declared_spec)
    if spec_root != SITE.resolve() or spec_path != ASSEMBLY_SPEC.resolve():
        raise BuildError("The CON profile assembly path disagrees with the runtime")
    specification = load_yaml(ASSEMBLY_SPEC) if specification is None else specification
    digest = specification.get("digest")
    if not isinstance(digest, dict) or digest.get("algorithm") != "sha256":
        raise BuildError("profiles/con/assembly.yaml must use sha256")
    output = digest.get("output")
    if not isinstance(output, str):
        raise BuildError("profiles/con/assembly.yaml must declare digest.output")
    _, root, path = assembly_scope_path(output)
    if root != SITE.resolve():
        raise BuildError("The assembly manifest output must be in the site checkout")
    _, profile_root, profile_output = assembly_scope_path(declared_output)
    if profile_root != SITE.resolve() or profile_output != path:
        raise BuildError("The profile and assembly manifests disagree on digest output")
    return path


def assembly_manifest() -> str:
    """Describe every reviewed input that can change the static artifact."""
    verify_declared_pins(load_yaml(PROFILE_ROOT / "profile.yaml"))
    specification = load_yaml(ASSEMBLY_SPEC)
    digest = specification.get("digest")
    if not isinstance(digest, dict):
        raise BuildError("profiles/con/assembly.yaml digest must be a mapping")
    scope = digest.get("scope")
    if (
        not isinstance(scope, list)
        or not scope
        or not all(isinstance(item, str) and item for item in scope)
        or len(scope) != len(set(scope))
    ):
        raise BuildError("Assembly digest scope must be a unique string list")
    if "component-commit-pins" not in scope:
        raise BuildError("Assembly digest scope omits component-commit-pins")
    output = assembly_manifest_path(specification)
    entries: dict[str, Path] = {}
    for item in scope:
        if item == "component-commit-pins":
            continue
        label, root, path = assembly_scope_path(item)
        for candidate in files_without_following_symlinks(path):
            if candidate == output:
                raise BuildError("Assembly digest output cannot be an input")
            relative = candidate.relative_to(root).as_posix()
            entry = f"{label}/{relative}"
            if entry in entries:
                raise BuildError(f"Assembly digest input is declared twice: {entry}")
            entries[entry] = candidate
    lines = ["# full-con-migration assembly manifest v1"]
    for label, path in sorted(entries.items()):
        lines.append(
            f"{hashlib.sha256(assembly_input_bytes(path)).hexdigest()}  input:{label}"
        )
    for name, commit in declared_component_pins():
        digest_value = hashlib.sha256(f"{commit}\n".encode()).hexdigest()
        lines.append(f"{digest_value}  pin:{name}@{commit}")
    return "\n".join([lines[0], *sorted(lines[1:])]) + "\n"


def verify_assembly_manifest() -> None:
    path = assembly_manifest_path()
    reject_output_symlink_ancestors(path, SITE)
    if (
        path.is_symlink()
        or not path.is_file()
        or path.read_text(encoding="utf-8") != assembly_manifest()
    ):
        raise BuildError(
            "The committed CON assembly digest is stale; run "
            "`pixi run update-con-assembly` after reviewing site inputs"
        )


def update_assembly_manifest() -> Path:
    path = assembly_manifest_path()
    reject_output_symlink_ancestors(path, SITE)
    if path.is_symlink():
        raise BuildError(f"Assembly manifest output is a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(assembly_manifest())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()
    return path


def remove_transport_overrides() -> None:
    """Exclude upstream graph and branding that the CON profile replaces."""
    names = {
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "apple-touch-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "favicon.ico",
        "graph.json",
        "mstile-150x150.png",
        "site.webmanifest",
    }
    roots = (ASSEMBLY / "static", ASSEMBLY / "themes" / "congo" / "static")
    for root in roots:
        for name in names:
            path = root / name
            if path.exists() or path.is_symlink():
                path.unlink()
    for name in ("fzj.svg", "hhu.svg"):
        path = ASSEMBLY / "assets" / "img" / name
        if path.exists() or path.is_symlink():
            path.unlink()


def assemble_source(
    asset_manifest: dict[str, Any],
    asset_files: dict[str, Path],
) -> None:
    safe_reset(ASSEMBLY)
    for name in ("archetypes", "config", "layouts"):
        reject_source_symlinks(SITE / name)
        copy_tree(SITE / name, ASSEMBLY / name)
    # The sibling checkout is only a hydration transport for unchanged annexed
    # assets and the initialized theme. Its Git trees are checked against SITE.
    for name in ("assets", "static", "themes"):
        if name in {"assets", "static"}:
            validate_upstream_annex_symlinks(UPSTREAM / name)
        else:
            reject_source_symlinks(UPSTREAM / name)
        copy_tree(UPSTREAM / name, ASSEMBLY / name)
    copy_tree(SITE / "config" / "con", ASSEMBLY / "config" / "con")
    # Profile asset pointers are preserved for manifest-driven materialization,
    # but a directory link must never redirect writes outside the assembly.
    source_symlinks(PROFILE_ROOT)
    copy_tree(
        PROFILE_ROOT,
        ASSEMBLY / "profiles" / "con",
        preserve_symlinks=True,
    )
    remove_transport_overrides()
    materialize_all_assets(ASSEMBLY, asset_manifest, asset_files)
    remaining_links = source_symlinks(ASSEMBLY)
    if remaining_links:
        raise BuildError(
            f"Static assembly retains an undeclared symlink: {remaining_links[0]}"
        )


def artifact_asset_targets(
    asset_manifest: dict[str, Any],
) -> dict[str, str]:
    """Map each declared projected/static asset to its built-site path."""
    targets: dict[str, str] = {}
    prefixes = {
        "projection_links": "profiles/con/projection/content/",
        "static_links": "profiles/con/static/",
    }
    for group, prefix in prefixes.items():
        links = asset_manifest.get(group, {})
        if not isinstance(links, dict):
            raise BuildError(f"profiles/con/assets.yaml {group} is invalid")
        for destination, source in sorted(links.items()):
            if not isinstance(destination, str) or not isinstance(source, str):
                raise BuildError("Asset links must be string mappings")
            if not destination.startswith(prefix):
                raise BuildError(
                    f"Asset destination is outside {prefix}: {destination}"
                )
            relative = destination.removeprefix(prefix)
            if not relative or relative in targets:
                raise BuildError(
                    f"Asset destination does not map uniquely: {destination}"
                )
            targets[relative] = source
    return targets


def role_asset(
    asset_manifest: dict[str, Any],
    asset_files: dict[str, Path],
    role: str,
) -> Path:
    entries = asset_manifest.get("assets", {})
    if not isinstance(entries, dict):
        raise BuildError("profiles/con/assets.yaml assets is invalid")
    matches = [
        destination
        for destination, entry in entries.items()
        if isinstance(entry, dict) and entry.get("role") == role
    ]
    if len(matches) != 1 or matches[0] not in asset_files:
        raise BuildError(f"Asset role must select one file: {role}")
    return asset_files[matches[0]]


def presentation_groups(
    section: dict[str, Any],
    group_key: str,
    member_key: str,
    label: str,
) -> tuple[PresentationGroup, ...]:
    groups = section.get(group_key)
    if not isinstance(groups, list) or not groups:
        raise BuildError(f"Presentation {label} must declare non-empty {group_key}")
    names: list[str] = []
    result: list[PresentationGroup] = []
    all_members: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            raise BuildError(f"Presentation {label} group must be a mapping")
        name = group.get("name")
        values = group.get(member_key)
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(values, list)
            or not values
            or not all(isinstance(value, str) and value for value in values)
        ):
            raise BuildError(f"Presentation {label} group is invalid: {group!r}")
        names.append(name)
        members = tuple(values)
        result.append(PresentationGroup(name, members))
        all_members.extend(members)
    if len(names) != len(set(names)):
        raise BuildError(f"Presentation {label} group names are not unique")
    if len(all_members) != len(set(all_members)):
        raise BuildError(f"Presentation {label} records are not unique")
    return tuple(result)


def flattened_members(groups: Sequence[PresentationGroup]) -> tuple[str, ...]:
    return tuple(member for group in groups for member in group.members)


def markdown_aliases(source: Path) -> frozenset[str]:
    """Read safe, explicit HTML aliases from one editorial front matter block."""
    lines = source.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return frozenset()
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration as error:
        raise BuildError(f"Editorial front matter is unterminated: {source}") from error
    metadata = yaml.safe_load("\n".join(lines[1:end])) or {}
    aliases = metadata.get("aliases", []) if isinstance(metadata, dict) else None
    if not isinstance(aliases, list) or not all(
        isinstance(alias, str)
        and re.fullmatch(r"/[a-z0-9][a-z0-9-]*\.html", alias) is not None
        for alias in aliases
    ):
        raise BuildError(f"Editorial aliases are invalid: {source}")
    if len(aliases) != len(set(aliases)):
        raise BuildError(f"Editorial aliases are duplicated: {source}")
    return frozenset(alias.removeprefix("/") for alias in aliases)


def presentation_routes(
    presentation: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], frozenset[str], frozenset[str]]:
    editorial = presentation.get("editorial")
    routes = editorial.get("routes") if isinstance(editorial, dict) else None
    if not isinstance(routes, list) or not routes:
        raise BuildError("Presentation editorial.routes must be a non-empty list")
    by_path: dict[str, dict[str, Any]] = {}
    names: set[str] = set()
    sources: set[str] = set()
    weights: list[int] = []
    output_routes: set[str] = set()
    output_aliases: set[str] = set()
    source_root = PurePosixPath("profiles/con/editorial/content")
    for entry in routes:
        if not isinstance(entry, dict):
            raise BuildError("Presentation editorial route must be a mapping")
        name = entry.get("name")
        path = entry.get("path")
        source = entry.get("source")
        navigation = entry.get("navigation")
        weight = entry.get("weight")
        if not isinstance(name, str) or not name.strip():
            raise BuildError(f"Presentation editorial route has no name: {entry!r}")
        if (
            not isinstance(path, str)
            or re.fullmatch(r"/[a-z0-9][a-z0-9/-]*/", path) is None
            or "//" in path
        ):
            raise BuildError(f"Presentation editorial route is invalid: {path!r}")
        if navigation not in {"main", "footer", "related"}:
            raise BuildError(
                f"Presentation editorial navigation is invalid: {navigation!r}"
            )
        if not isinstance(weight, int) or isinstance(weight, bool) or weight <= 0:
            raise BuildError(f"Presentation editorial weight is invalid: {weight!r}")
        if not isinstance(source, str):
            raise BuildError(f"Presentation editorial source is invalid: {source!r}")
        source_path = PurePosixPath(source)
        if (
            source_path.is_absolute()
            or ".." in source_path.parts
            or source_path.as_posix() != source
            or not source_path.is_relative_to(source_root)
            or source_path.suffix not in MARKDOWN_SUFFIXES
        ):
            raise BuildError(
                f"Presentation editorial source escapes its root: {source}"
            )
        resolved_source = SITE.joinpath(*source_path.parts)
        if resolved_source.is_symlink() or not resolved_source.is_file():
            raise BuildError(f"Presentation editorial source is absent: {source}")
        if path in by_path or name in names or source in sources:
            raise BuildError(f"Presentation editorial routes are not unique: {entry!r}")
        by_path[path] = entry
        names.add(name)
        sources.add(source)
        weights.append(weight)
        output_routes.add(path.strip("/"))
        aliases = markdown_aliases(resolved_source)
        overlap = output_aliases & aliases
        if overlap:
            raise BuildError(
                f"Presentation editorial aliases are duplicated: {overlap}"
            )
        output_aliases.update(aliases)
    editorial_root = SITE.joinpath(*source_root.parts)
    actual_sources = {
        path.relative_to(SITE).as_posix()
        for path in editorial_root.rglob("*")
        if path.suffix in MARKDOWN_SUFFIXES and (path.is_file() or path.is_symlink())
    }
    if sources != actual_sources:
        raise BuildError(
            "Presentation editorial source closure disagrees with the checkout: "
            f"undeclared={sorted(actual_sources - sources)}, "
            f"absent={sorted(sources - actual_sources)}"
        )
    if len(weights) != len(set(weights)) or weights != sorted(weights):
        raise BuildError("Presentation editorial weights must be unique and ordered")
    return by_path, frozenset(output_routes), frozenset(output_aliases)


def ordered_editorial_groups(
    source: str,
    section: str,
) -> tuple[PresentationGroup, ...]:
    """Read exact level-two headings and entity-link order from Markdown."""
    heading_pattern = re.compile(r"##[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*")
    reference_pattern = re.compile(
        r'\{\{<\s*ref\s+"(/' + re.escape(section) + r'/[^"/]+)"\s*>\}\}'
    )
    groups: list[PresentationGroup] = []
    name: str | None = None
    members: list[str] = []
    for line in (SITE / source).read_text(encoding="utf-8").splitlines():
        heading = heading_pattern.fullmatch(line)
        if heading:
            if name is not None:
                groups.append(PresentationGroup(name, tuple(members)))
            name = heading.group(1)
            members = []
        references = reference_pattern.findall(line)
        if references and name is None:
            raise BuildError(
                f"Editorial {section} link appears before its group heading"
            )
        members.extend(reference.removeprefix("/") for reference in references)
    if name is not None:
        groups.append(PresentationGroup(name, tuple(members)))
    return tuple(groups)


def ordered_editorial_refs(source: str, section: str) -> tuple[str, ...]:
    return flattened_members(ordered_editorial_groups(source, section))


def validate_presentation_contract(
    records: Sequence[SourceRecord],
    homepage_pid: str,
) -> PresentationContract:
    """Require presentation groups, routes, menus, and canonical data to agree."""
    profile = load_yaml(PROFILE_ROOT / "profile.yaml")
    paths = profile.get("paths")
    if not isinstance(paths, dict) or paths.get("presentation") != (
        PRESENTATION.relative_to(SITE).as_posix()
    ):
        raise BuildError("The profile presentation path disagrees with the runtime")
    presentation = load_yaml(PRESENTATION)
    if presentation.get("version") != 1 or presentation.get("profile") != "con":
        raise BuildError("profiles/con/presentation.yaml has an unsupported identity")

    people_section = presentation.get("people")
    projects_section = presentation.get("projects")
    if not isinstance(people_section, dict) or not isinstance(projects_section, dict):
        raise BuildError("Presentation people/projects must be mappings")
    people_groups = presentation_groups(people_section, "groups", "members", "people")
    project_categories = presentation_groups(
        projects_section, "categories", "projects", "projects"
    )
    people = flattened_members(people_groups)
    projects = flattened_members(project_categories)

    canonical_people = {
        record.record["pid"]
        for record in records
        if record.category == "canonical"
        and record.record.get("schema_type") == "xyzri:XYZPerson"
    }
    canonical_projects = {
        record.record["pid"]
        for record in records
        if record.category == "canonical"
        and record.record.get("schema_type") == "xyzri:XYZProject"
        and record.record["pid"] != homepage_pid
    }
    if set(people) != canonical_people:
        raise BuildError("Presentation people do not exactly cover canonical people")
    if set(projects) != canonical_projects:
        raise BuildError(
            "Presentation projects do not exactly cover canonical projects"
        )

    by_path, editorial_routes, editorial_aliases = presentation_routes(presentation)
    people_route = people_section.get("route")
    projects_route = projects_section.get("route")
    if people_route not in by_path or projects_route not in by_path:
        raise BuildError("Presentation group landing routes are not editorial routes")
    expected_people_groups = tuple(
        PresentationGroup(
            group.name,
            tuple(pid.removeprefix("xyzrins:") for pid in group.members),
        )
        for group in people_groups
    )
    expected_project_categories = tuple(
        PresentationGroup(
            category.name,
            tuple(pid.removeprefix("xyzrins:") for pid in category.members),
        )
        for category in project_categories
    )
    actual_people_groups = ordered_editorial_groups(
        by_path[people_route]["source"], "persons"
    )
    actual_project_categories = ordered_editorial_groups(
        by_path[projects_route]["source"], "projects"
    )
    if actual_people_groups != expected_people_groups:
        raise BuildError(
            "People editorial links/headings disagree with presentation groups/order"
        )
    if actual_project_categories != expected_project_categories:
        raise BuildError(
            "Project editorial links/headings disagree with presentation "
            "categories/order"
        )

    menu = tomllib.loads(MENU_CONFIG.read_text(encoding="utf-8"))
    declared_menu: dict[tuple[str, str], int] = {}
    for path, entry in by_path.items():
        navigation = entry["navigation"]
        if navigation in {"main", "footer"}:
            declared_menu[(navigation, path.strip("/"))] = entry["weight"]
    actual_menu: dict[tuple[str, str], int] = {}
    for navigation in ("main", "footer"):
        entries = menu.get(navigation, [])
        if not isinstance(entries, list):
            raise BuildError(f"CON {navigation} menu must be an array")
        for entry in entries:
            if not isinstance(entry, dict):
                raise BuildError(f"CON {navigation} menu entry must be a mapping")
            page_ref = entry.get("pageRef")
            weight = entry.get("weight")
            if not isinstance(page_ref, str) or not isinstance(weight, int):
                raise BuildError(f"CON {navigation} menu entry is invalid: {entry!r}")
            key = (navigation, page_ref.strip("/"))
            if key in actual_menu:
                raise BuildError(f"CON menu route is duplicated: {key}")
            actual_menu[key] = weight
    if actual_menu != declared_menu:
        raise BuildError("CON menu routes/weights disagree with presentation.yaml")

    return PresentationContract(
        editorial_routes=editorial_routes,
        editorial_aliases=editorial_aliases,
        people_groups=people_groups,
        project_categories=project_categories,
        people=people,
        projects=projects,
    )


def manifest_entries(root: Path) -> list[str]:
    return [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"{path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != ".DS_Store"
    ]


def manifest_digest(entries: list[str]) -> str:
    return hashlib.sha256(("\n".join(entries) + "\n").encode()).hexdigest()


def graph_contract(site: Path, expectations: ProjectionExpectations) -> None:
    graph_path = site / "graph.json"
    if not graph_path.is_file():
        raise BuildError("Static artifact has no graph.json")
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if {node.get("id") for node in nodes} != expectations.graph_node_pids or len(
        nodes
    ) != len(expectations.graph_node_pids):
        raise BuildError("Static graph nodes do not match the source inventory")
    pairs = {(edge.get("source"), edge.get("target")) for edge in edges}
    if pairs != expectations.graph_edges or len(edges) != len(expectations.graph_edges):
        raise BuildError("Static graph edges do not match native relationships")


def entity_routes(site: Path, expected_routes: Sequence[str] = ()) -> set[str]:
    routes: set[str] = set()
    declared_sections = {route.split("/", 1)[0] for route in expected_routes if route}
    for section in ENTITY_SECTIONS | declared_sections:
        root = site / section
        if not root.is_dir():
            continue
        for path in root.rglob("index.html"):
            relative = path.parent.relative_to(site).as_posix()
            if relative != section:
                routes.add(relative)
    return routes


def published_html_routes(site: Path) -> set[str]:
    """Return every non-home HTML route, including flat aliases."""
    routes: set[str] = set()
    for path in site.rglob("*.html"):
        if path.name == "index.html":
            if path.parent != site:
                routes.add(path.parent.relative_to(site).as_posix())
        else:
            routes.add(path.relative_to(site).as_posix())
    return routes


def declared_taxonomy_routes() -> frozenset[str]:
    """Derive framework-owned list routes from the pinned upstream config."""
    taxonomies = tomllib.loads(TAXONOMY_CONFIG.read_text(encoding="utf-8"))
    routes = list(taxonomies.values())
    if (
        not routes
        or not all(
            isinstance(route, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]*", route) is not None
            for route in routes
        )
        or len(routes) != len(set(routes))
    ):
        raise BuildError("Upstream taxonomy routes are invalid or duplicated")
    return frozenset(routes)


def verify_published_route_closure(
    site: Path,
    expected_entity_routes: Sequence[str],
    expected_editorial_routes: Sequence[str],
    expected_taxonomy_routes: Sequence[str] = (),
    expected_alias_routes: Sequence[str] = (),
    expected_framework_routes: Sequence[str] = (),
) -> None:
    """Reject missing or undeclared generated/editorial HTML routes."""
    expected = (
        set(expected_entity_routes)
        | set(expected_editorial_routes)
        | set(expected_taxonomy_routes)
        | set(expected_alias_routes)
        | set(expected_framework_routes)
    )
    actual = published_html_routes(site)
    if actual != expected:
        raise BuildError(
            "Static HTML route closure disagrees with presentation/source data: "
            f"missing={sorted(expected - actual)}, "
            f"undeclared={sorted(actual - expected)}"
        )


def verify_site(
    site: Path,
    base_url: str,
    asset_manifest: dict[str, Any],
    asset_files: dict[str, Path],
    expectations: ProjectionExpectations | None = None,
    presentation: PresentationContract | None = None,
) -> dict[str, Any]:
    contract = load_projection_contract()
    records = source_closure(contract)
    if expectations is None:
        expectations = validate_record_contract(records, contract)
    if presentation is None:
        presentation = validate_presentation_contract(records, contract.homepage_pid)
    taxonomy_routes = declared_taxonomy_routes()
    required = {
        "index.html",
        "graph.js",
        "graph.json",
        "site.webmanifest",
        "apple-touch-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "explore/index.html",
        "mstile-150x150.png",
        *(f"{route}/index.html" for route in expectations.entity_routes),
        *(f"{route}/index.html" for route in presentation.editorial_routes),
        *(f"{route}/index.html" for route in taxonomy_routes),
        *presentation.editorial_aliases,
        "404.html",
    }
    missing = sorted(path for path in required if not (site / path).is_file())
    if missing:
        raise BuildError(f"Static CON artifact is missing routes/assets: {missing}")
    verify_published_route_closure(
        site,
        expectations.entity_routes,
        presentation.editorial_routes,
        taxonomy_routes,
        presentation.editorial_aliases,
        {"404.html"},
    )
    routes = entity_routes(site, expectations.entity_routes)
    if routes != expectations.entity_routes:
        raise BuildError(
            "German or unexpected entity routes leaked into the CON artifact: "
            f"{sorted(routes)}"
        )
    graph_contract(site, expectations)

    for target, source in artifact_asset_targets(asset_manifest).items():
        output = site / target
        declared = asset_files.get(source)
        if declared is None or not output.is_file():
            raise BuildError(f"Declared site asset is absent: {target}")
        if (
            hashlib.sha256(output.read_bytes()).digest()
            != hashlib.sha256(declared.read_bytes()).digest()
        ):
            raise BuildError(f"Declared site asset is stale: {target}")

    homepage = (site / "index.html").read_text(encoding="utf-8")
    if "Center for Open Neuroscience" not in homepage:
        raise BuildError("Homepage branding does not identify CON")
    if "con-logo.png" not in homepage:
        raise BuildError("Homepage does not use the CON logo")
    upstream_branding = {
        "https://www.fz-juelich.de/",
        "https://www.medizin.hhu.de/",
    }
    leaked_links = sorted(link for link in upstream_branding if link in homepage)
    forbidden_assets = {
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
        "img/fzj.svg",
        "img/hhu.svg",
    }
    leaked_assets = sorted(name for name in forbidden_assets if (site / name).exists())
    if leaked_links or leaked_assets:
        raise BuildError(
            "Upstream institutional branding leaked into the CON artifact: "
            f"links={leaked_links}, assets={leaked_assets}"
        )
    base_path = urlsplit(base_url).path or "/"
    expected_explore = f"{base_path.rstrip('/')}/explore"
    unquoted_homepage = homepage.replace('"', "").replace("'", "")
    if f"href={expected_explore}" not in unquoted_homepage:
        raise BuildError("Homepage Explore link does not target the local static route")
    header_logo = role_asset(
        asset_manifest,
        asset_files,
        "upstream-compatible-header-brand",
    )
    expected_logo = hashlib.sha256(header_logo.read_bytes()).hexdigest()
    if not any(
        path.is_file()
        and hashlib.sha256(path.read_bytes()).hexdigest() == expected_logo
        for path in site.rglob("*")
    ):
        raise BuildError("The committed CON logo is absent from the site")
    manifest = json.loads((site / "site.webmanifest").read_text(encoding="utf-8"))
    if manifest.get("name") != "Center for Open Neuroscience":
        raise BuildError("The static web manifest does not identify CON")
    if "Congo" in json.dumps(manifest):
        raise BuildError("Upstream Congo branding leaked into the web manifest")
    for name in (
        "apple-touch-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "mstile-150x150.png",
    ):
        if hashlib.sha256((site / name).read_bytes()).hexdigest() != expected_logo:
            raise BuildError(f"Static CON branding is stale: {name}")
    person = site / "persons" / "yaroslav-halchenko" / "index.html"
    person_text = person.read_text(encoding="utf-8")
    if "Yaroslav" not in person_text:
        raise BuildError("Person page does not identify Yaroslav")

    audit = run(
        [
            sys.executable,
            ROOT / "tools" / "adapt_upstream_pages.py",
            site,
            "--base-path",
            base_path,
            "--edit-url",
            os.environ.get("SHACL_VUE_URL", DEFAULT_EDIT_URL),
            "--check-only",
        ],
        action="Audit static CON base-path links",
    )
    entries = manifest_entries(site)
    return {
        "base_url": base_url,
        "entity_routes": sorted(routes),
        "editorial_routes": sorted(presentation.editorial_routes),
        "editorial_aliases": sorted(presentation.editorial_aliases),
        "taxonomy_routes": sorted(taxonomy_routes),
        "files": len(entries),
        "manifest_sha256": manifest_digest(entries),
        "path_audit": audit.strip(),
    }


def build_site(destination: Path, base_url: str) -> dict[str, Any]:
    destination = safe_destination(destination)
    try:
        profile = load_yaml(PROFILE_ROOT / "profile.yaml")
        verify_final_site_state(profile)
        verify_declared_pins(profile)
        contract = load_projection_contract(profile)
        source_records = source_closure(contract)
        expectations = validate_record_contract(source_records, contract)
        presentation = validate_presentation_contract(
            source_records, contract.homepage_pid
        )
        verify_manifest(COMMITTED)
        verify_assembly_manifest()
        records = [
            json.loads(line)
            for line in (COMMITTED / "records.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        validate_projection(records, COMMITTED, expectations)
        stack_records(records, BUILD_ROOT / "records.jsonl")
        asset_manifest = load_asset_manifest(ASSET_MANIFEST)
        asset_files = hydrate_all_assets()
    except (ProjectionError, AssetError) as error:
        raise BuildError(str(error)) from error
    try:
        assemble_source(asset_manifest, asset_files)
    except AssetError as error:
        raise BuildError(str(error)) from error
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["HUGO_ENVIRONMENT"] = "con"
    version = run(["hugo", "version"], action="Inspect Hugo version")
    if "hugo v0.154.5" not in version or "extended" not in version:
        raise BuildError(f"Unexpected Hugo runtime: {version.strip()}")
    run(
        [
            "hugo",
            "--minify",
            "--cleanDestinationDir",
            "--environment",
            "con",
            "--source",
            ASSEMBLY,
            "--destination",
            destination,
            "--baseURL",
            base_url,
        ],
        environment=environment,
        action="Build the backend-free CON site",
    )
    base_path = urlsplit(base_url).path or "/"
    run(
        [
            sys.executable,
            ROOT / "tools" / "adapt_upstream_pages.py",
            destination,
            "--base-path",
            base_path,
            "--edit-url",
            os.environ.get("SHACL_VUE_URL", DEFAULT_EDIT_URL),
        ],
        action="Adapt generated CON paths and edit links",
    )
    report = verify_site(
        destination,
        base_url,
        asset_manifest,
        asset_files,
        expectations,
        presentation,
    )
    report_path = destination.parent / f"{destination.name}-build.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = destination.parent / f"{destination.name}-manifest.sha256"
    manifest_path.write_text(
        "\n".join(manifest_entries(destination)) + "\n",
        encoding="utf-8",
    )
    return report


def compare_builds(
    first: Path,
    second: Path,
    base_url: str,
) -> dict[str, Any]:
    first_report = build_site(first, base_url)
    second_report = build_site(second, base_url)
    first_entries = manifest_entries(first)
    second_entries = manifest_entries(second)
    if first_entries != second_entries:
        raise BuildError("Two clean static builds are not byte-identical")
    return {
        "first": first_report,
        "second": second_report,
        "byte_identical": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(os.environ.get("DESTINATION", DEFAULT_DESTINATION)),
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--update-assembly-manifest",
        action="store_true",
        help="replace the reviewed static-assembly input digest",
    )
    action.add_argument(
        "--check-assembly-manifest",
        action="store_true",
        help="verify only the reviewed static-assembly input digest",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument(
        "--repeat-destination",
        type=Path,
        help="also build here and require byte-identical output",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/") + "/"
    try:
        if args.update_assembly_manifest:
            print(f"Updated {update_assembly_manifest()}")
            return 0
        if args.check_assembly_manifest:
            verify_assembly_manifest()
            print(f"Verified {assembly_manifest_path()}")
            return 0
        if args.repeat_destination:
            report = compare_builds(
                args.destination,
                args.repeat_destination,
                base_url,
            )
        else:
            report = build_site(args.destination, base_url)
        print(json.dumps(report, sort_keys=True))
    except BuildError as error:
        print(f"clean-migration build: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
