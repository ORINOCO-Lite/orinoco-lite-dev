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
WORKFLOW = ROOT / ".github" / "workflows" / "engineering-ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "orinoco-release.yml"
CONSUMER_WORKFLOW = ROOT / ".github" / "workflows" / "orinoco-consumer-ci.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "orinoco-pages.yml"
PACKAGE_MANIFEST = ROOT / "packages" / "orinoco-lite" / "pyproject.toml"
DEVELOPER_SKILL = ROOT / ".agents" / "skills" / "develop-orinoco-lite"
ACCEPTED_CONSUMER_COMMIT = "96a87e38f149badf76d98ee9dc5fe2e4fd3b9c07"


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
        self.assertNotIn("feature", manifest)
        self.assertNotIn("environments", manifest)
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

    def test_ci_tasks_require_engine_and_development_contracts(self) -> None:
        tasks = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"]
        self.assertEqual(
            tasks["test-engine-strict"],
            "python tools/run_unittests.py --fail-on-skip --discover "
            "packages/orinoco-lite/tests",
        )
        self.assertEqual(
            set(tasks["test-ci"]["depends-on"]),
            {"test-engine-strict", "test-development"},
        )
        self.assertFalse((ROOT / "apm.yml").exists())
        self.assertFalse((ROOT / "apm.lock.yaml").exists())

    def test_developer_skill_is_native_and_scoped(self) -> None:
        self.assertFalse((ROOT / ".apm" / "skills").exists())
        for relative in ("SKILL.md", "agents/openai.yaml"):
            source = DEVELOPER_SKILL / relative
            self.assertTrue(source.is_file())

        skill = (DEVELOPER_SKILL / "SKILL.md").read_text(encoding="utf-8")
        for required in (
            "test-downstream-candidate",
            "--engine",
            "--template",
            "--mode quick",
            "--mode full",
            "<github-user>/orinoco-lite-demo",
            "ORINOCO-Lite/test-orinoco-downstream-website",
            "merge with a merge commit",
            "standing authority",
            "human-gated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, skill)

        interface = yaml.safe_load(
            (DEVELOPER_SKILL / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
        )["interface"]
        self.assertEqual(interface["display_name"], "Develop Orinoco Lite")
        self.assertIn("$develop-orinoco-lite", interface["default_prompt"])

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

    def test_static_builder_uses_one_authoritative_annex_pin(self) -> None:
        builder = (ROOT / "tools" / "build_upstream_site.sh").read_text(
            encoding="utf-8"
        )
        match = re.search(r"^annex_commit=([0-9a-f]{40})$", builder, re.M)
        self.assertIsNotNone(match)
        self.assertEqual(builder.count(match.group(1)), 1)
        self.assertIn(
            "upstream_url=https://hub.psychoinformatics.de/www/"
            "www-from-model.git",
            builder,
        )
        self.assertIn(
            '"$upstream_url" "+$annex_commit:$annex_remote_ref"',
            builder,
        )
        self.assertIn(
            '-c remote.$annex_remote_name.url="$upstream_url"',
            builder,
        )
        self.assertNotIn(
            "github.com/ORINOCO-Lite/www-from-model",
            builder,
        )

    def test_supported_checkouts_never_follow_branch_hints(self) -> None:
        paths = (
            ROOT / "tools" / "checkout_submodules.py",
            ROOT / "tools" / "upstream_checkout.py",
            WORKFLOW,
            RELEASE_WORKFLOW,
        )
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn("--remote", path.read_text(encoding="utf-8"))

        for module in (
            "submodules/dump-things-pyclient",
            "submodules/dump-things-service",
            "submodules/pool.psychoinformatics.de-ui",
            "submodules/query-things",
            "submodules/things-enrichment-tools",
            "submodules/things-schemas",
            "submodules/www-from-model",
        ):
            result = subprocess.run(
                [
                    "git",
                    "config",
                    "-f",
                    ".gitmodules",
                    "--get",
                    f"submodule.{module}.branch",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

        nested_modules = (
            ROOT / "submodules" / "www-from-model" / ".gitmodules"
        )
        result = subprocess.run(
            [
                "git",
                "config",
                "-f",
                str(nested_modules),
                "--get",
                "submodule.themes/congo.branch",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_retired_engineering_pages_workflow_stays_absent(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "upstream-pages-trial.yml"
        self.assertFalse(workflow.exists())

    def test_release_inputs_match_selected_dependencies(self) -> None:
        package = tomllib.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
        version = package["project"]["version"]
        package_metadata = ast.parse(
            (
                PACKAGE_MANIFEST.parent
                / "src"
                / "orinoco_lite"
                / "__init__.py"
            ).read_text(encoding="utf-8")
        )
        source_tree_versions = [
            node.value.value
            for node in ast.walk(package_metadata)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ]
        release_spec = yaml.safe_load(
            (ROOT / "release/runtime-source.yaml").read_text(encoding="utf-8")
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
        things_schemas_gitlink = subprocess.check_output(
            ["git", "rev-parse", "HEAD:submodules/things-schemas"],
            cwd=ROOT,
            text=True,
        ).strip()
        shacl_gitlink = subprocess.check_output(
            ["git", "rev-parse", "HEAD:shacl-vue"],
            cwd=ROOT / "submodules" / "pool.psychoinformatics.de-ui",
            text=True,
        ).strip()

        self.assertEqual(source_tree_versions, [version])
        self.assertEqual(release_spec["release"], version)
        self.assertNotIn("component_commits", release_spec["provenance"])
        for component in release_spec["provenance"]["source_inventory"].values():
            self.assertNotIn("commit", component)
        self.assertEqual(
            release_spec["compatibility"]["schema_profile"],
            "things-schemas/demo-research-information@"
            f"{things_schemas_gitlink}",
        )
        self.assertEqual(POOL_UI_COMMIT, pool_gitlink)
        self.assertEqual(SHACL_VUE_COMMIT, shacl_gitlink)

        dependency = next(
            item
            for item in package["project"]["dependencies"]
            if item.startswith("things-enrichment-tools @ ")
        )
        self.assertTrue(dependency.endswith(f"@{enrichment_gitlink}"))
        self.assertIn(
            enrichment_gitlink,
            (ROOT / "pixi.lock").read_text(encoding="utf-8"),
        )

    def test_ci_proves_bootstrap_before_the_targeted_build(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("submodules: false", workflow)
        self.assertNotIn("submodules: recursive", workflow)
        self.assertIn("pixi-version: v0.76.2", workflow)
        self.assertIn(
            "repository: ORINOCO-Lite/orinoco-lite-template",
            workflow,
        )
        self.assertIn("path: build/orinoco-lite-template", workflow)
        self.assertIn(
            "ORINOCO_TEMPLATE_CANDIDATE: "
            "${{ github.workspace }}/build/orinoco-lite-template",
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
        ):
            self.assertIn(f"pixi lock --script {script} --check", workflow)
        fixture = workflow.index("Check out the template candidate")
        components = workflow.index(
            "Initialize only release-authorized compatibility components"
        )
        install = workflow.index("frozen: true")
        tests = workflow.index("run: pixi run test-template-candidate-quick")
        build = workflow.index("run: pixi run build-upstream-static")
        self.assertLess(fixture, tests)
        self.assertLess(components, tests)
        self.assertLess(install, tests)
        self.assertLess(tests, build)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("run: pixi run build-upstream-static-worktree", workflow)
        self.assertIn("run: pixi run test-upstream-full", workflow)
        self.assertIn("run: pixi run check-upstream", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch'", workflow)

        release = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/run_unittests.py", release)
        self.assertIn("--fail-on-skip --discover packages/orinoco-lite/tests", release)
        self.assertIn("submodules/query-things", release)
        self.assertIn("set -o pipefail", release)
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

    def test_consumer_ci_runs_released_framework_checks(self) -> None:
        workflow = CONSUMER_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("timeout-minutes: 60", workflow)
        for task in (
            "validate",
            "projection-verify",
            "verify-runtime",
            "verify-hugo",
            "verify-ownership",
            "verify-build",
        ):
            self.assertIn(f"pixi run {task}", workflow)
        self.assertNotIn("test-all", workflow)
        self.assertNotIn("Playwright", workflow)


if __name__ == "__main__":
    unittest.main()
