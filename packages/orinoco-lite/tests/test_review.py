from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from orinoco_lite import site
from orinoco_lite.config import load_workspace
from orinoco_lite.errors import ConfigurationError, DriverError
from orinoco_lite.review import bind_review


CONFIG = """\
contract_version: 2
site:
  name: Review fixture
  base_url: https://example.invalid/orinoco/
"""

CONFIGURED_SITE = """\
contract_version: 2
site:
  name: Review fixture
  base_url: https://example.invalid/orinoco/
  repository: ORINOCO-Lite/example-site
  curation_service: HTTPS://Review.Example.Test:443/
"""

EXPECTED_CONFIG = """\
{
  "app_name": "Review fixture source metadata review",
  "format": "orinoco-curation-review-config",
  "repository": "ORINOCO-Lite/example-site",
  "service_origin": "https://review.example.test",
  "version": 1
}
"""


class StaticReviewBindingTests(unittest.TestCase):
    def test_disabled_binding_removes_the_reserved_review_route(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
            destination = root / "build/site/review"
            destination.mkdir(parents=True)
            (destination / "stale.html").write_text("stale\n", encoding="utf-8")

            report = bind_review(
                load_workspace(root),
                root / "runtime",
                destination,
            )

            self.assertEqual(report, {"enabled": False})
            self.assertFalse(destination.exists())

    def test_configured_binding_copies_shell_and_writes_strict_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orinoco.yaml").write_text(CONFIGURED_SITE, encoding="utf-8")
            shell = root / "runtime/review-shell"
            (shell / "assets").mkdir(parents=True)
            (shell / "index.html").write_text("review\n", encoding="utf-8")
            (shell / "assets/app.js").write_text("app\n", encoding="utf-8")
            (shell / "config.json").write_text(
                "runtime default\n",
                encoding="utf-8",
            )
            destination = root / "build/site/review"

            report = bind_review(
                load_workspace(root),
                root / "runtime",
                destination,
            )

            self.assertEqual(
                report,
                {
                    "enabled": True,
                    "repository": "ORINOCO-Lite/example-site",
                    "service_origin": "https://review.example.test",
                },
            )
            self.assertEqual(
                (destination / "config.json").read_text(encoding="utf-8"),
                EXPECTED_CONFIG,
            )
            self.assertEqual(
                (destination / "assets/app.js").read_text(encoding="utf-8"),
                "app\n",
            )
            self.assertEqual(
                (shell / "config.json").read_text(encoding="utf-8"),
                "runtime default\n",
            )

            (destination / "stale.html").write_text("stale\n", encoding="utf-8")
            second_report = bind_review(
                load_workspace(root),
                root / "runtime",
                destination,
            )

            self.assertEqual(second_report, report)
            self.assertFalse((destination / "stale.html").exists())
            self.assertEqual(
                (destination / "config.json").read_text(encoding="utf-8"),
                EXPECTED_CONFIG,
            )

    def test_generated_config_is_accepted_by_the_static_browser_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site_name = "r" * 233
            (root / "orinoco.yaml").write_text(
                CONFIGURED_SITE.replace("Review fixture", site_name),
                encoding="utf-8",
            )
            shell = root / "runtime/review-shell"
            shell.mkdir(parents=True)
            (shell / "index.html").write_text("review\n", encoding="utf-8")
            destination = root / "build/site/review"

            bind_review(load_workspace(root), root / "runtime", destination)

            config = json.loads(
                (destination / "config.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                set(config),
                {"app_name", "format", "repository", "service_origin", "version"},
            )
            self.assertEqual(
                len(config["app_name"].encode("utf-16-le")) // 2,
                256,
            )
            self.assertFalse(
                any(
                    ord(character) < 0x20 or ord(character) == 0x7F
                    for character in config["app_name"]
                )
            )
            origin = urlsplit(config["service_origin"])
            self.assertEqual(config["service_origin"], "https://review.example.test")
            self.assertEqual(origin.path, "")
            self.assertEqual(origin.query, "")
            self.assertEqual(origin.fragment, "")
            self.assertIsNone(origin.username)
            self.assertIsNone(origin.password)

    def test_configured_binding_requires_the_runtime_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orinoco.yaml").write_text(CONFIGURED_SITE, encoding="utf-8")

            with self.assertRaisesRegex(DriverError, "source-review shell"):
                bind_review(
                    load_workspace(root),
                    root / "runtime",
                    root / "build/site/review",
                )

    def test_binding_defends_against_a_partially_configured_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
            workspace = replace(
                load_workspace(root),
                repository="ORINOCO-Lite/example-site",
            )

            with self.assertRaisesRegex(ConfigurationError, "configured together"):
                bind_review(
                    workspace,
                    root / "runtime",
                    root / "build/site/review",
                )

    def test_site_build_binds_review_before_hashing_the_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(CONFIGURED_SITE, encoding="utf-8")
            runtime = root / "runtime"
            shell = runtime / "review-shell"
            shell.mkdir(parents=True)
            (shell / "index.html").write_text("review\n", encoding="utf-8")
            destination = root / "build/site"

            def run(command, *, cwd):
                del cwd
                normalized = [str(item) for item in command]
                hugo_destination = Path(
                    normalized[normalized.index("--destination") + 1]
                )
                hugo_destination.mkdir(parents=True)
                (hugo_destination / "index.html").write_text(
                    "built\n",
                    encoding="utf-8",
                )
                return ""

            with (
                patch.object(site, "_preflight_hugo"),
                patch.object(
                    site,
                    "_assemble",
                    return_value={
                        "copied_assets": 0,
                        "copied_links": 0,
                        "hydrated_assets": 0,
                    },
                ),
                patch.object(site, "_run", side_effect=run),
                patch.object(site, "bind_editor", return_value={"version": 2}),
            ):
                report = site.build_site(
                    config,
                    runtime,
                    destination,
                    "https://example.invalid/orinoco/",
                )

            self.assertTrue(report["review"]["enabled"])
            self.assertEqual(
                (destination / "review/config.json").read_text(encoding="utf-8"),
                EXPECTED_CONFIG,
            )
            manifest = (root / "build/site-manifest.sha256").read_text(
                encoding="utf-8"
            )
            self.assertIn("review/config.json", manifest)
            self.assertIn("review/index.html", manifest)


if __name__ == "__main__":
    unittest.main()
