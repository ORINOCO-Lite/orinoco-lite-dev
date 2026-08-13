#!/usr/bin/env python3
"""Render and verify the committed clean-migration projection."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
import tomllib
from typing import Any, Iterator, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
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
REVIEWED_FULL_MIGRATION_BASE = "a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8"
ACCEPTED_CLEAN_MIGRATION_TIP = "a122e506de9e4a13473edbe8d74a950d74032a16"
ACCEPTED_CLEAN_MIGRATION_PARENT_TIP = "f54cf5fdb2b5ae4bf03fe6939246316fd9ec818d"
FOUNDATION_SUBJECTS = (
    "build(clean-migration): add the CON site profile",
    "feat(content): add the clean CON vertical slice",
)
TERMINAL_PROJECTION_SUBJECT = "chore(projection): refresh the full CON snapshot"
ASSEMBLY_DIGEST_PATH = "profiles/con/assembly/SHA256SUMS"
CONVENTIONAL_SUBJECT = re.compile(
    r"^(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\([^)]+\))?!?: .+"
)
UPSTREAM_UPDATE_WORKFLOW = Path(".forgejo/workflows/update-from-pool.yaml")

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
PROJECTION_PYPI_ROOTS = (
    "dump-things-pyclient",
    "dump-things-service",
    "jinja2",
    "linkml",
    "linkml-runtime",
    "packaging",
    "pydantic",
    "pyyaml",
    "query-things",
    "rdflib",
)
PROJECTION_LOCAL_PYPI_PATHS = {
    "dump-things-pyclient": "submodules/dump-things-pyclient",
    "dump-things-service": "submodules/dump-things-service",
    "query-things": "submodules/query-things",
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


@dataclass(frozen=True)
class ProjectionContract:
    """Executable record, page, and graph policy from the site manifests."""

    canonical_root: Path
    reference_root: Path
    collection: str
    homepage_pid: str
    homepage_class: str
    homepage_record: Path
    homepage_template: Path
    page_templates: dict[str, Path]
    unrendered_classes: frozenset[str]
    graph_node_classes: frozenset[str]
    graph_relationship_fields: tuple[str, ...]
    snapshot_path: Path
    content_root: Path
    graph_output: Path
    digest_output: Path


@dataclass(frozen=True)
class ProjectionExpectations:
    """Closure derived from the profile contract and its source records."""

    canonical_pids: frozenset[str]
    reference_pids: frozenset[str]
    graph_node_pids: frozenset[str]
    graph_edges: frozenset[tuple[str, str]]
    markdown_pages: frozenset[str]
    entity_routes: frozenset[str]
    record_payloads: tuple[tuple[str, str], ...]


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
        raise ProjectionError(f"{action} failed ({result.returncode}): {detail}")
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
        raise ProjectionError(f"The pinned {label} worktree has changes:\n{status}")


def require_no_ignored_files(
    repository: Path,
    label: str,
    pathspecs: Sequence[str] = (),
) -> None:
    """Reject ignored worktree files that Git's normal clean check omits."""
    command: list[str | Path] = [
        "git",
        "-C",
        repository,
        "ls-files",
        "--others",
        "--ignored",
        "--exclude-standard",
    ]
    if pathspecs:
        command.extend(["--", *pathspecs])
    ignored = run(
        command,
        action=f"Inspect ignored files in the {label} worktree",
    ).splitlines()
    if ignored:
        raise ProjectionError(
            f"The pinned {label} worktree has ignored files: "
            + ", ".join(sorted(ignored))
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


def allowed_site_overlay_path(path: str, *, dirty: bool) -> bool:
    """Return whether one path belongs to the isolated downstream layer."""
    if path == ".gitmodules":
        return True
    if not dirty and path == "UPSTREAM.md":
        return True
    return path.startswith(("config/con/", "profiles/con/"))


def generated_snapshot_path(path: str) -> bool:
    """Identify projection and assembly outputs reserved for the terminal commit."""
    return path.startswith("profiles/con/projection/") or path == ASSEMBLY_DIGEST_PATH


def site_status_paths(repository: Path) -> list[str]:
    """Return every current and rename-source path from porcelain status."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ProjectionError(f"Inspect site worktree failed: {detail}")
    entries = result.stdout.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        if len(entry) < 4 or entry[2] != " ":
            raise ProjectionError(f"Cannot parse site status entry: {entry!r}")
        status = entry[:2]
        paths.append(entry[3:])
        if any(code in "RC" for code in status):
            if index >= len(entries) or not entries[index]:
                raise ProjectionError("Site status rename has no source path")
            paths.append(entries[index])
            index += 1
    return paths


def verify_site_worktree_isolation(repository: Path = SITE) -> None:
    """Allow dirty migration inputs, but reject upstream-owned changes."""
    unexpected = sorted(
        path
        for path in site_status_paths(repository)
        if not allowed_site_overlay_path(path, dirty=True)
    )
    if unexpected:
        raise ProjectionError(
            "The site worktree has dirty or untracked upstream-owned paths: "
            + ", ".join(unexpected)
        )


def checkpoint_refs(repository: Path = SITE) -> dict[str, str]:
    """Find local or remote-tracking refs for the accepted checkpoint."""
    output = run(
        [
            "git",
            "-C",
            repository,
            "for-each-ref",
            "--format=%(objectname) %(refname)",
            "refs/heads/codex/clean-migration",
            "refs/remotes/*/codex/clean-migration",
        ],
        action="Inspect the accepted clean-migration checkpoint",
    )
    return {
        ref: commit
        for line in output.splitlines()
        if line
        for commit, ref in [line.split(" ", 1)]
    }


def verify_terminal_history(
    terminal_indexes: Sequence[int],
    commit_count: int,
    *,
    require_terminal: bool,
) -> None:
    """Enforce preparation or final-mode generated snapshot history."""
    if len(terminal_indexes) > 1 or (
        terminal_indexes and terminal_indexes[0] != commit_count - 1
    ):
        raise ProjectionError(
            "The generated projection commit must be unique and terminal"
        )
    if require_terminal and len(terminal_indexes) != 1:
        raise ProjectionError(
            "Final acceptance requires exactly one terminal generated "
            f"projection commit, found {len(terminal_indexes)}"
        )


def verify_linear_successor_history(
    repository: Path,
    base: str,
    commits: Sequence[str],
) -> None:
    """Require every successor commit to have exactly its predecessor as parent."""
    expected_parent = base
    for commit in commits:
        parents = run(
            ["git", "-C", repository, "show", "-s", "--format=%P", commit],
            action=f"Inspect successor parents for {commit}",
        ).split()
        if parents != [expected_parent]:
            raise ProjectionError(
                "The successor site history must be a linear commit stack: "
                f"{commit} has parents {parents}, expected {[expected_parent]}"
            )
        expected_parent = commit


def verify_successor_history(
    profile: dict[str, Any],
    repository: Path = SITE,
    *,
    require_terminal: bool = False,
) -> None:
    """Validate focused successor commits without reviving the two-commit rule."""
    components = profile.get("components")
    if not isinstance(components, dict):
        raise ProjectionError("Profile components must be a mapping")
    website = components.get("www_from_model")
    if not isinstance(website, dict):
        raise ProjectionError("Profile www_from_model component must be a mapping")
    declared_upstream = website.get("commit")
    if declared_upstream != REVIEWED_FULL_MIGRATION_BASE:
        raise ProjectionError(
            "The full-migration profile must use the reviewed upstream base "
            f"{REVIEWED_FULL_MIGRATION_BASE}, found {declared_upstream!r}"
        )
    ancestor = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            declared_upstream,
            "HEAD",
        ],
        capture_output=True,
        text=True,
    )
    if ancestor.returncode:
        raise ProjectionError(
            "The reviewed upstream commit is not an ancestor of the "
            f"full-migration site: {declared_upstream}"
        )

    commits = run(
        [
            "git",
            "-C",
            repository,
            "rev-list",
            "--reverse",
            f"{declared_upstream}..HEAD",
        ],
        action="Inspect full-migration website commits",
    ).splitlines()
    if len(commits) < len(FOUNDATION_SUBJECTS):
        raise ProjectionError(
            "The successor site is missing its accepted foundation commits"
        )
    verify_linear_successor_history(repository, declared_upstream, commits)
    subjects = [
        run(
            ["git", "-C", repository, "show", "-s", "--format=%s", commit],
            action=f"Inspect successor commit {commit}",
        ).strip()
        for commit in commits
    ]
    if tuple(subjects[:2]) != FOUNDATION_SUBJECTS:
        raise ProjectionError(
            f"The successor foundation commit subjects differ: {subjects[:2]}"
        )
    unconventional = [
        subject for subject in subjects if not CONVENTIONAL_SUBJECT.fullmatch(subject)
    ]
    if unconventional:
        raise ProjectionError(
            f"Successor site commits must be Conventional Commits: {unconventional}"
        )

    terminal_indexes = [
        index
        for index, subject in enumerate(subjects)
        if subject == TERMINAL_PROJECTION_SUBJECT
    ]
    verify_terminal_history(
        terminal_indexes,
        len(commits),
        require_terminal=require_terminal,
    )
    for index, commit in enumerate(commits):
        paths = run(
            [
                "git",
                "-C",
                repository,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                commit,
            ],
            action=f"Inspect successor paths in {commit}",
        ).splitlines()
        unexpected = [
            path for path in paths if not allowed_site_overlay_path(path, dirty=False)
        ]
        if unexpected:
            raise ProjectionError(
                f"Successor commit {commit} changes upstream-owned paths: "
                + ", ".join(unexpected)
            )
        if index < len(FOUNDATION_SUBJECTS):
            continue
        generated = [path for path in paths if generated_snapshot_path(path)]
        if subjects[index] == TERMINAL_PROJECTION_SUBJECT:
            if not generated:
                raise ProjectionError(
                    "The terminal projection commit contains no generated outputs"
                )
            if len(generated) != len(paths):
                raise ProjectionError(
                    "The terminal projection commit contains hand-authored paths"
                )
        elif generated:
            raise ProjectionError(
                f"Hand-authored successor commit {commit} contains generated "
                "projection paths"
            )

    refs = checkpoint_refs(repository)
    if ACCEPTED_CLEAN_MIGRATION_TIP not in refs.values():
        raise ProjectionError(
            "No clean-migration checkpoint ref preserves accepted site tip "
            f"{ACCEPTED_CLEAN_MIGRATION_TIP}: {refs}"
        )
    parent_refs = checkpoint_refs(ROOT)
    if ACCEPTED_CLEAN_MIGRATION_PARENT_TIP not in parent_refs.values():
        raise ProjectionError(
            "No clean-migration checkpoint ref preserves accepted parent tip "
            f"{ACCEPTED_CLEAN_MIGRATION_PARENT_TIP}: {parent_refs}"
        )


def verify_final_site_state(
    profile: dict[str, Any] | None = None,
    repository: Path = SITE,
) -> None:
    """Require the immutable, clean site state used by final acceptance."""
    profile = (
        load_yaml(repository / "profiles" / "con" / "profile.yaml")
        if profile is None
        else profile
    )
    verify_successor_history(
        profile,
        repository,
        require_terminal=True,
    )
    require_clean_checkout(repository, "full-migration website")
    require_no_ignored_files(repository, "full-migration website")
    require_clean_checkout(ROOT, "full-migration coordinator")
    require_no_ignored_files(
        UPSTREAM,
        "www-from-model hydration transport",
        ("assets", "static", "themes/congo"),
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

    verify_successor_history(profile)
    verify_site_worktree_isolation()
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


def site_manifest_path(value: Any, label: str) -> Path:
    """Resolve one manifest path while keeping it inside the site checkout."""
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ProjectionError(f"{label} must be a relative site path")
    path = (SITE / value).resolve()
    if path != SITE and SITE not in path.parents:
        raise ProjectionError(f"{label} escapes the site checkout: {value}")
    return path


def require_manifest_path(value: Any, label: str, expected: Path) -> Path:
    """Require a site-relative declaration to match one runtime path."""
    try:
        expected_relative = expected.relative_to(SITE).as_posix()
    except ValueError as error:
        raise ProjectionError(
            f"Runtime path for {label} is outside the site checkout: {expected}"
        ) from error
    if value != expected_relative:
        raise ProjectionError(
            f"{label} declares {value!r}, but the runtime uses {expected_relative!r}"
        )
    path = site_manifest_path(value, label)
    if path != expected.resolve():
        raise ProjectionError(
            f"{label} declares {path}, but the runtime uses {expected.resolve()}"
        )
    return path


def unique_strings(value: Any, label: str) -> tuple[str, ...]:
    """Load a non-empty manifest string sequence without silent duplicates."""
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ProjectionError(f"{label} must be a non-empty string list")
    if len(set(value)) != len(value):
        raise ProjectionError(f"{label} contains duplicate values")
    return tuple(value)


def producer_mapping(path: Path, variable: str) -> dict[str, str]:
    """Read a literal producer mapping without importing upstream code."""
    if not path.is_file():
        raise ProjectionError(f"Graph producer is absent: {path}")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as error:
        raise ProjectionError(
            f"Cannot inspect graph producer {path}: {error}"
        ) from error
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if not any(
            isinstance(target, ast.Name) and target.id == variable for target in targets
        ):
            continue
        try:
            value = ast.literal_eval(statement.value)
        except (ValueError, TypeError) as error:
            raise ProjectionError(
                f"Graph producer {variable} must remain a literal mapping"
            ) from error
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in value.items()
        ):
            raise ProjectionError(f"Graph producer {variable} is not a string mapping")
        return value
    raise ProjectionError(f"Graph producer does not declare {variable}")


def load_projection_contract(
    profile: dict[str, Any] | None = None,
    specification: dict[str, Any] | None = None,
) -> ProjectionContract:
    """Load and cross-check the executable CON profile manifests."""
    profile = load_yaml(PROFILE_PATH) if profile is None else profile
    specification = (
        load_yaml(PROJECTION_SPEC_PATH) if specification is None else specification
    )

    paths = profile.get("paths")
    inputs = specification.get("inputs")
    if not isinstance(paths, dict) or not isinstance(inputs, dict):
        raise ProjectionError("Profile paths and projection inputs must be mappings")
    canonical_root = site_manifest_path(
        paths.get("canonical_records"), "profile.paths.canonical_records"
    )
    reference_root = site_manifest_path(
        paths.get("reference_records"), "profile.paths.reference_records"
    )
    for label, profile_path, input_value in (
        ("canonical_records", canonical_root, inputs.get("canonical_records")),
        ("reference_records", reference_root, inputs.get("reference_records")),
    ):
        input_path = site_manifest_path(input_value, f"projection.inputs.{label}")
        if input_path != profile_path:
            raise ProjectionError(
                f"Profile and projection {label} paths disagree: "
                f"{profile_path} != {input_path}"
            )

    snapshot_path = require_manifest_path(
        paths.get("qri_snapshot"),
        "profile.paths.qri_snapshot",
        COMMITTED / "records.jsonl",
    )
    content_root = require_manifest_path(
        paths.get("content"),
        "profile.paths.content",
        COMMITTED / "content",
    )
    graph_output = require_manifest_path(
        paths.get("graph"),
        "profile.paths.graph",
        COMMITTED / "static" / "graph.json",
    )
    digest_output = require_manifest_path(
        paths.get("digest"),
        "profile.paths.digest",
        COMMITTED / "SHA256SUMS",
    )

    schema = profile.get("schema")
    if not isinstance(schema, dict):
        raise ProjectionError("profile.schema must be a mapping")
    schema_relative = schema.get("path")
    if not isinstance(schema_relative, str) or Path(schema_relative).is_absolute():
        raise ProjectionError("profile.schema.path must be repository-relative")
    schema_repository = (ROOT / "submodules" / "things-schemas").resolve()
    expected_schema_relative = SCHEMA.relative_to(schema_repository).as_posix()
    declared_schema = (schema_repository / schema_relative).resolve()
    if (
        schema_relative != expected_schema_relative
        or Path(schema_relative).as_posix() != schema_relative
        or declared_schema != SCHEMA.resolve()
        or schema_repository not in declared_schema.parents
    ):
        raise ProjectionError(
            "profile.schema.path does not select the pinned source schema: "
            f"{schema_relative!r}"
        )

    identity = profile.get("identity")
    profile_homepage = profile.get("homepage")
    render = specification.get("render")
    if not all(
        isinstance(value, dict) for value in (identity, profile_homepage, render)
    ):
        raise ProjectionError(
            "Profile identity/homepage and projection render must be mappings"
        )
    assert isinstance(identity, dict)
    assert isinstance(profile_homepage, dict)
    assert isinstance(render, dict)
    render_homepage = render.get("homepage")
    if not isinstance(render_homepage, dict):
        raise ProjectionError("projection.render.homepage must be a mapping")
    homepage_pids = {
        identity.get("homepage_pid"),
        profile_homepage.get("pid"),
        render_homepage.get("pid"),
    }
    if len(homepage_pids) != 1 or not all(
        isinstance(pid, str) and pid for pid in homepage_pids
    ):
        raise ProjectionError(
            "Profile identity and render manifests disagree on homepage PID"
        )
    homepage_pid = next(iter(homepage_pids))
    homepage_class = profile_homepage.get("class")
    if not isinstance(homepage_class, str) or not homepage_class:
        raise ProjectionError("profile.homepage.class must be a CURIE string")
    homepage_record = site_manifest_path(
        profile_homepage.get("record"), "profile.homepage.record"
    )
    homepage_template = site_manifest_path(
        render_homepage.get("template"), "projection.render.homepage.template"
    )

    if render.get("engine") != "qri":
        raise ProjectionError("projection.render.engine must be 'qri'")
    require_manifest_path(
        render.get("content_root"),
        "projection.render.content_root",
        content_root,
    )
    pages = render.get("pages")
    if not isinstance(pages, dict) or not pages:
        raise ProjectionError("projection.render.pages must be a non-empty mapping")
    if not all(
        isinstance(class_name, str)
        and class_name
        and isinstance(template, str)
        and template
        for class_name, template in pages.items()
    ):
        raise ProjectionError("projection.render.pages must map classes to paths")
    page_templates = {
        class_name: site_manifest_path(
            template, f"projection.render.pages.{class_name}"
        )
        for class_name, template in pages.items()
    }
    unrendered_classes = frozenset(
        unique_strings(
            render.get("unrendered_classes"),
            "projection.render.unrendered_classes",
        )
    )
    overlap = set(page_templates) & unrendered_classes
    if overlap:
        raise ProjectionError(
            f"Rendered and unrendered class declarations overlap: {sorted(overlap)}"
        )
    if homepage_class not in page_templates:
        raise ProjectionError(
            "The homepage class must also declare its ordinary page template"
        )

    graph = specification.get("graph")
    if not isinstance(graph, dict):
        raise ProjectionError("projection.graph must be a mapping")
    if graph.get("missing_external_targets") != "reject":
        raise ProjectionError(
            "projection.graph.missing_external_targets must be 'reject'"
        )
    graph_node_classes = frozenset(
        unique_strings(graph.get("node_classes"), "projection.graph.node_classes")
    )
    graph_relationship_fields = unique_strings(
        graph.get("relationship_fields"),
        "projection.graph.relationship_fields",
    )
    producer = site_manifest_path(graph.get("producer"), "projection.graph.producer")
    require_manifest_path(graph.get("output"), "projection.graph.output", graph_output)
    producer_node_classes = set(producer_mapping(producer, "wanted_node_types"))
    producer_relationship_fields = set(producer_mapping(producer, "wanted_edge_types"))
    if graph_node_classes != producer_node_classes:
        raise ProjectionError(
            "Declared graph node classes differ from the pinned producer: "
            f"declared={sorted(graph_node_classes)}, "
            f"producer={sorted(producer_node_classes)}"
        )
    if set(graph_relationship_fields) != producer_relationship_fields:
        raise ProjectionError(
            "Declared graph relationship fields differ from the pinned producer: "
            f"declared={sorted(graph_relationship_fields)}, "
            f"producer={sorted(producer_relationship_fields)}"
        )

    build = profile.get("build")
    snapshot = specification.get("snapshot")
    if not isinstance(build, dict) or not isinstance(snapshot, dict):
        raise ProjectionError("Profile build and projection snapshot must be mappings")
    collection = build.get("metadata_collection")
    if (
        not isinstance(collection, str)
        or not collection
        or snapshot.get("collection") != collection
    ):
        raise ProjectionError(
            "Profile and projection manifests disagree on metadata collection"
        )
    if collection != COLLECTION:
        raise ProjectionError(
            f"Projection runtime supports only collection {COLLECTION!r}, "
            f"found {collection!r}"
        )
    require_manifest_path(
        snapshot.get("records"),
        "projection.snapshot.records",
        snapshot_path,
    )
    if snapshot.get("format") != "qri-record-jsonl":
        raise ProjectionError("projection.snapshot.format must be 'qri-record-jsonl'")
    if snapshot.get("sort_key") != ["schema_type", "pid"]:
        raise ProjectionError("projection.snapshot.sort_key must be [schema_type, pid]")
    declared_counts = snapshot.get("expected_records", {})
    if not isinstance(declared_counts, dict) or not all(
        category in {"canonical", "reference"} and isinstance(count, int) and count >= 0
        for category, count in declared_counts.items()
    ):
        raise ProjectionError(
            "projection.snapshot.expected_records must contain non-negative "
            "canonical/reference counts"
        )

    digest = specification.get("digest")
    if not isinstance(digest, dict):
        raise ProjectionError("projection.digest must be a mapping")
    if digest.get("algorithm") != "sha256":
        raise ProjectionError("projection.digest.algorithm must be 'sha256'")
    require_manifest_path(
        digest.get("output"),
        "projection.digest.output",
        digest_output,
    )

    for label, path in {
        "profile.homepage.record": homepage_record,
        "projection.render.homepage.template": homepage_template,
        **{
            f"projection.render.pages.{class_name}": template
            for class_name, template in page_templates.items()
        },
    }.items():
        if not path.is_file():
            raise ProjectionError(f"{label} is absent: {path}")

    return ProjectionContract(
        canonical_root=canonical_root,
        reference_root=reference_root,
        collection=collection,
        homepage_pid=homepage_pid,
        homepage_class=homepage_class,
        homepage_record=homepage_record,
        homepage_template=homepage_template,
        page_templates=page_templates,
        unrendered_classes=unrendered_classes,
        graph_node_classes=graph_node_classes,
        graph_relationship_fields=graph_relationship_fields,
        snapshot_path=snapshot_path,
        content_root=content_root,
        graph_output=graph_output,
        digest_output=digest_output,
    )


def safe_reset(path: Path) -> None:
    """Replace one named build directory and nothing outside build state."""
    resolved = path.resolve()
    build = (ROOT / "build").resolve()
    if build not in resolved.parents or resolved == build:
        raise ProjectionError(f"Refusing to replace non-build path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def require_contained_input(path: Path, root: Path, label: str) -> Path:
    """Reject input symlinks that resolve outside their declared root."""
    resolved_root = root.resolve()
    resolved = path.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ProjectionError(
            f"{label} resolves outside {resolved_root}: {path} -> {resolved}"
        )
    return resolved


def source_records(root: Path, category: str) -> list[SourceRecord]:
    resolved_root = root.resolve()
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            require_contained_input(
                candidate,
                resolved_root,
                f"{category} source input",
            )
    records: list[SourceRecord] = []
    for path in sorted(root.rglob("*.yaml")):
        if path.name == ".dumpthings.yaml":
            continue
        require_contained_input(path, resolved_root, f"{category} source record")
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


def source_closure(contract: ProjectionContract) -> list[SourceRecord]:
    """Load canonical and reference inventories from their declared roots."""
    return [
        *source_records(contract.canonical_root, "canonical"),
        *source_records(contract.reference_root, "reference"),
    ]


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


def normalized_payload(value: Any) -> str:
    """Return one deterministic, complete JSON representation."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise ProjectionError(
            f"Record payload is not normalized JSON: {error}"
        ) from error


def record_payload_index(
    records: Sequence[dict[str, Any]],
) -> dict[str, str]:
    """Index complete normalized payloads while rejecting duplicate PIDs."""
    result: dict[str, str] = {}
    for record in records:
        pid = record.get("pid")
        if not isinstance(pid, str) or not pid:
            raise ProjectionError("Record payload has no string PID")
        if pid in result:
            raise ProjectionError(f"Record payload PID is duplicated: {pid}")
        result[pid] = normalized_payload(record)
    return result


def native_value_fingerprint(value: Any) -> Counter[tuple[str, str]]:
    """Capture every qualifier on every nested native Things object."""
    result: Counter[tuple[str, str]] = Counter()
    if isinstance(value, dict):
        schema_type = value.get("schema_type")
        if isinstance(schema_type, str) and schema_type.startswith("dlthings:"):
            result[(schema_type, normalized_payload(value))] += 1
        for child in value.values():
            result.update(native_value_fingerprint(child))
    elif isinstance(value, list):
        for child in value:
            result.update(native_value_fingerprint(child))
    return result


def accepted_schema_types(schema: Path) -> set[str]:
    view = SchemaView(str(schema))
    return {str(view.get_uri(name, expand=False)) for name in view.all_classes()}


def relationship_targets(record: dict[str, Any], field: str) -> Iterator[str]:
    """Yield one producer relationship's object PIDs, rejecting bad shapes."""
    values = record.get(field, [])
    if values is None:
        return
    if not isinstance(values, list):
        values = [values]
    for value in values:
        target = value.get("object") if isinstance(value, dict) else value
        targets = target if isinstance(target, list) else [target]
        if not targets or not all(isinstance(item, str) and item for item in targets):
            raise ProjectionError(
                f"{record.get('pid', '<unknown>')}: malformed {field} target"
            )
        yield from targets


def linked_values(
    record: dict[str, Any], relationship_fields: Sequence[str]
) -> Iterator[tuple[str, str]]:
    """Yield every record PID/reference reached through native link slots."""
    for field in relationship_fields:
        values = record.get(field, [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            for target in relationship_targets({field: value}, field):
                yield field, target
            if isinstance(value, dict):
                roles = value.get("roles", [])
                if not isinstance(roles, list):
                    roles = [roles]
                for role in roles:
                    if not isinstance(role, str) or not role:
                        raise ProjectionError(
                            f"{record.get('pid', '<unknown>')}: malformed "
                            f"{field}.roles target"
                        )
                    yield f"{field}.roles", role
    for field in ("kind", "rules"):
        values = record.get(field, [])
        if not isinstance(values, list):
            values = [values]
        for value in values:
            target = value.get("object") if isinstance(value, dict) else value
            if not isinstance(target, str) or not target:
                raise ProjectionError(
                    f"{record.get('pid', '<unknown>')}: malformed {field} target"
                )
            yield field, target
    identifiers = record.get("identifiers", [])
    if not isinstance(identifiers, list):
        identifiers = [identifiers]
    for identifier in identifiers:
        if not isinstance(identifier, dict) or "creator" not in identifier:
            continue
        creator = identifier["creator"]
        if not isinstance(creator, str) or not creator:
            raise ProjectionError(
                f"{record.get('pid', '<unknown>')}: malformed "
                "identifiers.creator target"
            )
        yield "identifiers.creator", creator


def entity_route(pid: str) -> str:
    """Return the upstream qri/Hugo route encoded by one web record PID."""
    prefix = "xyzrins:"
    if not pid.startswith(prefix):
        raise ProjectionError(
            f"Renderable record PID does not use the xyzrins namespace: {pid}"
        )
    route = pid.removeprefix(prefix).strip("/")
    if (
        not route
        or route == "."
        or any(part in {"", ".", ".."} for part in route.split("/"))
    ):
        raise ProjectionError(f"Renderable record has an unsafe route: {pid}")
    return route


def validate_record_contract(
    records: list[SourceRecord],
    contract: ProjectionContract | None = None,
) -> ProjectionExpectations:
    """Validate source closure and derive its pages and native graph."""
    contract = load_projection_contract() if contract is None else contract
    unexpected = [
        record.path
        for record in records
        if record.category not in {"canonical", "reference"}
    ]
    if unexpected:
        raise ProjectionError(f"Unexpected non-source records: {unexpected}")

    canonical = {
        record.record["pid"] for record in records if record.category == "canonical"
    }
    references = {
        record.record["pid"] for record in records if record.category == "reference"
    }
    if not canonical:
        raise ProjectionError("The canonical record inventory is empty")
    if not references:
        raise ProjectionError("The reference record inventory is empty")

    by_pid = {record.record["pid"]: record for record in records}
    if len(by_pid) != len(records):
        raise ProjectionError("Record PIDs must be unique")
    homepage = by_pid.get(contract.homepage_pid)
    if homepage is None or homepage.category != "canonical":
        raise ProjectionError(
            f"Homepage PID is not a canonical record: {contract.homepage_pid}"
        )
    if homepage.record.get("schema_type") != contract.homepage_class:
        raise ProjectionError(
            f"Homepage {contract.homepage_pid} must be "
            f"{contract.homepage_class}, found "
            f"{homepage.record.get('schema_type')}"
        )
    if homepage.path.resolve() != contract.homepage_record:
        raise ProjectionError(
            "The declared homepage record path does not contain the homepage PID"
        )

    accepted = accepted_schema_types(SCHEMA)
    adjacency: dict[str, set[str]] = defaultdict(set)
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
                    f"{record['pid']}: unknown CURIE type designator: {schema_type}"
                )

        for attribute in record.get("attributes", []):
            if not isinstance(attribute, dict):
                continue
            if attribute.get("predicate") in FORBIDDEN_BRIDGE_PREDICATES:
                raise ProjectionError(
                    f"{record['pid']}: AttributeSpecification cannot encode "
                    f"relationship predicate {attribute.get('predicate')}"
                )
        for field, target in linked_values(record, contract.graph_relationship_fields):
            if target not in by_pid:
                raise ProjectionError(
                    f"{record['pid']}: dangling {field} target {target}"
                )
            adjacency[record["pid"]].add(target)

    reachable = set(canonical)
    pending = list(canonical)
    while pending:
        source = pending.pop()
        for target in adjacency[source]:
            if target not in reachable:
                reachable.add(target)
                pending.append(target)
    unused_references = references - reachable
    if unused_references:
        raise ProjectionError(
            "Reference records are outside the canonical native-link closure: "
            f"{sorted(unused_references)}"
        )

    graph_node_pids = {
        item.record["pid"]
        for item in records
        if item.category == "canonical"
        and item.record["schema_type"] in contract.graph_node_classes
    }
    graph_reference_classes = {
        item.record["schema_type"]
        for item in records
        if item.category == "reference"
        and item.record["schema_type"] in contract.graph_node_classes
    }
    if graph_reference_classes:
        raise ProjectionError(
            "Reference classes would materialize as graph nodes: "
            f"{sorted(graph_reference_classes)}"
        )
    graph_edges: set[tuple[str, str]] = set()
    for item in records:
        pid = item.record["pid"]
        if pid not in graph_node_pids:
            continue
        for field in contract.graph_relationship_fields:
            for target in relationship_targets(item.record, field):
                if target not in graph_node_pids:
                    raise ProjectionError(
                        f"{pid}: native graph target {target} from {field} "
                        "does not materialize as a canonical graph node"
                    )
                graph_edges.add((pid, target))

    declared_classes = set(contract.page_templates) | set(contract.unrendered_classes)
    record_classes = {item.record["schema_type"] for item in records}
    undeclared_classes = record_classes - declared_classes
    if undeclared_classes:
        raise ProjectionError(
            "Record classes have no rendered/unrendered policy: "
            f"{sorted(undeclared_classes)}"
        )
    rendered_references = {
        item.record["schema_type"]
        for item in records
        if item.category == "reference"
        and item.record["schema_type"] in contract.page_templates
    }
    if rendered_references:
        raise ProjectionError(
            "Reference classes cannot produce entity pages: "
            f"{sorted(rendered_references)}"
        )

    entity_routes = {
        entity_route(item.record["pid"])
        for item in records
        if item.category == "canonical"
        and item.record["pid"] != contract.homepage_pid
        and item.record["schema_type"] in contract.page_templates
    }
    markdown_pages = {
        "_index.md",
        *(f"{route}/_index.md" for route in entity_routes),
    }
    return ProjectionExpectations(
        canonical_pids=frozenset(canonical),
        reference_pids=frozenset(references),
        graph_node_pids=frozenset(graph_node_pids),
        graph_edges=frozenset(graph_edges),
        markdown_pages=frozenset(markdown_pages),
        entity_routes=frozenset(entity_routes),
        record_payloads=tuple(
            sorted(
                (pid, normalized_payload(item.record)) for pid, item in by_pid.items()
            )
        ),
    )


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
                f"{item.record['pid']}: JSON/RDF/JSON round trip failed: {error}"
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
                f"{item.record['pid']}: round trip changed native-object qualifiers"
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
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
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
def dump_things_service(records: list[SourceRecord], state: Path) -> Iterator[str]:
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
    (state / "dtc-validation.log").write_text("".join(validation_log), encoding="utf-8")

    environment["DTC_TOKEN"] = READER_TOKEN
    exported = run(
        ["dtc", "get-records", url, COLLECTION],
        environment=environment,
        action="Export validated CON records through dtc",
    )
    parsed = [json.loads(line) for line in exported.splitlines() if line.strip()]
    parsed.sort(key=lambda record: (record["schema_type"], record["pid"]))
    expected = record_payload_index([item.record for item in records])
    actual = record_payload_index(parsed)
    if actual != expected:
        mismatched = sorted(
            pid
            for pid in set(actual) | set(expected)
            if actual.get(pid) != expected.get(pid)
        )
        raise ProjectionError(
            "dtc export payload differs from the normalized source closure: "
            f"{mismatched}"
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


def upstream_qri_pipelines(
    contract: ProjectionContract,
    workflow_path: Path | None = None,
) -> tuple[dict[str, list[list[str]]], list[list[str]]]:
    """Derive page-selection pipelines from the pinned upstream workflow."""
    path = SITE / UPSTREAM_UPDATE_WORKFLOW if workflow_path is None else workflow_path
    workflow = load_yaml(path)
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        raise ProjectionError("Pinned upstream workflow has no jobs mapping")
    create_pages = jobs.get("create_pages")
    if not isinstance(create_pages, dict):
        raise ProjectionError("Pinned upstream workflow has no create_pages job")
    steps = create_pages.get("steps")
    if not isinstance(steps, list):
        raise ProjectionError("Pinned upstream create_pages job has no steps")

    page_pipelines: dict[str, list[list[str]]] = {}
    page_templates: dict[str, Path] = {}
    homepage_pipeline: list[list[str]] | None = None
    homepage_template: Path | None = None
    expected_output = "content/{__pid_curie_reference}/_index.md"
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("run"), str):
            continue
        script = re.sub(r"\\\s*\n\s*", " ", step["run"]).strip()
        segments = [segment.strip() for segment in script.split("|")]
        if not segments or not segments[0].startswith("qri list "):
            continue
        try:
            commands = [shlex.split(segment) for segment in segments]
        except ValueError as error:
            raise ProjectionError(
                f"Cannot parse pinned upstream qri pipeline: {error}"
            ) from error
        if any(not command or command[0] != "qri" for command in commands):
            raise ProjectionError(
                "Pinned upstream page pipeline contains a non-qri command"
            )
        renderer = commands[-1]
        if len(renderer) != 4 or renderer[:2] != ["qri", "render-record"]:
            raise ProjectionError(
                "Pinned upstream page pipeline has an unexpected renderer"
            )
        if renderer[3] != expected_output:
            raise ProjectionError(
                "Pinned upstream page pipeline has an unexpected output path: "
                f"{renderer[3]!r}"
            )
        template = site_manifest_path(
            renderer[2], "pinned upstream qri render template"
        )
        selection = commands[:-1]
        first = selection[0]
        is_homepage = first[:3] == ["qri", "list", "--pid"]
        if is_homepage:
            if len(first) != 4 or first[3] != "xyzrins:.":
                raise ProjectionError(
                    "Pinned upstream homepage pipeline selects an unexpected PID"
                )
            if homepage_pipeline is not None:
                raise ProjectionError(
                    "Pinned upstream workflow defines multiple homepage pipelines"
                )
        else:
            if len(first) != 4 or first[:3] != ["qri", "list", "--class"]:
                raise ProjectionError(
                    "Pinned upstream page pipeline has an unexpected selector"
                )
            schema_type = first[3]
            if schema_type in page_pipelines:
                raise ProjectionError(
                    "Pinned upstream workflow defines multiple pipelines for "
                    f"{schema_type}"
                )

        adapted: list[list[str]] = []
        for command in selection:
            command = [
                contract.collection if token == "public" else token for token in command
            ]
            command = [
                contract.homepage_pid if token == "xyzrins:." else token
                for token in command
            ]
            if command[:2] == ["qri", "inject-links-pid"] and not any(
                token in {"-c", "--collection"} for token in command
            ):
                command.extend(["-c", contract.collection])
            adapted.append(command)

        if is_homepage:
            homepage_pipeline = adapted
            homepage_template = template
        else:
            page_pipelines[schema_type] = adapted
            page_templates[schema_type] = template

    if homepage_pipeline is None or homepage_template is None:
        raise ProjectionError("Pinned upstream workflow has no homepage qri pipeline")
    if homepage_template != contract.homepage_template:
        raise ProjectionError(
            "Declared homepage template differs from the pinned upstream pipeline"
        )
    unsupported = set(contract.page_templates) - set(page_pipelines)
    if unsupported:
        raise ProjectionError(
            f"Rendered classes have no pinned qri pipeline: {sorted(unsupported)}"
        )
    mismatched = {
        schema_type: (contract.page_templates[schema_type], page_templates[schema_type])
        for schema_type in contract.page_templates
        if contract.page_templates[schema_type] != page_templates[schema_type]
    }
    if mismatched:
        raise ProjectionError(
            "Declared page templates differ from pinned upstream pipelines: "
            f"{mismatched}"
        )
    return page_pipelines, homepage_pipeline


def render_qri(
    url: str,
    records: list[dict[str, Any]],
    output: Path,
    state: Path,
    contract: ProjectionContract,
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
    selection_commands, homepage_commands = upstream_qri_pipelines(contract)
    for schema_type, page_template in sorted(contract.page_templates.items()):
        commands = selection_commands[schema_type]
        name = schema_type.removeprefix("xyzri:XYZ").lower()
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
        homepage_commands,
        environment,
        action="Select and inline the CON homepage projection",
    )
    qri_pipeline(
        [
            [
                "qri",
                "render-record",
                contract.homepage_template,
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
    records: list[dict[str, Any]],
    output: Path,
    expectations: ProjectionExpectations | None = None,
) -> dict[str, Any]:
    if expectations is None:
        contract = load_projection_contract()
        expectations = validate_record_contract(source_closure(contract), contract)
    graph = json.loads((output / "static" / "graph.json").read_text())
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ProjectionError("Upstream graph output has no node/edge lists")
    node_pids = {node.get("id") for node in nodes}
    if node_pids != expectations.graph_node_pids or len(nodes) != len(
        expectations.graph_node_pids
    ):
        raise ProjectionError(
            "CON graph node closure differs: "
            f"expected={sorted(expectations.graph_node_pids)}, "
            f"actual={sorted(node_pids)}"
        )
    edge_pairs = {(edge.get("source"), edge.get("target")) for edge in edges}
    if edge_pairs != expectations.graph_edges or len(edges) != len(
        expectations.graph_edges
    ):
        raise ProjectionError(
            "CON graph edge closure differs: "
            f"expected={sorted(expectations.graph_edges)}, "
            f"actual={sorted(edge_pairs)}"
        )
    actual_payloads = record_payload_index(records)
    expected_payloads = dict(expectations.record_payloads)
    if actual_payloads != expected_payloads:
        mismatched = sorted(
            pid
            for pid in set(actual_payloads) | set(expected_payloads)
            if actual_payloads.get(pid) != expected_payloads.get(pid)
        )
        raise ProjectionError(
            f"qri record payload differs from source inventory: {mismatched}"
        )

    actual_pages = {
        path.relative_to(output / "content").as_posix()
        for path in (output / "content").rglob("*.md")
    }
    if actual_pages != expectations.markdown_pages:
        raise ProjectionError(
            "Unexpected qri page closure: "
            f"expected={sorted(expectations.markdown_pages)}, "
            f"actual={sorted(actual_pages)}"
        )
    return {
        "records": len(records),
        "canonical_records": len(expectations.canonical_pids),
        "reference_records": len(expectations.reference_pids),
        "generated_records": 0,
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "pages": len(actual_pages),
        "native_edges": sorted([list(pair) for pair in edge_pairs]),
    }


def files_below(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    resolved_root = root.resolve()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            require_contained_input(path, resolved_root, "Scoped file input")
        if path.is_file() and path.name != ".DS_Store":
            yield path


def scoped_digest_path(value: str) -> tuple[str, Path, Path]:
    """Resolve one digest scope entry to its labeled repository root."""
    if value.startswith("upstream:"):
        label = "upstream"
        root = SITE
        relative = value.removeprefix("upstream:")
    elif value.startswith("parent:"):
        label = "parent"
        root = ROOT
        relative = value.removeprefix("parent:")
    else:
        label = "site"
        root = SITE
        relative = value
    if not relative or Path(relative).is_absolute():
        raise ProjectionError(f"Invalid projection digest scope path: {value}")
    path = root / relative
    require_contained_input(path, root, f"Projection digest scope {value}")
    return label, path, root


def input_files(
    specification: dict[str, Any] | None = None,
) -> list[tuple[str, Path]]:
    """Expand the projection manifest's explicit metadata-only file scope."""
    specification = (
        load_yaml(PROJECTION_SPEC_PATH) if specification is None else specification
    )
    digest = specification.get("digest")
    if not isinstance(digest, dict):
        raise ProjectionError("projection.digest must be a mapping")
    scope = unique_strings(digest.get("scope"), "projection.digest.scope")
    sentinels = {"component-commit-pins", "projection-runtime-pins"}
    missing_sentinels = sentinels - set(scope)
    if missing_sentinels:
        raise ProjectionError(
            "Projection digest scope omits required pin sets: "
            f"{sorted(missing_sentinels)}"
        )

    entries: list[tuple[str, Path]] = []
    for item in scope:
        if item in sentinels:
            continue
        label, path, repository_root = scoped_digest_path(item)
        resolved_path = path.resolve()
        if resolved_path == COMMITTED.resolve() or COMMITTED.resolve() in (
            resolved_path.parents
        ):
            raise ProjectionError(
                f"Projection outputs cannot also be digest inputs: {item}"
            )
        if path.is_file():
            paths = [path]
        elif path.is_dir():
            paths = list(files_below(path))
        else:
            raise ProjectionError(f"Projection digest input is absent: {path}")
        for candidate in paths:
            require_contained_input(
                candidate,
                resolved_path if path.is_dir() else repository_root,
                f"Projection digest input {item}",
            )
            relative = candidate.relative_to(repository_root).as_posix()
            entries.append((f"{label}/{relative}", candidate))
    labels = [label for label, _ in entries]
    if len(labels) != len(set(labels)):
        raise ProjectionError("Projection digest scope names an input twice")
    return sorted(entries, key=lambda item: item[0])


def projection_local_runtime_pins(config: dict[str, Any]) -> dict[str, str]:
    """Bind local Pixi package paths and overrides to pinned submodules."""
    pypi = config.get("pypi-dependencies", {})
    if not isinstance(pypi, dict):
        raise ProjectionError("Pixi PyPI dependency table is missing")
    local_pins: dict[str, str] = {}
    for name, path in PROJECTION_LOCAL_PYPI_PATHS.items():
        declaration = pypi.get(name)
        expected = {"path": path}
        if declaration != expected:
            raise ProjectionError(
                f"Projection runtime {name} must be declared exactly as {expected}, "
                f"found {declaration!r}"
            )
        local_pins[f"local:{name}"] = f"path={path}"

    options = config.get("pypi-options", {})
    overrides = (
        options.get("dependency-overrides") if isinstance(options, dict) else None
    )
    expected_overrides = {
        "dump-things-pyclient": {
            "path": PROJECTION_LOCAL_PYPI_PATHS["dump-things-pyclient"]
        }
    }
    if overrides != expected_overrides:
        raise ProjectionError(
            "Projection runtime dependency overrides must be declared exactly as "
            f"{expected_overrides}, found {overrides!r}"
        )
    local_pins["override:dump-things-pyclient"] = (
        "path=" + PROJECTION_LOCAL_PYPI_PATHS["dump-things-pyclient"]
    )
    return local_pins


def projection_runtime_pins() -> list[tuple[str, str]]:
    """Return only direct runtimes that can alter metadata projection bytes."""
    config = tomllib.loads((ROOT / "pixi.toml").read_text(encoding="utf-8"))
    conda = config.get("dependencies", {})
    pypi = config.get("pypi-dependencies", {})
    if not isinstance(conda, dict) or not isinstance(pypi, dict):
        raise ProjectionError("Pixi dependency tables are missing")
    sources = {
        "python": conda.get("python"),
        "jinja2": pypi.get("jinja2"),
        "packaging": pypi.get("packaging"),
        "pyyaml": pypi.get("pyyaml"),
        "linkml": pypi.get("linkml"),
        "linkml-runtime": pypi.get("linkml-runtime"),
        "pydantic": pypi.get("pydantic"),
        "rdflib": pypi.get("rdflib"),
    }
    if not all(isinstance(value, str) and value for value in sources.values()):
        raise ProjectionError(
            "Projection runtime dependencies must use direct string pins"
        )
    local_pins = projection_local_runtime_pins(config)
    return sorted(
        [*(sources.items()), *(local_pins.items())],
        key=lambda item: item[0],
    )


def conda_package_name(reference: str, known_names: set[str]) -> str:
    """Recover a Conda package name from one resolved artifact reference."""
    filename = Path(urlsplit(reference).path).name
    for suffix in (".conda", ".tar.bz2"):
        if filename.endswith(suffix):
            filename = filename[: -len(suffix)]
            break
    matches = [name for name in known_names if filename.startswith(f"{name}-")]
    if not matches:
        raise ProjectionError(
            f"Cannot identify resolved Conda package from {reference!r}"
        )
    return max(matches, key=len)


def conda_package_version(reference: str, name: str) -> str:
    """Return the version encoded in one resolved Conda artifact name."""
    filename = Path(urlsplit(reference).path).name
    for suffix in (".conda", ".tar.bz2"):
        if filename.endswith(suffix):
            filename = filename[: -len(suffix)]
            break
    remainder = filename.removeprefix(f"{name}-")
    version, separator, _ = remainder.partition("-")
    if not separator or not version:
        raise ProjectionError(
            f"Cannot identify resolved Conda version from {reference!r}"
        )
    return version


def lock_platform_environment(
    platform: str,
    subdir: str,
    python_version: str,
) -> dict[str, str]:
    """Return deterministic marker values for one locked target platform."""
    major_minor = ".".join(python_version.split(".")[:2])
    environment = {
        "implementation_name": "cpython",
        "implementation_version": python_version,
        "os_name": "posix",
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_version": "",
        "python_full_version": python_version,
        "python_version": major_minor,
    }
    if subdir == "linux-64":
        environment.update(
            {
                "platform_machine": "x86_64",
                "platform_system": "Linux",
                "sys_platform": "linux",
            }
        )
    elif subdir == "osx-arm64":
        environment.update(
            {
                "platform_machine": "arm64",
                "platform_system": "Darwin",
                "sys_platform": "darwin",
            }
        )
    else:
        raise ProjectionError(
            f"Projection runtime does not define marker values for {platform}: {subdir}"
        )
    return environment


def require_deterministic_marker(requirement: Requirement) -> None:
    """Reject requirement markers that depend on an unspecified host kernel."""
    marker_text = str(requirement.marker or "")
    if re.search(
        r"\b(?:platform_release|platform_version)\b",
        marker_text,
    ):
        raise ProjectionError(
            f"Projection dependency uses a host-specific marker: {str(requirement)!r}"
        )


def projection_runtime_lock_records(
    lock_path: Path | None = None,
) -> list[tuple[str, str]]:
    """Resolve projection-only direct/transitive packages from Pixi's lock."""
    lock_path = ROOT / "pixi.lock" if lock_path is None else lock_path
    if not lock_path.is_file() or lock_path.is_symlink():
        raise ProjectionError(f"Resolved Pixi lock is absent or symlinked: {lock_path}")
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    if not isinstance(lock, dict) or lock.get("version") != 7:
        raise ProjectionError("Projection runtime requires Pixi lock format 7")
    packages = lock.get("packages")
    environments = lock.get("environments")
    platforms = lock.get("platforms")
    if (
        not isinstance(packages, list)
        or not isinstance(environments, dict)
        or not isinstance(platforms, list)
    ):
        raise ProjectionError("Pixi lock package/environment tables are malformed")
    default = environments.get("default")
    if not isinstance(default, dict) or not isinstance(default.get("packages"), dict):
        raise ProjectionError("Pixi lock has no default environment package table")

    package_by_reference: dict[tuple[str, str], dict[str, Any]] = {}
    conda_names: set[str] = {"python"}
    config = tomllib.loads((ROOT / "pixi.toml").read_text(encoding="utf-8"))
    direct_conda = config.get("dependencies", {})
    if isinstance(direct_conda, dict):
        conda_names.update(str(name) for name in direct_conda)
    targets = config.get("target", {})
    if isinstance(targets, dict):
        for target in targets.values():
            if isinstance(target, dict) and isinstance(
                target.get("dependencies"), dict
            ):
                conda_names.update(str(name) for name in target["dependencies"])
    for package in packages:
        if not isinstance(package, dict):
            raise ProjectionError("Pixi lock package entry is not a mapping")
        references = [
            (kind, package[kind])
            for kind in ("conda", "pypi")
            if isinstance(package.get(kind), str)
        ]
        if len(references) != 1:
            raise ProjectionError(
                "Pixi lock package entry must have one Conda or PyPI reference"
            )
        kind, reference = references[0]
        key = (kind, reference)
        if key in package_by_reference:
            raise ProjectionError(f"Pixi lock repeats package reference {key}")
        package_by_reference[key] = package
        for dependency in package.get("depends", []):
            if isinstance(dependency, str):
                name = dependency.split()[0]
                if not name.startswith("__"):
                    conda_names.add(name)

    platform_subdirs: dict[str, str] = {}
    for value in platforms:
        if not isinstance(value, dict) or not isinstance(value.get("name"), str):
            raise ProjectionError("Pixi lock platform entry is malformed")
        name = value["name"]
        subdir = value.get("subdir", name)
        if not isinstance(subdir, str):
            raise ProjectionError(f"Pixi lock platform {name} has no subdir")
        platform_subdirs[name] = subdir

    result: list[tuple[str, str]] = []
    for platform, references in sorted(default["packages"].items()):
        if platform not in platform_subdirs or not isinstance(references, list):
            raise ProjectionError(
                f"Pixi lock environment platform is invalid: {platform}"
            )
        selected: dict[tuple[str, str], dict[str, Any]] = {}
        for reference_item in references:
            if not isinstance(reference_item, dict) or len(reference_item) != 1:
                raise ProjectionError(
                    f"Pixi lock reference for {platform} is malformed"
                )
            kind, reference = next(iter(reference_item.items()))
            if kind not in {"conda", "pypi"} or not isinstance(reference, str):
                raise ProjectionError(
                    f"Pixi lock reference for {platform} is malformed"
                )
            package = package_by_reference.get((kind, reference))
            if package is None:
                raise ProjectionError(
                    f"Pixi lock reference has no package entry: {reference}"
                )
            if kind == "pypi":
                raw_name = package.get("name")
                if not isinstance(raw_name, str):
                    raise ProjectionError(f"PyPI package has no name: {reference}")
                name = canonicalize_name(raw_name)
            else:
                name = conda_package_name(reference, conda_names)
            key = (kind, name)
            if key in selected:
                raise ProjectionError(
                    f"Pixi lock selects {kind}:{name} twice for {platform}"
                )
            selected[key] = package

        python_package = selected.get(("conda", "python"))
        if python_package is None:
            raise ProjectionError(f"Pixi lock has no Python package for {platform}")
        match = re.search(
            r"/python-(\d+\.\d+\.\d+)-",
            str(python_package["conda"]),
        )
        if match is None:
            raise ProjectionError(
                f"Cannot determine locked Python version for {platform}"
            )
        marker_environment = lock_platform_environment(
            platform,
            platform_subdirs[platform],
            match.group(1),
        )

        roots = {("conda", "python"): {""}}
        roots.update(
            {("pypi", canonicalize_name(name)): {""} for name in PROJECTION_PYPI_ROOTS}
        )
        active_extras = {key: set(extras) for key, extras in roots.items()}
        pending = list(active_extras)
        visited: dict[tuple[str, str], set[str]] = {}
        while pending:
            key = pending.pop()
            extras = active_extras[key]
            if visited.get(key) == extras:
                continue
            visited[key] = set(extras)
            package = selected.get(key)
            if package is None:
                raise ProjectionError(
                    f"Projection runtime dependency is not locked for {platform}: "
                    f"{key[0]}:{key[1]}"
                )
            dependencies: list[tuple[tuple[str, str], set[str]]] = []
            if key[0] == "conda":
                for dependency in package.get("depends", []):
                    if not isinstance(dependency, str):
                        raise ProjectionError(
                            f"Conda dependency for {key[1]} is malformed"
                        )
                    name = dependency.split()[0]
                    if not name.startswith("__"):
                        dependencies.append((("conda", name), set()))
            else:
                for dependency in package.get("requires_dist", []):
                    if not isinstance(dependency, str):
                        raise ProjectionError(
                            f"PyPI dependency for {key[1]} is malformed"
                        )
                    try:
                        requirement = Requirement(dependency)
                    except InvalidRequirement as error:
                        raise ProjectionError(
                            f"Cannot parse locked requirement {dependency!r}"
                        ) from error
                    require_deterministic_marker(requirement)
                    if requirement.marker is not None and not any(
                        requirement.marker.evaluate(
                            {**marker_environment, "extra": extra}
                        )
                        for extra in extras
                    ):
                        continue
                    dependencies.append(
                        (
                            ("pypi", canonicalize_name(requirement.name)),
                            set(requirement.extras),
                        )
                    )
            for dependency_key, dependency_extras in dependencies:
                if dependency_key not in selected:
                    raise ProjectionError(
                        f"Projection dependency is unresolved for {platform}: "
                        f"{key[1]} -> {dependency_key[1]}"
                    )
                required_extras = {"", *dependency_extras}
                if required_extras <= active_extras.get(dependency_key, set()):
                    continue
                active_extras.setdefault(dependency_key, set()).update(required_extras)
                pending.append(dependency_key)

        for kind, name in sorted(visited):
            package = selected[(kind, name)]
            fields = (
                ("conda", "sha256", "md5", "depends", "constrains")
                if kind == "conda"
                else (
                    "pypi",
                    "name",
                    "version",
                    "sha256",
                    "requires_dist",
                    "requires_python",
                )
            )
            payload = {field: package[field] for field in fields if field in package}
            payload["active_extras"] = sorted(visited[(kind, name)])
            payload["platform_subdir"] = platform_subdirs[platform]
            version = package.get("version")
            if kind == "conda":
                identity = conda_package_version(str(package["conda"]), name)
            else:
                identity = version if isinstance(version, str) else "local"
            label = f"{platform_subdirs[platform]}:{kind}:{name}@{identity}"
            result.append(
                (
                    label,
                    digest_bytes((normalized_payload(payload) + "\n").encode("utf-8")),
                )
            )
    return sorted(result)


def projection_runtime_lock_digest(lock_path: Path | None = None) -> str:
    """Fingerprint only the resolved runtime closure used by projection."""
    records = projection_runtime_lock_records(lock_path)
    payload = "".join(f"{digest}  {label}\n" for label, digest in records)
    return digest_bytes(payload.encode("utf-8"))


def projection_component_pins() -> list[tuple[str, str]]:
    """Return source/runtime commits that can alter projection bytes."""
    return [
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
    ]


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


def projection_profile_digest_bytes(path: Path) -> bytes:
    """Serialize only profile declarations that can alter projection bytes."""
    profile = load_yaml(path)
    identity = profile.get("identity")
    paths = profile.get("paths")
    schema = profile.get("schema")
    homepage = profile.get("homepage")
    build = profile.get("build")
    if not all(
        isinstance(value, dict) for value in (identity, paths, schema, homepage, build)
    ):
        raise ProjectionError("Projection profile contract sections are malformed")
    payload = {
        "version": profile.get("version"),
        "name": profile.get("name"),
        "identity": {"homepage_pid": identity.get("homepage_pid")},
        "paths": {
            key: paths.get(key)
            for key in (
                "canonical_records",
                "reference_records",
                "qri_snapshot",
                "content",
                "graph",
                "digest",
            )
        },
        "schema": {key: schema.get(key) for key in ("path", "discriminator_contract")},
        "homepage": {key: homepage.get(key) for key in ("pid", "class", "record")},
        "build": {"metadata_collection": build.get("metadata_collection")},
    }
    return (normalized_payload(payload) + "\n").encode("utf-8")


def projection_input_bytes(label: str, path: Path) -> bytes:
    """Return the projection-relevant representation of one scoped input."""
    if label == "site/profiles/con/profile.yaml":
        return projection_profile_digest_bytes(path)
    return path.read_bytes()


def projection_manifest(output: Path) -> str:
    lines = ["# clean-migration projection manifest v1"]
    for label, path in input_files():
        if not path.is_file():
            raise ProjectionError(f"Projection input is absent: {path}")
        lines.append(
            f"{digest_bytes(projection_input_bytes(label, path))}  input:{label}"
        )
    for name, commit in projection_component_pins():
        lines.append(
            f"{digest_bytes((commit + chr(10)).encode())}  pin:{name}@{commit}"
        )
    for name, version in projection_runtime_pins():
        value = f"{name}{version}"
        lines.append(f"{digest_bytes((value + chr(10)).encode())}  pin:runtime:{value}")
    for label, digest in projection_runtime_lock_records():
        lines.append(f"{digest}  pin:runtime-resolved:{label}")
    lines.append(
        f"{projection_runtime_lock_digest()}  pin:runtime-lock:projection-closure"
    )
    for path in files_below(output):
        if path.name == "SHA256SUMS" or path.name.startswith("qri-cache"):
            continue
        relative = path.relative_to(output).as_posix()
        lines.append(f"{digest_bytes(path.read_bytes())}  output:{relative}")
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
        raise ProjectionError("The clean-migration website profile is not checked out")
    profile = load_yaml(PROFILE_PATH)
    verify_declared_pins(profile)
    contract = load_projection_contract(profile)
    all_records = source_closure(contract)
    expectations = validate_record_contract(all_records, contract)
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
        render_qri(url, exported, output, state, contract)
    report = validate_projection(exported, output, expectations)
    shutil.rmtree(state)
    (output / "SHA256SUMS").write_text(projection_manifest(output), encoding="utf-8")
    stack_records(exported, BUILD_ROOT / "records.jsonl")
    report_path = BUILD_ROOT / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def compare_trees(left: Path, right: Path) -> None:
    left_files = {path.relative_to(left).as_posix(): path for path in files_below(left)}
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
    render_parser.add_argument("--output", type=Path, default=BUILD_ROOT / "candidate")
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
            verify_final_site_state(load_yaml(PROFILE_PATH))
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
