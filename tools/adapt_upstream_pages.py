#!/usr/bin/env python3
"""Adapt the upstream Hugo artifact for a GitHub Pages project path.

Hugo applies ``baseURL`` to links it owns.  The upstream Psychoinformatics
templates and graph bundle also contain a small number of root-absolute URLs
that Hugo cannot rewrite.  This script adjusts only the generated artifact;
the pinned upstream source tree remains byte-for-byte unchanged.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote


HTML_URL_RE = re.compile(
    r"(?P<prefix>\b(?:href|src|action|poster)\s*=\s*)"
    r"(?:"
    r"(?P<quote>[\"'])(?P<quoted>/[^\"']*)(?P=quote)"
    r"|"
    r"(?P<bare>/[^\s>]+)"
    r")",
    re.IGNORECASE,
)
GRAPH_FETCH_RE = re.compile(r"fetch\((?P<quote>[\"'])/graph\.json(?P=quote)\)")


@dataclass
class AdaptationStats:
    html_files_changed: int = 0
    html_urls_rewritten: int = 0
    graph_script_urls_rewritten: int = 0
    graph_node_urls_rewritten: int = 0
    webmanifest_urls_rewritten: int = 0


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


def rewrite_graph_script(text: str, base_path: str) -> tuple[str, int]:
    rewrites = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal rewrites
        rewrites += 1
        quote = match.group("quote")
        return f"fetch({quote}{base_path}graph.json{quote})"

    return GRAPH_FETCH_RE.sub(replace, text), rewrites


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


def audit_site(site_dir: Path, base_path: str) -> list[str]:
    """Return root-path leaks that would escape a Pages project path."""

    base_path = normalize_base_path(base_path)
    violations: list[str] = []
    for html_path in sorted(site_dir.rglob("*.html")):
        text = html_path.read_text(encoding="utf-8")
        for match in HTML_URL_RE.finditer(text):
            url = match.group("quoted") or match.group("bare")
            if prefix_root_url(url, base_path) != url:
                violations.append(f"{html_path.relative_to(site_dir)}: {url}")

    graph_script = site_dir / "graph.js"
    if graph_script.is_file():
        for match in GRAPH_FETCH_RE.finditer(graph_script.read_text(encoding="utf-8")):
            violations.append(f"graph.js: /graph.json ({match.start()})")

    graph_data_path = site_dir / "graph.json"
    if graph_data_path.is_file():
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


def adapt_site(site_dir: Path, base_path: str) -> AdaptationStats:
    """Rewrite the generated site in place and fail if any path leaks remain."""

    base_path = normalize_base_path(base_path)
    if not site_dir.is_dir():
        raise FileNotFoundError(f"site directory does not exist: {site_dir}")

    stats = AdaptationStats()
    if base_path == "/":
        return stats

    for html_path in sorted(site_dir.rglob("*.html")):
        original = html_path.read_text(encoding="utf-8")
        rewritten, count = rewrite_html(original, base_path)
        if count:
            html_path.write_text(rewritten, encoding="utf-8")
            stats.html_files_changed += 1
            stats.html_urls_rewritten += count

    graph_script = site_dir / "graph.js"
    if graph_script.is_file():
        original = graph_script.read_text(encoding="utf-8")
        rewritten, count = rewrite_graph_script(original, base_path)
        if count:
            graph_script.write_text(rewritten, encoding="utf-8")
            stats.graph_script_urls_rewritten += count

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

    violations = audit_site(site_dir, base_path)
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        base_path = normalize_base_path(args.base_path)
        if not args.site_dir.is_dir():
            raise FileNotFoundError(f"site directory does not exist: {args.site_dir}")
        if args.check_only:
            violations = audit_site(args.site_dir, base_path)
            print(
                json.dumps({"base_path": base_path, "violations": violations}, indent=2)
            )
            return 1 if violations else 0

        stats = adapt_site(args.site_dir, base_path)
        print(json.dumps({"base_path": base_path, **asdict(stats)}, indent=2))
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
