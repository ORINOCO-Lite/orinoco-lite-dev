from __future__ import annotations

from pathlib import Path
import subprocess
import tomllib
import unittest
import yaml

from orinoco_lite.release_editor import POOL_UI_COMMIT, SHACL_VUE_COMMIT


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "pixi.toml"
WORKFLOW = ROOT / ".github" / "workflows" / "engineering-ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "orinoco-release.yml"
PACKAGE_MANIFEST = ROOT / "pyproject.toml"
DEVELOPER_SKILL = ROOT / ".agents" / "skills" / "develop-orinoco-lite"
ACCEPTED_CONSUMER_COMMIT = "96a87e38f149badf76d98ee9dc5fe2e4fd3b9c07"


class DevelopmentEnvironmentTests(unittest.TestCase):
    def test_root_environment_contains_the_engineering_toolchain(self) -> None:
        # CI temporarily replaces the editable dependency with the built wheel.
        # This contract concerns the committed engineering declaration; the
        # workflow separately verifies the package actually imported from disk.
        serialized = subprocess.check_output(
            ["git", "show", "HEAD:pixi.toml"], cwd=ROOT, text=True,
        )
        manifest = tomllib.loads(serialized)
        workspace = manifest["workspace"]
        self.assertEqual(workspace["requires-pixi"], ">=0.76,<0.77")
        self.assertEqual(manifest["dependencies"]["python"], ">=3.12,<3.13")
        for name in ("hugo", "nodejs", "make"):
            self.assertIn(name, manifest["dependencies"])
        self.assertEqual(
            manifest["pypi-dependencies"]["orinoco-lite"],
            {"path": ".", "editable": True},
        )
        self.assertNotIn("feature", manifest)
        self.assertNotIn("environments", manifest)
        for forbidden in (
            'path = "submodules/dump-things-service"',
        ):
            self.assertNotIn(forbidden, serialized)



    def test_developer_skill_is_native_and_scoped(self) -> None:
        self.assertFalse((ROOT / ".apm" / "skills").exists())
        for relative in ("SKILL.md", "agents/openai.yaml"):
            source = DEVELOPER_SKILL / relative
            self.assertTrue(source.is_file())

        interface = yaml.safe_load(
            (DEVELOPER_SKILL / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
        )["interface"]
        self.assertEqual(interface["display_name"], "Develop Orinoco Lite")
        self.assertIn("$develop-orinoco-lite", interface["default_prompt"])

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



if __name__ == "__main__":
    unittest.main()
