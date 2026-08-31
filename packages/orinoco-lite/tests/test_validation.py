from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from orinoco_lite.annotations import (
    annotation_companion,
    annotation_files,
    assertion_sha256,
)
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


DISPLAY_LABEL_ASSERTION = {
    "predicate": "skos:prefLabel",
    "schema_type": "dlthings:AttributeSpecification",
    "value": "Test person",
}


class DownstreamValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
        for relative in (
            "site-specific/metadata/records/XYZPerson",
            "site-specific/metadata/records/XYZAgentRole",
            ".orinoco-lite/provenance",
            "site-specific/content",
            "site-specific",
            "extensions/adapters/zotero",
            "generated",
            "extensions",
            "build",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        (self.root / "site-specific/metadata/records/XYZPerson/person.yaml").write_text(
            "pid: xyzrins:persons/test\n"
            "schema_type: xyzri:XYZPerson\n"
            "display_label: Test person\n"
            "attributes:\n"
            "- predicate: skos:prefLabel\n"
            "  schema_type: dlthings:AttributeSpecification\n"
            "  value: Test person\n",
            encoding="utf-8",
        )
        (self.root / "site-specific/metadata/records/XYZAgentRole/role.yaml").write_text(
            "pid: xyzrins:roles/test\nschema_type: xyzri:XYZAgentRole\n",
            encoding="utf-8",
        )
        (self.root / ".orinoco-lite/provenance/selection.yaml").write_text(
            "version: 1\n", encoding="utf-8"
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
        (self.root / "site-specific/metadata/records/.dumpthings.yaml").write_text(
            "type: records\nnamespace: fixture\n", encoding="utf-8"
        )
        report = validate_workspace(load_workspace(self.root))
        self.assertEqual(report["records"], 2)

    def test_other_yaml_at_or_below_record_source_remains_fail_closed(self) -> None:
        cases = (
            ("site-specific/metadata/records/ordinary.yaml", "pid and schema_type"),
            (
                "site-specific/metadata/records/.review.yaml",
                "Everything below paths.records must be a Thing YAML record",
            ),
            (
                "site-specific/metadata/records/XYZPerson/.dumpthings.yaml",
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
            "site-specific/metadata/records/README.md",
            "site-specific/metadata/records/.DS_Store",
            "site-specific/metadata/records/XYZPerson/notes.txt",
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
        (self.root / "site-specific/metadata/records/XYZPerson/second.YAML").write_text(
            "pid: xyzrins:persons/second\nschema_type: xyzri:XYZPerson\n",
            encoding="utf-8",
        )
        report = validate_workspace(load_workspace(self.root))
        self.assertEqual(3, report["records"])

    def test_duplicate_pid_in_record_inventory_fails(self) -> None:
        (self.root / "site-specific/metadata/records/XYZAgentRole/role.yaml").write_text(
            "pid: xyzrins:persons/test\nschema_type: xyzri:XYZAgentRole\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "duplicated"):
            validate_workspace(load_workspace(self.root))

    def test_extensions_reject_website_functionality(self) -> None:
        for relative in (
            "layouts/term.html",
            "static/app.js",
            "assets/theme.css",
            "workflows/pages.yaml",
        ):
            with self.subTest(relative=relative):
                path = self.root / "extensions" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("forbidden\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    ConfigurationError,
                    "Website functionality is forbidden under extensions",
                ):
                    validate_workspace(load_workspace(self.root))
                path.unlink()

    def test_extensions_accept_metadata_adapter_executables(self) -> None:
        adapter = self.root / "extensions/adapters/example/adapter.py"
        adapter.parent.mkdir(parents=True, exist_ok=True)
        adapter.write_text("def acquire():\n    return []\n", encoding="utf-8")

        report = validate_workspace(load_workspace(self.root))

        self.assertEqual(1, report["files"]["extensions"])

    def test_metadata_outside_record_root_fails(self) -> None:
        legacy = self.root / "site-specific/metadata/reference"
        legacy.mkdir()
        with self.assertRaisesRegex(
            ConfigurationError,
            "Everything below site-specific/metadata must be part of paths.records or",
        ):
            validate_workspace(load_workspace(self.root))

    def test_configured_site_specific_metadata_boundary_fails_closed(self) -> None:
        config = self.root / "orinoco.yaml"
        config.write_text(
            CONFIG
            + "paths:\n"
            + "  records: declared/metadata/records\n",
            encoding="utf-8",
        )
        destination = self.root / "declared/metadata/records"
        destination.parent.mkdir(parents=True)
        (self.root / "site-specific/metadata/records").rename(destination)
        unknown = self.root / "declared/metadata/private/state.yaml"
        unknown.parent.mkdir(parents=True)
        unknown.write_text("not: allowed\n", encoding="utf-8")

        with self.assertRaisesRegex(ConfigurationError, "declared/metadata/private"):
            validate_workspace(load_workspace(self.root))

    def test_configured_annotation_diagnostic_names_derived_root(self) -> None:
        config = self.root / "orinoco.yaml"
        config.write_text(
            CONFIG
            + "paths:\n"
            + "  records: site-specific/metadata/records\n",
            encoding="utf-8",
        )
        unsupported = (
            self.root
            / "site-specific/metadata/overlays/annotations/README.md"
        )
        unsupported.parent.mkdir(parents=True)
        unsupported.write_text("not a companion\n", encoding="utf-8")

        with self.assertRaisesRegex(
            ConfigurationError,
            "Everything below site-specific/metadata/overlays/annotations",
        ):
            annotation_files(load_workspace(self.root))

    def test_one_component_record_root_does_not_claim_the_repository_root(self) -> None:
        config = self.root / "orinoco.yaml"
        config.write_text(
            CONFIG + "paths:\n  records: records\n",
            encoding="utf-8",
        )
        (self.root / "site-specific/metadata/records").rename(self.root / "records")

        report = validate_workspace(load_workspace(self.root))

        self.assertEqual(report["records"], 2)

    def test_one_component_record_root_keeps_derived_overlays_strict(self) -> None:
        config = self.root / "orinoco.yaml"
        config.write_text(
            CONFIG + "paths:\n  records: records\n",
            encoding="utf-8",
        )
        (self.root / "site-specific/metadata/records").rename(self.root / "records")
        unknown = self.root / "overlays/private/state.yaml"
        unknown.parent.mkdir(parents=True)
        unknown.write_text("not: allowed\n", encoding="utf-8")

        with self.assertRaisesRegex(ConfigurationError, "overlays/private"):
            validate_workspace(load_workspace(self.root))

    def test_mirrored_canonical_annotation_companion_passes(self) -> None:
        companion_path = (
            self.root
            / "site-specific/metadata/overlays/annotations/XYZPerson/person.yaml"
        )
        companion_path.parent.mkdir(parents=True)
        entry = {
            "path": "/attributes",
            "assertion_sha256": assertion_sha256(DISPLAY_LABEL_ASSERTION),
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
        unknown = self.root / "site-specific/metadata/overlays/private/state.yaml"
        unknown.parent.mkdir(parents=True)
        unknown.write_text("not: allowed\n", encoding="utf-8")
        with self.assertRaisesRegex(ConfigurationError, "overlays/annotations"):
            validate_workspace(load_workspace(self.root))
        unknown.unlink()
        unknown.parent.rmdir()

        orphan = self.root / "site-specific/metadata/overlays/annotations/orphan.yaml"
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
            / "site-specific/metadata/overlays/annotations/XYZPerson/person.yaml"
        )
        companion_path.parent.mkdir(parents=True)
        entry = {
            "path": "/attributes",
            "assertion_sha256": assertion_sha256({"value": "wrong"}),
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
        person = self.root / "site-specific/metadata/records/XYZPerson/person.yaml"
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
            ConfigurationError, "configured annotation companion tree"
        ):
            validate_workspace(load_workspace(self.root))

    def test_full_uri_discriminator_fails_closed(self) -> None:
        (self.root / "site-specific/metadata/records/XYZPerson/person.yaml").write_text(
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
