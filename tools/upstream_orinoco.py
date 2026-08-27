#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
#
# [tool.pixi.workspace]
# channels = ["conda-forge"]
# platforms = [
#   { platform = "osx-arm64", macos = "14.0" },
#   "linux-64",
# ]
#
# [tool.pixi.dependencies]
# python = ">=3.12,<3.13"
#
# [tool.pixi.pypi-dependencies]
# copier = "==9.10.3"
# pyyaml = "==6.0.2"
# ///
"""Compose the latest upstream snapshot as an ordinary Orinoco Lite repo."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
STACK = BUILD / "upstream-stack"
SNAPSHOT = STACK / "snapshot"
SNAPSHOT_RECORDS = SNAPSHOT / "metadata" / "records"
SNAPSHOT_MANIFEST = SNAPSHOT / "manifest.json"
RAW_JSONL = STACK / "pool" / "public-thing.jsonl"
POOL_MANIFEST = STACK / "pool" / "manifest.json"
CANONICAL_JSONL = SNAPSHOT / "records.jsonl"
ORINOCO_STORAGE = SNAPSHOT / "orinoco-storage"
ORINOCO_RECORDS = ORINOCO_STORAGE / "metadata" / "records"
ORINOCO_ANNOTATIONS = ORINOCO_STORAGE / "metadata" / "overlays" / "annotations"
ORINOCO_STORAGE_MANIFEST = ORINOCO_STORAGE / "manifest.json"
UPSTREAM_SITE = ROOT / "submodules" / "www-from-model"
DEFAULT_DESTINATION = BUILD / "upstream-orinoco-site"
DEFAULT_TEMPLATE_SOURCE = "gh:ORINOCO-Lite/orinoco-lite-template"
DEFAULT_TEMPLATE_VERSION = "v0.2.0rc10"
PUBLIC_TEMPLATE_SOURCE = "gh:ORINOCO-Lite/orinoco-lite-template"
IGNORED_SOURCE_NAMES = frozenset(
    {".datalad", ".git", ".github", ".gitmodules", "__pycache__"}
)
FRAMEWORK_DIRECTORIES = (
    "archetypes",
    "assets",
    "config",
    "layouts",
    "static",
    "themes",
)
PAGE_POLICIES: dict[str, dict[str, Any]] = {
    "xyzri:XYZDataset": {
        "template": "site/projection-templates/dataset.md.j2",
        "inline": [
            "about",
            "attributed_to::object",
            "kind",
            "rules",
            "characterized_by::object",
        ],
    },
    "xyzri:XYZObjective": {
        "template": "site/projection-templates/objective.md.j2",
        "inline": ["part_of", "depends_on"],
    },
    "xyzri:XYZTopic": {
        "template": "site/projection-templates/topic.md.j2",
        "inline": ["part_of"],
    },
    "xyzri:XYZProject": {
        "template": "site/projection-templates/project.md.j2",
        "select": {
            "links_to": {
                "field": "part_of",
                "pid": "xyzrins:.",
                "recursive": True,
            }
        },
        "reverse_injections": [
            {"from": "generated_by", "to": "generated"},
            {"from": "part_of", "to": "parts"},
        ],
        "inline": [
            "associated_with::object",
            "associated_with::roles",
            "influenced_by::object",
            "influenced_by::roles",
            "identifiers::creator",
            "part_of",
        ],
    },
    "xyzri:XYZPerson": {
        "template": "site/projection-templates/person.md.j2",
        "select": {
            "linked_from": {
                "pid": "xyzrins:.",
                "field": "associated_with",
            }
        },
        "inline": [
            "delegated_by::object",
            "delegated_by::roles",
            "identifiers::creator",
        ],
    },
    "xyzri:XYZPublication": {
        "template": "site/projection-templates/publication.md.j2",
        "inline": ["about", "attributed_to::object"],
    },
    "xyzri:XYZInstrument": {
        "template": "site/projection-templates/instrument.md.j2",
        "inline": ["about", "attributed_to::object", "kind", "rules"],
    },
}
HOMEPAGE_POLICY = {
    "pid": "xyzrins:.",
    "template": "site/projection-templates/homepage.md.j2",
    "reverse_injections": [
        {"from": "generated_by", "to": "generated"},
        {"from": "part_of", "to": "parts"},
    ],
    "inline": [
        "associated_with::object",
        "associated_with::roles",
        "influenced_by::object",
        "influenced_by::roles",
        "identifiers::creator",
        "part_of",
    ],
}
GRAPH_NODE_CLASSES = (
    "xyzri:XYZDataset",
    "xyzri:XYZInstrument",
    "xyzri:XYZObjective",
    "xyzri:XYZOrganization",
    "xyzri:XYZPerson",
    "xyzri:XYZProject",
    "xyzri:XYZPublication",
    "xyzri:XYZTopic",
)
GRAPH_RELATIONSHIP_FIELDS = (
    "about",
    "associated_with",
    "attributed_to",
    "delegated_by",
    "generated_by",
    "influenced_by",
    "part_of",
)


class UpstreamOrinocoError(RuntimeError):
    """Report an unsafe or incomplete fixture composition."""


def require_script_environment() -> None:
    manifest = os.environ.get("PIXI_PROJECT_MANIFEST", "")
    if not manifest or Path(manifest).resolve() != Path(__file__).resolve():
        raise UpstreamOrinocoError(
            "Run through the instantiate-upstream-orinoco Pixi task"
        )
    if shutil.which("copier") is None or shutil.which("git") is None:
        raise UpstreamOrinocoError("The locked fixture environment is incomplete")


def run(
    arguments: Sequence[str | Path],
    *,
    cwd: Path = ROOT,
    capture: bool = False,
) -> str:
    result = subprocess.run(
        [str(item) for item in arguments],
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise UpstreamOrinocoError(
            f"{' '.join(str(item) for item in arguments)} failed "
            f"with status {result.returncode}: {detail}"
        )
    return result.stdout.strip() if capture else ""


def _safe_destination(destination: Path) -> Path:
    resolved = destination.resolve(strict=False)
    build = BUILD.resolve()
    if resolved == build or build not in resolved.parents:
        raise UpstreamOrinocoError(
            f"fixture destination must be below {BUILD}: {resolved}"
        )
    return resolved


def _ignored(relative: Path) -> bool:
    return any(part in IGNORED_SOURCE_NAMES for part in relative.parts)


def copy_regular_tree(source: Path, destination: Path) -> None:
    """Flatten source symlinks and nested repositories into ordinary files."""

    if not source.is_dir():
        raise UpstreamOrinocoError(f"missing upstream source directory: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for candidate in sorted(source.rglob("*")):
        relative = candidate.relative_to(source)
        if _ignored(relative):
            continue
        target = destination / relative
        if candidate.is_dir() and not candidate.is_symlink():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not candidate.is_file():
            raise UpstreamOrinocoError(
                f"upstream payload is not locally available: {candidate}; "
                "run the preparation task so git-annex can hydrate it"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate, target, follow_symlinks=True)
        shutil.copymode(candidate, target, follow_symlinks=True)


def _record_inventory() -> tuple[int, Counter[str], dict[str, set[str]]]:
    classes: Counter[str] = Counter()
    namespaces: dict[str, set[str]] = defaultdict(set)
    pids: set[str] = set()
    for path in sorted(ORINOCO_RECORDS.rglob("*.yaml")):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise UpstreamOrinocoError(f"snapshot record is not a mapping: {path}")
        pid = value.get("pid")
        schema_type = value.get("schema_type")
        if not isinstance(pid, str) or not isinstance(schema_type, str):
            raise UpstreamOrinocoError(f"snapshot record identity is invalid: {path}")
        if pid in pids:
            raise UpstreamOrinocoError(f"snapshot repeats PID {pid!r}")
        pids.add(pid)
        classes[schema_type] += 1
        namespace = pid.split(":", 1)[0] if ":" in pid else "(none)"
        namespaces[schema_type].add(namespace)
    if not pids:
        raise UpstreamOrinocoError(f"snapshot has no YAML records: {SNAPSHOT_RECORDS}")
    return len(pids), classes, namespaces


def _write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            dict(value),
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy_portable_json(
    source: Path,
    destination: Path,
    *,
    rewrites: Mapping[str, str],
) -> None:
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise UpstreamOrinocoError(f"provenance source is not an object: {source}")
    for key, replacement in rewrites.items():
        if key not in value:
            raise UpstreamOrinocoError(
                f"provenance source lacks required field {key!r}: {source}"
            )
        value[key] = replacement
    _write_json(destination, value)


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _normalize_copier_answers(destination: Path, template_version: str) -> None:
    path = destination / ".copier-answers.yml"
    answers = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(answers, dict):
        raise UpstreamOrinocoError("Copier did not write a valid answers file")
    answers.pop("_src_path", None)
    answers.pop("_commit", None)
    normalized = {
        "_src_path": PUBLIC_TEMPLATE_SOURCE,
        **answers,
        "_commit": template_version,
    }
    _write_yaml(path, normalized)


def render_template(
    destination: Path,
    *,
    template_source: str,
    template_version: str,
) -> None:
    answers = {
        "project_name": "Latest upstream pool snapshot",
        "project_slug": "upstream-orinoco-snapshot",
        "repository_slug": "example/upstream-orinoco-snapshot",
        "site_base_url": "https://example.invalid/upstream-orinoco-snapshot/",
        "site_description": (
            "A generated Orinoco Lite fixture for the latest upstream pool snapshot."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="upstream-orinoco-copier-") as temporary:
        data_file = Path(temporary) / "answers.yaml"
        _write_yaml(data_file, answers)
        run(
            [
                "copier",
                "copy",
                "--quiet",
                "--defaults",
                "--overwrite",
                "--vcs-ref",
                template_version,
                "--data-file",
                data_file,
                template_source,
                destination,
            ]
        )
    _normalize_copier_answers(destination, template_version)


def projection_contract(classes: Counter[str]) -> dict[str, Any]:
    return {
        "version": 2,
        "routing": {"strip_prefix": "xyzrins:"},
        "references": {"missing_targets": "preserve"},
        "editor": {"record_scope": "editable"},
        "homepage": HOMEPAGE_POLICY,
        "pages": PAGE_POLICIES,
        "unrendered_classes": sorted(set(classes) - set(PAGE_POLICIES)),
        "graph": {
            "producer": "site/projection-tools/pool2graph.py",
            "node_classes": list(GRAPH_NODE_CLASSES),
            "relationship_fields": list(GRAPH_RELATIONSHIP_FIELDS),
            "missing_external_targets": "drop",
        },
    }


def assert_ordinary_repository(destination: Path) -> None:
    forbidden: list[str] = []
    for path in sorted(destination.rglob("*")):
        if ".git" in path.parts and path != destination / ".git":
            continue
        if path.is_symlink():
            forbidden.append(path.relative_to(destination).as_posix())
    if (destination / ".gitmodules").exists():
        forbidden.append(".gitmodules")
    links = run(
        ["git", "-C", destination, "ls-files", "--stage"], capture=True
    )
    if any(line.startswith("160000 ") for line in links.splitlines()):
        forbidden.append("gitlink")
    if forbidden:
        raise UpstreamOrinocoError(
            "generated downstream is not ordinary: " + ", ".join(forbidden[:10])
        )


def compose(
    destination: Path,
    *,
    template_source: str,
    template_version: str,
    replace: bool,
) -> dict[str, Any]:
    destination = _safe_destination(destination)
    required = [
        SNAPSHOT_RECORDS,
        SNAPSHOT_MANIFEST,
        RAW_JSONL,
        POOL_MANIFEST,
        CANONICAL_JSONL,
        ORINOCO_RECORDS,
        ORINOCO_ANNOTATIONS,
        ORINOCO_STORAGE_MANIFEST,
        UPSTREAM_SITE / "content",
        UPSTREAM_SITE / "page_templates",
        UPSTREAM_SITE / "code" / "pool2graph.py",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise UpstreamOrinocoError(
            "missing prepared fixture inputs: " + ", ".join(str(path) for path in missing)
        )
    if destination.exists():
        if not replace:
            raise UpstreamOrinocoError(
                f"destination already exists (pass --replace): {destination}"
            )
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    render_template(
        destination,
        template_source=template_source,
        template_version=template_version,
    )

    copy_regular_tree(ORINOCO_RECORDS, destination / "metadata" / "records")
    copy_regular_tree(
        ORINOCO_ANNOTATIONS,
        destination / "metadata" / "overlays" / "annotations",
    )
    for name in FRAMEWORK_DIRECTORIES:
        copy_regular_tree(
            UPSTREAM_SITE / name,
            destination / "site" / "framework" / name,
        )
    copy_regular_tree(
        UPSTREAM_SITE / "page_templates",
        destination / "site" / "projection-templates",
    )
    graph_destination = destination / "site" / "projection-tools" / "pool2graph.py"
    graph_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(UPSTREAM_SITE / "code" / "pool2graph.py", graph_destination)
    copy_regular_tree(UPSTREAM_SITE / "content", destination / "custom" / "editorial")

    record_count, classes, namespaces = _record_inventory()
    _write_yaml(destination / "site" / "projection.yaml", projection_contract(classes))
    _write_yaml(
        destination / "custom" / "assets" / "manifest.yaml",
        {"version": 1, "profile": "upstream-snapshot", "assets": {}},
    )
    provenance = destination / ".orinoco-lite" / "provenance"
    if provenance.exists():
        for placeholder in provenance.glob(".gitkeep"):
            placeholder.unlink()
    provenance.mkdir(parents=True, exist_ok=True)
    portable_source = "source-adapters/upstream-snapshot/public-thing.jsonl"
    _copy_portable_json(
        SNAPSHOT_MANIFEST,
        provenance / "upstream-snapshot.json",
        rewrites={"source_jsonl": portable_source},
    )
    _copy_portable_json(
        POOL_MANIFEST,
        provenance / "upstream-pool-capture.json",
        rewrites={"snapshot": portable_source},
    )
    shutil.copyfile(
        ORINOCO_STORAGE_MANIFEST,
        provenance / "upstream-storage-projection.json",
    )
    adapter = destination / "source-adapters" / "upstream-snapshot"
    adapter.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RAW_JSONL, adapter / "public-thing.jsonl")
    shutil.copyfile(CANONICAL_JSONL, adapter / "canonical-records.jsonl")
    upstream_commit = run(
        ["git", "-C", UPSTREAM_SITE, "rev-parse", "HEAD"], capture=True
    )
    theme_commit = run(
        ["git", "-C", UPSTREAM_SITE / "themes" / "congo", "rev-parse", "HEAD"],
        capture=True,
    )
    composition = {
        "format": "orinoco-upstream-downstream-fixture-v1",
        "record_count": record_count,
        "record_classes": dict(sorted(classes.items())),
        "rendered_pid_namespaces": {
            schema_type: sorted(namespaces.get(schema_type, set()))
            for schema_type in PAGE_POLICIES
            if schema_type in classes
        },
        "source_presentation_commit": upstream_commit,
        "source_theme_commit": theme_commit,
        "template_source": PUBLIC_TEMPLATE_SOURCE,
        "template_version": template_version,
    }
    _write_json(provenance / "composition.json", composition)
    (destination / "UPSTREAM-SNAPSHOT.md").write_text(
        """# Generated upstream snapshot fixture

This ordinary Git repository was composed from the latest cached public-pool
JSONL snapshot. The untouched source and canonical-order JSONL streams are in
`source-adapters/upstream-snapshot/`. Their exact canonical YAML snapshot was
reloaded and value checked before composition.

Orinoco stores machine PAV provenance separately, so `metadata/records/` and
`metadata/overlays/annotations/` are a reversible storage projection of that
source. Full-URI PAV aliases and expanded annotation values are normalized to
the companion contract and counted in
`.orinoco-lite/provenance/upstream-storage-projection.json`. The original
lexical representation remains in the source JSONL. The upstream presentation,
page templates, graph producer, and committed content snapshot are flattened
from their recorded source commits; no submodules or git-annex links remain.

The repository intentionally keeps JSON/YAML serialization separate from the
Orinoco semantic JSON/RDF/JSON validation step. Use the engineering workspace's
`check-upstream-orinoco` task to probe the fixture's released engine and to
exercise the current development engine against the same verified released
runtime. Once a release containing every policy named by `site/projection.yaml`
is adopted here, the repository's own `pixi run validate`, `pixi run build`,
and `pixi run serve` tasks are the direct deployment interface; Copier is not a
runtime dependency.
""",
        encoding="utf-8",
    )
    presentation_root = destination / "site" / "framework"
    composition["presentation_tree_sha256"] = _tree_digest(presentation_root)
    _write_json(provenance / "composition.json", composition)

    run(["git", "init", "--initial-branch", "main", destination])
    assert_ordinary_repository(destination)
    print(
        f"Instantiated {record_count} upstream records as an ordinary repo: "
        f"{destination}"
    )
    print("The generated repository is intentionally uncommitted for review.")
    return composition


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("instantiate",))
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--template-source",
        default=os.environ.get("ORINOCO_TEMPLATE_SOURCE", DEFAULT_TEMPLATE_SOURCE),
    )
    parser.add_argument("--template-version", default=DEFAULT_TEMPLATE_VERSION)
    parser.add_argument("--replace", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        require_script_environment()
        result = compose(
            args.destination,
            template_source=args.template_source,
            template_version=args.template_version,
            replace=args.replace,
        )
    except UpstreamOrinocoError as error:
        parser.exit(1, f"upstream-orinoco: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
