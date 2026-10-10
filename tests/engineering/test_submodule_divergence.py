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
from tools.submodule_divergence import CSV_PATH, comparison_url, read_rows, render

ROOT = Path(__file__).resolve().parents[2]
GOOD = 'fix(data): preserve quoted "é, x" values [intent:general]'


class DivergenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = init_repository(self.directory / "source")
        self.base = commit_file(self.source, "value", "base", "Original upstream title")
        self.root = init_repository(self.directory / "parent")
        commit_file(self.root, "README", "fixture", "Initialize fixture")
        add_submodule(self.root, self.source, "modules/child")
        git(self.root, "commit", "-am", "Record child")
        self.child = self.root / "modules/child"
        git(self.child, "config", "user.name", "Divergence Test")
        git(self.child, "config", "user.email", "test@example.invalid")
        self.selected = commit_file(self.child, "value", "local", GOOD)
        git(self.root, "add", "modules/child")
        self.csv = self.root / CSV_PATH

    def run_script(self, *args, status=0, setup=False):
        script = "setup_submodule_remotes.py" if setup else "submodule_divergence.py"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / script),
                "--root",
                str(self.root),
                *args,
            ],
            text=True,
            capture_output=True,
            env={**os.environ, "GIT_ALLOW_PROTOCOL": "file"},
        )
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual(result.stdout, "")
        return result

    def row(self):
        return read_rows(self.csv.read_text())["modules/child"]

    def test_create_without_seed_then_idempotent(self):
        self.run_script("--no-fetch")
        first = self.csv.read_bytes()
        self.run_script("--no-fetch")
        self.run_script("--check")
        self.assertEqual(first, self.csv.read_bytes())
        self.assertEqual(self.row()["local_commit_subjects"], GOOD)
        self.assertEqual(self.row()["local_commits"], "1")
        self.assertEqual(self.row()["upstream_commits"], "0")
        self.assertEqual(git(self.root, "ls-files", "--", CSV_PATH).stdout, "")

    def test_reads_staged_pins_not_child_head(self):
        git(self.child, "checkout", self.base)
        self.run_script("--no-fetch")
        self.assertEqual(self.row()["selected_commit"], self.selected)

    def test_check_missing_csv_does_not_create_it(self):
        before = git(self.child, "show-ref").stdout
        self.run_script("--check", status=1)
        self.assertFalse(self.csv.exists())
        self.assertEqual(git(self.child, "show-ref").stdout, before)

    def test_csv_is_output_even_when_malformed(self):
        self.csv.parent.mkdir(parents=True)
        self.csv.write_text("not configuration\n")
        self.run_script("--check", status=1)
        self.assertEqual(self.csv.read_text(), "not configuration\n")
        self.run_script("--no-fetch")
        self.assertEqual(self.row()["upstream_commit"], self.base)

    def test_local_titles_are_reported_without_enforcement_or_repairs(self):
        invalid = commit_file(self.child, "value", "bad", "Legacy local title")
        git(self.root, "add", "modules/child")
        self.run_script("--no-fetch")
        result = self.run_script("--no-fetch")
        self.assertIn("Legacy local title", self.row()["local_commit_subjects"])
        self.assertNotIn("Original upstream title", self.row()["local_commit_subjects"])
        self.assertEqual(result.stderr, "")
        self.assertEqual(git(self.child, "rev-parse", "HEAD").stdout.strip(), invalid)

    def test_upstream_ahead_is_information_not_violation(self):
        upstream = commit_file(self.source, "upstream", "new", "Upstream change")
        self.run_script()
        self.assertEqual(self.row()["upstream_commit"], upstream)
        self.assertEqual(self.row()["upstream_commits"], "1")
        self.run_script()
        self.assertEqual(
            git(self.child, "rev-parse", "HEAD").stdout.strip(), self.selected
        )

    def test_shared_merge_ancestors_are_not_counted_as_local_changes(self):
        tree = git(self.source, "rev-parse", "HEAD^{tree}").stdout.strip()

        def commit(parents, title):
            args = ["commit-tree", tree]
            for parent in parents:
                args += ["-p", parent]
            return git(self.source, *args, "-m", title).stdout.strip()

        left = commit([self.base], "Original upstream left")
        right = commit([self.base], "Original upstream right")
        local = commit([left, right], "fix(data): combine branches [intent:general]")
        upstream = commit([right, left], "Original upstream merge")
        git(self.source, "update-ref", "refs/heads/main", upstream)
        git(self.source, "update-ref", "refs/heads/local", local)
        git(self.child, "fetch", "origin")
        git(self.root, "update-index", "--cacheinfo", "160000", local, "modules/child")
        self.run_script()
        row = self.row()
        self.assertEqual(row["local_commits"], "1")
        self.assertEqual(row["upstream_commits"], "1")
        self.assertEqual(
            row["local_commit_subjects"], "fix(data): combine branches [intent:general]"
        )
        self.run_script("--check")

    def test_failed_fetch_preserves_output(self):
        add_submodule(self.root, self.source, "modules/healthy")
        self.run_script("--no-fetch")
        before = self.csv.read_bytes()
        git(self.child, "remote", "set-url", "origin", str(self.directory / "missing"))
        self.run_script(status=2)
        self.assertEqual(self.csv.read_bytes(), before)

    def test_new_dependency_needs_no_csv_row(self):
        add_submodule(self.root, self.source, "modules/new")
        self.run_script("--no-fetch")
        self.assertIn("modules/new", read_rows(self.csv.read_text()))

    def test_nested_pin_and_branch_come_from_selected_parent(self):
        source = init_repository(self.directory / "nested-source")
        pin = commit_file(source, "nested", "stable", "Upstream nested")
        git(source, "branch", "stable")
        commit_file(source, "nested", "development", "Upstream development")
        add_submodule(self.child, source, "nested")
        nested = self.child / "nested"
        git(nested, "checkout", pin)
        git(
            self.child,
            "config",
            "-f",
            ".gitmodules",
            "submodule.nested.branch",
            "stable",
        )
        git(self.child, "add", ".gitmodules", "nested")
        git(
            self.child,
            "commit",
            "-m",
            "build(deps): select nested [intent:integration]",
        )
        git(self.root, "add", "modules/child")
        git(self.child, "checkout", self.selected)
        self.run_script("--no-fetch")
        row = read_rows(self.csv.read_text())["modules/child/nested"]
        self.assertEqual(row["selected_commit"], pin)
        self.assertEqual(row["upstream_ref"], "refs/heads/stable")
        self.assertEqual(row["local_commits"], "0")

    def test_fork_uses_upstream_default_when_no_branch_declared(self):
        git(
            self.root,
            "config",
            "-f",
            ".gitmodules",
            "--unset",
            "submodule.modules/child.branch",
        )
        git(self.root, "add", ".gitmodules")
        git(self.source, "branch", "-m", "master")
        git(self.child, "remote", "add", "upstream", self.source.as_uri())
        self.run_script()
        self.assertEqual(self.row()["upstream_ref"], "refs/heads/master")
        self.run_script("--no-fetch")
        self.assertIn(
            "compare/master...",
            comparison_url("https://github.com/ORINOCO-Lite/example.git", "master"),
        )

    def test_fetch_updates_cached_default_when_upstream_renames_branch(self):
        git(
            self.root,
            "config",
            "-f",
            ".gitmodules",
            "--unset",
            "submodule.modules/child.branch",
        )
        git(self.root, "add", ".gitmodules")
        git(self.child, "remote", "add", "upstream", self.source.as_uri())
        self.run_script()
        self.assertEqual(self.row()["upstream_ref"], "refs/heads/main")
        git(self.source, "branch", "-m", "new-default")
        self.run_script()
        self.assertEqual(self.row()["upstream_ref"], "refs/heads/new-default")
        self.assertEqual(
            git(
                self.child, "symbolic-ref", "refs/remotes/upstream/HEAD"
            ).stdout.strip(),
            "refs/remotes/upstream/new-default",
        )
        self.run_script("--check")

    def test_no_fetch_explains_missing_default_ref(self):
        git(
            self.root,
            "config",
            "-f",
            ".gitmodules",
            "--unset",
            "submodule.modules/child.branch",
        )
        git(self.root, "add", ".gitmodules")
        git(self.child, "remote", "add", "upstream", self.source.as_uri())
        result = self.run_script("--no-fetch", status=2)
        self.assertIn("run without --no-fetch", result.stderr)
        self.assertFalse(self.csv.exists())

    def test_shallow_dependency_requires_fetch_and_is_completed(self):
        import shutil

        git(self.child, "push", "origin", "HEAD:refs/heads/local")
        shutil.rmtree(self.child)
        git(
            self.root,
            "clone",
            "--depth",
            "1",
            "--branch",
            "local",
            self.source.as_uri(),
            str(self.child),
        )
        result = self.run_script("--check", status=2)
        self.assertIn("complete history", result.stderr)
        # Setup expands the clone's single-branch fetch mapping.
        self.run_script(setup=True)
        self.run_script()
        self.assertEqual(
            git(self.child, "rev-parse", "--is-shallow-repository").stdout.strip(),
            "false",
        )
        self.run_script("--check")

    def save_report(self):
        self.run_script("--no-fetch")
        git(self.root, "add", CSV_PATH, "modules/child")
        git(self.root, "commit", "-m", "Record current divergence")

    def test_fork_keeps_declared_branch_even_when_default_differs(self):
        git(self.source, "branch", "stable")
        commit_file(self.source, "new", "development", "Development only")
        git(
            self.root,
            "config",
            "-f",
            ".gitmodules",
            "submodule.modules/child.branch",
            "stable",
        )
        git(self.root, "add", ".gitmodules")
        git(self.child, "remote", "add", "upstream", self.source.as_uri())
        self.run_script()
        self.assertEqual(self.row()["upstream_ref"], "refs/heads/stable")
        self.assertEqual(self.row()["upstream_commit"], self.base)

    def test_staged_check_ignores_existing_stale_report_and_unavailable_checkout(self):
        self.save_report()
        self.csv.write_text("pre-existing malformed report\n")
        git(self.root, "add", CSV_PATH)
        git(self.root, "commit", "-m", "Legacy report")
        git(self.child, "push", "origin", "HEAD:refs/heads/local")
        git(self.root, "submodule", "deinit", "-f", "--", "modules/child")
        (self.root / "README").write_text("unrelated change")
        git(self.root, "add", "README")
        self.run_script("--staged-check")

    def test_staged_check_requires_staged_report_for_changed_pin(self):
        self.save_report()
        commit_file(self.child, "value", "new local", "Another legacy title")
        git(self.root, "add", "modules/child")
        self.run_script("--staged-check", status=1)
        self.run_script("--no-fetch")
        # Correct working file alone cannot disguise a stale staged report.
        self.run_script("--staged-check", status=1)
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check")
        self.assertIn("Another legacy title", self.row()["local_commit_subjects"])

    def test_staged_check_ignores_upstream_movement_for_unchanged_dependency(self):
        self.save_report()
        commit_file(self.source, "upstream", "new", "New upstream work")
        git(self.child, "fetch", "origin")
        (self.root / "README").write_text("unrelated change")
        git(self.root, "add", "README")
        self.run_script("--staged-check")
        self.run_script("--check", status=1)

    def test_staged_check_requires_refresh_for_declared_branch_change(self):
        self.save_report()
        git(self.source, "branch", "stable")
        git(self.child, "fetch", "origin")
        git(
            self.root,
            "config",
            "-f",
            ".gitmodules",
            "submodule.modules/child.branch",
            "stable",
        )
        git(self.root, "add", ".gitmodules")
        self.run_script("--staged-check", status=1)
        self.run_script("--no-fetch")
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check")

    def test_staged_check_does_not_fetch(self):
        self.save_report()
        commit_file(self.child, "value", "new", "New local title")
        git(self.root, "add", "modules/child")
        self.run_script("--no-fetch")
        git(self.root, "add", CSV_PATH)
        # Same cached upstream URL is kept in the report; URL rewrite blocks access.
        git(
            self.child,
            "config",
            "url.file:///missing-source/.insteadOf",
            self.source.as_uri(),
        )
        self.run_script("--staged-check")

    def test_staged_check_validates_changed_report_rows_without_pin_change(self):
        self.save_report()
        self.csv.write_text(self.csv.read_text().replace(self.selected, self.base))
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check", status=1)

    def test_staged_check_ignores_unstaged_report_edits(self):
        self.save_report()
        self.csv.write_text("unrelated unstaged draft\n")
        self.run_script("--staged-check")

    def add_nested(self):
        source = init_repository(self.directory / "nested-source")
        commit_file(source, "value", "base", "Nested upstream")
        add_submodule(self.child, source, "nested")
        git(self.child, "commit", "-am", "Select nested dependency")
        git(self.root, "add", "modules/child")
        return source, self.child / "nested"

    def test_staged_check_grandfathers_unchanged_nested_report_drift(self):
        source, nested = self.add_nested()
        self.save_report()
        original_nested = read_rows(self.csv.read_text())["modules/child/nested"]
        commit_file(source, "upstream", "new", "New nested upstream work")
        git(nested, "fetch", "origin")
        commit_file(self.child, "value", "another", "Unrelated parent change")
        git(self.root, "add", "modules/child")
        self.run_script("--no-fetch")
        rows = read_rows(self.csv.read_text())
        rows["modules/child/nested"] = original_nested
        self.csv.write_text(render(rows.values()))
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check")
        self.run_script("--check", status=1)

    def test_staged_check_requires_updated_nested_selection_row(self):
        _, nested = self.add_nested()
        self.save_report()
        original_nested = read_rows(self.csv.read_text())["modules/child/nested"]
        git(nested, "config", "user.name", "Divergence Test")
        git(nested, "config", "user.email", "test@example.invalid")
        commit_file(nested, "value", "local", "Nested local change")
        git(self.child, "add", "nested")
        git(self.child, "commit", "-m", "Select new nested commit")
        git(self.root, "add", "modules/child")
        self.run_script("--no-fetch")
        generated = self.csv.read_text()
        rows = read_rows(generated)
        rows["modules/child/nested"] = original_nested
        self.csv.write_text(render(rows.values()))
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check", status=1)
        self.csv.write_text(generated)
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check")

    def test_staged_check_requires_removed_dependency_row_removed(self):
        self.save_report()
        git(self.root, "rm", "-f", "modules/child")
        self.run_script("--staged-check", status=1)
        self.csv.write_text(render([]))
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check")

    def test_staged_check_skips_missing_unchanged_nested_checkout(self):
        _, nested = self.add_nested()
        self.save_report()
        commit_file(self.child, "value", "new", "Unrelated parent change")
        git(self.root, "add", "modules/child")
        self.run_script("--no-fetch")
        git(self.root, "add", CSV_PATH)
        git(self.child, "submodule", "deinit", "-f", "--", "nested")
        self.assertFalse((nested / ".git").exists())
        self.run_script("--staged-check")

    def test_staged_check_can_remove_nested_checkout_and_report_row(self):
        _, nested = self.add_nested()
        self.save_report()
        git(self.child, "rm", "-f", "nested")
        git(self.child, "commit", "-m", "Remove nested dependency")
        git(self.root, "add", "modules/child")
        self.assertFalse((nested / ".git").exists())
        self.run_script("--staged-check", status=1)
        self.run_script("--no-fetch")
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check")

    def test_staged_check_allows_repairing_malformed_committed_report(self):
        self.save_report()
        self.csv.write_text("legacy malformed report\n")
        git(self.root, "add", CSV_PATH)
        git(self.root, "commit", "-m", "Legacy broken report")
        self.run_script("--no-fetch")
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged-check")


if __name__ == "__main__":
    unittest.main()
