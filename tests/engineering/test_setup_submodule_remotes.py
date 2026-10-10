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
from tools.setup_submodule_remotes import selected_modules

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

    def test_initializes_recursive_submodules_at_selected_pins(self):
        nested, pin = self.add_nested()
        selected = git(self.child, "rev-parse", "HEAD").stdout.strip()
        git(self.child, "push", "origin", "HEAD:refs/heads/selected")
        git(self.child, "submodule", "deinit", "-f", "--", "nested")
        git(self.root, "submodule", "deinit", "-f", "--", "modules/child")
        self.run_script("--check", status=1)
        self.assertFalse((self.child / ".git").exists())
        self.run_script()
        self.run_script("--check")
        self.assertEqual(git(self.child, "rev-parse", "HEAD").stdout.strip(), selected)
        self.assertEqual(git(nested, "rev-parse", "HEAD").stdout.strip(), pin)

    def test_setup_preserves_initialized_checkout_and_local_changes(self):
        newer = commit_file(self.source, "value", "newer", "Upstream update")
        git(self.child, "fetch", "origin")
        git(self.child, "checkout", newer)
        (self.child / "value").write_text("work in progress")
        self.run_script()
        self.assertEqual(git(self.child, "rev-parse", "HEAD").stdout.strip(), newer)
        self.assertEqual((self.child / "value").read_text(), "work in progress")
        self.assertEqual(list(selected_modules(self.root))[0][2], self.base)

    def test_repairs_nested_mirror_without_changing_origin(self):
        nested, _ = self.add_nested("https://github.com/ORINOCO-Lite/shacl-vue.git")
        before = git(nested, "remote", "get-url", "origin").stdout
        self.run_script("--check", status=1)
        self.assertNotIn("upstream", git(nested, "remote").stdout)
        self.run_script()
        self.run_script("--check")
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
        self.run_script("--check", status=1)
        self.run_script()
        self.run_script("--check")
        self.assertIn("+refs/heads/*:refs/remotes/origin/*",
                      git(self.child, "config", "--get-all", "remote.origin.fetch").stdout)
        self.assertEqual(git(self.child, "show-ref").stdout, before)

    def test_unstaged_url_change_stops_initialization(self):
        git(self.root, "submodule", "deinit", "-f", "--", "modules/child")
        git(self.root, "config", "-f", ".gitmodules", "submodule.modules/child.url",
            "https://example.invalid/other.git")
        result = self.run_script(status=2)
        self.assertIn("reconcile unstaged .gitmodules", result.stderr)
        self.assertFalse((self.child / ".git").exists())

    def test_nested_initialization_requires_selected_parent_checkout(self):
        nested, _ = self.add_nested()
        git(self.child, "submodule", "deinit", "-f", "--", "nested")
        git(self.child, "checkout", self.base)
        result = self.run_script(status=2)
        self.assertIn("its current index selects different dependencies", result.stderr)
        self.assertFalse((nested / ".git").exists())

    def test_selected_paths_ignore_unrelated_missing_checkout(self):
        add_submodule(self.root, self.source, "modules/unrelated")
        git(self.root, "commit", "-am", "Record unrelated")
        git(self.root, "submodule", "deinit", "-f", "--", "modules/unrelated")
        modules = list(selected_modules(self.root, paths={"modules/child"}, revision="HEAD"))
        self.assertEqual([module[0] for module in modules], ["modules/child"])
        self.assertEqual(modules[0][2], self.base)


if __name__ == "__main__":
    unittest.main()
