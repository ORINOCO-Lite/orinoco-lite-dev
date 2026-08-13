import json
import re
import tempfile
import unittest
from pathlib import Path

from tools.adapt_upstream_pages import (
    adapt_site,
    audit_site,
    editor_link_hrefs,
    editor_link_url,
    normalize_base_path,
    normalize_edit_url,
    prefix_root_url,
)


VERSION_RE = re.compile(r"\?v=([0-9a-f]{64})")


def write_graph_site(site_dir: Path, *, label: str = "Example") -> None:
    (site_dir / "index.html").write_text(
        '<script type="module" src="/graph.js"></script>', encoding="utf-8"
    )
    (site_dir / "graph.js").write_text(
        'async function load(){return fetch("/graph.json")}', encoding="utf-8"
    )
    (site_dir / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "example", "label": label, "url": "/persons/example"}
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )


def graph_version(site_dir: Path) -> str:
    match = VERSION_RE.search((site_dir / "index.html").read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError("site index has no graph bundle version")
    return match.group(1)


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
            violations = audit_site(site_dir, "/orinoco-lite-dev")
            self.assertIn("index.html: /graph.js", violations)
            self.assertIn(
                "index.html: graph script URL /graph.js has no complete graph bundle",
                violations,
            )

    def test_root_base_path_requires_and_adds_graph_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            write_graph_site(site_dir)

            before = audit_site(site_dir, "/")
            self.assertTrue(
                any("graph script URL /graph.js" in violation for violation in before)
            )
            self.assertTrue(
                any("graph data URL /graph.json" in violation for violation in before)
            )

            stats = adapt_site(site_dir, "/")
            key = graph_version(site_dir)
            self.assertEqual(len(key), 64)
            self.assertEqual(stats.graph_html_urls_versioned, 1)
            self.assertEqual(stats.graph_script_urls_rewritten, 1)
            self.assertIn(
                f'fetch("/graph.json?v={key}")',
                (site_dir / "graph.js").read_text(encoding="utf-8"),
            )
            self.assertEqual(audit_site(site_dir, "/"), [])

    def test_edit_url_rewrite_is_configurable_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            (site_dir / "index.html").write_text(
                '<a href="https://pool.psychoinformatics.de/ui/?pid=example&edit=true">Edit</a>',
                encoding="utf-8",
            )

            local_edit_url = "http://127.0.0.1:3000/"
            before = audit_site(site_dir, "/", local_edit_url)
            self.assertEqual(
                before, ["index.html: edit URL https://pool.psychoinformatics.de/ui/"]
            )

            stats = adapt_site(site_dir, "/", local_edit_url)
            self.assertEqual(stats.edit_urls_rewritten, 1)
            self.assertIn(
                'href="http://127.0.0.1:3000/?pid=example&edit=true"',
                (site_dir / "index.html").read_text(encoding="utf-8"),
            )
            self.assertEqual(audit_site(site_dir, "/", local_edit_url), [])
            self.assertEqual(
                adapt_site(site_dir, "/", local_edit_url).edit_urls_rewritten, 0
            )

    def test_root_relative_edit_url_is_normalized_and_fail_closed(self) -> None:
        self.assertEqual(normalize_edit_url("/edit"), "/edit/")
        self.assertEqual(normalize_edit_url("/project/edit/"), "/project/edit/")
        self.assertEqual(
            normalize_edit_url("https://con.github.io/project/edit/"),
            "https://con.github.io/project/edit/",
        )
        for value in (
            "edit/",
            "//example.test/edit/",
            "/../edit/",
            "/edit/?query=true",
            "/edit/#fragment",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_edit_url(value)

    def test_root_relative_editor_link_stays_on_the_serving_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            pid = "xyzrins:persons/example"
            page = site_dir / "index.html"
            page.write_text(
                "<html><body>"
                f"<script>const limitGraphRootNodeId='{pid}';</script>"
                '<a href="https://pool.psychoinformatics.de/ui/'
                "?sh%3ANodeShape=dlthings%3AThing&amp;"
                "pid=xyzrins%3Apersons%2Fexample&amp;edit=true\">"
                "Edit this record</a></body></html>",
                encoding="utf-8",
            )

            stats = adapt_site(site_dir, "/", "/edit/")
            rendered = page.read_text(encoding="utf-8")
            self.assertEqual(stats.edit_urls_rewritten, 1)
            self.assertEqual(
                editor_link_hrefs(rendered),
                [editor_link_url("/edit/", pid)],
            )
            self.assertEqual(audit_site(site_dir, "/", "/edit/"), [])

    def test_record_page_without_footer_link_gets_bound_editor_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            pid = "xyzrins:projects/space & query?"
            page = site_dir / "projects" / "escaped" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text(
                "<html><body><main>Consumer footer override</main>"
                f'<script>const limitGraphRootNodeId="{pid}"</script>'
                "</body></html>",
                encoding="utf-8",
            )
            edit_url = "https://con.github.io/example/edit/"

            before = audit_site(site_dir, "/", edit_url)
            self.assertEqual(
                before,
                [
                    f"projects/escaped/index.html: record PID {pid} has 0 "
                    "editor links (expected 1)"
                ],
            )
            stats = adapt_site(site_dir, "/", edit_url)
            self.assertEqual(stats.edit_links_injected, 1)
            rendered = page.read_text(encoding="utf-8")
            self.assertIn("Edit this record</a>", rendered)
            self.assertIn(
                "pid=xyzrins%3Aprojects%2Fspace%20%26%20query%3F", rendered
            )
            self.assertIn("&amp;edit=true", rendered)
            self.assertEqual(
                editor_link_hrefs(rendered), [editor_link_url(edit_url, pid)]
            )
            self.assertEqual(audit_site(site_dir, "/", edit_url), [])

            first_bytes = page.read_bytes()
            second = adapt_site(site_dir, "/", edit_url)
            self.assertEqual(second.edit_links_injected, 0)
            self.assertEqual(page.read_bytes(), first_bytes)

    def test_existing_record_editor_link_is_rewritten_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            pid = "xyzrins:persons/example"
            page = site_dir / "index.html"
            page.write_text(
                "<html><body>"
                f"<script>const limitGraphRootNodeId='{pid}';</script>"
                '<a href="https://pool.psychoinformatics.de/ui/'
                "?sh%3ANodeShape=dlthings%3AThing&amp;"
                "pid=xyzrins%3Apersons%2Fexample&amp;edit=true\">"
                "Edit this record</a></body></html>",
                encoding="utf-8",
            )
            edit_url = "http://127.0.0.1:3000/"

            stats = adapt_site(site_dir, "/", edit_url)
            rendered = page.read_text(encoding="utf-8")
            self.assertEqual(stats.edit_urls_rewritten, 1)
            self.assertEqual(stats.edit_links_injected, 0)
            self.assertEqual(rendered.count("Edit this record"), 1)
            self.assertEqual(
                editor_link_hrefs(rendered), [editor_link_url(edit_url, pid)]
            )
            self.assertEqual(audit_site(site_dir, "/", edit_url), [])

    def test_audit_rejects_duplicate_and_mismatched_record_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            pid = "xyzrins:persons/example"
            wrong_href = editor_link_url(
                "https://example.test/edit/", "xyzrins:persons/wrong"
            ).replace("&", "&amp;")
            page = site_dir / "index.html"
            page.write_text(
                "<html><body>"
                f"<script>const limitGraphRootNodeId = '{pid}';</script>"
                f'<a href="{wrong_href}">Edit this record</a>'
                f'<a href="{wrong_href}">Edit this record</a>'
                "</body></html>",
                encoding="utf-8",
            )

            violations = audit_site(site_dir, "/", "https://example.test/edit/")
            self.assertIn(
                f"index.html: record PID {pid} has 2 editor links (expected 1)",
                violations,
            )
            self.assertEqual(
                violations.count(
                    f"index.html: editor link query is not bound to PID {pid}"
                ),
                2,
            )

    def test_malformed_record_marker_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            (site_dir / "index.html").write_text(
                "<html><body><script>"
                "const limitGraphRootNodeId = 'xyzrins:persons/example;"
                "</script></body></html>",
                encoding="utf-8",
            )

            violation = (
                "index.html: record page must contain exactly one valid "
                "limitGraphRootNodeId marker"
            )
            self.assertIn(violation, audit_site(site_dir, "/"))
            with self.assertRaisesRegex(RuntimeError, "valid limitGraphRootNodeId"):
                adapt_site(site_dir, "/")

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
            self.assertGreaterEqual(len(before), 7)

            stats = adapt_site(site_dir, "/orinoco-lite-dev")
            key = graph_version(site_dir)
            self.assertEqual(stats.html_files_changed, 2)
            self.assertEqual(stats.html_urls_rewritten, 4)
            self.assertEqual(stats.graph_html_urls_versioned, 1)
            self.assertEqual(stats.graph_script_urls_rewritten, 1)
            self.assertEqual(stats.graph_node_urls_rewritten, 1)
            self.assertEqual(stats.webmanifest_urls_rewritten, 1)
            self.assertIn(
                f'src=/orinoco-lite-dev/graph.js?v={key}',
                (site_dir / "index.html").read_text(encoding="utf-8"),
            )
            self.assertIn(
                f'fetch("/orinoco-lite-dev/graph.json?v={key}")',
                (site_dir / "graph.js").read_text(encoding="utf-8"),
            )
            self.assertEqual(audit_site(site_dir, "/orinoco-lite-dev"), [])

            # A second pass proves that deployment retries are deterministic.
            before_second = {
                path.relative_to(site_dir): path.read_bytes()
                for path in site_dir.rglob("*")
                if path.is_file()
            }
            second = adapt_site(site_dir, "/orinoco-lite-dev")
            self.assertEqual(second.html_urls_rewritten, 0)
            self.assertEqual(second.graph_html_urls_versioned, 0)
            self.assertEqual(second.graph_script_urls_rewritten, 0)
            self.assertEqual(second.graph_node_urls_rewritten, 0)
            self.assertEqual(second.webmanifest_urls_rewritten, 0)
            self.assertEqual(
                before_second,
                {
                    path.relative_to(site_dir): path.read_bytes()
                    for path in site_dir.rglob("*")
                    if path.is_file()
                },
            )

    def test_root_and_project_paths_have_distinct_bundle_keys(self) -> None:
        with (
            tempfile.TemporaryDirectory() as root_temp,
            tempfile.TemporaryDirectory() as project_temp,
        ):
            root_site = Path(root_temp)
            project_site = Path(project_temp)
            write_graph_site(root_site)
            write_graph_site(project_site)

            adapt_site(root_site, "/")
            adapt_site(project_site, "/clean-migration/")

            self.assertNotEqual(graph_version(root_site), graph_version(project_site))
            self.assertEqual(audit_site(root_site, "/"), [])
            self.assertEqual(audit_site(project_site, "/clean-migration/"), [])

    def test_distinct_graph_bytes_produce_distinct_resource_urls(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_temp,
            tempfile.TemporaryDirectory() as second_temp,
        ):
            first_site = Path(first_temp)
            second_site = Path(second_temp)
            write_graph_site(first_site, label="First graph")
            write_graph_site(second_site, label="Second graph")

            adapt_site(first_site, "/")
            adapt_site(second_site, "/")

            first_index = (first_site / "index.html").read_text(encoding="utf-8")
            second_index = (second_site / "index.html").read_text(encoding="utf-8")
            self.assertNotEqual(graph_version(first_site), graph_version(second_site))
            self.assertNotEqual(first_index, second_index)

    def test_audit_rejects_stale_bundle_versions_after_data_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            write_graph_site(site_dir)
            adapt_site(site_dir, "/")
            old_key = graph_version(site_dir)

            graph_path = site_dir / "graph.json"
            graph_path.write_text(
                graph_path.read_text(encoding="utf-8").replace("Example", "Changed"),
                encoding="utf-8",
            )

            violations = audit_site(site_dir, "/")
            self.assertTrue(
                any(
                    f"graph script URL /graph.js?v={old_key}" in violation
                    for violation in violations
                )
            )
            self.assertTrue(
                any(
                    f"graph data URL /graph.json?v={old_key}" in violation
                    for violation in violations
                )
            )

    def test_audit_rejects_unversioned_and_mismatched_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            write_graph_site(site_dir)
            adapt_site(site_dir, "/")
            key = graph_version(site_dir)

            index_path = site_dir / "index.html"
            index_path.write_text(
                index_path.read_text(encoding="utf-8").replace(
                    f"/graph.js?v={key}", "/graph.js"
                ),
                encoding="utf-8",
            )
            script_path = site_dir / "graph.js"
            script_path.write_text(
                script_path.read_text(encoding="utf-8").replace(key, "0" * 64),
                encoding="utf-8",
            )

            violations = audit_site(site_dir, "/")
            self.assertTrue(
                any(
                    "graph script URL /graph.js (expected" in item
                    for item in violations
                )
            )
            self.assertTrue(
                any(
                    f"graph data URL /graph.json?v={'0' * 64} (expected" in item
                    for item in violations
                )
            )

    def test_audit_rejects_missing_graph_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            site_dir = Path(temp_dir)
            write_graph_site(site_dir)
            (site_dir / "index.html").write_text(
                "<main>No graph</main>", encoding="utf-8"
            )
            (site_dir / "graph.js").write_text("const graph = true", encoding="utf-8")

            violations = audit_site(site_dir, "/")
            self.assertIn("site: graph.js has no HTML script reference", violations)
            self.assertIn("graph.js: missing graph.json fetch", violations)


if __name__ == "__main__":
    unittest.main()
