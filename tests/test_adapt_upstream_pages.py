import json
import tempfile
import unittest
from pathlib import Path

from tools.adapt_upstream_pages import (
    adapt_site,
    audit_site,
    normalize_base_path,
    prefix_root_url,
)


class AdaptUpstreamPagesTests(unittest.TestCase):
    def test_normalize_base_path(self) -> None:
        self.assertEqual(normalize_base_path("/"), "/")
        self.assertEqual(normalize_base_path("/orinoco-lite-dev"), "/orinoco-lite-dev/")
        self.assertEqual(
            normalize_base_path("/orinoco-lite-dev/"), "/orinoco-lite-dev/"
        )
        with self.assertRaises(ValueError):
            normalize_base_path("orinoco-lite-dev")
        with self.assertRaises(ValueError):
            normalize_base_path("/../escape")

    def test_prefix_root_url_is_idempotent(self) -> None:
        base = "/orinoco-lite-dev/"
        self.assertEqual(prefix_root_url("/graph.js", base), f"{base}graph.js")
        self.assertEqual(prefix_root_url(f"{base}graph.js", base), f"{base}graph.js")
        self.assertEqual(
            prefix_root_url("//example.test/a.js", base), "//example.test/a.js"
        )
        self.assertEqual(
            prefix_root_url("https://example.test/a.js", base),
            "https://example.test/a.js",
        )

    def test_audit_normalizes_base_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            (site_dir / "index.html").write_text(
                '<script src="/graph.js"></script>', encoding="utf-8"
            )
            self.assertEqual(
                audit_site(site_dir, "/orinoco-lite-dev"), ["index.html: /graph.js"]
            )

    def test_root_base_path_allows_root_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            (site_dir / "graph.js").write_text('fetch("/graph.json")', encoding="utf-8")
            self.assertEqual(audit_site(site_dir, "/"), [])

    def test_adapt_site_rewrites_all_upstream_escape_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            (site_dir / "nested").mkdir()
            (site_dir / "index.html").write_text(
                '<script src=/graph.js></script><a href="/explore">Explore</a>',
                encoding="utf-8",
            )
            (site_dir / "nested" / "index.html").write_text(
                "<link href='/grid-list.css'><a href=/projects/example>Project</a>",
                encoding="utf-8",
            )
            (site_dir / "graph.js").write_text(
                'async function load(){return fetch("/graph.json")}',
                encoding="utf-8",
            )
            (site_dir / "graph.json").write_text(
                json.dumps(
                    {
                        "nodes": [
                            {"id": "person", "url": "/persons/example"},
                            {"id": "external", "url": "https://example.test/person"},
                            {"id": "none", "url": None},
                        ],
                        "edges": [],
                    }
                ),
                encoding="utf-8",
            )
            (site_dir / "site.webmanifest").write_text(
                json.dumps(
                    {
                        "icons": [
                            {"src": "/android-chrome-192x192.png"},
                            {"src": "https://example.test/external.png"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            before = audit_site(site_dir, "/orinoco-lite-dev")
            self.assertEqual(len(before), 7)

            stats = adapt_site(site_dir, "/orinoco-lite-dev")
            self.assertEqual(stats.html_files_changed, 2)
            self.assertEqual(stats.html_urls_rewritten, 4)
            self.assertEqual(stats.graph_script_urls_rewritten, 1)
            self.assertEqual(stats.graph_node_urls_rewritten, 1)
            self.assertEqual(stats.webmanifest_urls_rewritten, 1)
            self.assertEqual(audit_site(site_dir, "/orinoco-lite-dev"), [])

            # A second pass proves that deployment retries are deterministic.
            second = adapt_site(site_dir, "/orinoco-lite-dev")
            self.assertEqual(second.html_urls_rewritten, 0)
            self.assertEqual(second.graph_script_urls_rewritten, 0)
            self.assertEqual(second.graph_node_urls_rewritten, 0)
            self.assertEqual(second.webmanifest_urls_rewritten, 0)


if __name__ == "__main__":
    unittest.main()
