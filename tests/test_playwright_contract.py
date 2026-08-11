from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PlaywrightContractTests(unittest.TestCase):
    def test_root_package_is_private_and_exactly_pinned(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertTrue(package["private"])
        version = package["devDependencies"]["@playwright/test"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertNotRegex(version, r"[~^*xX]")

    def test_browser_runtime_and_artifacts_stay_in_ignored_build_state(self) -> None:
        pixi = (ROOT / "pixi.toml").read_text(encoding="utf-8")
        self.assertIn('PLAYWRIGHT_BROWSERS_PATH = "build/playwright-browsers"', pixi)
        self.assertIn("install-browser-tests =", pixi)
        self.assertIn("test-browser =", pixi)
        tasks = tomllib.loads(pixi)["tasks"]
        self.assertIn(
            "install-browser-tests",
            tasks["test-browser"]["depends-on"],
        )
        config = (ROOT / "playwright.config.mjs").read_text(encoding="utf-8")
        self.assertIn("build/playwright", config)
        self.assertIn("reuseExistingServer: false", config)
        self.assertIn("workers: 1", config)

    def test_authenticated_spec_disables_secret_bearing_artifacts(self) -> None:
        source = (ROOT / "tests/browser/authenticated-editor.spec.mjs").read_text(
            encoding="utf-8"
        )
        self.assertIn("trace: 'off'", source)
        self.assertIn("screenshot: 'off'", source)
        self.assertIn("video: 'off'", source)
        self.assertNotIn("editor-token?", source)


if __name__ == "__main__":
    unittest.main()
