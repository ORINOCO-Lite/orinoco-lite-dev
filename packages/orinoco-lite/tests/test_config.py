from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from orinoco_lite.config import (
    ConfigurationError,
    DEFAULT_CURATION_SERVICE,
    find_workspace_root,
    github_repository,
    load_lock,
    load_workspace,
)


CONFIG = """\
contract_version: 2
"""


SITE_DATA = """\
version: 1
identity:
  title: Test Orinoco downstream
  description: A configuration fixture.
  base_url: https://example.invalid/test-site/
"""


LOCK = """\
lock_version: 1
engine:
  distribution: orinoco-lite
  version: 0.1.0
  url: https://example.invalid/releases/orinoco_lite-0.1.0-py3-none-any.whl
  sha256: cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
"""


class WorkspaceConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
        (self.root / "orinoco.lock").write_text(LOCK, encoding="utf-8")
        (self.root / "site-specific").mkdir()
        (self.root / "site-specific/site.yaml").write_text(
            SITE_DATA, encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_defaults_resolve_relative_to_consumer(self) -> None:
        workspace = load_workspace(self.root)
        self.assertEqual(workspace.site_name, "Test Orinoco downstream")
        self.assertEqual(workspace.base_url, "https://example.invalid/test-site/")
        self.assertEqual(
            workspace.site_data["identity"]["description"],
            "A configuration fixture.",
        )
        self.assertNotIn("site", workspace.raw)
        self.assertEqual(
            workspace.path("records").resolve(),
            (self.root / "site-specific/metadata/records").resolve(),
        )
        self.assertEqual(
            workspace.path("site").resolve(),
            (self.root / "site-specific").resolve(),
        )
        self.assertEqual(
            workspace.environment()["ORINOCO_RECORDS_ROOT"],
            str((self.root / "site-specific/metadata/records").resolve()),
        )
        self.assertNotIn("ORINOCO_SOURCE_ADAPTERS_ROOT", workspace.environment())
        self.assertNotIn("ORINOCO_FRAMEWORK_ROOT", workspace.environment())
        self.assertNotIn("ORINOCO_CANONICAL_ROOT", workspace.environment())
        self.assertNotIn("ORINOCO_REFERENCE_ROOT", workspace.environment())
        self.assertNotIn("ORINOCO_INTEGRATIONS_ROOT", workspace.environment())
        self.assertIsNone(workspace.repository)
        self.assertEqual(workspace.curation_service, DEFAULT_CURATION_SERVICE)

    def test_curation_service_is_optional_and_independent_of_repository(
        self,
    ) -> None:
        sites = (
            (
                "  repository: ORINOCO-Lite/example-site\n",
                "ORINOCO-Lite/example-site",
                DEFAULT_CURATION_SERVICE,
            ),
            (
                "  curation_service: https://review.example.test/\n",
                None,
                "https://review.example.test",
            ),
        )
        for extra, repository, service in sites:
            with self.subTest(extra=extra):
                (self.root / "orinoco.yaml").write_text(
                    CONFIG + "site:\n" + extra,
                    encoding="utf-8",
                )

                workspace = load_workspace(self.root)

                self.assertEqual(workspace.repository, repository)
                self.assertEqual(workspace.curation_service, service)

    def test_trusted_build_repository_coordinate_is_strict(self) -> None:
        self.assertEqual(
            github_repository(
                "ORINOCO-Lite/example-site",
                "GitHub repository build coordinate",
            ),
            "ORINOCO-Lite/example-site",
        )
        for invalid in (
            "not-a-repository",
            "ORINOCO-Lite/example..site",
            " ORINOCO-Lite/example-site",
            "ORINOCO-Lite/example-site/extra",
        ):
            with self.subTest(value=invalid):
                with self.assertRaisesRegex(
                    ConfigurationError,
                    "owner/repository",
                ):
                    github_repository(
                        invalid,
                        "GitHub repository build coordinate",
                    )

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
                    CONFIG
                    + "site:\n"
                    + "  repository: ORINOCO-Lite/example-site\n"
                    + f"  curation_service: {configured}\n",
                    encoding="utf-8",
                )

                workspace = load_workspace(self.root)

                self.assertEqual(workspace.repository, "ORINOCO-Lite/example-site")
                self.assertEqual(workspace.curation_service, expected)

    def test_static_editor_github_handoff_coordinates_fail_closed(self) -> None:
        invalid_sites = (
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
                    CONFIG + "site:\n" + extra,
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
            CONFIG + "site:\n" + configured,
            encoding="utf-8",
        )
        (self.root / "site-specific/site.yaml").write_text(
            SITE_DATA.replace(
                "  title: Test Orinoco downstream\n",
                f"  title: {exact_name}\n",
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
                (self.root / "site-specific/site.yaml").write_text(
                    SITE_DATA.replace(
                        "  title: Test Orinoco downstream\n",
                        f"  title: {invalid_name}\n",
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    ConfigurationError,
                    r"site-specific/site\.yaml identity\.title",
                ):
                    load_workspace(self.root)

    def test_nearest_ancestor_discovers_workspace(self) -> None:
        nested = self.root / "metadata" / "records"
        nested.mkdir(parents=True)
        self.assertEqual(find_workspace_root(nested), self.root.resolve())

    def test_public_identity_is_owned_only_by_site_specific_data(self) -> None:
        for field, value in (
            ("name", "Legacy name"),
            ("description", "Legacy description"),
            ("base_url", "https://example.invalid/legacy/"),
        ):
            with self.subTest(field=field):
                (self.root / "orinoco.yaml").write_text(
                    CONFIG + f"site:\n  {field}: {value}\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    ConfigurationError,
                    r"public site identity.*site-specific/site\.yaml",
                ):
                    load_workspace(self.root)

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
            + "  generated: metadata\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "distinct"):
            load_workspace(self.root)

    def test_paths_share_the_browser_service_normalization_contract(self) -> None:
        (self.root / "orinoco.yaml").write_text(
            CONFIG + "paths:\n  records: metadata/records/\n",
            encoding="utf-8",
        )
        self.assertEqual(
            load_workspace(self.root).paths["records"],
            "metadata/records",
        )

        invalid = (
            " metadata/records",
            "metadata/records ",
            "a" * 1_025,
        )
        for value in invalid:
            with self.subTest(value=value[:40]):
                (self.root / "orinoco.yaml").write_text(
                    CONFIG + f"paths:\n  records: {value!r}\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    ConfigurationError,
                    "normalized relative",
                ):
                    load_workspace(self.root)

        (self.root / "orinoco.yaml").write_text(
            CONFIG + 'paths:\n  records: "metadata/\\trecords"\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "normalized relative"):
            load_workspace(self.root)

    def test_removed_path_names_are_not_accepted_as_aliases(self) -> None:
        for name in (
            "assets",
            "canonical",
            "reference",
            "integrations",
            "provenance",
        ):
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

    def test_lock_carries_only_the_wheel_coordinate(self) -> None:
        lock = load_lock(self.root / "orinoco.lock")
        self.assertEqual(lock.engine_version, "0.1.0")

    def test_lock_rejects_placeholder_digests_and_mismatched_wheel(self) -> None:
        for digest in ("c" * 64,):
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
