from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import tomllib
import unittest
import yaml

from orinoco_lite.release_editor import POOL_UI_COMMIT, SHACL_VUE_COMMIT


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "pixi.toml"
SCRIPT = ROOT / "tools" / "upstream_static.py"
SCRIPT_LOCK = ROOT / "tools" / "upstream_static.py.pixi.lock"
FULL_SCRIPT_LOCK = ROOT / "tools" / "upstream_full.py.pixi.lock"
ORINOCO_SCRIPT_LOCK = ROOT / "tools" / "upstream_orinoco.py.pixi.lock"
CHECK_ORINOCO_SCRIPT_LOCK = ROOT / "tools" / "check_upstream_orinoco.py.pixi.lock"
WORKFLOW = ROOT / ".github" / "workflows" / "engineering-ci.yml"
UPSTREAM_PAGES_WORKFLOW = (
    ROOT / ".github" / "workflows" / "upstream-pages-trial.yml"
)
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "orinoco-release.yml"
CONSUMER_WORKFLOW = ROOT / ".github" / "workflows" / "orinoco-consumer-ci.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "orinoco-pages.yml"
PACKAGE_MANIFEST = ROOT / "packages" / "orinoco-lite" / "pyproject.toml"
ACCEPTED_CONSUMER_COMMIT = "32c8df154fa11693efe9d20d298f553943b89096"


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
        self.assertEqual(
            manifest["feature"]["skills"]["dependencies"],
            {"apm-cli": "==0.28.0"},
        )
        self.assertEqual(
            manifest["environments"]["skills"],
            {"features": ["skills"], "no-default-feature": True},
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
        self.assertTrue(ORINOCO_SCRIPT_LOCK.is_file())
        self.assertTrue(CHECK_ORINOCO_SCRIPT_LOCK.is_file())

    def test_ci_tasks_require_every_compatibility_fixture(self) -> None:
        tasks = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"]
        self.assertEqual(
            tasks["test-engine-strict"],
            "python tools/run_unittests.py --fail-on-skip --discover "
            "packages/orinoco-lite/tests",
        )
        self.assertEqual(
            tasks["test-accepted-consumer"],
            "python tools/run_unittests.py --fail-on-skip "
            "tests.accepted_consumer_compatibility",
        )
        self.assertEqual(
            set(tasks["test-ci"]["depends-on"]),
            {"test-engine-strict", "test-accepted-consumer", "test-development"},
        )
        skills = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["feature"][
            "skills"
        ]["tasks"]
        self.assertEqual(
            skills["apm-check"],
            "apm install --frozen && apm audit --ci",
        )

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
        self.assertEqual(pixi["dependencies"]["hugo"], "==0.161.1")
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

    def test_static_builds_share_one_annex_metadata_pin(self) -> None:
        builder = (ROOT / "tools" / "build_upstream_site.sh").read_text(
            encoding="utf-8"
        )
        match = re.search(r"^annex_commit=([0-9a-f]{40})$", builder, re.M)
        self.assertIsNotNone(match)
        workflow = UPSTREAM_PAGES_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count(match.group(1)), 2)

    def test_release_pin_surfaces_match_reviewed_gitlinks(self) -> None:
        package = tomllib.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
        version = package["project"]["version"]
        release_spec = yaml.safe_load(
            (ROOT / f"release/runtime-source-v{version}.yaml").read_text(
                encoding="utf-8"
            )
        )
        pool_gitlink = subprocess.check_output(
            [
                "git",
                "rev-parse",
                "HEAD:submodules/pool.psychoinformatics.de-ui",
            ],
            cwd=ROOT,
            text=True,
        ).strip()
        enrichment_gitlink = subprocess.check_output(
            ["git", "rev-parse", "HEAD:submodules/things-enrichment-tools"],
            cwd=ROOT,
            text=True,
        ).strip()
        shacl_gitlink = subprocess.check_output(
            ["git", "rev-parse", "HEAD:shacl-vue"],
            cwd=ROOT / "submodules" / "pool.psychoinformatics.de-ui",
            text=True,
        ).strip()

        self.assertEqual(release_spec["release"], version)
        self.assertEqual(
            release_spec["provenance"]["component_commits"]["pool_ui"],
            pool_gitlink,
        )
        self.assertEqual(
            release_spec["provenance"]["source_inventory"]["editor_shell"][
                "shacl_vue_commit"
            ],
            shacl_gitlink,
        )
        self.assertEqual(POOL_UI_COMMIT, pool_gitlink)
        self.assertEqual(SHACL_VUE_COMMIT, shacl_gitlink)

        dependency = next(
            item
            for item in package["project"]["dependencies"]
            if item.startswith("things-enrichment-tools @ ")
        )
        self.assertTrue(dependency.endswith(f"@{enrichment_gitlink}"))
        for lock_path in (ROOT / "pixi.lock", CHECK_ORINOCO_SCRIPT_LOCK):
            self.assertIn(
                enrichment_gitlink,
                lock_path.read_text(encoding="utf-8"),
            )

    def test_ci_proves_bootstrap_before_the_targeted_build(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("submodules: false", workflow)
        self.assertNotIn("submodules: recursive", workflow)
        self.assertIn("pixi-version: v0.76.2", workflow)
        self.assertIn(
            "repository: ORINOCO-Lite/test-orinoco-downstream-website",
            workflow,
        )
        self.assertIn(f"ref: {ACCEPTED_CONSUMER_COMMIT}", workflow)
        self.assertIn("path: build/accepted-consumer", workflow)
        self.assertIn("sparse-checkout-cone-mode: false", workflow)
        for relative in (
            "/metadata/",
            "/site/projection.yaml",
            "/site/projection-templates/",
            "/site/projection-tools/",
        ):
            self.assertIn(relative, workflow)
        self.assertIn(
            "ORINOCO_TEST_ACCEPTED_CONSUMER: "
            "${{ github.workspace }}/build/accepted-consumer",
            workflow,
        )
        self.assertIn(
            "submodules/pool.psychoinformatics.de-ui",
            workflow,
        )
        self.assertIn("submodules/things-schemas", workflow)
        self.assertIn("--init --depth 1 -- shacl-vue", workflow)
        for script in (
            "tools/upstream_static.py",
            "tools/upstream_full.py",
            "tools/upstream_orinoco.py",
            "tools/check_upstream_orinoco.py",
        ):
            self.assertIn(f"pixi lock --script {script} --check", workflow)
        fixture = workflow.index("Check out the frozen accepted-consumer inputs")
        components = workflow.index(
            "Initialize only release-authorized compatibility components"
        )
        install = workflow.index("frozen: true")
        skills = workflow.index("run: pixi run -e skills apm-check")
        tests = workflow.index("run: pixi run test-ci")
        build = workflow.index("run: pixi run build-upstream-static")
        self.assertLess(fixture, tests)
        self.assertLess(components, tests)
        self.assertLess(install, tests)
        self.assertLess(skills, tests)
        self.assertLess(tests, build)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("run: pixi run build-upstream-static-worktree", workflow)
        self.assertIn("run: pixi run test-upstream-full", workflow)
        self.assertIn("run: pixi run check-upstream", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)

        release = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/run_unittests.py", release)
        self.assertIn("--fail-on-skip --discover packages/orinoco-lite/tests", release)
        self.assertNotIn("may report an intentional skip", release)

    def test_pages_workflow_records_only_successful_default_branch_deployments(
        self,
    ) -> None:
        workflow = PAGES_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_call:", workflow)
        self.assertIn("Require the current default-branch commit", workflow)
        self.assertIn("pixi run validate", workflow)
        self.assertIn("pixi run build-pages", workflow)
        self.assertIn("tools/prepare_pages_publication.py", workflow)
        self.assertIn("Check out the exact publication tooling", workflow)
        self.assertIn("repository: ${{ inputs['workflow-repository'] }}", workflow)
        self.assertIn("ref: ${{ inputs['workflow-sha'] }}", workflow)
        self.assertIn("needs:\n      - build\n      - deploy", workflow)
        self.assertIn("git push --atomic --force origin", workflow)
        self.assertIn("refs/heads/latest-hugo-projection", workflow)
        self.assertIn("refs/heads/gh-pages", workflow)
        self.assertIn("orinoco-pages-publication-${{ github.run_id }}", workflow)
        self.assertIn("overwrite: true", workflow)
        deploy = workflow.index("name: Deploy the built site")
        record = workflow.index("name: Record the successful deployment")
        push = workflow.index("git push --atomic --force origin")
        self.assertLess(deploy, record)
        self.assertLess(record, push)

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
        mirror_step = "Select and bound the Linux package mirror"
        self.assertIn(mirror_step, workflow)
        self.assertIn(
            "inputs.command == 'test-all' && runner.os == 'Linux'",
            workflow,
        )
        self.assertIn("https://archive.ubuntu.com/ubuntu/", workflow)
        self.assertIn("sudo tee /etc/apt/apt-mirrors.txt", workflow)
        self.assertNotIn("azure.archive.ubuntu.com", workflow)
        self.assertIn('Acquire::Retries "3";', workflow)
        self.assertIn('Acquire::http::Timeout "30";', workflow)
        self.assertIn('Acquire::https::Timeout "30";', workflow)
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
            workflow.index(mirror_step),
        )
        self.assertLess(
            workflow.index(mirror_step),
            workflow.index("Run the consumer facade"),
        )
        self.assertLess(
            workflow.index("Run the consumer facade"),
            workflow.index("Save the exact Playwright browser cache"),
        )


if __name__ == "__main__":
    unittest.main()
