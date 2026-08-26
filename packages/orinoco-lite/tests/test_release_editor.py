from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.errors import DriverError
from orinoco_lite.release_editor import (
    GIT_IDENTITY,
    REVIEW_BUNDLE_DISPATCH,
    SUBMISSION_ARIA_BINDING,
    _apply_submission_accessibility_patch,
    _initialize_repository,
)


class DeterministicEditorGitTests(unittest.TestCase):
    def test_independent_source_copies_have_identical_git_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repositories = [root / "first", root / "second"]
            commits = []
            with patch.dict(
                os.environ,
                {
                    "GIT_AUTHOR_DATE": "2035-01-01T00:00:00Z",
                    "GIT_COMMITTER_DATE": "2040-01-01T00:00:00Z",
                    "GIT_AUTHOR_NAME": "Hostile inherited author",
                },
            ):
                for repository in repositories:
                    repository.mkdir()
                    (repository / "source.txt").write_text(
                        "reviewed editor source\n", encoding="utf-8"
                    )
                    commits.append(_initialize_repository(repository, "a" * 40))
            self.assertEqual(commits[0], commits[1])
            for repository in repositories:
                result = subprocess.run(
                    [
                        "git",
                        "show",
                        "-s",
                        "--format=%at%x00%ct%x00%an%x00%ae%x00%cn%x00%ce",
                        "HEAD",
                    ],
                    cwd=repository,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(
                    result.stdout.strip().split("\0"),
                    [
                        "946684800",
                        "946684800",
                        GIT_IDENTITY["GIT_AUTHOR_NAME"],
                        GIT_IDENTITY["GIT_AUTHOR_EMAIL"],
                        GIT_IDENTITY["GIT_COMMITTER_NAME"],
                        GIT_IDENTITY["GIT_COMMITTER_EMAIL"],
                    ],
                )


class SubmissionAccessibilityOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_root = Path(__file__).resolve().parents[3]
        self.shacl = (
            self.source_root
            / "submodules/pool.psychoinformatics.de-ui/shacl-vue"
        )
        self.component = self.shacl / "src/components/SubmitComp.vue"
        self.patch = self.source_root / "release/editor-v2/SubmitComp.vue.patch"

    def require_source_fixture(self) -> None:
        if not self.component.is_file():
            self.skipTest("pinned SHACL Vue source fixture is unavailable")

    def test_reviewed_patch_applies_and_binds_the_canonical_pid_helper(self) -> None:
        self.require_source_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "shacl-vue"
            target = copied / "src/components/SubmitComp.vue"
            target.parent.mkdir(parents=True)
            target.write_bytes(self.component.read_bytes())

            _apply_submission_accessibility_patch(copied, target, self.patch)

            source = target.read_text(encoding="utf-8")
            self.assertEqual(source.count(SUBMISSION_ARIA_BINDING), 1)
            self.assertIn(
                "import { buildReviewBundle, dispatchReviewBundle,",
                source,
            )
            self.assertIn("recordIri: record.node_iri", source)
            self.assertIn("prefixes: allPrefixes", source)
            self.assertEqual(source.count(REVIEW_BUNDLE_DISPATCH), 1)
            self.assertLess(
                source.index("dlJSON(bundle, reviewBundleFilename(bundle.records));"),
                source.index(REVIEW_BUNDLE_DISPATCH),
            )

    def test_missing_accessibility_patch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            component = root / "src/components/SubmitComp.vue"
            component.parent.mkdir(parents=True)
            component.write_text("<template />\n", encoding="utf-8")
            with self.assertRaisesRegex(DriverError, "patch is missing"):
                _apply_submission_accessibility_patch(
                    root,
                    component,
                    root / "missing.patch",
                )


if __name__ == "__main__":
    unittest.main()
