from __future__ import annotations

import ast
from pathlib import Path
import re
import tomllib
import unittest
import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "pixi.toml"
SCRIPT = ROOT / "tools" / "upstream_static.py"
SCRIPT_LOCK = ROOT / "tools" / "upstream_static.py.pixi.lock"
FULL_SCRIPT_LOCK = ROOT / "tools" / "upstream_full.py.pixi.lock"
WORKFLOW = ROOT / ".github" / "workflows" / "engineering-ci.yml"
CONSUMER_WORKFLOW = ROOT / ".github" / "workflows" / "orinoco-consumer-ci.yml"


class DevelopmentEnvironmentTests(unittest.TestCase):
    def test_root_environment_is_engine_only_and_bootstrappable(self) -> None:
        manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
        workspace = manifest["workspace"]
        self.assertEqual(workspace["requires-pixi"], ">=0.76,<0.77")
        self.assertEqual(manifest["dependencies"], {"python": ">=3.12,<3.13"})
        self.assertEqual(
            manifest["pypi-dependencies"]["orinoco-lite"],
            {"path": "packages/orinoco-lite", "editable": True},
        )
        serialized = MANIFEST.read_text(encoding="utf-8")
        for forbidden in (
            'path = "submodules/',
            'hugo =',
            'git-annex =',
            'nodejs =',
            'serve =',
            'build =',
            'serve-static =',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_upstream_tasks_use_the_locked_standalone_script(self) -> None:
        tasks = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"]
        self.assertEqual(
            tasks["build-upstream-static"],
            '"$PIXI_EXE" run --frozen --script tools/upstream_static.py build',
        )
        self.assertEqual(
            tasks["serve-upstream-static"],
            '"$PIXI_EXE" run --frozen --script tools/upstream_static.py serve',
        )
        self.assertEqual(
            tasks["build-upstream-static-worktree"],
            '"$PIXI_EXE" run --frozen --script tools/upstream_static.py build '
            "--checkout worktree",
        )
        self.assertEqual(
            tasks["serve-upstream-static-worktree"],
            '"$PIXI_EXE" run --frozen --script tools/upstream_static.py serve '
            "--checkout worktree",
        )
        self.assertTrue(SCRIPT_LOCK.is_file())
        lock = yaml.safe_load(SCRIPT_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(lock["version"], 7)
        self.assertEqual(set(lock["environments"]), {"default"})
        self.assertTrue(FULL_SCRIPT_LOCK.is_file())

    def test_script_metadata_is_exact_and_platform_complete(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        match = re.search(r"^# /// script\n(?P<body>.*?)^# ///$", source, re.M | re.S)
        self.assertIsNotNone(match)
        metadata = "\n".join(
            line.removeprefix("# ") if line != "#" else ""
            for line in match.group("body").splitlines()
        )
        document = tomllib.loads(metadata)
        self.assertEqual(document["requires-python"], ">=3.12,<3.13")
        pixi = document["tool"]["pixi"]
        self.assertEqual(pixi["dependencies"]["hugo"], "==0.154.5")
        self.assertEqual(
            pixi["target"]["linux-64"]["dependencies"]["git-annex"],
            "==10.20260601",
        )
        self.assertEqual(
            pixi["target"]["osx-arm64-macos-14-0"]["pypi-dependencies"][
                "git-annex"
            ],
            "==10.20260601",
        )
        ast.parse(source)

    def test_builder_never_moves_gitlinks_after_scoped_preparation(self) -> None:
        builder = (ROOT / "tools" / "build_upstream_site.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("submodule update", builder)
        self.assertIn("restore_annex_status.py", builder)
        refresh = builder.index('refresh "$site_root" "$status_snapshot"')
        restore = builder.index('config core.worktree "$original_core_worktree"')
        self.assertLess(refresh, restore)
        checkout = (ROOT / "tools" / "upstream_checkout.py").read_text()
        self.assertIn("prepare_static_checkout", checkout)
        self.assertIn("prepare_full_checkout", checkout)
        self.assertIn('mode == "recorded"', checkout)
        self.assertIn("restore_local_state", builder)
        self.assertIn("--no-write-fetch-head", builder)

    def test_ci_proves_bootstrap_before_the_targeted_build(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("submodules: false", workflow)
        self.assertIn("pixi-version: v0.76.2", workflow)
        install = workflow.index("frozen: true")
        tests = workflow.index("run: pixi run test")
        build = workflow.index("run: pixi run build-upstream-static")
        self.assertLess(install, tests)
        self.assertLess(tests, build)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("run: pixi run build-upstream-static-worktree", workflow)
        self.assertIn("run: pixi run test-upstream-full", workflow)
        self.assertIn("run: pixi run check-upstream", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)

    def test_consumer_ci_bounds_and_reuses_exact_browser_downloads(self) -> None:
        workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
        cache_action = "55cc8345863c7cc4c66a329aec7e433d2d1c52a9"
        cache_key = (
            "orinoco-playwright-v1-${{ inputs.runner }}-${{ runner.os }}-"
            "${{ runner.arch }}-chromium-webkit-${{ hashFiles('pixi.toml', "
            "'.orinoco-lite/tests/browser/package.json', "
            "'.orinoco-lite/tests/browser/package-lock.json', "
            "'.orinoco-lite/tools/install_browser_tests.py') }}"
        )

        self.assertIn("timeout-minutes: 60", workflow)
        self.assertIn(f"actions/cache/restore@{cache_action}", workflow)
        self.assertIn(f"actions/cache/save@{cache_action}", workflow)
        self.assertEqual(workflow.count("continue-on-error: true"), 2)
        self.assertIn('SEGMENT_DOWNLOAD_TIMEOUT_MINS: "5"', workflow)
        self.assertEqual(workflow.count(cache_key), 2)
        self.assertEqual(workflow.count("build/playwright-browsers\n"), 2)
        self.assertEqual(
            workflow.count("!build/playwright-browsers/.links"),
            2,
        )
        self.assertNotIn("restore-keys:", workflow)
        self.assertIn("inputs.command == 'test-all'", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn(
            "github.ref == format('refs/heads/{0}', "
            "github.event.repository.default_branch)",
            workflow,
        )
        self.assertIn(
            "steps.playwright-browser-cache.outputs.cache-hit != 'true'",
            workflow,
        )
        self.assertLess(
            workflow.index("Install locked Pixi"),
            workflow.index("Restore the exact Playwright browser cache"),
        )
        self.assertLess(
            workflow.index("Restore the exact Playwright browser cache"),
            workflow.index("Run the consumer facade"),
        )
        self.assertLess(
            workflow.index("Run the consumer facade"),
            workflow.index("Save the exact Playwright browser cache"),
        )


if __name__ == "__main__":
    unittest.main()
