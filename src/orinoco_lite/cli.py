"""Stable command-line interface for one-repository Orinoco Lite sites."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import subprocess
from typing import Any, Sequence
from urllib.parse import urlsplit

from . import __version__, source_description
from .config import (
    github_repository,
    load_workspace,
)
from .driver import invoke_driver
from .errors import ConfigurationError, OrinocoError
from .resources import resolve_resources
from .validation import report_json, validate_workspace


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orinoco-lite", description=__doc__, epilog="Use `orinoco-lite dev --help` for development-only commands.")
    parser.add_argument("--root", type=Path, help="directory containing orinoco.yaml")
    parser.add_argument("--version", action="version", version=f"orinoco-lite {__version__}\nsource: {source_description()}")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate site-owned inputs")
    validate.add_argument(
        "--structural-only",
        action="store_true",
        help="skip the release's semantic validation driver",
    )
    validate.add_argument("--json", action="store_true", help="print the report as JSON")
    validate.add_argument("--no-cache", action="store_true", help="repeat semantic checks instead of reusing their cached result")

    build = commands.add_parser("build", help="validate inputs and build the static site")
    build.add_argument("--destination", type=Path)
    build.add_argument("--publication-bundle", type=Path,
                       help="also write a Git bundle of this build for recording after deployment (requires clean committed inputs)")
    build.add_argument("--no-cache", action="store_true", help="regenerate projection and semantic checks")
    build.add_argument("--base-url", default=os.environ.get("ORINOCO_BASE_URL"))
    build.add_argument(
        "--build-timestamp",
        default=os.environ.get("ORINOCO_BUILD_TIMESTAMP"),
        help="UTC ISO 8601 timestamp embedded in the static site footer",
    )
    build.add_argument(
        "--github-repository",
        default=os.environ.get("GITHUB_REPOSITORY"),
        metavar="OWNER/REPOSITORY",
        help=(
            "trusted repository coordinate embedded in the static curation "
            "interfaces (defaults to GITHUB_REPOSITORY)"
        ),
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
        "projection", help="generate the metadata projection without building a website"
    )
    projection.add_argument("projection_command", choices=("update",))
    projection.add_argument("--no-cache", action="store_true", help="regenerate projection and semantic checks")

    run = commands.add_parser("run", help="run an advanced release driver")
    run.add_argument("driver")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    dev = commands.add_parser("dev", help="development-only commands")
    dev_commands = dev.add_subparsers(dest="dev_command", required=True)
    dev_commands.add_parser("prepare-resources", help="compile bundled editor, review, and schema resources")
    enable = dev_commands.add_parser("enable", help="connect an editable package checkout and prepare its resources")
    enable.add_argument("path", nargs="?", type=Path, help="source checkout (default: ../orinoco-lite-dev; cloned if missing)")
    dev_commands.add_parser("disable", help="restore the package selection used before editable development")
    setup = dev_commands.add_parser("setup", help="instantiate a downstream from local template and captured site inputs")
    setup.add_argument("destination", nargs="?", type=Path)
    setup.add_argument("--template", type=Path)
    setup.add_argument("--site-specific", type=Path, help="install this repository instead of converting the cached pool")
    setup.add_argument("--snapshot", type=Path, help="cached pool JSONL (default: engineering build/upstream-stack/pool/public-thing.jsonl)")
    setup.add_argument("--populate", action="store_true", help="clone missing template or site-specific repositories")
    setup.add_argument("--force", action="store_true", help="remove and recreate the downstream destination")
    from . import local_preview, publication, shacl_handoff

    commands.add_parser("verify-site", parents=[local_preview.parser()], add_help=False,
                        help="check the built site through localhost and 127.0.0.1")
    commands.add_parser("publication", parents=[publication.parser()], add_help=False,
                        help="record already-deployed output from a build's Git bundle")
    commands.add_parser("shacl-handoff", parents=[shacl_handoff._parser()], add_help=False,
                        help="inspect and materialize GitHub editor proposals")
    return parser


def _workspace(args: argparse.Namespace):
    return load_workspace(args.root)


def _resolve(args: argparse.Namespace):
    workspace = _workspace(args)
    return workspace, resolve_resources()


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
        resources = resolve_resources()
        status = invoke_driver("validate", workspace, resources,
                               extra_arguments=("--no-cache",) if args.no_cache else ())
        if status:
            return status
        report["package_version"] = __version__
    if args.json:
        sys.stdout.write(report_json(report))
    else:
        print(f"Validated {report['records']} records for {workspace.site_name}")
    return 0


def _update_projection(args, workspace, resources) -> int:
    options = {"extra_arguments": ("--no-cache",)} if getattr(args, "no_cache", False) else {}
    return invoke_driver("projection-update", workspace, resources, **options)


def _build(args: argparse.Namespace) -> int:
    workspace, resources = _resolve(args)
    build_repository = (
        github_repository(
            args.github_repository,
            "GitHub repository build coordinate",
        )
        if args.github_repository is not None
        else None
    )
    destination = _safe_build_destination(workspace, args.destination)
    bundle = getattr(args, "publication_bundle", None)
    if bundle is not None:
        from .publication import require_clean_source
        bundle = _safe_build_destination(workspace, bundle)
        if bundle == destination or destination in bundle.parents:
            raise ConfigurationError("Publication bundle must be outside the website destination")
        require_clean_source(workspace.root)
    validate_workspace(workspace)
    projection_status = _update_projection(args, workspace, resources)
    if projection_status:
        return projection_status
    base_url = args.base_url or workspace.base_url
    build_timestamp = getattr(args, "build_timestamp", None)
    if build_timestamp is None and urlsplit(base_url).scheme in {"http", "https"}:
        build_timestamp = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    build_environment = (
        {"ORINOCO_GITHUB_REPOSITORY": build_repository}
        if build_repository is not None
        else None
    )
    status = invoke_driver(
        "build",
        workspace,
        resources,
        values={"base_url": base_url, "destination": str(destination)},
        environment=build_environment,
        extra_arguments=(
            ("--build-timestamp", build_timestamp)
            if build_timestamp is not None
            else ()
        ),
    )
    if status == 0 and bundle is not None:
        from .publication import prepare
        prepare(workspace.root, "generated/projection",
                destination.relative_to(workspace.root).as_posix(),
                bundle.relative_to(workspace.root).as_posix())
    return status


def _serve(args: argparse.Namespace) -> int:
    workspace = _workspace(args)
    directory = args.directory or workspace.path("build") / "site"
    if not directory.is_absolute():
        directory = workspace.root / directory
    directory = directory.resolve()
    if not directory.is_dir() or not (directory / "index.html").is_file():
        raise ConfigurationError(
            f"Static site is absent at {directory}; run `orinoco-lite build` first"
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
    workspace, resources = _resolve(args)
    bundle = args.bundle.resolve()
    extra = ["--write"] if args.write else []
    return invoke_driver(
        "editor-apply",
        workspace,
        resources,
        values={"bundle": str(bundle)},
        extra_arguments=extra,
    )


def _projection(args: argparse.Namespace) -> int:
    workspace, resources = _resolve(args)
    validate_workspace(workspace)
    return _update_projection(args, workspace, resources)


def _run(args: argparse.Namespace) -> int:
    workspace, resources = _resolve(args)
    arguments = args.arguments
    if arguments and arguments[0] == "--":
        arguments = arguments[1:]
    return invoke_driver(
        args.driver,
        workspace,
        resources,
        extra_arguments=arguments,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command in {"verify-site", "publication", "shacl-handoff"}:
            from . import local_preview, publication, shacl_handoff
            return {"verify-site": local_preview, "publication": publication,
                    "shacl-handoff": shacl_handoff}[args.command].execute(args)
        if args.command == "dev" and args.dev_command in {"enable", "disable", "setup"}:
            from . import development, instantiate
            if args.dev_command == "setup":
                instantiate.setup(args.destination, template=args.template, site_specific=args.site_specific,
                                  snapshot=args.snapshot, populate=args.populate, force=args.force)
            elif args.dev_command == "enable":
                development.enable(args.root or Path.cwd(), args.path)
            else:
                development.disable(args.root or Path.cwd())
            return 0
        if args.command == "dev" and args.dev_command == "prepare-resources":
            from .prepare_resources import main as prepare_resources
            prepare_resources()
            return 0
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
    except (OrinocoError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"orinoco-lite: {error}\n")
    parser.error(f"Unknown command: {args.command}")
    return 2
