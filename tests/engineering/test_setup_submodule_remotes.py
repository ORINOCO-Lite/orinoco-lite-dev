from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.engineering.test_checkout_submodules import (
    add_submodule,
    commit_file,
    git,
    init_repository,
)

ROOT = Path(__file__).resolve().parents[2]


class SubmoduleSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = init_repository(self.directory / "source")
        self.base = commit_file(self.source, "value", "base", "Upstream")
        self.root = init_repository(self.directory / "parent")
        commit_file(self.root, "README", "fixture", "Initialize fixture")
        add_submodule(self.root, self.source, "modules/child")
        git(self.root, "commit", "-am", "Record child")
        self.child = self.root / "modules/child"

    def run_script(self, *args, status=0):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/setup_submodule_remotes.py"),
             "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            env={**os.environ, "GIT_ALLOW_PROTOCOL": "file"},
        )
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual(result.stdout, "")
        return result

    def add_nested(self, url=None):
        source = init_repository(self.directory / "nested-source")
        pin = commit_file(source, "value", "nested", "Nested upstream")
        add_submodule(self.child, source, "nested")
        if url:
            git(self.child, "config", "-f", ".gitmodules",
                "submodule.nested.url", url)
        git(self.child, "add", ".gitmodules", "nested")
        git(self.child, "-c", "user.name=Setup Test",
            "-c", "user.email=setup@example.invalid", "commit", "-m", "Add nested")
        git(self.root, "add", "modules/child")
        return self.child / "nested", pin

    def test_repairs_nested_mirror_without_changing_origin(self):
        nested, _ = self.add_nested("https://github.com/ORINOCO-Lite/shacl-vue.git")
        before = git(nested, "remote", "get-url", "origin").stdout
        self.assertNotIn("upstream", git(nested, "remote").stdout)
        self.run_script()
        self.assertEqual(git(nested, "remote", "get-url", "upstream").stdout.strip(),
                         "https://hub.psychoinformatics.de/orinoco/shacl-vue.git")
        self.assertEqual(git(nested, "remote", "get-url", "origin").stdout, before)
        self.assertEqual(git(nested, "config", "--get-all", "remote.upstream.fetch").stdout.strip(),
                         "+refs/heads/*:refs/remotes/upstream/*")

    def test_personal_mirror_keeps_other_remotes(self):
        git(self.root, "config", "-f", ".gitmodules", "submodule.modules/child.url",
            "https://github.com/alice/query-things.git")
        git(self.root, "add", ".gitmodules")
        git(self.child, "remote", "add", "upstream", "https://github.com/ORINOCO-Lite/query-things.git")
        git(self.child, "remote", "add", "orinoco-lite", "https://github.com/ORINOCO-Lite/query-things.git")
        origin = git(self.child, "remote", "get-url", "origin").stdout
        self.run_script()
        self.assertEqual(git(self.child, "remote", "get-url", "upstream").stdout.strip(),
                         "https://hub.psychoinformatics.de/orinoco/query-things.git")
        self.assertEqual(git(self.child, "remote", "get-url", "origin").stdout, origin)
        self.assertEqual(git(self.child, "remote", "get-url", "orinoco-lite").stdout.strip(),
                         "https://github.com/ORINOCO-Lite/query-things.git")

    def test_expands_single_branch_fetch_mapping_without_fetching(self):
        before = git(self.child, "show-ref").stdout
        git(self.child, "config", "remote.origin.fetch", "+refs/heads/main:refs/remotes/origin/main")
        self.run_script()
        self.assertIn("+refs/heads/*:refs/remotes/origin/*",
                      git(self.child, "config", "--get-all", "remote.origin.fetch").stdout)
        self.assertEqual(git(self.child, "show-ref").stdout, before)



class CheckoutHookTests(unittest.TestCase):
    def run_hook(self, path, *args):
        return subprocess.run(
            ["/bin/sh", str(ROOT / ".githooks/post-checkout"), *args],
            env={**os.environ, "PATH": str(path)}, text=True, capture_output=True,
        )

    def test_missing_pixi_warns_without_failing_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_hook(directory, "old", "new", "1")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Pixi is missing", result.stderr)
        self.assertIn("sh .githooks/post-checkout", result.stderr)

    def test_file_checkout_does_not_initialize(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_hook(directory, "old", "new", "0")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_failed_bootstrap_warns_without_failing_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            pixi = Path(directory) / "pixi"
            pixi.write_text("#!/bin/sh\nexit 1\n")
            pixi.chmod(0o755)
            result = self.run_hook(directory)
        self.assertEqual(result.returncode, 0)
        self.assertIn("initialization failed", result.stderr)
        self.assertIn("sh .githooks/post-checkout", result.stderr)


if __name__ == "__main__":
    unittest.main()
