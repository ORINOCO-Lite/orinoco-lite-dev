from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from orinoco_lite.config import (
    ConfigurationError,
    find_workspace_root,
    load_lock,
    load_workspace,
)


CONFIG = """\
contract_version: 2
site:
  name: Test Orinoco downstream
  base_url: https://example.invalid/test-site/
"""


LOCK = """\
lock_version: 1
engine:
  distribution: orinoco-lite
  version: 0.1.0
  url: https://example.invalid/releases/orinoco_lite-0.1.0-py3-none-any.whl
  sha256: cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
runtime:
  version: 0.1.0
  path: vendor/orinoco-runtime.tar.gz
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  manifest_sha256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
"""


class WorkspaceConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
        (self.root / "orinoco.lock").write_text(LOCK, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_defaults_resolve_relative_to_consumer(self) -> None:
        workspace = load_workspace(self.root)
        self.assertEqual(workspace.site_name, "Test Orinoco downstream")
        self.assertEqual(
            workspace.path("records").resolve(),
            (self.root / "metadata/records").resolve(),
        )
        self.assertEqual(workspace.path("site").resolve(), (self.root / "site").resolve())
        self.assertEqual(
            workspace.path("source_adapters").resolve(),
            (self.root / "source-adapters").resolve(),
        )
        self.assertEqual(
            workspace.environment()["ORINOCO_RECORDS_ROOT"],
            str((self.root / "metadata/records").resolve()),
        )
        self.assertEqual(
            workspace.environment()["ORINOCO_SOURCE_ADAPTERS_ROOT"],
            str((self.root / "source-adapters").resolve()),
        )
        self.assertNotIn("ORINOCO_CANONICAL_ROOT", workspace.environment())
        self.assertNotIn("ORINOCO_REFERENCE_ROOT", workspace.environment())
        self.assertNotIn("ORINOCO_INTEGRATIONS_ROOT", workspace.environment())
        self.assertEqual(
            workspace.path("provenance").resolve(),
            (self.root / ".orinoco-lite/provenance").resolve(),
        )
        self.assertIsNone(workspace.repository)
        self.assertIsNone(workspace.curation_service)

    def test_static_editor_github_handoff_coordinates_are_explicit(self) -> None:
        origins = (
            (
                "HTTPS://Review.Example.Test:443/",
                "https://review.example.test",
            ),
            (
                "https://Review.Example.Test:8443/",
                "https://review.example.test:8443",
            ),
            ("http://LOCALHOST:80/", "http://localhost"),
            ("https://[2001:0DB8::1]:443/", "https://[2001:db8::1]"),
        )
        for configured, expected in origins:
            with self.subTest(origin=configured):
                (self.root / "orinoco.yaml").write_text(
                    CONFIG.replace(
                        "  base_url: https://example.invalid/test-site/\n",
                        "  base_url: https://example.invalid/test-site/\n"
                        "  repository: ORINOCO-Lite/example-site\n"
                        f"  curation_service: {configured}\n",
                    ),
                    encoding="utf-8",
                )

                workspace = load_workspace(self.root)

                self.assertEqual(workspace.repository, "ORINOCO-Lite/example-site")
                self.assertEqual(workspace.curation_service, expected)

    def test_static_editor_github_handoff_coordinates_fail_closed(self) -> None:
        invalid_sites = (
            "  repository: ORINOCO-Lite/example-site\n",
            "  curation_service: https://review.example.test/\n",
            "  repository: not-a-repository\n"
            "  curation_service: https://review.example.test/\n",
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: http://review.example.test/\n",
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: https://review.example.test/edit/\n",
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: https://user@review.example.test/\n",
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: https://review.example.test/?mode=review\n",
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: https://review.example.test/#review\n",
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: https://127.1/\n",
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: https://0x7f000001/\n",
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: https://faß.example/\n",
        )
        for extra in invalid_sites:
            with self.subTest(extra=extra):
                (self.root / "orinoco.yaml").write_text(
                    CONFIG.replace(
                        "  base_url: https://example.invalid/test-site/\n",
                        "  base_url: https://example.invalid/test-site/\n" + extra,
                    ),
                    encoding="utf-8",
                )
                with self.assertRaises(ConfigurationError):
                    load_workspace(self.root)

    def test_site_name_matches_the_static_review_browser_contract(self) -> None:
        configured = (
            "  repository: ORINOCO-Lite/example-site\n"
            "  curation_service: https://review.example.test/\n"
        )
        exact_name = "r" * 233
        (self.root / "orinoco.yaml").write_text(
            CONFIG.replace(
                "  name: Test Orinoco downstream\n",
                f"  name: {exact_name}\n",
            ).replace(
                "  base_url: https://example.invalid/test-site/\n",
                "  base_url: https://example.invalid/test-site/\n" + configured,
            ),
            encoding="utf-8",
        )
        self.assertEqual(load_workspace(self.root).site_name, exact_name)

        invalid_names = (
            "r" * 234,
            '"review\\u007fname"',
            '"review\\u0009name"',
            '"' + ("\U0001f4da" * 117) + '"',
        )
        for invalid_name in invalid_names:
            with self.subTest(name=invalid_name):
                (self.root / "orinoco.yaml").write_text(
                    CONFIG.replace(
                        "  name: Test Orinoco downstream\n",
                        f"  name: {invalid_name}\n",
                    ).replace(
                        "  base_url: https://example.invalid/test-site/\n",
                        "  base_url: https://example.invalid/test-site/\n"
                        + configured,
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ConfigurationError, "site.name"):
                    load_workspace(self.root)

    def test_nearest_ancestor_discovers_workspace(self) -> None:
        nested = self.root / "metadata" / "records"
        nested.mkdir(parents=True)
        self.assertEqual(find_workspace_root(nested), self.root.resolve())

    def test_paths_cannot_escape_or_collide(self) -> None:
        (self.root / "orinoco.yaml").write_text(
            CONFIG + "paths:\n  records: ../outside\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ConfigurationError, "normalized relative"):
            load_workspace(self.root)
        (self.root / "orinoco.yaml").write_text(
            CONFIG
            + "paths:\n"
            + "  records: metadata\n"
            + "  provenance: metadata\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "distinct"):
            load_workspace(self.root)

    def test_removed_path_names_are_not_accepted_as_aliases(self) -> None:
        for name in ("canonical", "reference", "integrations"):
            with self.subTest(name=name):
                (self.root / "orinoco.yaml").write_text(
                    CONFIG + f"paths:\n  {name}: legacy\n", encoding="utf-8"
                )
                with self.assertRaisesRegex(ConfigurationError, "unknown path keys"):
                    load_workspace(self.root)

    def test_version_one_contract_is_rejected(self) -> None:
        (self.root / "orinoco.yaml").write_text(
            CONFIG.replace("contract_version: 2", "contract_version: 1"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "contract_version must be 2"):
            load_workspace(self.root)

    def test_lock_requires_one_immutable_runtime_location(self) -> None:
        lock = load_lock(self.root / "orinoco.lock")
        self.assertEqual(lock.runtime.path, "vendor/orinoco-runtime.tar.gz")
        (self.root / "orinoco.lock").write_text(
            LOCK.replace(
                "  path: vendor/orinoco-runtime.tar.gz\n",
                "  path: vendor/orinoco-runtime.tar.gz\n"
                "  url: https://example.invalid/runtime.tar.gz\n",
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "exactly one"):
            load_lock(self.root / "orinoco.lock")

    def test_lock_rejects_placeholder_digests_and_mismatched_wheel(self) -> None:
        for digest in ("c" * 64, "a" * 64, "b" * 64):
            value = LOCK.replace(digest, "0" * 64)
            (self.root / "orinoco.lock").write_text(value, encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "sha256"):
                load_lock(self.root / "orinoco.lock")
        (self.root / "orinoco.lock").write_text(
            LOCK.replace("orinoco_lite-0.1.0-", "orinoco_lite-0.1.1-"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "exact locked.*wheel"):
            load_lock(self.root / "orinoco.lock")


if __name__ == "__main__":
    unittest.main()
