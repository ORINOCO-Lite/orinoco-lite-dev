from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from orinoco_lite.annotations import annotation_companion, assertion_sha256
from orinoco_lite.canonical import canonical_yaml
from orinoco_lite.config import load_workspace
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.validation import validate_workspace


CONFIG = """\
contract_version: 2
site:
  name: Complete fixture
  base_url: https://example.invalid/complete/
"""


class DownstreamValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
        for relative in (
            "metadata/records/XYZPerson",
            "metadata/records/XYZAgentRole",
            ".orinoco-lite/provenance",
            "editorial",
            "assets/files",
            "site",
            "source-adapters/zotero",
            "generated",
            "extensions",
            "build",
        ):
            (self.root / relative).mkdir(parents=True)
        (self.root / "metadata/records/XYZPerson/person.yaml").write_text(
            "pid: xyzrins:persons/test\n"
            "schema_type: xyzri:XYZPerson\n"
            "display_label: Test person\n",
            encoding="utf-8",
        )
        (self.root / "metadata/records/XYZAgentRole/role.yaml").write_text(
            "pid: xyzrins:roles/test\nschema_type: xyzri:XYZAgentRole\n",
            encoding="utf-8",
        )
        (self.root / ".orinoco-lite/provenance/selection.yaml").write_text(
            "version: 1\n", encoding="utf-8"
        )
        (self.root / "assets/manifest.yaml").write_text(
            "version: 1\nassets: []\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_complete_flattened_layout_passes(self) -> None:
        report = validate_workspace(load_workspace(self.root))
        self.assertEqual(report["records"], 2)
        self.assertEqual(report["annotation_companions"], 0)
        self.assertEqual(report["annotation_assertions"], 0)
        self.assertEqual(
            report["record_classes"],
            {"xyzri:XYZAgentRole": 1, "xyzri:XYZPerson": 1},
        )

    def test_record_source_control_markers_are_not_records(self) -> None:
        (self.root / "metadata/records/.dumpthings.yaml").write_text(
            "type: records\nnamespace: fixture\n", encoding="utf-8"
        )
        report = validate_workspace(load_workspace(self.root))
        self.assertEqual(report["records"], 2)

    def test_other_yaml_at_or_below_record_source_remains_fail_closed(self) -> None:
        cases = (
            ("metadata/records/ordinary.yaml", "pid and schema_type"),
            (
                "metadata/records/.review.yaml",
                "Everything below paths.records must be a Thing YAML record",
            ),
            (
                "metadata/records/XYZPerson/.dumpthings.yaml",
                "Everything below paths.records must be a Thing YAML record",
            ),
        )
        for relative, message in cases:
            with self.subTest(relative=relative):
                path = self.root / relative
                path.write_text("type: records\n", encoding="utf-8")
                with self.assertRaisesRegex(ConfigurationError, message):
                    validate_workspace(load_workspace(self.root))
                path.unlink()

    def test_non_record_content_below_record_source_fails_closed(self) -> None:
        for relative in (
            "metadata/records/README.md",
            "metadata/records/.DS_Store",
            "metadata/records/XYZPerson/notes.txt",
        ):
            with self.subTest(relative=relative):
                path = self.root / relative
                path.write_text("not a Thing\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    ConfigurationError,
                    "Everything below paths.records must be a Thing YAML record",
                ):
                    validate_workspace(load_workspace(self.root))
                path.unlink()

    def test_yaml_suffix_matching_is_case_insensitive(self) -> None:
        (self.root / "metadata/records/XYZPerson/second.YAML").write_text(
            "pid: xyzrins:persons/second\nschema_type: xyzri:XYZPerson\n",
            encoding="utf-8",
        )
        report = validate_workspace(load_workspace(self.root))
        self.assertEqual(3, report["records"])

    def test_duplicate_pid_in_record_inventory_fails(self) -> None:
        (self.root / "metadata/records/XYZAgentRole/role.yaml").write_text(
            "pid: xyzrins:persons/test\nschema_type: xyzri:XYZAgentRole\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "duplicated"):
            validate_workspace(load_workspace(self.root))

    def test_metadata_outside_record_root_fails(self) -> None:
        legacy = self.root / "metadata/reference"
        legacy.mkdir()
        with self.assertRaisesRegex(
            ConfigurationError,
            "Everything below metadata must be part of paths.records or",
        ):
            validate_workspace(load_workspace(self.root))

    def test_mirrored_canonical_annotation_companion_passes(self) -> None:
        companion_path = (
            self.root
            / "metadata/overlays/annotations/XYZPerson/person.yaml"
        )
        companion_path.parent.mkdir(parents=True)
        entry = {
            "path": "/display_label",
            "assertion_sha256": assertion_sha256("Test person"),
            "pav:importedBy": "xyzrins:source-adapters/example/v1",
            "pav:importedFrom": "https://source.example/people/test",
        }
        companion_path.write_text(
            canonical_yaml(
                annotation_companion("xyzrins:persons/test", [entry])
            ),
            encoding="utf-8",
        )

        report = validate_workspace(load_workspace(self.root))

        self.assertEqual(report["annotation_companions"], 1)
        self.assertEqual(report["annotation_assertions"], 1)

    def test_annotation_tree_rejects_unknown_overlay_and_bad_mirror(self) -> None:
        unknown = self.root / "metadata/overlays/private/state.yaml"
        unknown.parent.mkdir(parents=True)
        unknown.write_text("not: allowed\n", encoding="utf-8")
        with self.assertRaisesRegex(ConfigurationError, "overlays/annotations"):
            validate_workspace(load_workspace(self.root))
        unknown.unlink()
        unknown.parent.rmdir()

        orphan = self.root / "metadata/overlays/annotations/orphan.yaml"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text(
            canonical_yaml(
                annotation_companion("xyzrins:persons/missing", [])
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "no mirrored metadata record"):
            validate_workspace(load_workspace(self.root))

    def test_annotation_tree_rejects_noncanonical_and_stale_selector(self) -> None:
        companion_path = (
            self.root
            / "metadata/overlays/annotations/XYZPerson/person.yaml"
        )
        companion_path.parent.mkdir(parents=True)
        entry = {
            "path": "/display_label",
            "assertion_sha256": assertion_sha256("wrong"),
            "pav:importedBy": "xyzrins:source-adapters/example/v1",
            "pav:importedFrom": "https://source.example/people/test",
        }
        companion = annotation_companion("xyzrins:persons/test", [entry])
        companion_path.write_text("- not-a-mapping\n", encoding="utf-8")
        with self.assertRaisesRegex(ConfigurationError, "must be mappings"):
            validate_workspace(load_workspace(self.root))

        companion_path.write_text(
            "record: xyzrins:persons/test\nassertions: []\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "not canonically serialized"):
            validate_workspace(load_workspace(self.root))

        companion_path.write_text(canonical_yaml(companion), encoding="utf-8")
        with self.assertRaisesRegex(ConfigurationError, "zero assertions"):
            validate_workspace(load_workspace(self.root))

    def test_inline_machine_pav_is_rejected_without_a_companion(self) -> None:
        person = self.root / "metadata/records/XYZPerson/person.yaml"
        person.write_text(
            "pid: xyzrins:persons/test\n"
            "schema_type: xyzri:XYZPerson\n"
            "identifiers:\n"
            "  - notation: test\n"
            "    schema_type: dlthings:Identifier\n"
            "    annotations:\n"
            "      http://purl.org/pav/importedBy: bypass\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ConfigurationError, "metadata/overlays/annotations"
        ):
            validate_workspace(load_workspace(self.root))

    def test_full_uri_discriminator_fails_closed(self) -> None:
        (self.root / "metadata/records/XYZPerson/person.yaml").write_text(
            "pid: xyzrins:persons/test\n"
            "schema_type: https://example.invalid/XYZPerson\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "CURIE"):
            validate_workspace(load_workspace(self.root))

    def test_gitlink_fails_downstream_contract(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "update-index",
                "--add",
                "--cacheinfo",
                "160000,0123456789012345678901234567890123456789,component",
            ],
            check=True,
        )
        with self.assertRaisesRegex(ConfigurationError, "gitlinks"):
            validate_workspace(load_workspace(self.root))


if __name__ == "__main__":
    unittest.main()
