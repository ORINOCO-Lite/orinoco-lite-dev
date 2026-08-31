from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.errors import DriverError
from orinoco_lite.release_editor import (
    DOWNLOAD_AND_DISPATCH,
    GIT_IDENTITY,
    REVIEW_BUNDLE_DISPATCH,
    REVIEW_BUNDLE_PROPOSAL,
    SHARED_ORIGIN_INFORMATION,
    SHARED_ORIGIN_WARNING,
    SUBMISSION_ARIA_BINDING,
    SUBMISSION_HEADER_ICON,
    SUBMISSION_HEADER_TOOLTIP,
    _apply_submission_accessibility_patch,
    _apply_submission_header_patch,
    _dependency_inventory,
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


class DependencyInventoryTests(unittest.TestCase):
    @staticmethod
    def write_package(
        root: Path,
        name: str,
        version: str,
        license_text: str,
    ) -> None:
        root.mkdir(parents=True)
        (root / "package.json").write_text(
            json.dumps({"license": "MIT", "name": name, "version": version})
            + "\n",
            encoding="utf-8",
        )
        (root / "LICENSE").write_text(license_text, encoding="utf-8")

    def test_recurses_through_installed_package_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            node_modules = root / "node_modules"
            self.write_package(
                node_modules / "example",
                "example",
                "2.0.0",
                "MIT top-level\n",
            )
            parent = node_modules / "parent"
            self.write_package(parent, "parent", "1.0.0", "MIT parent\n")
            self.write_package(
                parent / "node_modules/example",
                "example",
                "1.0.0",
                "MIT nested\n",
            )
            self.write_package(
                parent / "fixtures/not-installed",
                "not-installed",
                "9.9.9",
                "MIT fixture\n",
            )

            inventory = _dependency_inventory(
                node_modules,
                root / "licenses",
                component="review",
            )
            repeated = _dependency_inventory(
                node_modules,
                root / "licenses-repeated",
                component="review",
            )

            self.assertEqual(inventory, repeated)
            self.assertEqual(inventory["format"], "orinoco-review-dependency-inventory")
            self.assertEqual(
                [(item["name"], item["version"]) for item in inventory["packages"]],
                [
                    ("example", "1.0.0"),
                    ("example", "2.0.0"),
                    ("parent", "1.0.0"),
                ],
            )

    def test_copied_license_names_do_not_collide_after_sanitizing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            node_modules = root / "node_modules"
            self.write_package(
                node_modules / "@scope/example",
                "@scope/example",
                "1.0.0",
                "MIT scoped\n",
            )
            self.write_package(
                node_modules / "-scope-example",
                "-scope-example",
                "1.0.0",
                "MIT unscoped\n",
            )

            inventory = _dependency_inventory(node_modules, root / "licenses")

            license_files = [
                item["license_files"][0] for item in inventory["packages"]
            ]
            self.assertEqual(len(set(license_files)), 2)
            self.assertEqual(
                {
                    (root / "licenses" / path).read_text(encoding="utf-8")
                    for path in license_files
                },
                {"MIT scoped\n", "MIT unscoped\n"},
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
        self.header = self.shacl / "src/components/AppHeader.vue"
        self.header_patch = (
            self.source_root / "release/editor-v2/AppHeader.vue.patch"
        )

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
                "    beginReviewBundleProposal,\n    buildReviewBundle,",
                source,
            )
            self.assertIn("recordIri: record.node_iri", source)
            self.assertIn("prefixes: allPrefixes", source)
            self.assertEqual(source.count(REVIEW_BUNDLE_DISPATCH), 2)
            self.assertEqual(source.count(REVIEW_BUNDLE_PROPOSAL), 1)
            self.assertEqual(source.count("Propose via GitHub"), 1)
            self.assertIn("const framedContext = isFramedContext();", source)
            self.assertIn(
                "Direct GitHub proposal unavailable while embedded",
                source,
            )
            self.assertEqual(source.count("framedContext ||"), 1)
            self.assertNotIn("Confirm GitHub proposal", source)
            self.assertNotIn("Confirm and create draft pull request", source)
            self.assertLess(
                source.index("handoff = beginReviewBundleProposal("),
                source.index("await buildSelectedReviewBundle()"),
            )
            self.assertIn(DOWNLOAD_AND_DISPATCH, source)
            self.assertIn(SHARED_ORIGIN_WARNING, source)
            self.assertIn(SHARED_ORIGIN_INFORMATION, source)
            self.assertNotIn("publicHistoryAcknowledged", source)
            self.assertNotIn("sharedOriginAcknowledged", source)

    def test_reviewed_header_patch_uses_submit_copy_and_icon(self) -> None:
        self.require_source_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "shacl-vue"
            target = copied / "src/components/AppHeader.vue"
            target.parent.mkdir(parents=True)
            target.write_bytes(self.header.read_bytes())

            _apply_submission_header_patch(
                copied,
                target,
                self.header_patch,
            )

            source = target.read_text(encoding="utf-8")
            self.assertEqual(source.count(SUBMISSION_HEADER_ICON), 2)
            self.assertEqual(source.count(SUBMISSION_HEADER_TOOLTIP), 1)
            self.assertNotIn("'Download review bundle' : 'Submit'", source)

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

    def test_accessibility_patch_rejects_a_non_diff_preamble(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            component = root / "src/components/SubmitComp.vue"
            component.parent.mkdir(parents=True)
            component.write_text("<template />\n", encoding="utf-8")
            patch_path = root / "proposal.patch"
            patch_path.write_text("unexpected output\ndiff --git a/x b/x\n", encoding="utf-8")
            with self.assertRaisesRegex(DriverError, "invalid preamble"):
                _apply_submission_accessibility_patch(
                    root,
                    component,
                    patch_path,
                )


if __name__ == "__main__":
    unittest.main()
