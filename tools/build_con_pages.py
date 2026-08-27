#!/usr/bin/env python3
"""Build and audit the backend-free CON GitHub Pages artifact.

The public artifact is deliberately self-contained.  It embeds the canonical
record sources needed by a browser-only editor, but it never embeds a service
URL, credential, or GitHub write token.  A separately built static editor can
be supplied with ``--editor-source``; without one, the artifact contains a
small read-only handoff page and the same deterministic record catalog.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
from typing import Any, Iterator, Sequence
from urllib.parse import parse_qs, urlsplit

from adapt_upstream_pages import audit_site, normalize_base_path
from build_con_site import (
    BuildError,
    PROFILE_ROOT,
    ROOT,
    SITE,
    build_site,
    load_projection_contract,
    load_yaml,
    manifest_digest,
    manifest_entries,
    safe_destination,
)
from con_projection import ProjectionError, git_commit, source_closure


DEFAULT_DESTINATION = ROOT / "build" / "pages-preview" / "orinoco-lite-dev"
DEFAULT_REPEAT_DESTINATION = (
    ROOT / "build" / "pages-preview-repeat" / "orinoco-lite-dev"
)
DEFAULT_EDITOR_SOURCE = ROOT / "build" / "pages-editor"
DEFAULT_BASE_URL = "https://orinoco-lite.github.io/orinoco-lite-dev/"
EDITOR_ROUTE = "edit/"
CATALOG_NAME = "record-sources.json"
PUBLICATION_NAME = "publication.json"
PUBLICATION_KEYS = {
    "base_path",
    "base_url",
    "editor",
    "files",
    "parent_commit",
    "payload_manifest_sha256",
    "site_commit",
    "site_manifest_sha256",
    "version",
}
POOL_UI = ROOT / "submodules" / "pool.psychoinformatics.de-ui"
THINGS_SCHEMAS = ROOT / "submodules" / "things-schemas"
LOCAL_URL_RE = re.compile(
    rb"https?://(?:127(?:\.[0-9]{1,3}){3}|localhost)(?::[0-9]+)?",
    re.IGNORECASE,
)
GERMAN_EDITOR_URL = b"https://pool.psychoinformatics.de/ui/"
GITHUB_TOKEN_RE = re.compile(rb"gh(?:[opusr]|pat)_[A-Za-z0-9_]{20,}")
EDIT_LINK_RE = re.compile(
    r"\bhref\s*=\s*(?:\"(?P<double>[^\"]*edit=true[^\"]*)\"|"
    r"'(?P<single>[^']*edit=true[^']*)'|(?P<bare>[^\s>]*edit=true[^\s>]*))",
    re.IGNORECASE,
)


def normalized_pages_url(value: str) -> tuple[str, str]:
    """Validate an HTTPS project URL and return it with its base path."""

    try:
        parsed = urlsplit(value.strip())
        parsed.port
    except ValueError as error:
        raise BuildError("Pages base URL is invalid") from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise BuildError("Pages base URL must be a credential-free absolute HTTPS URL")
    base_path = normalize_base_path(parsed.path or "/")
    return f"{parsed.scheme}://{parsed.netloc}{base_path}", base_path


def editor_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/{EDITOR_ROUTE}"


@contextmanager
def temporary_environment(name: str, value: str) -> Iterator[None]:
    previous = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def editor_input_digest(source: Path) -> str:
    """Hash the editor inputs while excluding generated binding metadata."""

    digest = hashlib.sha256()
    excluded = {"editor-contract.json", CATALOG_NAME}
    for path in sorted(
        candidate for candidate in source.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(source).as_posix()
        if relative in excluded:
            continue
        digest.update(
            relative.encode("utf-8")
            + b"\0"
            + hashlib.sha256(path.read_bytes()).digest()
        )
    return digest.hexdigest()


def relative_editor_file(source: Path, value: Any, label: str) -> Path:
    """Resolve one required editor-local file without accepting a URL."""

    if not isinstance(value, str) or not value:
        raise BuildError(f"Static editor {label} must be a relative file path")
    parsed = urlsplit(value)
    relative = PurePosixPath(parsed.path)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or relative.is_absolute()
        or relative.as_posix() != value
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise BuildError(f"Static editor {label} must be a normalized relative file")
    candidate = source.joinpath(*relative.parts)
    if candidate.is_symlink() or not candidate.is_file():
        raise BuildError(f"Static editor {label} is missing: {value}")
    return candidate


def expected_editor_metadata() -> dict[str, Any]:
    contract = load_projection_contract()
    return {
        "pool_ui_commit": git_commit(POOL_UI),
        "record_count": len(source_closure(contract)),
        "schema_commit": git_commit(THINGS_SCHEMAS),
        "site_commit": git_commit(SITE),
    }


def validate_editor_source(source: Path) -> dict[str, Any]:
    """Validate the static, credential-free patch-download editor contract."""

    if not source.is_dir() or not (source / "index.html").is_file():
        raise BuildError("Static editor source must contain index.html")
    contract_path = source / "editor-contract.json"
    config_path = source / "config.json"
    if not contract_path.is_file() or not config_path.is_file():
        raise BuildError(
            "Static editor source must contain editor-contract.json and config.json"
        )
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildError(
            "Static editor contract/config is not valid UTF-8 JSON"
        ) from error
    expected = {
        "authentication": "none",
        "backend": "none",
        "mode": "patch-download",
        "version": 1,
    }
    if not isinstance(contract, dict) or any(
        contract.get(key) != value for key, value in expected.items()
    ):
        raise BuildError(
            "Static editor contract must declare version 1, patch-download "
            "mode, no backend, and no authentication"
        )
    expected_metadata = expected_editor_metadata()
    if any(contract.get(key) != value for key, value in expected_metadata.items()):
        raise BuildError(
            "Static editor contract does not match the pinned pool UI, schema, "
            "site, or record closure"
        )
    if contract.get("input_sha256") != editor_input_digest(source):
        raise BuildError("Static editor input digest is stale")
    expected_config = {
        "review_bundle_catalog": CATALOG_NAME,
        "review_bundle_mode": "patch-download",
        "use_service": False,
        "use_token": False,
    }
    if not isinstance(config, dict) or any(
        config.get(key) != value for key, value in expected_config.items()
    ):
        raise BuildError(
            "Static editor config must disable service/token use and select "
            "the relative patch-download record catalog"
        )
    for key in ("class_url", "data_url", "external_config_url", "shapes_url"):
        relative_editor_file(source, config.get(key), key)
    forbidden_backend_fields = sorted(
        key
        for key, value in config.items()
        if isinstance(key, str)
        and key != "use_service"
        and ("service_url" in key.lower() or key.lower() in {"api_url", "token"})
        and value is not None
        and value != ""
        and value is not False
    )
    if forbidden_backend_fields:
        raise BuildError(
            "Static editor config retains backend/token fields: "
            + ", ".join(forbidden_backend_fields)
        )
    for candidate in source.rglob("*"):
        relative = candidate.relative_to(source)
        if candidate.is_symlink():
            raise BuildError(f"Static editor bundle contains a symlink: {relative}")
        if ".git" in relative.parts:
            raise BuildError(f"Static editor bundle contains Git state: {relative}")
    return contract


def copy_editor(source: Path, destination: Path) -> None:
    validate_editor_source(source)
    shutil.copytree(source, destination, dirs_exist_ok=False)


def canonical_record_catalog() -> dict[str, Any]:
    """Return exact canonical YAML inputs with immutable source coordinates."""

    profile = load_yaml(PROFILE_ROOT / "profile.yaml")
    contract = load_projection_contract(profile)
    records = []
    for source in source_closure(contract):
        if source.category != "canonical":
            continue
        resolved = source.path.resolve()
        site_root = SITE.resolve()
        if site_root not in resolved.parents:
            raise BuildError(
                f"Canonical record escapes the site checkout: {source.path}"
            )
        relative = resolved.relative_to(site_root).as_posix()
        if PurePosixPath(relative).as_posix() != relative:
            raise BuildError(f"Canonical record path is not normalized: {relative}")
        content = resolved.read_text(encoding="utf-8")
        records.append(
            {
                "content": content,
                "path": relative,
                "pid": source.record["pid"],
                "schema_type": source.record["schema_type"],
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )
    records.sort(key=lambda item: (item["pid"], item["path"]))
    return {
        "format": "con-static-record-sources",
        "patch_root": "centerforopenneuroscience.org",
        "records": records,
        "site_commit": git_commit(SITE),
        "version": 1,
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_fallback_editor(destination: Path, base_path: str) -> None:
    """Provide a truthful handoff when the optional editor is not bundled."""

    destination.mkdir(parents=True, exist_ok=False)
    catalog_url = f"{base_path}{EDITOR_ROUTE}{CATALOG_NAME}"
    destination.joinpath("index.html").write_text(
        "<!doctype html>\n"
        '<html lang="en"><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        "<title>CON metadata editing handoff</title>\n"
        "<main><h1>Metadata editing handoff</h1>\n"
        "<p>This preview has no write service and stores no GitHub token. "
        "The pinned canonical YAML sources are available for a local, "
        "reviewable patch workflow.</p>\n"
        f'<p><a href="{html.escape(catalog_url, quote=True)}">'
        "Download the record source catalog</a></p>\n"
        "<p>A browser editor can be added here once its patch-export bundle "
        "passes the same static deployment checks.</p></main>\n"
        "</html>\n",
        encoding="utf-8",
    )


def scan_public_artifact(destination: Path) -> list[str]:
    """Return forbidden local/backend URLs found in public text assets."""

    violations: list[str] = []
    text_suffixes = {
        ".css",
        ".html",
        ".js",
        ".json",
        ".map",
        ".md",
        ".nt",
        ".rdf",
        ".svg",
        ".toml",
        ".ttl",
        ".txt",
        ".webmanifest",
        ".xml",
        ".yaml",
        ".yml",
    }
    paths: list[Path] = []
    for directory, directory_names, file_names in os.walk(
        destination, followlinks=False
    ):
        current = Path(directory)
        kept_directories: list[str] = []
        for name in directory_names:
            path = current / name
            if path.is_symlink():
                violations.append(
                    f"{path.relative_to(destination)}: public artifact symlink"
                )
            else:
                kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in file_names:
            path = current / name
            if path.is_symlink():
                violations.append(
                    f"{path.relative_to(destination)}: public artifact symlink"
                )
            else:
                paths.append(path)
    for path in sorted(paths):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        content = path.read_bytes()
        if match := LOCAL_URL_RE.search(content):
            violations.append(
                f"{path.relative_to(destination)}: local URL "
                f"{match.group(0).decode('ascii', 'replace')}"
            )
        if GERMAN_EDITOR_URL in content:
            violations.append(f"{path.relative_to(destination)}: German editor URL")
        if GITHUB_TOKEN_RE.search(content):
            violations.append(
                f"{path.relative_to(destination)}: GitHub token-shaped value"
            )
    return violations


def audit_editor_links(destination: Path, expected_url: str) -> list[str]:
    """Require every generated record edit link to use the static editor."""

    expected = urlsplit(expected_url)
    violations: list[str] = []
    count = 0
    for path in sorted(destination.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for match in EDIT_LINK_RE.finditer(text):
            count += 1
            value = html.unescape(
                match.group("double") or match.group("single") or match.group("bare")
            )
            parsed = urlsplit(value)
            query = parse_qs(parsed.query, keep_blank_values=True)
            if (
                (parsed.scheme, parsed.netloc, parsed.path)
                != (expected.scheme, expected.netloc, expected.path)
                or query.get("edit") != ["true"]
                or not query.get("pid")
                or not query.get("sh:NodeShape")
            ):
                violations.append(
                    f"{path.relative_to(destination)}: invalid static edit link"
                )
    if count == 0:
        violations.append("site: no record edit links target the static editor")
    return violations


def manifest_path(entry: str) -> str:
    try:
        _, relative = entry.split("  ", 1)
    except ValueError as error:
        raise BuildError(f"Malformed artifact manifest entry: {entry}") from error
    return relative


def publication_manifest_entries(destination: Path) -> tuple[list[str], list[str]]:
    """Return the pre-publication payload and pre-editor site manifests."""

    entries = [
        entry
        for entry in manifest_entries(destination)
        if manifest_path(entry) != PUBLICATION_NAME
    ]
    site_entries = [
        entry
        for entry in entries
        if manifest_path(entry) != ".nojekyll"
        and not manifest_path(entry).startswith(EDITOR_ROUTE)
    ]
    return entries, site_entries


def publication_violations(
    destination: Path,
    base_url: str,
    editor_kind: str,
) -> list[str]:
    """Validate publication provenance against the exact current payload."""

    path = destination / PUBLICATION_NAME
    if path.is_symlink() or not path.is_file():
        return [f"site: missing {PUBLICATION_NAME}"]
    try:
        observed = json.loads(path.read_text(encoding="utf-8"))
        payload_entries, site_entries = publication_manifest_entries(destination)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, BuildError) as error:
        return [f"site: invalid {PUBLICATION_NAME}: {error}"]
    if not isinstance(observed, dict) or set(observed) != PUBLICATION_KEYS:
        return [f"site: {PUBLICATION_NAME} has unexpected fields"]
    normalized_url, base_path = normalized_pages_url(base_url)
    expected = {
        "base_path": base_path,
        "base_url": normalized_url,
        "editor": editor_kind,
        "files": len(payload_entries),
        "parent_commit": git_commit(ROOT),
        "payload_manifest_sha256": manifest_digest(payload_entries),
        "site_commit": git_commit(SITE),
        "site_manifest_sha256": manifest_digest(site_entries),
        "version": 1,
    }
    return [
        f"site: {PUBLICATION_NAME} {key} is stale"
        for key, value in expected.items()
        if observed.get(key) != value
    ]


def audit_pages_artifact(
    destination: Path,
    base_url: str,
    *,
    require_editor: bool = False,
    require_publication: bool = True,
) -> dict[str, Any]:
    base_url, base_path = normalized_pages_url(base_url)
    expected_editor_url = editor_url(base_url)
    violations = audit_site(destination, base_path, expected_editor_url)
    violations.extend(scan_public_artifact(destination))
    violations.extend(audit_editor_links(destination, expected_editor_url))
    editor = destination / EDITOR_ROUTE
    catalog = editor / CATALOG_NAME
    if not (destination / ".nojekyll").is_file():
        violations.append("site: missing .nojekyll")
    if not (editor / "index.html").is_file():
        violations.append("site: missing static editing handoff")
    if not catalog.is_file():
        violations.append(f"site: missing {EDITOR_ROUTE}{CATALOG_NAME}")
    else:
        try:
            observed_catalog = json.loads(catalog.read_text(encoding="utf-8"))
            expected_catalog = canonical_record_catalog()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, BuildError) as error:
            violations.append(f"site: invalid static record catalog: {error}")
        else:
            if observed_catalog != expected_catalog:
                violations.append(
                    "site: static record catalog does not match canonical YAML"
                )
    if (destination / "CNAME").exists():
        violations.append("site: CNAME/custom-domain configuration is out of scope")
    contract_path = editor / "editor-contract.json"
    if contract_path.is_file():
        try:
            validate_editor_source(editor)
        except BuildError as error:
            violations.append(f"site: {error}")
    elif require_editor:
        violations.append("site: required patch-export editor is not bundled")
    editor_kind = "patch-download" if contract_path.is_file() else "record-handoff"
    if require_publication:
        violations.extend(publication_violations(destination, base_url, editor_kind))
    if violations:
        detail = "\n".join(f"  - {item}" for item in violations)
        raise BuildError(f"Pages artifact audit failed:\n{detail}")
    entries = manifest_entries(destination)
    return {
        "base_path": base_path,
        "base_url": base_url,
        "editor": editor_kind,
        "files": len(entries),
        "manifest_sha256": manifest_digest(entries),
    }


def build_pages_artifact(
    destination: Path,
    base_url: str,
    *,
    editor_source: Path | None = None,
    require_editor: bool = False,
) -> dict[str, Any]:
    destination = safe_destination(destination)
    base_url, base_path = normalized_pages_url(base_url)
    if require_editor and editor_source is None:
        raise BuildError("--require-editor requires --editor-source")
    with temporary_environment("SHACL_VUE_URL", editor_url(base_url)):
        site_report = build_site(destination, base_url)

    edit_destination = destination / EDITOR_ROUTE
    if editor_source is None:
        write_fallback_editor(edit_destination, base_path)
    else:
        copy_editor(editor_source.resolve(), edit_destination)
    write_json(edit_destination / CATALOG_NAME, canonical_record_catalog())
    destination.joinpath(".nojekyll").write_bytes(b"")
    payload_report = audit_pages_artifact(
        destination,
        base_url,
        require_editor=require_editor,
        require_publication=False,
    )
    publication = {
        **{
            key: value
            for key, value in payload_report.items()
            if key != "manifest_sha256"
        },
        "parent_commit": git_commit(ROOT),
        "payload_manifest_sha256": payload_report["manifest_sha256"],
        "site_commit": git_commit(SITE),
        "site_manifest_sha256": site_report["manifest_sha256"],
        "version": 1,
    }
    write_json(destination / PUBLICATION_NAME, publication)
    # Re-audit after publication metadata enters the uploaded artifact.
    report = audit_pages_artifact(
        destination,
        base_url,
        require_editor=require_editor,
    )
    complete = {**publication, **report}
    destination.parent.joinpath(f"{destination.name}-pages-build.json").write_text(
        json.dumps(complete, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    destination.parent.joinpath(f"{destination.name}-pages-manifest.sha256").write_text(
        "\n".join(manifest_entries(destination)) + "\n",
        encoding="utf-8",
    )
    return complete


def compare_pages_builds(
    first: Path,
    second: Path,
    base_url: str,
    *,
    editor_source: Path | None = None,
    require_editor: bool = False,
) -> dict[str, Any]:
    first_report = build_pages_artifact(
        first,
        base_url,
        editor_source=editor_source,
        require_editor=require_editor,
    )
    second_report = build_pages_artifact(
        second,
        base_url,
        editor_source=editor_source,
        require_editor=require_editor,
    )
    if manifest_entries(first) != manifest_entries(second):
        raise BuildError("Two clean Pages builds are not byte-identical")
    return {"byte_identical": True, "first": first_report, "second": second_report}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--editor-source",
        type=Path,
        default=DEFAULT_EDITOR_SOURCE,
    )
    parser.add_argument("--require-editor", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--repeat-destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.check_only:
            report = audit_pages_artifact(
                args.destination,
                args.base_url,
                require_editor=args.require_editor,
            )
        elif args.repeat_destination:
            report = compare_pages_builds(
                args.destination,
                args.repeat_destination,
                args.base_url,
                editor_source=args.editor_source,
                require_editor=args.require_editor,
            )
        else:
            report = build_pages_artifact(
                args.destination,
                args.base_url,
                editor_source=args.editor_source,
                require_editor=args.require_editor,
            )
        print(json.dumps(report, sort_keys=True))
    except (BuildError, ProjectionError, OSError, ValueError) as error:
        print(f"CON Pages build: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
