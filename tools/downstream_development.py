#!/usr/bin/env python3
"""Exercise unreleased Orinoco changes against an ordinary downstream."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Iterable, Mapping, Sequence

import yaml


IGNORED_WORKING_TREE_NAMES = {
    ".git",
    ".orinoco",
    ".pixi",
    "__pycache__",
    "build",
    "generated",
    "node_modules",
    "playwright-report",
    "test-results",
}
SITE_OWNED_BEHAVIORS = {
    "create-once-never-overwrite",
    "site-owned-input",
    "site-owned-acceptance",
    "site-owned-policy",
    "site-owned-stable-hook",
}
RELEASE_COORDINATES = {
    "engine_version",
    "engine_url",
    "engine_sha256",
    "runtime_version",
    "runtime_url",
    "runtime_sha256",
    "runtime_manifest_sha256",
    "template_source",
    "template_version",
    "workflow_repository",
    "workflow_sha",
    "workflow_ref",
}
QUICK_TASKS = (
    "validate",
    "build",
    "test-browser-chromium",
)
FULL_TASKS = ("test-all",)
OPTIONAL_TASKS: set[str] = set()
GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class DevelopmentError(RuntimeError):
    """Report an invalid candidate or failed downstream exercise."""


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise DevelopmentError(f"{label} must be a YAML mapping")
    return value


def _load_yaml(path: Path, label: str) -> Mapping[str, object]:
    if not path.is_file():
        raise DevelopmentError(f"{label} is missing: {path}")
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise DevelopmentError(f"{label} is not valid UTF-8 YAML: {path}") from error
    return _mapping(value, label)


def _ignore_working_tree(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_WORKING_TREE_NAMES}


def copy_working_tree(source: Path, destination: Path) -> None:
    """Copy candidate bytes without repository or generated runtime state."""

    source = source.resolve()
    destination = destination.resolve()
    if not source.is_dir():
        raise DevelopmentError(f"Working tree is missing: {source}")
    if destination == source or source in destination.parents:
        raise DevelopmentError(
            f"Candidate destination cannot be inside its source tree: {destination}"
        )
    if destination.exists():
        raise DevelopmentError(f"Candidate destination already exists: {destination}")
    shutil.copytree(source, destination, ignore=_ignore_working_tree)


def _copy_site_path(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise DevelopmentError(f"Site-owned input cannot be a symlink: {source}")
    if source.is_dir():
        if destination.is_symlink():
            raise DevelopmentError(
                f"Site-owned directory conflicts with a generated symlink: {destination}"
            )
        if destination.exists() and not destination.is_dir():
            raise DevelopmentError(
                f"Site-owned directory conflicts with a generated file: {destination}"
            )
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            _copy_site_path(child, destination / child.name)
    elif source.is_file():
        if destination.exists() and destination.is_dir():
            raise DevelopmentError(
                f"Site-owned file conflicts with a generated directory: {destination}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def site_owned_patterns(downstream: Path) -> tuple[str, ...]:
    """Return the checked downstream's declared preservation surfaces."""

    ownership = _load_yaml(
        downstream / ".orinoco-lite/template-ownership.yml",
        "Template ownership contract",
    )
    classes = _mapping(ownership.get("classes"), "Ownership classes")
    patterns: set[str] = set()
    for name, raw in classes.items():
        entry = _mapping(raw, f"Ownership class {name}")
        if entry.get("behavior") not in SITE_OWNED_BEHAVIORS:
            continue
        paths = entry.get("paths")
        if not isinstance(paths, list) or not all(
            isinstance(path, str) and path for path in paths
        ):
            raise DevelopmentError(f"Ownership class {name} has invalid paths")
        patterns.update(paths)
    if not patterns:
        raise DevelopmentError("Ownership contract declares no site-owned paths")
    return tuple(sorted(patterns))


def _pattern_matches(root: Path, pattern: str) -> Iterable[Path]:
    if pattern.endswith("/**"):
        prefix = root / pattern[:-3]
        return (prefix,) if prefix.exists() else ()
    if any(character in pattern for character in "*?["):
        return tuple(sorted(root.glob(pattern)))
    candidate = root / pattern
    return (candidate,) if candidate.exists() else ()


def overlay_site_owned(downstream: Path, candidate: Path) -> tuple[str, ...]:
    """Copy only the source downstream's declared site-owned paths."""

    copied: set[str] = set()
    for pattern in site_owned_patterns(downstream):
        for source in _pattern_matches(downstream, pattern):
            relative = source.relative_to(downstream)
            _copy_site_path(source, candidate / relative)
            copied.add(relative.as_posix())
    return tuple(sorted(copied))


def _template_answers(downstream: Path, template: Path) -> dict[str, object]:
    downstream_answers = _load_yaml(
        downstream / ".copier-answers.yml",
        "Downstream Copier answers",
    )
    candidate_defaults = _load_yaml(
        template / ".github-template-answers.yml",
        "Candidate template defaults",
    )
    selected = {
        key: value
        for key, value in candidate_defaults.items()
        if not key.startswith("_")
    }
    selected.update(
        {
            key: value
            for key, value in downstream_answers.items()
            if not key.startswith("_") and key not in RELEASE_COORDINATES
        }
    )
    if not selected:
        raise DevelopmentError("Downstream Copier answers contain no template data")
    return selected


def _normalize_copier_answers(candidate: Path, answers: Mapping[str, object]) -> None:
    path = candidate / ".copier-answers.yml"
    rendered = dict(_load_yaml(path, "Rendered Copier answers"))
    rendered.pop("_src_path", None)
    rendered.pop("_commit", None)
    source = answers.get("template_source")
    version = answers.get("template_version")
    if not isinstance(source, str) or not isinstance(version, str):
        raise DevelopmentError(
            "Candidate template defaults require template_source and template_version"
        )
    normalized = {"_src_path": source, **rendered, "_commit": version}
    path.write_text(
        yaml.safe_dump(normalized, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _run(
    command: Sequence[str | Path],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
) -> None:
    rendered = " ".join(str(item) for item in command)
    print(f"+ {rendered}", flush=True)
    try:
        completed = subprocess.run(
            [str(item) for item in command],
            cwd=cwd,
            env=environment,
            check=False,
        )
    except FileNotFoundError as error:
        raise DevelopmentError(f"Required command is unavailable: {command[0]}") from error
    if completed.returncode:
        raise DevelopmentError(
            f"Command failed with status {completed.returncode}: {rendered}"
        )


def initialize_candidate_repository(candidate: Path) -> str:
    """Create one deterministic ephemeral metadata base for adapter exercises."""

    environment = dict(os.environ)
    environment.update(
        {
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
        }
    )
    _run(("git", "init", "--quiet", "--initial-branch=main"), cwd=candidate)
    _run(("git", "config", "user.name", "Orinoco candidate"), cwd=candidate)
    _run(
        ("git", "config", "user.email", "orinoco-candidate@example.invalid"),
        cwd=candidate,
    )
    _run(("git", "add", "--all"), cwd=candidate)
    _run(
        (
            "git",
            "commit",
            "--quiet",
            "--no-gpg-sign",
            "-m",
            "test: stage downstream candidate",
        ),
        cwd=candidate,
        environment=environment,
    )
    completed = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=candidate,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode or len(completed.stdout.strip()) != 40:
        raise DevelopmentError("Could not resolve the candidate metadata base")
    return completed.stdout.strip()


def render_template(
    downstream: Path,
    template: Path,
    candidate: Path,
    scratch: Path,
) -> None:
    """Render all current template working-tree bytes with downstream answers."""

    template = template.resolve()
    if not (template / "copier.yml").is_file() or not (
        template / "pixi.toml"
    ).is_file():
        raise DevelopmentError(
            f"Template candidate lacks copier.yml or pixi.toml: {template}"
        )
    source = scratch / "template-source"
    copy_working_tree(template, source)
    selected_answers = _template_answers(downstream, template)
    answers = scratch / "answers.yml"
    answers.write_text(
        yaml.safe_dump(
            selected_answers,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    pixi = shutil.which("pixi")
    if pixi is None:
        raise DevelopmentError("Pixi is unavailable")
    _run(
        (
            pixi,
            "run",
            "--frozen",
            "--manifest-path",
            template / "pixi.toml",
            "copier",
            "copy",
            "--quiet",
            "--defaults",
            "--overwrite",
            "--trust",
            "--data-file",
            answers,
            source,
            candidate,
        ),
        cwd=template,
    )
    _normalize_copier_answers(candidate, selected_answers)
    overlay_site_owned(downstream, candidate)


def candidate_environment(
    engine: Path | None,
    repository: str | None = None,
) -> dict[str, str]:
    """Return an environment that imports an unreleased engine first."""

    environment = dict(os.environ)
    if repository is not None:
        if GITHUB_REPOSITORY.fullmatch(repository) is None:
            raise DevelopmentError("Repository must use GitHub OWNER/REPOSITORY form")
        environment["GITHUB_REPOSITORY"] = repository
    if engine is None:
        return environment
    engine = engine.resolve()
    source = engine / "packages/orinoco-lite/src"
    if not (source / "orinoco_lite/__init__.py").is_file():
        raise DevelopmentError(f"Engine candidate has no Orinoco source tree: {engine}")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        os.fspath(source) if not existing else os.pathsep.join((os.fspath(source), existing))
    )
    environment["ORINOCO_CANDIDATE_ENGINE_ROOT"] = os.fspath(engine)
    environment["ORINOCO_UNSAFE_DEVELOPMENT_RUNTIME"] = "1"
    return environment


def prepare_candidate_editor_shell(
    engine: Path,
    destination: Path,
    environment: Mapping[str, str],
) -> None:
    """Build the working-tree editor used by a downstream candidate."""

    pool_ui = engine.resolve() / "submodules/pool.psychoinformatics.de-ui"
    if not (pool_ui / "Makefile").is_file() or not (
        pool_ui / "shacl-vue/package.json"
    ).is_file():
        raise DevelopmentError(
            "Engine candidate editor sources are missing; initialize the "
            "pool.psychoinformatics.de-ui submodule recursively"
        )
    source = destination.parent / "editor-source"
    shutil.copytree(pool_ui, source)
    _run(
        (
            sys.executable,
            "-m",
            "orinoco_lite.release_editor",
            "--pool-ui",
            source,
            "--overlay",
            engine.resolve() / "release/editor-v2",
            "--shell",
            destination,
            "--licenses",
            destination.parent / "editor-licenses",
        ),
        cwd=engine.resolve(),
        environment=environment,
    )


def github_repository(downstream: Path, explicit: str | None = None) -> str:
    """Resolve the selected downstream's ordinary GitHub project identity."""

    if explicit is not None:
        if GITHUB_REPOSITORY.fullmatch(explicit) is None:
            raise DevelopmentError(
                "--repository must use GitHub OWNER/REPOSITORY form"
            )
        return explicit
    completed = subprocess.run(
        ("git", "remote", "get-url", "origin"),
        cwd=downstream,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise DevelopmentError(
            "Cannot discover the downstream GitHub repository; pass --repository"
        )
    remote = completed.stdout.strip()
    prefixes = (
        "git@github.com:",
        "ssh://git@github.com/",
        "https://github.com/",
        "http://github.com/",
    )
    for prefix in prefixes:
        if not remote.startswith(prefix):
            continue
        coordinate = remote.removeprefix(prefix).removesuffix(".git")
        if GITHUB_REPOSITORY.fullmatch(coordinate):
            return coordinate
    raise DevelopmentError(
        "Cannot derive GitHub OWNER/REPOSITORY from origin; pass --repository"
    )


def task_names(mode: str, overrides: Sequence[str]) -> tuple[str, ...]:
    if overrides:
        return tuple(overrides)
    if mode == "quick":
        return QUICK_TASKS
    if mode == "full":
        return FULL_TASKS
    raise DevelopmentError(f"Unknown downstream test mode: {mode}")


def _available_tasks(manifest: Path) -> frozenset[str]:
    try:
        value = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise DevelopmentError(f"Candidate pixi.toml is invalid: {manifest}") from error
    tasks = value.get("tasks")
    if tasks is None:
        return frozenset()
    if not isinstance(tasks, dict) or not all(isinstance(name, str) for name in tasks):
        raise DevelopmentError(f"Candidate pixi.toml tasks are invalid: {manifest}")
    return frozenset(tasks)


def _candidate_output_sources(
    downstream: Path,
    engine: Path | None,
    template: Path | None,
) -> tuple[tuple[str, Path], ...]:
    sources = [("downstream", downstream.resolve())]
    if engine is not None:
        sources.append(("engine", engine.resolve()))
    if template is not None:
        sources.append(("template", template.resolve()))
    return tuple(sources)


def validate_candidate_output(
    workspace: Path,
    sources: Sequence[tuple[str, Path]],
) -> None:
    """Reject an output that could recursively capture a selected source."""

    workspace = workspace.resolve()
    for label, source in sources:
        source = source.resolve()
        if workspace == source or source in workspace.parents:
            raise DevelopmentError(
                f"Candidate output cannot be inside the {label} source: {workspace}"
            )


def exercise_candidate(
    candidate: Path,
    *,
    engine: Path | None,
    repository: str | None = None,
    tasks: Sequence[str],
) -> None:
    manifest = candidate / "pixi.toml"
    if not manifest.is_file():
        raise DevelopmentError(f"Candidate has no pixi.toml: {candidate}")
    pixi = shutil.which("pixi")
    if pixi is None:
        raise DevelopmentError("Pixi is unavailable")
    available_tasks = _available_tasks(manifest)
    selected_tasks = tuple(
        task
        for task in tasks
        if task not in OPTIONAL_TASKS or task in available_tasks
    )
    for task in tasks:
        if task in OPTIONAL_TASKS and task not in available_tasks:
            print(
                f"Skipping optional task absent from candidate pixi.toml: {task}",
                flush=True,
            )
    environment = candidate_environment(engine, repository)
    with tempfile.TemporaryDirectory(prefix="orinoco-candidate-shells-") as temporary:
        if engine is not None and selected_tasks:
            application = engine.resolve() / "packages/curation-review-app"
            if not (application / "node_modules").is_dir():
                _run(("npm", "ci", "--ignore-scripts"), cwd=application)
            _run(("npm", "run", "build:review"), cwd=application)
            editor_shell = Path(temporary) / "editor-shell"
            prepare_candidate_editor_shell(engine, editor_shell, environment)
            environment["ORINOCO_CANDIDATE_EDITOR_SHELL"] = os.fspath(editor_shell)
        for task in selected_tasks:
            _run(
                (
                    pixi,
                    "run",
                    "--frozen",
                    "--manifest-path",
                    manifest,
                    task,
                ),
                cwd=candidate,
                environment=environment,
            )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--downstream", type=Path, required=True)
    result.add_argument("--engine", type=Path)
    result.add_argument("--template", type=Path)
    result.add_argument(
        "--repository",
        help="GitHub OWNER/REPOSITORY override; defaults to the downstream origin",
    )
    result.add_argument("--mode", choices=("quick", "full"), default="quick")
    result.add_argument(
        "--task",
        action="append",
        default=[],
        help="run this downstream Pixi task instead of the mode defaults; repeatable",
    )
    result.add_argument(
        "--output",
        type=Path,
        help="use and retain this new candidate directory",
    )
    result.add_argument(
        "--keep",
        action="store_true",
        help="retain an automatically created candidate after success",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    downstream = args.downstream.resolve()
    if not (downstream / "orinoco.yaml").is_file():
        print(f"Downstream has no orinoco.yaml: {downstream}", file=sys.stderr)
        return 2
    if args.engine is None and args.template is None:
        print("Select --engine, --template, or both", file=sys.stderr)
        return 2

    try:
        repository = github_repository(downstream, args.repository)
    except DevelopmentError as error:
        print(error, file=sys.stderr)
        return 2

    automatic = args.output is None
    workspace = (
        Path(tempfile.mkdtemp(prefix="orinoco-downstream-candidate-"))
        if automatic
        else args.output.resolve()
    )
    if not automatic:
        try:
            validate_candidate_output(
                workspace,
                _candidate_output_sources(downstream, args.engine, args.template),
            )
        except DevelopmentError as error:
            print(error, file=sys.stderr)
            return 2
        if workspace.exists():
            print(f"Candidate output already exists: {workspace}", file=sys.stderr)
            return 2
        workspace.mkdir(parents=True)
    candidate = workspace / "downstream"
    scratch = workspace / "scratch"
    scratch.mkdir()
    print(f"Staging downstream candidate at {candidate}", flush=True)
    succeeded = False
    try:
        if args.template is None:
            copy_working_tree(downstream, candidate)
        else:
            render_template(downstream, args.template, candidate, scratch)
        metadata_base = initialize_candidate_repository(candidate)
        print(f"Candidate metadata base: {metadata_base}", flush=True)
        exercise_candidate(
            candidate,
            engine=args.engine,
            repository=repository,
            tasks=task_names(args.mode, args.task),
        )
        succeeded = True
    except DevelopmentError as error:
        print(f"Downstream candidate failed: {error}", file=sys.stderr)
        print(f"Failed candidate retained at {candidate}", file=sys.stderr)
        return 1
    finally:
        if succeeded and automatic and not args.keep:
            shutil.rmtree(workspace)

    if workspace.exists():
        print(f"Downstream candidate passed and remains at {candidate}")
    else:
        print("Downstream candidate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
