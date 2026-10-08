from __future__ import annotations

import csv
import os
import shutil
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
from tools.submodule_divergence import CSV_PATH, FIELDS, read_rows

SCRIPT = Path(__file__).resolve().parents[2] / "tools/submodule_divergence.py"
GOOD = 'fix(data): preserve quoted "é, x" values [intent:general]'


class DivergenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        directory = Path(self.temporary.name)
        self.source = init_repository(directory / "source")
        self.base = commit_file(self.source, "value", "base", "Original upstream title")
        self.root = init_repository(directory / "parent")
        commit_file(self.root, "README", "fixture", "Initialize fixture")
        add_submodule(self.root, self.source, "modules/child")
        git(self.root, "commit", "-am", "Record child")
        self.child = self.root / "modules/child"
        git(self.child, "config", "user.name", "Divergence Test")
        git(self.child, "config", "user.email", "test@example.invalid")
        self.selected = commit_file(self.child, "value", "local", GOOD)
        git(self.root, "add", "modules/child")
        git(self.root, "commit", "-m", "Select local change")
        self.csv = self.root / CSV_PATH
        self.csv.parent.mkdir(parents=True)
        with self.csv.open("w", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerow(
                dict(
                    path="modules/child",
                    upstream_url=self.source.as_uri(),
                    upstream_ref="HEAD",
                    upstream_commit=self.base,
                )
            )
        self.run_script()
        git(self.root, "add", CSV_PATH)
        git(self.root, "commit", "-m", "Record snapshot")

    def run_script(self, *args, status=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            env={**os.environ, "GIT_ALLOW_PROTOCOL": "file"},
        )
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual(result.stdout, "")
        return result

    def row(self):
        return read_rows(self.csv.read_text())["modules/child"]

    def test_exact_subjects_counts_noop_and_no_checkout_changes(self):
        first = self.csv.read_bytes()
        self.run_script("--check")
        self.run_script()
        self.assertEqual(first, self.csv.read_bytes())
        self.assertEqual(self.row()["local_commit_subjects"], GOOD)
        self.assertEqual(self.row()["local_commits"], "1")
        self.assertEqual(self.row()["upstream_commits"], "0")
        # An unrelated checkout HEAD must not change the parent's recorded pin.
        git(self.child, "checkout", self.base)
        self.run_script("--check")
        self.assertEqual(self.row()["selected_commit"], self.selected)

    def test_staged_pin_requires_staged_csv_not_working_copy(self):
        newer = commit_file(
            self.child, "value", "new", "feat(data): add field [intent:integration]"
        )
        git(self.root, "add", "modules/child")
        result = self.run_script("--staged", "--check", status=1)
        self.assertIn("CSV is stale", result.stderr)
        self.run_script("--staged")
        self.assertEqual(self.row()["selected_commit"], newer)
        self.run_script("--staged", "--check", status=1)
        git(self.root, "add", CSV_PATH)
        self.run_script("--staged", "--check")

    def test_fix_repairs_working_csv_but_never_stages_and_requires_retry(self):
        newer = commit_file(
            self.child, "value", "new", "fix(data): new value [intent:general]"
        )
        git(self.root, "add", "modules/child")
        staged = git(self.root, "show", f":{CSV_PATH}").stdout
        unrelated = self.root / "notes.txt"
        unrelated.write_text("keep my notes")
        result = self.run_script("--fix", status=1)
        self.assertIn("Nothing was staged", result.stderr)
        self.assertEqual(self.row()["selected_commit"], newer)
        self.assertEqual(git(self.root, "show", f":{CSV_PATH}").stdout, staged)
        self.assertEqual(unrelated.read_text(), "keep my notes")
        repaired = self.csv.read_bytes()
        result = self.run_script("--fix", status=1)
        self.assertIn("already in the working file", result.stderr)
        self.assertEqual(self.csv.read_bytes(), repaired)
        git(self.root, "add", CSV_PATH)
        self.run_script("--fix")

    def test_fix_preserves_partially_staged_csv(self):
        commit_file(self.child, "value", "new", "fix(data): new value [intent:general]")
        git(self.root, "add", "modules/child")
        self.csv.write_text(
            self.csv.read_text().replace(GOOD.replace('"', '""'), "staged edit")
        )
        git(self.root, "add", CSV_PATH)
        staged = git(self.root, "show", f":{CSV_PATH}").stdout
        self.csv.write_text(self.csv.read_text() + "\n")
        working = self.csv.read_bytes()
        result = self.run_script("--fix", status=1)
        self.assertIn("unstaged edits; no files changed", result.stderr)
        self.assertEqual(self.csv.read_bytes(), working)
        self.assertEqual(git(self.root, "show", f":{CSV_PATH}").stdout, staged)

    def test_read_only_check_never_repairs(self):
        commit_file(self.child, "value", "new", "fix(data): new value [intent:general]")
        git(self.root, "add", "modules/child")
        before = self.csv.read_bytes()
        self.run_script("--staged", "--check", status=1)
        self.assertEqual(self.csv.read_bytes(), before)

    def test_fix_repairs_csv_but_leaves_invalid_history_unchanged(self):
        invalid = commit_file(self.child, "value", "bad", "Unclassified local change")
        git(self.root, "add", "modules/child")
        result = self.run_script("--fix", status=1)
        self.assertIn("Updated", result.stderr)
        self.assertIn("cannot be fixed automatically", result.stderr)
        self.assertIn("Unclassified local change", result.stderr)
        self.assertEqual(git(self.child, "rev-parse", "HEAD").stdout.strip(), invalid)
        self.assertEqual(self.row()["selected_commit"], invalid)
        git(self.root, "add", CSV_PATH)
        result = self.run_script("--fix", status=1)
        self.assertIn("cannot be fixed automatically", result.stderr)
        self.assertNotIn("Updated", result.stderr)

    def test_fix_rejects_network_and_read_only_flags(self):
        for option in ("--check", "--fetch", "--prepare"):
            result = self.run_script("--fix", option, status=2)
            self.assertIn("--fix is offline", result.stderr)

    def test_all_existing_local_titles_are_checked_but_upstream_is_exempt(self):
        commit_file(self.child, "value", "bad", "Legacy local title")
        git(self.root, "add", "modules/child")
        git(self.root, "commit", "-m", "Select legacy local commit")
        self.run_script()
        result = self.run_script("--check", status=1)
        self.assertIn("Legacy local title", result.stderr)
        self.assertNotIn("Original upstream title", result.stderr)
        self.assertNotIn("CSV is stale", result.stderr)

    def test_fetch_detects_upstream_advance_and_does_not_advance_pins(self):
        upstream = commit_file(self.source, "upstream", "new", "Upstream change")
        self.run_script("--fetch")
        self.assertEqual(self.row()["upstream_commit"], upstream)
        self.assertEqual(self.row()["upstream_commits"], "1")
        self.assertEqual(self.row()["selected_commit"], self.selected)
        before = self.csv.read_bytes()
        self.run_script("--fetch")
        self.assertEqual(self.csv.read_bytes(), before)

    def test_failed_fetch_preserves_csv(self):
        before = self.csv.read_text()
        self.csv.write_text(
            before.replace(self.source.as_uri(), self.source.as_uri() + "-missing")
        )
        before = self.csv.read_bytes()
        result = self.run_script("--fetch", status=2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.csv.read_bytes(), before)

    def test_unknown_new_submodule_requires_explicit_upstream(self):
        add_submodule(self.root, self.source, "modules/new")
        result = self.run_script("--staged", status=2)
        self.assertIn("Add a CSV row for modules/new", result.stderr)

    def test_nested_pins_follow_selected_parent_not_checkout_head(self):
        nested_source = init_repository(Path(self.temporary.name) / "nested")
        nested_base = commit_file(nested_source, "nested", "base", "Upstream nested")
        nested_pin = commit_file(
            nested_source, "nested", "local", "fix(nested): fix value [intent:general]"
        )
        add_submodule(self.child, nested_source, "nested")
        git(
            self.child,
            "commit",
            "-am",
            "build(deps): select nested dependency [intent:integration]",
        )
        git(self.root, "add", "modules/child")
        git(self.root, "commit", "-m", "Select nested parent")
        with self.csv.open("a", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
            writer.writerow(
                dict(
                    path="modules/child/nested",
                    upstream_url=nested_source.as_uri(),
                    upstream_ref="HEAD",
                    upstream_commit=nested_base,
                )
            )
        git(self.child, "checkout", self.selected)
        git(self.child / "nested", "checkout", nested_base)
        self.run_script()
        rows = read_rows(self.csv.read_text())
        self.assertEqual(rows["modules/child/nested"]["selected_commit"], nested_pin)
        self.run_script("--check")

    def test_shallow_clone_can_prepare_recorded_history_without_advancing_snapshot(
        self,
    ):
        git(self.child, "push", self.source.as_uri(), "HEAD:refs/heads/local")
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
        before = self.csv.read_bytes()
        result = self.run_script("--check", status=2)
        self.assertIn("complete history is required", result.stderr)
        self.run_script("--prepare", "--check")
        self.assertEqual(self.csv.read_bytes(), before)

    def test_unrelated_staged_change_does_not_require_submodule_history(self):
        (self.root / "README").write_text("edited")
        git(self.root, "add", "README")
        git(self.root, "submodule", "deinit", "-f", "--", "modules/child")
        self.run_script("--staged", "--check")
        self.run_script("--fix")


if __name__ == "__main__":
    unittest.main()
