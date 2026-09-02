from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from tools import downstream_development as development


class DownstreamDevelopmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.downstream = self.root / "source"
        self.downstream.mkdir()
        ownership = {
            "classes": {
                "template_owned": {
                    "behavior": "copier-three-way-update",
                    "paths": ["README.md"],
                },
                "site_data": {
                    "behavior": "create-once-never-overwrite",
                    "paths": ["orinoco.yaml", "site-specific/**"],
                },
                "extensions": {
                    "behavior": "site-owned-stable-hook",
                    "paths": ["extensions/**"],
                },
                "generated": {
                    "behavior": "ignored-runtime-output",
                    "paths": ["generated/**"],
                },
            }
        }
        ownership_path = self.downstream / ".orinoco-lite/template-ownership.yml"
        ownership_path.parent.mkdir()
        ownership_path.write_text(
            yaml.safe_dump(ownership, sort_keys=False), encoding="utf-8"
        )
        (self.downstream / "orinoco.yaml").write_text(
            "contract_version: 2\n", encoding="utf-8"
        )
        (self.downstream / "site-specific/metadata/records").mkdir(parents=True)
        (self.downstream / "site-specific/metadata/records/one.yaml").write_text(
            "pid: example:one\n", encoding="utf-8"
        )
        (self.downstream / "extensions/source-adapters/example").mkdir(
            parents=True
        )
        (self.downstream / "extensions/source-adapters/example/run.py").write_text(
            "print('example')\n", encoding="utf-8"
        )
        (self.downstream / "README.md").write_text(
            "source framework\n", encoding="utf-8"
        )
        (self.downstream / "generated").mkdir()
        (self.downstream / "generated/stale.txt").write_text(
            "stale\n", encoding="utf-8"
        )
        (self.downstream / ".copier-answers.yml").write_text(
            yaml.safe_dump(
                {
                    "_src_path": "gh:old/template",
                    "_commit": "v0.1.0",
                    "project_slug": "downstream-site",
                    "project_name": "Downstream name",
                    "site_description": "Obsolete downstream description",
                    "site_base_url": "https://obsolete.example.invalid/",
                    "engine_version": "0.1.0",
                    "template_source": "gh:old/template",
                    "template_version": "v0.1.0",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_copy_working_tree_omits_repository_and_runtime_output(self) -> None:
        (self.downstream / ".git").mkdir()
        (self.downstream / ".git/config").write_text("ignored\n", encoding="utf-8")
        destination = self.root / "copy"

        development.copy_working_tree(self.downstream, destination)

        self.assertTrue((destination / "orinoco.yaml").is_file())
        self.assertFalse((destination / ".git").exists())
        self.assertFalse((destination / "generated").exists())

    def test_overlay_copies_declared_site_data_not_framework(self) -> None:
        candidate = self.root / "candidate"
        candidate.mkdir()
        (candidate / "README.md").write_text(
            "candidate framework\n", encoding="utf-8"
        )
        (candidate / "site-specific").mkdir()
        (candidate / "site-specific/stale.txt").write_text(
            "candidate-only\n", encoding="utf-8"
        )

        copied = development.overlay_site_owned(self.downstream, candidate)

        self.assertEqual(
            (
                "extensions",
                "orinoco.yaml",
                "site-specific",
            ),
            copied,
        )
        self.assertEqual(
            "candidate framework\n",
            (candidate / "README.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            "pid: example:one\n",
            (
                candidate / "site-specific/metadata/records/one.yaml"
            ).read_text(encoding="utf-8"),
        )
        self.assertFalse((candidate / "generated").exists())
        self.assertFalse((candidate / "site-specific/stale.txt").exists())

    def test_overlay_omits_nested_runtime_state(self) -> None:
        cache = self.downstream / "extensions/source-adapters/example/.pixi/envs/bin"
        cache.mkdir(parents=True)
        (cache / "python").symlink_to("/usr/bin/python3")
        candidate = self.root / "candidate"
        candidate.mkdir()

        development.overlay_site_owned(self.downstream, candidate)

        self.assertTrue(
            (candidate / "extensions/source-adapters/example/run.py").is_file()
        )
        self.assertFalse(
            (candidate / "extensions/source-adapters/example/.pixi").exists()
        )

    def test_engine_environment_prefers_candidate_source(self) -> None:
        engine = self.root / "engine"
        package = engine / "packages/orinoco-lite/src/orinoco_lite"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")

        with patch.dict(os.environ, {"PYTHONPATH": "/existing"}, clear=False):
            environment = development.candidate_environment(
                engine,
                "example/downstream",
            )

        self.assertEqual(
            os.pathsep.join(
                (
                    os.fspath(engine.resolve() / "packages/orinoco-lite/src"),
                    "/existing",
                )
            ),
            environment["PYTHONPATH"],
        )
        self.assertEqual(
            os.fspath(engine.resolve()),
            environment["ORINOCO_CANDIDATE_ENGINE_ROOT"],
        )
        self.assertEqual("1", environment["ORINOCO_UNSAFE_DEVELOPMENT_RUNTIME"])
        self.assertEqual("example/downstream", environment["GITHUB_REPOSITORY"])

    def test_github_repository_is_discovered_from_ssh_origin(self) -> None:
        subprocess.run(
            ("git", "init", "--quiet"),
            cwd=self.downstream,
            check=True,
        )
        subprocess.run(
            (
                "git",
                "remote",
                "add",
                "origin",
                "git@github.com:example/downstream.git",
            ),
            cwd=self.downstream,
            check=True,
        )

        self.assertEqual(
            "example/downstream",
            development.github_repository(self.downstream),
        )
        self.assertEqual(
            "override/site",
            development.github_repository(
                self.downstream,
                "override/site",
            ),
        )

    def test_template_answers_use_only_current_candidate_questions(self) -> None:
        template = self.root / "template"
        template.mkdir()
        (template / "copier.yml").write_text(
            yaml.safe_dump(
                {
                    "_subdirectory": "copier-template",
                    "project_slug": {"type": "str", "default": "template-site"},
                    "engine_version": {"type": "str", "default": "0.2.0"},
                    "template_source": {
                        "type": "str",
                        "default": "gh:new/template",
                    },
                    "template_version": {
                        "type": "str",
                        "default": "v0.2.0",
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        answers = development._template_answers(self.downstream, template)

        self.assertEqual("downstream-site", answers["project_slug"])
        self.assertEqual("0.2.0", answers["engine_version"])
        self.assertEqual("gh:new/template", answers["template_source"])
        self.assertEqual("v0.2.0", answers["template_version"])
        self.assertNotIn("project_name", answers)
        self.assertNotIn("site_description", answers)
        self.assertNotIn("site_base_url", answers)

    def test_normalized_answers_use_candidate_release_identity(self) -> None:
        candidate = self.root / "candidate"
        candidate.mkdir()
        (candidate / ".copier-answers.yml").write_text(
            "_src_path: .\nproject_name: Example\n_commit: HEAD\n",
            encoding="utf-8",
        )

        development._normalize_copier_answers(
            candidate,
            {
                "template_source": "gh:new/template",
                "template_version": "v0.2.0",
            },
        )

        normalized = yaml.safe_load(
            (candidate / ".copier-answers.yml").read_text(encoding="utf-8")
        )
        self.assertEqual("gh:new/template", normalized["_src_path"])
        self.assertEqual("v0.2.0", normalized["_commit"])

    def test_quick_and_full_modes_have_distinct_scopes(self) -> None:
        self.assertEqual(
            (
                "validate",
                "build",
            ),
            development.task_names("quick", ()),
        )
        self.assertEqual(
            (
                "validate",
                "projection-verify",
                "verify-runtime",
                "verify-hugo",
                "verify-ownership",
                "verify-build",
            ),
            development.task_names("full", ()),
        )
        self.assertEqual(
            ("validate", "custom"),
            development.task_names("full", ("validate", "custom")),
        )

    def test_candidate_repository_has_a_clean_repeatable_metadata_base(self) -> None:
        candidate = self.root / "candidate"
        development.copy_working_tree(self.downstream, candidate)

        first = development.initialize_candidate_repository(candidate)
        repeat = self.root / "candidate-repeat"
        development.copy_working_tree(self.downstream, repeat)
        second = development.initialize_candidate_repository(repeat)

        self.assertEqual(len(first), 40)
        self.assertEqual(first, second)
        status = subprocess.run(
            ("git", "status", "--short"),
            cwd=candidate,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(status.stdout, "")
        committed = subprocess.run(
            ("git", "ls-tree", "-r", "--name-only", "HEAD"),
            cwd=candidate,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        self.assertIn("site-specific/metadata/records/one.yaml", committed)
        self.assertNotIn("generated/stale.txt", committed)

    def test_build_task_prepares_candidate_shells(self) -> None:
        candidate = self.root / "candidate"
        candidate.mkdir()
        (candidate / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
        engine = self.root / "engine"
        package = engine / "packages/orinoco-lite/src/orinoco_lite"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        application = engine / "packages/curation-review-app"
        (application / "node_modules").mkdir(parents=True)

        with (
            patch.object(development.shutil, "which", return_value="/bin/pixi"),
            patch.object(development, "prepare_candidate_editor_shell") as editor,
            patch.object(development, "_run") as run,
        ):
            development.exercise_candidate(
                candidate,
                engine=engine,
                tasks=("build",),
            )

        self.assertEqual(
            ("npm", "run", "build:review"),
            run.call_args_list[0].args[0],
        )
        editor.assert_called_once()
        self.assertEqual("build", run.call_args_list[1].args[0][-1])
        environment = run.call_args_list[1].kwargs["environment"]
        self.assertIn("ORINOCO_CANDIDATE_EDITOR_SHELL", environment)

    def test_focused_indirect_build_task_prepares_candidate_review_shell(self) -> None:
        candidate = self.root / "candidate"
        candidate.mkdir()
        (candidate / "pixi.toml").write_text("[workspace]\n", encoding="utf-8")
        engine = self.root / "engine"
        package = engine / "packages/orinoco-lite/src/orinoco_lite"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        application = engine / "packages/curation-review-app"
        (application / "node_modules").mkdir(parents=True)

        with (
            patch.object(development.shutil, "which", return_value="/bin/pixi"),
            patch.object(development, "prepare_candidate_editor_shell"),
            patch.object(development, "_run") as run,
        ):
            development.exercise_candidate(
                candidate,
                engine=engine,
                tasks=("build-browser-pages",),
            )

        self.assertEqual(
            ("npm", "run", "build:review"),
            run.call_args_list[0].args[0],
        )
        self.assertEqual(
            "build-browser-pages",
            run.call_args_list[1].args[0][-1],
        )

    def test_selected_tasks_are_run(self) -> None:
        candidate = self.root / "candidate"
        candidate.mkdir()
        (candidate / "pixi.toml").write_text(
            '[tasks]\nvalidate = "python -V"\n', encoding="utf-8"
        )

        with (
            patch.object(development.shutil, "which", return_value="/bin/pixi"),
            patch.object(development, "_run") as run,
        ):
            development.exercise_candidate(
                candidate,
                engine=None,
                tasks=("validate",),
            )

        self.assertEqual(1, run.call_count)
        self.assertEqual("validate", run.call_args.args[0][-1])

    def test_candidate_output_may_not_be_nested_in_any_source(self) -> None:
        engine = self.root / "engine"
        template = self.root / "template"
        engine.mkdir()
        template.mkdir()
        sources = development._candidate_output_sources(
            self.downstream,
            engine,
            template,
        )

        for source in (self.downstream, engine, template):
            with self.subTest(source=source), self.assertRaisesRegex(
                development.DevelopmentError, "cannot be inside"
            ):
                development.validate_candidate_output(source / "candidate", sources)

    def test_copy_rejects_destination_inside_source(self) -> None:
        with self.assertRaisesRegex(development.DevelopmentError, "inside its source"):
            development.copy_working_tree(
                self.downstream,
                self.downstream / "candidate",
            )

    def test_cli_requires_an_engine_or_template_candidate(self) -> None:
        self.assertEqual(
            2,
            development.main(("--downstream", os.fspath(self.downstream))),
        )


if __name__ == "__main__":
    unittest.main()
