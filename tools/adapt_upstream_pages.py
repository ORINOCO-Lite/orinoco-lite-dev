#!/usr/bin/env python3
"""Adapt the upstream Hugo artifact for a GitHub Pages project path.

Hugo applies ``baseURL`` to links it owns.  The upstream Psychoinformatics
templates and graph bundle also contain a small number of root-absolute URLs
that Hugo cannot rewrite.  This script adjusts only the generated artifact;
the pinned upstream source tree remains byte-for-byte unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit


HTML_URL_RE = re.compile(
    r"(?P<prefix>\b(?:href|src|action|poster)\s*=\s*)"
    r"(?:"
    r"(?P<quote>[\"'])(?P<quoted>/[^\"']*)(?P=quote)"
    r"|"
    r"(?P<bare>/[^\s>]+)"
    r")",
    re.IGNORECASE,
)
GRAPH_FETCH_RE = re.compile(
    r"(?P<prefix>\bfetch\(\s*)(?P<quote>[\"'])"
    r"(?P<url>/[^\"']*graph\.json(?:\?[^\"']*)?)(?P=quote)"
)
GRAPH_SCRIPT_SRC_RE = re.compile(
    r"(?P<prefix>\bsrc\s*=\s*)"
    r"(?:"
    r"(?P<quote>[\"'])(?P<quoted>/[^\"']*graph\.js(?:\?[^\"']*)?)(?P=quote)"
    r"|"
    r"(?P<bare>/[^\s>]*graph\.js(?:\?[^\s>]*)?)"
    r")",
    re.IGNORECASE,
)
EDIT_HREF_RE = re.compile(
    r"(?P<prefix>\bhref\s*=\s*)(?P<quote>[\"'])"
    r"(?P<url>https?://[^\"']+/ui/)",
    re.IGNORECASE,
)
DEFAULT_EDIT_URL = "https://pool.psychoinformatics.de/ui/"


@dataclass
class AdaptationStats:
    html_files_changed: int = 0
    html_urls_rewritten: int = 0
    graph_html_urls_versioned: int = 0
    graph_script_urls_rewritten: int = 0
    graph_node_urls_rewritten: int = 0
    webmanifest_urls_rewritten: int = 0
    edit_urls_rewritten: int = 0


def normalize_base_path(value: str) -> str:
    """Return a canonical root-relative path with leading/trailing slashes."""

    value = unquote(value.strip())
    if not value.startswith("/"):
        raise ValueError("base path must start with '/'")
    if "?" in value or "#" in value or "\\" in value:
        raise ValueError("base path cannot contain a query, fragment, or backslash")

    parts = [part for part in value.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise ValueError("base path cannot contain '.' or '..' segments")
    return "/" if not parts else f"/{'/'.join(parts)}/"


def normalize_edit_url(value: str) -> str:
    """Return a URL suitable as the base of a SHACL Vue edit link."""

    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("edit URL must be an absolute HTTP(S) URL")
    if parsed.query or parsed.fragment:
        raise ValueError("edit URL cannot contain a query or fragment")
    return f"{value.rstrip('/')}/"


def prefix_root_url(url: str, base_path: str) -> str:
    """Prefix a root-local URL unless it is external or already adapted."""

    if not url.startswith("/") or url.startswith("//"):
        return url
    if base_path == "/":
        return url
    if url == base_path[:-1] or url.startswith(base_path):
        return url
    return f"{base_path}{url.lstrip('/')}"


def rewrite_html(text: str, base_path: str) -> tuple[str, int]:
    rewrites = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal rewrites
        url = match.group("quoted") or match.group("bare")
        rewritten = prefix_root_url(url, base_path)
        if rewritten == url:
            return match.group(0)
        rewrites += 1
        quote = match.group("quote") or ""
        return f"{match.group('prefix')}{quote}{rewritten}{quote}"

    return HTML_URL_RE.sub(replace, text), rewrites


def graph_resource_url(base_path: str, filename: str, bundle_key: str | None) -> str:
    """Return the canonical root-local URL for a graph bundle resource."""

    url = f"{base_path}{filename}"
    return url if bundle_key is None else f"{url}?v={bundle_key}"


def rewrite_graph_script(
    text: str, base_path: str, bundle_key: str | None = None
) -> tuple[str, int]:
    """Normalize every graph data fetch to one optionally versioned URL."""

    rewrites = 0
    expected_url = graph_resource_url(base_path, "graph.json", bundle_key)

    def replace(match: re.Match[str]) -> str:
        nonlocal rewrites
        if match.group("url") == expected_url:
            return match.group(0)
        rewrites += 1
        quote = match.group("quote")
        return f"{match.group('prefix')}{quote}{expected_url}{quote}"

    return GRAPH_FETCH_RE.sub(replace, text), rewrites


def rewrite_graph_html_urls(
    text: str, base_path: str, bundle_key: str
) -> tuple[str, int]:
    """Give every generated graph script reference the bundle cache key."""

    rewrites = 0
    expected_url = graph_resource_url(base_path, "graph.js", bundle_key)

    def replace(match: re.Match[str]) -> str:
        nonlocal rewrites
        current_url = match.group("quoted") or match.group("bare")
        if current_url == expected_url:
            return match.group(0)
        rewrites += 1
        quote = match.group("quote") or ""
        return f"{match.group('prefix')}{quote}{expected_url}{quote}"

    return GRAPH_SCRIPT_SRC_RE.sub(replace, text), rewrites


def graph_bundle_key(graph_script: str, graph_data: str) -> str:
    """Hash a canonical manifest of the unversioned graph bundle bytes."""

    entries = []
    for path, text in (("graph.js", graph_script), ("graph.json", graph_data)):
        content = text.encode("utf-8")
        entries.append(
            {
                "path": path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
        )
    manifest = json.dumps(
        {"files": entries, "version": 1},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(manifest).hexdigest()


def expected_graph_bundle(site_dir: Path, base_path: str) -> tuple[str, str] | None:
    """Return the expected cache key and unversioned script, if complete."""

    graph_script_path = site_dir / "graph.js"
    graph_data_path = site_dir / "graph.json"
    if not graph_script_path.is_file() or not graph_data_path.is_file():
        return None
    graph_script = graph_script_path.read_text(encoding="utf-8")
    unversioned_script, _ = rewrite_graph_script(graph_script, base_path)
    graph_data = graph_data_path.read_text(encoding="utf-8")
    return graph_bundle_key(unversioned_script, graph_data), unversioned_script


def rewrite_edit_urls(text: str, edit_url: str) -> tuple[str, int]:
    rewrites = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal rewrites
        current_url = match.group("url")
        if current_url == edit_url:
            return match.group(0)
        rewrites += 1
        quote = match.group("quote")
        return f"{match.group('prefix')}{quote}{edit_url}"

    return EDIT_HREF_RE.sub(replace, text), rewrites


def rewrite_graph_data(data: object, base_path: str) -> int:
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        raise ValueError("graph.json does not contain a nodes list")

    rewrites = 0
    for node in data["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("url"), str):
            continue
        rewritten = prefix_root_url(node["url"], base_path)
        if rewritten != node["url"]:
            node["url"] = rewritten
            rewrites += 1
    return rewrites


def rewrite_webmanifest_data(data: object, base_path: str) -> int:
    """Prefix root-local icon URLs in a generated web app manifest."""

    if not isinstance(data, dict) or not isinstance(data.get("icons"), list):
        raise ValueError("site.webmanifest does not contain an icons list")

    rewrites = 0
    for icon in data["icons"]:
        if not isinstance(icon, dict) or not isinstance(icon.get("src"), str):
            continue
        rewritten = prefix_root_url(icon["src"], base_path)
        if rewritten != icon["src"]:
            icon["src"] = rewritten
            rewrites += 1
    return rewrites


def audit_site(
    site_dir: Path, base_path: str, edit_url: str = DEFAULT_EDIT_URL
) -> list[str]:
    """Return path, edit-link, and graph-bundle contract violations."""

    base_path = normalize_base_path(base_path)
    edit_url = normalize_edit_url(edit_url)
    violations: list[str] = []
    graph_script_path = site_dir / "graph.js"
    graph_data_path = site_dir / "graph.json"
    graph_script_exists = graph_script_path.is_file()
    graph_data_exists = graph_data_path.is_file()
    bundle = expected_graph_bundle(site_dir, base_path)
    expected_script_url: str | None = None
    expected_data_url: str | None = None
    if graph_script_exists != graph_data_exists:
        missing = "graph.json" if graph_script_exists else "graph.js"
        violations.append(f"site: graph bundle is missing {missing}")
    if bundle is not None:
        bundle_key, _ = bundle
        expected_script_url = graph_resource_url(base_path, "graph.js", bundle_key)
        expected_data_url = graph_resource_url(base_path, "graph.json", bundle_key)

    graph_html_references = 0
    for html_path in sorted(site_dir.rglob("*.html")):
        text = html_path.read_text(encoding="utf-8")
        for match in HTML_URL_RE.finditer(text):
            url = match.group("quoted") or match.group("bare")
            if prefix_root_url(url, base_path) != url:
                violations.append(f"{html_path.relative_to(site_dir)}: {url}")
        for match in EDIT_HREF_RE.finditer(text):
            if match.group("url") != edit_url:
                violations.append(
                    f"{html_path.relative_to(site_dir)}: edit URL {match.group('url')}"
                )
        for match in GRAPH_SCRIPT_SRC_RE.finditer(text):
            graph_html_references += 1
            url = match.group("quoted") or match.group("bare")
            if expected_script_url is None:
                violations.append(
                    f"{html_path.relative_to(site_dir)}: graph script URL {url} "
                    "has no complete graph bundle"
                )
            elif url != expected_script_url:
                violations.append(
                    f"{html_path.relative_to(site_dir)}: graph script URL {url} "
                    f"(expected {expected_script_url})"
                )

    if bundle is not None and graph_html_references == 0:
        violations.append("site: graph.js has no HTML script reference")

    if graph_script_exists:
        graph_script = graph_script_path.read_text(encoding="utf-8")
        graph_fetches = list(GRAPH_FETCH_RE.finditer(graph_script))
        if not graph_fetches:
            violations.append("graph.js: missing graph.json fetch")
        elif expected_data_url is not None:
            for match in graph_fetches:
                if match.group("url") != expected_data_url:
                    violations.append(
                        f"graph.js: graph data URL {match.group('url')} "
                        f"(expected {expected_data_url})"
                    )

    if graph_data_exists:
        graph_data = json.loads(graph_data_path.read_text(encoding="utf-8"))
        if not isinstance(graph_data, dict) or not isinstance(
            graph_data.get("nodes"), list
        ):
            violations.append("graph.json: missing nodes list")
        else:
            for node in graph_data["nodes"]:
                if not isinstance(node, dict) or not isinstance(node.get("url"), str):
                    continue
                if prefix_root_url(node["url"], base_path) != node["url"]:
                    violations.append(
                        f"graph.json node {node.get('id', '<unknown>')}: {node['url']}"
                    )

    webmanifest_path = site_dir / "site.webmanifest"
    if webmanifest_path.is_file():
        webmanifest = json.loads(webmanifest_path.read_text(encoding="utf-8"))
        if not isinstance(webmanifest, dict) or not isinstance(
            webmanifest.get("icons"), list
        ):
            violations.append("site.webmanifest: missing icons list")
        else:
            for index, icon in enumerate(webmanifest["icons"]):
                if not isinstance(icon, dict) or not isinstance(icon.get("src"), str):
                    continue
                if prefix_root_url(icon["src"], base_path) != icon["src"]:
                    violations.append(f"site.webmanifest icon {index}: {icon['src']}")
    return violations


def adapt_site(
    site_dir: Path, base_path: str, edit_url: str = DEFAULT_EDIT_URL
) -> AdaptationStats:
    """Rewrite the generated site in place and fail if any path leaks remain."""

    base_path = normalize_base_path(base_path)
    edit_url = normalize_edit_url(edit_url)
    if not site_dir.is_dir():
        raise FileNotFoundError(f"site directory does not exist: {site_dir}")

    stats = AdaptationStats()

    graph_data_path = site_dir / "graph.json"
    if graph_data_path.is_file():
        graph_data = json.loads(graph_data_path.read_text(encoding="utf-8"))
        count = rewrite_graph_data(graph_data, base_path)
        if count:
            graph_data_path.write_text(
                json.dumps(graph_data, ensure_ascii=False, separators=(",", ":"))
                + "\n",
                encoding="utf-8",
            )
            stats.graph_node_urls_rewritten += count

    graph_script_path = site_dir / "graph.js"
    bundle = expected_graph_bundle(site_dir, base_path)
    bundle_key: str | None = None
    if bundle is not None:
        bundle_key, _ = bundle
        original = graph_script_path.read_text(encoding="utf-8")
        rewritten, count = rewrite_graph_script(original, base_path, bundle_key)
        if count:
            graph_script_path.write_text(rewritten, encoding="utf-8")
            stats.graph_script_urls_rewritten += count

    for html_path in sorted(site_dir.rglob("*.html")):
        original = html_path.read_text(encoding="utf-8")
        rewritten, count = rewrite_html(original, base_path)
        rewritten, edit_count = rewrite_edit_urls(rewritten, edit_url)
        graph_count = 0
        if bundle_key is not None:
            rewritten, graph_count = rewrite_graph_html_urls(
                rewritten, base_path, bundle_key
            )
        if rewritten != original:
            html_path.write_text(rewritten, encoding="utf-8")
            stats.html_files_changed += 1
            stats.html_urls_rewritten += count
            stats.edit_urls_rewritten += edit_count
            stats.graph_html_urls_versioned += graph_count

    webmanifest_path = site_dir / "site.webmanifest"
    if webmanifest_path.is_file():
        webmanifest = json.loads(webmanifest_path.read_text(encoding="utf-8"))
        count = rewrite_webmanifest_data(webmanifest, base_path)
        if count:
            webmanifest_path.write_text(
                json.dumps(webmanifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            stats.webmanifest_urls_rewritten += count

    violations = audit_site(site_dir, base_path, edit_url)
    if violations:
        sample = "\n".join(f"  - {item}" for item in violations[:20])
        raise RuntimeError(
            f"{len(violations)} root-path leak(s) remain after adaptation:\n{sample}"
        )
    return stats


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_dir", type=Path, help="generated Hugo output directory")
    parser.add_argument(
        "--base-path",
        required=True,
        help="GitHub Pages base path, for example /orinoco-lite-dev",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="report root-path leaks without changing the artifact",
    )
    parser.add_argument(
        "--edit-url",
        default=DEFAULT_EDIT_URL,
        help="SHACL Vue base URL for generated edit links",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        base_path = normalize_base_path(args.base_path)
        edit_url = normalize_edit_url(args.edit_url)
        if not args.site_dir.is_dir():
            raise FileNotFoundError(f"site directory does not exist: {args.site_dir}")
        if args.check_only:
            violations = audit_site(args.site_dir, base_path, edit_url)
            print(
                json.dumps({"base_path": base_path, "violations": violations}, indent=2)
            )
            return 1 if violations else 0

        stats = adapt_site(args.site_dir, base_path, edit_url)
        print(json.dumps({"base_path": base_path, **asdict(stats)}, indent=2))
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
