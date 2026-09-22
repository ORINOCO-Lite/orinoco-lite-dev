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
    parser = argparse.ArgumentParser(
        prog="orinoco-lite",
        description="Maintain your site's metadata and build a static website with Orinoco Lite.",
        epilog=("Run from your website repository. For a local preview, run 'orinoco-lite build' "
                "followed by 'orinoco-lite serve'. Use COMMAND --help for options and "
                "'orinoco-lite dev --help' when contributing package or template changes."),
    )
    parser.add_argument("--root", type=Path, help="directory containing orinoco.yaml")
    parser.add_argument("--version", action="version", version=f"orinoco-lite {__version__}\nsource: {source_description()}")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser(
        "validate", help="check your metadata and site configuration",
        description=("Check your site's configuration, metadata records, and schema-defined "
                     "relationships without generating pages or a website. Use this when "
                     "reviewing input changes. The build command already includes these checks."),
    )
    validate.add_argument(
        "--structural-only",
        action="store_true",
        help="check file layout, configuration, and record structure only; skip schema and relationship checks",
    )
    validate.add_argument("--json", action="store_true", help="print the report as JSON")
    validate.add_argument("--no-cache", action="store_true", help="repeat schema and relationship checks even when a previous build validated the same inputs")

    build = commands.add_parser(
        "build", help="build your website from its metadata and content",
        description=("Validate your inputs and generate a static website in build/site. "
                     "Unchanged metadata-derived pages and graph data are reused automatically. "
                     "Preview the result with 'orinoco-lite serve'. Building does not publish your site."),
    )
    build.add_argument("--destination", type=Path, help="output directory under build/ (default: build/site)")
    build.add_argument("--publication-bundle", type=Path, metavar="PATH",
                       help="also save this build as a Git bundle at PATH under build/ for deployment history; commit input changes first (normally set by the Pages workflow)")
    build.add_argument("--no-cache", action="store_true", help="repeat metadata checks and regenerate metadata-derived pages and graph data; does not fetch new source data")
    build.add_argument("--base-url", default=os.environ.get("ORINOCO_BASE_URL"),
                       help="website URL, including any path prefix; use / for a local preview (default: ORINOCO_BASE_URL or your site configuration)")
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
            "GitHub repository for the website's online editing and review links "
            "(default: GITHUB_REPOSITORY, usually supplied by GitHub Actions)"
        ),
    )

    serve = commands.add_parser(
        "serve", help="preview a built website on your computer",
        description="Serve an existing website build locally. Run build first; this command does not rebuild or watch for changes.",
    )
    serve.add_argument("--directory", type=Path, help="website directory to serve (default: build/site)")
    serve.add_argument("--bind", default="127.0.0.1", help="address to listen on (default: 127.0.0.1, this computer only)")
    serve.add_argument("--port", type=int, default=8767, help="local HTTP port (default: 8767)")

    editor = commands.add_parser("editor", help="static-editor review operations")
    editor_commands = editor.add_subparsers(dest="editor_command", required=True)
    apply = editor_commands.add_parser("apply", help="validate/apply a review bundle")
    apply.add_argument("bundle", type=Path)
    apply.add_argument("--write", action="store_true")

    projection = commands.add_parser(
        "projection", help="generate intermediate metadata pages and graph data",
        description=("Generate the Hugo pages, normalized records, and graph data under "
                     "generated/projection for inspection or further processing. This does "
                     "not build HTML. For a website preview, use build, which performs this step automatically."),
    )
    projection.add_argument("projection_command", choices=("update",))
    projection.add_argument("--no-cache", action="store_true", help="repeat metadata checks and regenerate intermediate output rather than reuse cached results")

    run = commands.add_parser("run", help="run an advanced release driver")
    run.add_argument("driver")
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    from . import package_update
    package_update.register(commands)
    dev = commands.add_parser("dev", help="development-only commands")
    dev_commands = dev.add_subparsers(dest="dev_command", required=True)
    dev_commands.add_parser("prepare-resources", help="compile bundled editor, review, and schema resources")
    enable = dev_commands.add_parser("enable", help="connect an editable package checkout and prepare its resources")
    enable.add_argument("path", nargs="?", type=Path, help="source checkout (default: ../orinoco-lite-dev; cloned if missing)")
    dev_commands.add_parser("disable", help="restore the package selection used before editable development")
    from . import upstream, pool_capture, record_stages
    upstream.register(dev_commands)
    records = dev_commands.add_parser("records", help="capture, convert, and compare records")
    record_commands = records.add_subparsers(dest="records_command", required=True)
    pool_capture.register_capture(record_commands)
    record_stages.register(record_commands)
    from . import local_preview, publication, shacl_handoff, curation_actions

    preview_parser = local_preview.parser()
    commands.add_parser("curation", parents=[curation_actions.parser()], add_help=False,
                        help="run the trusted source-adapter GitHub workflow")
    publication_parser = publication.parser()
    commands.add_parser("verify-site", parents=[preview_parser], add_help=False,
                        description=preview_parser.description, epilog=preview_parser.epilog,
                        help="check that an existing local build can be served")
    commands.add_parser("publication", parents=[publication_parser], add_help=False,
                        description=publication_parser.description, epilog=publication_parser.epilog,
                        help="save a successful deployment in your repository's generated-output branches")
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


def _netlify_preview_environment() -> dict[str, str]:
    """Bind a Netlify deploy preview to its exact GitHub pull request."""

    if (
        os.environ.get("NETLIFY") != "true"
        or os.environ.get("CONTEXT") != "deploy-preview"
    ):
        return {}

    repository_url = os.environ.get("REPOSITORY_URL", "")
    prefix = "https://github.com/"
    if not repository_url.startswith(prefix):
        raise ConfigurationError(
            "Netlify REPOSITORY_URL must identify a GitHub repository"
        )
    repository = repository_url.removeprefix(prefix).removesuffix(".git")
    repository = github_repository(repository, "Netlify GitHub repository")

    pull_request = os.environ.get("REVIEW_ID", "")
    commit = os.environ.get("COMMIT_REF", "")
    if not pull_request.isdigit() or int(pull_request) < 1:
        raise ConfigurationError("Netlify REVIEW_ID must be a pull-request number")
    if len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        raise ConfigurationError("Netlify COMMIT_REF must be a full Git commit")

    return {
        "ORINOCO_CANDIDATE_CONTENT_COMMIT": commit,
        "ORINOCO_CANDIDATE_PULL_REQUEST": pull_request,
        "ORINOCO_GITHUB_REPOSITORY": repository,
        "ORINOCO_UNSAFE_DEVELOPMENT_PACKAGE": "1",
    }


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
    preview_environment = _netlify_preview_environment()
    repository_value = args.github_repository or preview_environment.get(
        "ORINOCO_GITHUB_REPOSITORY"
    )
    build_repository = (
        github_repository(
            repository_value,
            "GitHub repository build coordinate",
        )
        if repository_value is not None
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
    build_environment = dict(preview_environment)
    if build_repository is not None:
        build_environment["ORINOCO_GITHUB_REPOSITORY"] = build_repository
    status = invoke_driver(
        "build",
        workspace,
        resources,
        values={"base_url": base_url, "destination": str(destination)},
        environment=build_environment or None,
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
        if args.command == "dev" and args.dev_command in {"records", "upstream"}:
            from .package_update import check_environment
            check_environment(args.root or Path.cwd())
        if args.command == "package":
            from . import package_update
            package_update.update(args.root or Path.cwd(), args.revision, args.repository, check=args.check)
            return 0
        if args.command == "dev" and args.dev_command == "records":
            from . import pool_capture, record_stages
            if args.records_command == "get":
                return pool_capture.execute(args)
            return record_stages.execute(args)
        if args.command in {"verify-site", "publication", "shacl-handoff", "curation"}:
            from . import local_preview, publication, shacl_handoff, curation_actions
            return {"verify-site": local_preview, "publication": publication,
                    "shacl-handoff": shacl_handoff, "curation": curation_actions}[args.command].execute(args)
        if args.command == "dev" and args.dev_command == "upstream":
            from . import upstream
            return upstream.execute(args)
        if args.command == "dev" and args.dev_command in {"enable", "disable"}:
            from . import development
            if args.dev_command == "enable":
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
