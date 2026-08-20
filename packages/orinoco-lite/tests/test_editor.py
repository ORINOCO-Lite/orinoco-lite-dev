from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from orinoco_lite.annotations import annotation_companion, assertion_sha256
from orinoco_lite.canonical import canonical_yaml
from orinoco_lite.config import load_workspace
from orinoco_lite.editor import (
    BUNDLE_FORMAT,
    VERSION,
    _atomic_apply,
    apply_bundle,
    apply_bundle_report,
    record_catalog,
)
from orinoco_lite.errors import ConfigurationError, DriverError


CONFIG = """\
contract_version: 2
site:
  name: Editor fixture
  base_url: https://example.invalid/editor/
"""


class EditorBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
        for relative in (
            "metadata/records/XYZPerson",
            "metadata/records/XYZAgentRole",
            ".orinoco-lite/provenance",
            "editorial",
            "assets",
            "site/projection-templates",
            "site/projection-tools",
            "source-adapters",
            "generated",
            "extensions",
            "build",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        (self.root / "assets/manifest.yaml").write_text(
            "version: 1\nassets: {}\n", encoding="utf-8"
        )
        (self.root / "site/projection-templates/person.md.j2").write_text(
            "{{ display_label }}\n", encoding="utf-8"
        )
        (self.root / "site/projection-tools/graph.py").write_text(
            "import json, sys\njson.dump({'nodes': [], 'edges': []}, sys.stdout)\n",
            encoding="utf-8",
        )
        (self.root / "site/projection.yaml").write_text(
            "version: 2\n"
            "routing:\n  strip_prefix: 'xyzrins:'\n"
            "homepage:\n  pid: xyzrins:persons/first\n"
            "  template: site/projection-templates/person.md.j2\n"
            "pages:\n  xyzri:XYZPerson:\n"
            "    template: site/projection-templates/person.md.j2\n"
            "unrendered_classes: [xyzri:XYZAgentRole]\n"
            "graph:\n  producer: site/projection-tools/graph.py\n"
            "  node_classes: [xyzri:XYZPerson]\n"
            "  relationship_fields: []\n"
            "  missing_external_targets: reject\n",
            encoding="utf-8",
        )
        self.first = self.root / "metadata/records/XYZPerson/first.yaml"
        self.second = self.root / "metadata/records/XYZPerson/second.yaml"
        self.first.write_text(
            "pid: xyzrins:persons/first\n"
            "schema_type: xyzri:XYZPerson\n"
            "display_label: First\n",
            encoding="utf-8",
        )
        self.second.write_text(
            "pid: xyzrins:persons/second\n"
            "schema_type: xyzri:XYZPerson\n"
            "display_label: Second\n",
            encoding="utf-8",
        )
        (self.root / "metadata/records/XYZAgentRole/role.yaml").write_text(
            "pid: xyzrins:roles/member\n"
            "schema_type: xyzri:XYZAgentRole\n"
            "display_label: Member\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.name", "Fixture"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.email", "fixture@example.invalid"],
            check=True,
        )
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "fixture"], check=True
        )
        self.workspace = load_workspace(self.root)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()

        class FixtureConverter:
            def convert(self, value, class_name):
                from rdflib import Graph
                from rdflib.namespace import RDFS

                graph = Graph()
                graph.parse(data=value, format="turtle")
                subject = next(graph.subjects())
                label = next(graph.objects(subject, RDFS.label))
                return {
                    "pid": f"xyzrins:persons/{str(subject).rsplit('/', 1)[-1]}",
                    "schema_type": f"xyzri:{class_name}",
                    "display_label": str(label),
                }

        self.converter_patch = patch(
            "orinoco_lite.editor._converters",
            return_value=(FixtureConverter(), FixtureConverter()),
        )
        self.converter_patch.start()

    def tearDown(self) -> None:
        self.converter_patch.stop()
        self.temporary.cleanup()

    def _bundle(self, updates: dict[str, str]) -> Path:
        catalog = record_catalog(self.workspace)
        entries = {item["pid"]: item for item in catalog["records"]}
        records = []
        for pid, label in updates.items():
            source = entries[pid]
            slug = pid.rsplit("/", 1)[-1]
            records.append(
                {
                    "pid": pid,
                    "rdf_turtle": (
                        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                        f'<https://example.invalid/persons/{slug}> rdfs:label '
                        f"{json.dumps(label)} .\n"
                    ),
                    "schema_type": source["schema_type"],
                    "source_path": source["path"],
                    "source_sha256": source["sha256"],
                }
            )
        bundle = self.root / "bundle.json"
        bundle.write_text(
            json.dumps(
                {
                    "format": BUNDLE_FORMAT,
                    "records": records,
                    "source_commit": catalog["source_commit"],
                    "version": VERSION,
                }
            ),
            encoding="utf-8",
        )
        return bundle

    def test_catalog_uses_projection_editability_policy(self) -> None:
        catalog = record_catalog(self.workspace)
        self.assertEqual(catalog["version"], 2)
        self.assertEqual(len(catalog["records"]), 2)
        self.assertEqual(
            [record["pid"] for record in catalog["records"]],
            ["xyzrins:persons/first", "xyzrins:persons/second"],
        )

    def test_bundle_dry_run_and_write(self) -> None:
        bundle = self._bundle({"xyzrins:persons/first": "Changed"})
        report = apply_bundle_report(
            self.workspace, self.runtime, bundle, write=False
        )
        difference = report["diff"]
        self.assertIn("+display_label: Changed", difference)
        self.assertEqual(report["format"], "orinoco-editor-apply-report")
        self.assertEqual(
            report["changed_paths"],
            ["metadata/records/XYZPerson/first.yaml"],
        )
        self.assertFalse(report["applied"])
        self.assertIn("display_label: First", self.first.read_text())
        apply_bundle(self.workspace, self.runtime, bundle, write=True)
        self.assertIn("display_label: Changed", self.first.read_text())

    def test_bundle_rejects_traversal_duplicate_and_stale(self) -> None:
        bundle = self._bundle({"xyzrins:persons/first": "Changed"})
        value = json.loads(bundle.read_text())
        value["records"][0]["source_path"] = "../first.yaml"
        bundle.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(DriverError, "source path"):
            apply_bundle(self.workspace, self.runtime, bundle, write=False)
        bundle = self._bundle({"xyzrins:persons/first": "Changed"})
        value = json.loads(bundle.read_text())
        value["records"].append(value["records"][0])
        bundle.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(DriverError, "duplicate PID"):
            apply_bundle(self.workspace, self.runtime, bundle, write=False)
        bundle = self._bundle({"xyzrins:persons/first": "Changed"})
        value = json.loads(bundle.read_text())
        value["records"][0]["source_sha256"] = "0" * 64
        bundle.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(DriverError, "stale"):
            apply_bundle(self.workspace, self.runtime, bundle, write=False)

    def test_multi_record_replace_failure_rolls_back(self) -> None:
        originals = {self.first: self.first.read_bytes(), self.second: self.second.read_bytes()}
        updates = {
            self.first: self.first.read_text().replace("First", "Changed first"),
            self.second: self.second.read_text().replace("Second", "Changed second"),
        }
        real_replace = __import__("os").replace
        staged_replaces = 0

        def failing_replace(source, destination):
            nonlocal staged_replaces
            if str(source).endswith(".staged"):
                staged_replaces += 1
                if staged_replaces == 2:
                    raise OSError("injected replacement failure")
            return real_replace(source, destination)

        with patch("orinoco_lite.editor.os.replace", side_effect=failing_replace):
            with self.assertRaisesRegex(OSError, "injected"):
                _atomic_apply(updates)
        self.assertEqual(self.first.read_bytes(), originals[self.first])
        self.assertEqual(self.second.read_bytes(), originals[self.second])

    def test_human_replacement_reconciles_companion_in_the_same_apply(self) -> None:
        companion = (
            self.root
            / "metadata/overlays/annotations/XYZPerson/first.yaml"
        )
        companion.parent.mkdir(parents=True)
        companion.write_text(
            canonical_yaml(
                annotation_companion(
                    "xyzrins:persons/first",
                    [
                        {
                            "path": "/display_label",
                            "assertion_sha256": assertion_sha256("First"),
                            "pav:importedBy": "xyzrins:source-adapters/example/v1",
                            "pav:importedFrom": "https://source.example/people/first",
                        }
                    ],
                )
            ),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "add companion"],
            check=True,
        )
        bundle = self._bundle({"xyzrins:persons/first": "Human replacement"})

        report = apply_bundle_report(
            self.workspace, self.runtime, bundle, write=False
        )

        self.assertEqual(
            report["changed_paths"],
            [
                "metadata/overlays/annotations/XYZPerson/first.yaml",
                "metadata/records/XYZPerson/first.yaml",
            ],
        )
        self.assertIn("- assertion_sha256:", report["diff"])
        apply_bundle(self.workspace, self.runtime, bundle, write=True)
        self.assertEqual(
            yaml.safe_load(companion.read_text(encoding="utf-8"))["assertions"],
            [],
        )
        self.assertEqual(
            self.first.read_text(encoding="utf-8"),
            canonical_yaml(
                {
                    "display_label": "Human replacement",
                    "pid": "xyzrins:persons/first",
                    "schema_type": "xyzri:XYZPerson",
                }
            ),
        )

    def test_dirty_companion_and_bundle_inline_pav_fail_closed(self) -> None:
        companion = (
            self.root
            / "metadata/overlays/annotations/XYZPerson/first.yaml"
        )
        companion.parent.mkdir(parents=True)
        companion.write_text(
            canonical_yaml(
                annotation_companion(
                    "xyzrins:persons/first",
                    [
                        {
                            "path": "/display_label",
                            "assertion_sha256": assertion_sha256("First"),
                            "pav:importedBy": "xyzrins:source-adapters/example/v1",
                            "pav:importedFrom": "https://source.example/people/first",
                        }
                    ],
                )
            ),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "add companion"],
            check=True,
        )
        bundle = self._bundle({"xyzrins:persons/first": "Human replacement"})
        companion.write_text(
            canonical_yaml(
                annotation_companion("xyzrins:persons/first", [])
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(DriverError, "conflicting local change"):
            apply_bundle(self.workspace, self.runtime, bundle, write=False)

        subprocess.run(
            ["git", "-C", str(self.root), "restore", companion.relative_to(self.root)],
            check=True,
        )

        class InlinePavConverter:
            def convert(self, _value, class_name):
                return {
                    "pid": "xyzrins:persons/first",
                    "schema_type": f"xyzri:{class_name}",
                    "display_label": "Human replacement",
                    "annotations": {"pav:importedBy": "bypass"},
                }

        with patch(
            "orinoco_lite.editor._converters",
            return_value=(InlinePavConverter(), InlinePavConverter()),
        ):
            with self.assertRaisesRegex(
                ConfigurationError, "metadata/overlays/annotations"
            ):
                apply_bundle(self.workspace, self.runtime, bundle, write=False)


if __name__ == "__main__":
    unittest.main()
