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
SITE_OWNED_PATHS = ("site-specific", "extensions")
RELEASE_COORDINATES = {"package_url", "package_sha256"}
QUICK_TASKS = (
    "validate",
    "build",
)
FULL_TASKS = (
    "validate",
    "verify-build",
)
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
    """Copy candidate bytes without repository or generated resources state."""

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
    if source.name in IGNORED_WORKING_TREE_NAMES:
        return
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
    for pattern in SITE_OWNED_PATHS:
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
    configuration = _load_yaml(
        template / "copier.yml",
        "Candidate Copier configuration",
    )
    selected: dict[str, object] = {}
    for key, raw in configuration.items():
        if key.startswith("_"):
            continue
        question = _mapping(raw, f"Candidate Copier question {key}")
        if "default" not in question:
            raise DevelopmentError(
                f"Candidate Copier question {key} has no non-interactive default"
            )
        selected[key] = question["default"]
    selected.update(
        {
            key: value
            for key, value in downstream_answers.items()
            if key in selected and key not in RELEASE_COORDINATES
        }
    )
    if not selected:
        raise DevelopmentError("Downstream Copier answers contain no template data")
    return selected


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
    overlay_site_owned(downstream, candidate)


def candidate_environment(
    package: Path | None,
    repository: str | None = None,
    source_commit: str | None = None,
    pull_request: int | None = None,
) -> dict[str, str]:
    """Run the installed package with the downstream's repository identity."""

    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    if repository is not None:
        if GITHUB_REPOSITORY.fullmatch(repository) is None:
            raise DevelopmentError("Repository must use GitHub OWNER/REPOSITORY form")
        environment["GITHUB_REPOSITORY"] = repository
    if source_commit is not None:
        if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
            raise DevelopmentError("--source-commit must be a full lowercase Git SHA")
        environment["ORINOCO_CANDIDATE_CONTENT_COMMIT"] = source_commit
    if pull_request is not None:
        if pull_request < 1 or source_commit is None:
            raise DevelopmentError(
                "--pull-request requires a positive number and --source-commit"
            )
        environment["ORINOCO_CANDIDATE_PULL_REQUEST"] = str(pull_request)
    if package is not None and not (
        package / "packages/orinoco-lite/pyproject.toml"
    ).is_file():
        raise DevelopmentError(f"Package candidate has no Orinoco source tree: {package}")
    if package is not None:
        environment["ORINOCO_UNSAFE_DEVELOPMENT_PACKAGE"] = "1"
    return environment


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


def _candidate_output_sources(
    downstream: Path,
    package: Path | None,
    template: Path | None,
) -> tuple[tuple[str, Path], ...]:
    sources = [("downstream", downstream.resolve())]
    if package is not None:
        sources.append(("package", package.resolve()))
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
    package: Path | None,
    repository: str | None = None,
    source_commit: str | None = None,
    pull_request: int | None = None,
    tasks: Sequence[str],
) -> None:
    manifest = candidate / "pixi.toml"
    if not manifest.is_file():
        raise DevelopmentError(f"Candidate has no pixi.toml: {candidate}")
    pixi = shutil.which("pixi")
    if pixi is None:
        raise DevelopmentError("Pixi is unavailable")
    selected_tasks = tuple(tasks)
    environment = candidate_environment(
        package, repository, source_commit, pull_request
    )
    if package is not None and selected_tasks:
        wheel_directory = candidate / ".orinoco/candidate-wheel"
        wheel_directory.mkdir(parents=True, exist_ok=True)
        _run(
            (
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                wheel_directory,
                package.resolve() / "packages/orinoco-lite",
            ),
            cwd=package.resolve(),
            environment=environment,
        )
        wheels = tuple(wheel_directory.glob("orinoco_lite-*.whl"))
        if len(wheels) != 1:
            raise DevelopmentError("Package candidate did not produce exactly one wheel")
        _run(
            (
                pixi, "add", "--manifest-path", manifest, "--pypi",
                f"orinoco-lite @ {wheels[0].resolve()}",
            ),
            cwd=candidate,
            environment=environment,
        )
    for task in selected_tasks:
        _run(
            (pixi, "run", "--frozen", "--manifest-path", manifest, task),
            cwd=candidate,
            environment=environment,
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--downstream", type=Path, required=True)
    result.add_argument("--package", type=Path)
    result.add_argument("--template", type=Path)
    result.add_argument(
        "--repository",
        help="GitHub OWNER/REPOSITORY override; defaults to the downstream origin",
    )
    result.add_argument(
        "--source-commit",
        help="real downstream commit recorded by a deploy-preview candidate",
    )
    result.add_argument(
        "--pull-request",
        type=int,
        help="draft pull request that owns this deploy-preview candidate",
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
    if args.package is None and args.template is None:
        print("Select --package, --template, or both", file=sys.stderr)
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
                _candidate_output_sources(downstream, args.package, args.template),
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
            package=args.package,
            repository=repository,
            source_commit=args.source_commit,
            pull_request=args.pull_request,
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
