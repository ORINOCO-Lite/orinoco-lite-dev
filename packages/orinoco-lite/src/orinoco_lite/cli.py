"""Stable command-line interface for one-repository Orinoco Lite sites."""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
from typing import Any, Sequence

from . import __version__
from .config import (
    github_repository,
    load_workspace,
    load_workspace_lock,
)
from .driver import invoke_driver
from .errors import ConfigurationError, OrinocoError
from .resources import resolve_resources
from .validation import report_json, validate_workspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="directory containing orinoco.yaml")
    parser.add_argument("--version", action="version", version=f"orinoco {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate site-owned inputs")
    validate.add_argument(
        "--structural-only",
        action="store_true",
        help="skip the release's semantic validation driver",
    )
    validate.add_argument("--json", action="store_true", help="print the report as JSON")

    build = commands.add_parser("build", help="build the deterministic static site")
    build.add_argument("--destination", type=Path)
    build.add_argument("--base-url")
    build.add_argument(
        "--github-repository",
        default=os.environ.get("GITHUB_REPOSITORY"),
        metavar="OWNER/REPOSITORY",
        help=(
            "trusted repository coordinate embedded in the static curation "
            "interfaces (defaults to GITHUB_REPOSITORY)"
        ),
    )
    build.add_argument(
        "--skip-structural-validation",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    serve = commands.add_parser("serve", help="serve an already built static site")
    serve.add_argument("--directory", type=Path)
    serve.add_argument("--bind", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8767)

    editor = commands.add_parser("editor", help="static-editor review operations")
    editor_commands = editor.add_subparsers(dest="editor_command", required=True)
    apply = editor_commands.add_parser("apply", help="validate/apply a review bundle")
    apply.add_argument("bundle", type=Path)
    apply.add_argument("--write", action="store_true")

    projection = commands.add_parser(
        "projection", help="refresh or verify generated projection"
    )
    projection.add_argument("projection_command", choices=("update", "verify"))

    run = commands.add_parser("run", help="run an advanced release driver")
    run.add_argument("driver")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    return parser


def _workspace(args: argparse.Namespace):
    return load_workspace(args.root)


def _resolve(args: argparse.Namespace):
    workspace = _workspace(args)
    lock = load_workspace_lock(workspace)
    return workspace, lock, resolve_resources(workspace, lock)


def _safe_build_destination(workspace, value: Path | None) -> Path:
    destination = value or workspace.path("build") / "site"
    if not destination.is_absolute():
        destination = workspace.root / destination
    resolved = destination.resolve(strict=False)
    build_root = workspace.path("build").resolve(strict=False)
    if resolved == build_root or build_root not in resolved.parents:
        raise ConfigurationError(
            f"Build destination must be below {build_root}: {resolved}"
        )
    return resolved


def _validate(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    report = validate_workspace(workspace)
    if not args.structural_only:
        lock = load_workspace_lock(workspace)
        resources = resolve_resources(workspace, lock)
        status = invoke_driver("validate", workspace, lock, resources)
        if status:
            return status
        report["package_version"] = __version__
    if args.json:
        sys.stdout.write(report_json(report))
    else:
        print(f"Validated {report['records']} records for {workspace.site_name}")
    return 0


def _build(args: argparse.Namespace) -> int:
    workspace, lock, resources = _resolve(args)
    build_repository = (
        github_repository(
            args.github_repository,
            "GitHub repository build coordinate",
        )
        if args.github_repository is not None
        else None
    )
    if not args.skip_structural_validation:
        validate_workspace(workspace)
    semantic_status = invoke_driver("validate", workspace, lock, resources)
    if semantic_status:
        return semantic_status
    destination = _safe_build_destination(workspace, args.destination)
    base_url = args.base_url or workspace.base_url
    build_environment = (
        {"ORINOCO_GITHUB_REPOSITORY": build_repository}
        if build_repository is not None
        else None
    )
    return invoke_driver(
        "build",
        workspace,
        lock,
        resources,
        values={"base_url": base_url, "destination": str(destination)},
        environment=build_environment,
    )


def _serve(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    directory = args.directory or workspace.path("build") / "site"
    if not directory.is_absolute():
        directory = workspace.root / directory
    directory = directory.resolve()
    if not directory.is_dir() or not (directory / "index.html").is_file():
        raise ConfigurationError(
            f"Static site is absent at {directory}; run `orinoco build` first"
        )
    if not 0 <= args.port <= 65535:
        raise ConfigurationError("Serve port must be between 0 and 65535")
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    host, port = server.server_address[:2]
    print(f"Serving {workspace.site_name} at http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _editor(args: argparse.Namespace) -> int:
    workspace, lock, resources = _resolve(args)
    bundle = args.bundle.resolve()
    extra = ["--write"] if args.write else []
    return invoke_driver(
        "editor-apply",
        workspace,
        lock,
        resources,
        values={"bundle": str(bundle)},
        extra_arguments=extra,
    )


def _projection(args: argparse.Namespace) -> int:
    workspace, lock, resources = _resolve(args)
    validate_workspace(workspace)
    return invoke_driver(
        f"projection-{args.projection_command}", workspace, lock, resources
    )


def _run(args: argparse.Namespace) -> int:
    workspace, lock, resources = _resolve(args)
    arguments = args.arguments
    if arguments and arguments[0] == "--":
        arguments = arguments[1:]
    return invoke_driver(
        args.driver,
        workspace,
        lock,
        resources,
        extra_arguments=arguments,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "build":
            return _build(args)
        if args.command == "serve":
            return _serve(args)
        if args.command == "editor":
            return _editor(args)
        if args.command == "projection":
            return _projection(args)
        if args.command == "run":
            return _run(args)
    except OrinocoError as error:
        parser.exit(2, f"orinoco: {error}\n")
    parser.error(f"Unknown command: {args.command}")
    return 2
