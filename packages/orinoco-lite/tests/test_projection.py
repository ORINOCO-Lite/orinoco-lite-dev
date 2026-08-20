from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.annotations import annotation_companion, assertion_sha256
from orinoco_lite.canonical import canonical_yaml
from orinoco_lite.config import DEFAULT_PATHS, WorkspaceConfig
from orinoco_lite.errors import DriverError
from orinoco_lite.integrity import tree_sha256
from orinoco_lite.projection import (
    _machine_pav_fingerprint,
    projection_manifest,
    render_projection,
    update_projection,
    verify_projection,
)
from orinoco_lite.release_schema import localize_schema


CON_ROOT = Path(__file__).resolve().parents[4]
ENGINE_ROOT = Path(__file__).resolve().parents[3]
ACCEPTED_CONSUMER = CON_ROOT / "test-orinoco-downstream-website"
SCHEMA_SOURCE = ENGINE_ROOT / "submodules/things-schemas/src"


@unittest.skipUnless(
    (ACCEPTED_CONSUMER / "site/projection.yaml").is_file()
    and (ACCEPTED_CONSUMER / "generated/projection").is_dir()
    and (SCHEMA_SOURCE / "demo-research-information/unreleased.yaml").is_file(),
    "full-fidelity sibling fixture is not available",
)
class FullProjectionAcceptanceTests(unittest.TestCase):
    """Exercise the accepted full consumer without an engineering-tree runtime."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "consumer"
        self.runtime_010 = Path(self.temporary.name) / "runtime-0.1.0"
        self.runtime_011 = Path(self.temporary.name) / "runtime-0.1.1"
        self.root.mkdir()
        for relative in (
            "metadata",
            "site/projection.yaml",
            "site/projection-templates",
            "site/projection-tools",
            "generated/projection",
        ):
            source = ACCEPTED_CONSUMER / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copyfile(source, destination)
        localize_schema(
            SCHEMA_SOURCE,
            SCHEMA_SOURCE / "demo-research-information/unreleased.yaml",
            self.runtime_010 / "schema",
        )
        shutil.copytree(self.runtime_010 / "schema", self.runtime_011 / "schema")
        for runtime, release in ((self.runtime_010, "0.1.0"), (self.runtime_011, "0.1.1")):
            (runtime / "runtime-manifest.json").write_text(
                json.dumps({"release": release}) + "\n", encoding="utf-8"
            )
        self.workspace = WorkspaceConfig(
            root=self.root,
            config_path=self.root / "orinoco.yaml",
            lock_path=self.root / "orinoco.lock",
            site_name="Full fixture",
            base_url="https://example.invalid/",
            paths=DEFAULT_PATHS,
            command_aliases={},
            raw={},
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _active_files(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
            and path.name not in {".gitattributes", "SHA256SUMS"}
            and "provenance" not in path.parts
        }

    def test_full_parity_stale_recovery_atomicity_and_patch_compatibility(self) -> None:
        candidate = Path(self.temporary.name) / "candidate"
        previous_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(1000)
            with self.assertNoLogs("dump_things_service", level="WARNING"):
                report = render_projection(self.workspace, self.runtime_010, candidate)
            self.assertEqual(sys.getrecursionlimit(), 1000)
        finally:
            sys.setrecursionlimit(previous_limit)
        self.assertEqual(
            report,
            {
                "records": 199,
                "pages": 185,
                "graph_nodes": 186,
                "graph_edges": 467,
            },
        )
        self.assertEqual(
            self._active_files(ACCEPTED_CONSUMER / "generated/projection"),
            self._active_files(candidate),
        )
        self.assertNotIn(
            "xyzri:XYZ",
            (Path(__file__).parents[1] / "src/orinoco_lite/projection.py").read_text(),
        )

        committed = self.root / "generated/projection"
        provenance = committed / "provenance"
        preserved = Path(self.temporary.name) / "preserved-provenance"
        if provenance.is_dir():
            shutil.copytree(provenance, preserved)
        shutil.rmtree(committed)
        shutil.copytree(candidate, committed)
        if preserved.is_dir():
            shutil.copytree(preserved, committed / "provenance")

        semantic = {key: report[key] for key in report if key != "pages"}
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            verified = verify_projection(self.workspace, self.runtime_010)
        self.assertTrue(verified["deterministic"])
        self.assertEqual(
            projection_manifest(self.workspace, self.runtime_010, committed),
            projection_manifest(self.workspace, self.runtime_011, committed),
        )

        record = next(
            path
            for path in (self.root / "metadata/records").rglob("*.yaml")
            if not path.name.startswith(".")
        )
        record.write_text(record.read_text() + "# stale edit\n", encoding="utf-8")
        with self.assertRaisesRegex(DriverError, "stale"):
            verify_projection(self.workspace, self.runtime_010)
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            update_projection(self.workspace, self.runtime_010)
            verify_projection(self.workspace, self.runtime_011)

        before = tree_sha256(committed)
        real_replace = os.replace
        replacements = 0

        def fail_install(source, destination):
            nonlocal replacements
            replacements += 1
            if replacements == 2:
                raise OSError("injected projection install failure")
            return real_replace(source, destination)

        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            with patch("orinoco_lite.projection.os.replace", side_effect=fail_install):
                with self.assertRaisesRegex(OSError, "injected"):
                    update_projection(self.workspace, self.runtime_010)
        self.assertEqual(tree_sha256(committed), before)

        producer = self.root / "site/projection-tools/pool2graph.py"
        producer.write_text(
            producer.read_text() + "\nprint('missing node', file=sys.stderr)\n",
            encoding="utf-8",
        )
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            with self.assertRaisesRegex(DriverError, "missing node"):
                render_projection(
                    self.workspace,
                    self.runtime_010,
                    Path(self.temporary.name) / "bad-graph",
                )


class GenericProjectionContractTests(unittest.TestCase):
    """Keep core projection mechanics hermetic and independent of CON content."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "consumer"
        self.runtime = Path(self.temporary.name) / "runtime"
        for relative in (
            "metadata/records/Person",
            "site/projection-templates",
            "site/projection-tools",
            "generated",
        ):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        (self.root / "metadata/records/Person/home.yaml").write_text(
            "pid: acme:.\nschema_type: acme:Person\ndisplay_label: Home\n",
            encoding="utf-8",
        )
        (self.root / "metadata/records/Person/one.yaml").write_text(
            "pid: acme:people/one\nschema_type: acme:Person\ndisplay_label: One\n",
            encoding="utf-8",
        )
        (self.root / "site/projection-templates/page.md.j2").write_text(
            "---\npid: {{ pid }}\n---\n{{ display_label }}\n", encoding="utf-8"
        )
        (self.root / "site/projection-tools/graph.py").write_text(
            "import json,sys\n"
            "records=[json.loads(line) for line in sys.stdin if line.strip()]\n"
            "json.dump({'nodes':[{'id': r['pid']} for r in records], 'edges':[]},sys.stdout)\n",
            encoding="utf-8",
        )
        (self.root / "site/projection.yaml").write_text(
            "version: 2\n"
            "routing:\n  strip_prefix: 'acme:'\n"
            "homepage:\n  pid: 'acme:.'\n  template: site/projection-templates/page.md.j2\n"
            "pages:\n  'acme:Person':\n    template: site/projection-templates/page.md.j2\n"
            "unrendered_classes: []\n"
            "graph:\n  producer: site/projection-tools/graph.py\n"
            "  node_classes: ['acme:Person']\n  relationship_fields: []\n"
            "  missing_external_targets: reject\n",
            encoding="utf-8",
        )
        schema = self.runtime / "schema/demo/main.yaml"
        imported = self.runtime / "schema/types/base.yaml"
        schema.parent.mkdir(parents=True)
        imported.parent.mkdir(parents=True)
        schema.write_text("id: https://example.invalid/main\nimports: [../types/base]\n", encoding="utf-8")
        imported.write_text("id: https://example.invalid/base\n", encoding="utf-8")
        sources = []
        for relative in ("demo/main.yaml", "types/base.yaml"):
            data = (self.runtime / "schema" / relative).read_bytes()
            sources.append(
                {
                    "localized_path": relative,
                    "source_path": relative,
                    "source_sha256": hashlib.sha256(data).hexdigest(),
                    "localized_sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        (self.runtime / "schema/source-inventory.json").write_text(
            json.dumps(
                {
                    "entrypoint": "demo/main.yaml",
                    "format": "orinoco-localized-linkml-source-closure",
                    "sources": sources,
                    "version": 1,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self.workspace = WorkspaceConfig(
            root=self.root,
            config_path=self.root / "orinoco.yaml",
            lock_path=self.root / "orinoco.lock",
            site_name="Generic fixture",
            base_url="https://example.invalid/",
            paths=DEFAULT_PATHS,
            command_aliases={},
            raw={},
        )
        self.semantic = {
            "records": 2,
            "graph_nodes": 2,
            "graph_edges": 0,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_non_xyz_route_closure_pin_and_single_semantic_pass(self) -> None:
        with patch(
            "orinoco_lite.projection.validate_semantics", return_value=self.semantic
        ) as semantic:
            update_projection(self.workspace, self.runtime)
            semantic.reset_mock()
            report = verify_projection(self.workspace, self.runtime)
            semantic.assert_called_once()
        self.assertTrue(report["deterministic"])
        self.assertTrue(
            (
                self.root
                / "generated/projection/content/people/one/_index.md"
            ).is_file()
        )
        imported = self.runtime / "schema/types/base.yaml"
        imported.write_text(imported.read_text() + "# semantic change\n", encoding="utf-8")
        with self.assertRaisesRegex(DriverError, "stale"):
            verify_projection(self.workspace, self.runtime)

    def test_joined_annotations_reach_machine_projection_only(self) -> None:
        companion = self.root / (
            "metadata/overlays/annotations/Person/one.yaml"
        )
        companion.parent.mkdir(parents=True)
        companion.write_text(
            canonical_yaml(
                annotation_companion(
                    "acme:people/one",
                    [
                        {
                            "path": "/display_label",
                            "assertion_sha256": assertion_sha256("One"),
                            "pav:importedBy": "acme:source-adapters/example/v1",
                            "pav:importedFrom": "https://source.example/people/one",
                        }
                    ],
                )
            ),
            encoding="utf-8",
        )

        class Slot:
            range = "string"

        class Type:
            uri = "xsd:string"

        class Schema:
            def __init__(self, _path):
                pass

            def get_slot(self, name):
                return Slot() if name == "display_label" else None

            def get_class(self, _name):
                return None

            def get_type(self, _name):
                return Type()

            def get_uri(self, name, *, expand):
                self.assert_false = expand
                return {"display_label": "skos:prefLabel"}[name]

        output = Path(self.temporary.name) / "annotated-projection"
        with patch(
            "orinoco_lite.projection.validate_semantics", return_value=self.semantic
        ), patch("orinoco_lite.records.SchemaView", Schema):
            render_projection(self.workspace, self.runtime, output)

        public_page = output / "content/people/one/_index.md"
        self.assertEqual(
            public_page.read_text(encoding="utf-8"),
            "---\npid: acme:people/one\n---\nOne\n",
        )
        records = [
            json.loads(line)
            for line in (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        joined = next(item for item in records if item["pid"] == "acme:people/one")
        self.assertNotIn("annotations", joined)
        self.assertEqual(
            joined["attributes"][0]["annotations"]["pav:importedBy"]
            ["annotation_value"],
            "acme:source-adapters/example/v1",
        )
        stored = (
            self.root / "metadata/records/Person/one.yaml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("pav:imported", stored)
        manifest = (output / "SHA256SUMS").read_text(encoding="utf-8")
        self.assertIn(
            "input:metadata/overlays/annotations/Person/one.yaml",
            manifest,
        )

    def test_machine_pav_fingerprint_binds_provenance_to_assertion(self) -> None:
        annotation = {
            "pav:importedBy": {
                "annotation_tag": "pav:importedBy",
                "annotation_value": "acme:source-adapters/example/v1",
            },
            "pav:importedFrom": {
                "annotation_tag": "pav:importedFrom",
                "annotation_value": "https://source.example/people/one",
            },
        }
        original = {
            "notation": "source-one",
            "schema_type": "dlthings:Identifier",
            "annotations": annotation,
        }
        changed_assertion = deepcopy(original)
        changed_assertion["notation"] = "source-two"
        changed_source = deepcopy(original)
        changed_source["annotations"]["pav:importedFrom"][
            "annotation_value"
        ] = "https://source.example/people/two"

        self.assertNotEqual(
            _machine_pav_fingerprint(original),
            _machine_pav_fingerprint(changed_assertion),
        )
        self.assertNotEqual(
            _machine_pav_fingerprint(original),
            _machine_pav_fingerprint(changed_source),
        )

    def test_update_preserves_projection_control_sidecar_and_active_ledger(self) -> None:
        projection = self.root / "generated/projection"
        projection.mkdir()
        sidecar = projection / ".gitattributes"
        sidecar_bytes = b"* annex.largefiles=nothing\n"
        sidecar.write_bytes(sidecar_bytes)

        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            update_projection(self.workspace, self.runtime)
            report = verify_projection(self.workspace, self.runtime)

        self.assertEqual(sidecar.read_bytes(), sidecar_bytes)
        self.assertTrue((projection / "SHA256SUMS").is_file())
        self.assertNotIn(
            "output:.gitattributes",
            (projection / "SHA256SUMS").read_text(encoding="utf-8"),
        )
        self.assertTrue(report["deterministic"])

    def test_verify_rejects_arbitrary_undeclared_sidecar(self) -> None:
        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            update_projection(self.workspace, self.runtime)

        projection = self.root / "generated/projection"
        undeclared = projection / ".undeclared-sidecar"
        undeclared.write_text("must remain in deterministic scope\n", encoding="utf-8")
        (projection / "SHA256SUMS").write_text(
            projection_manifest(self.workspace, self.runtime, projection),
            encoding="utf-8",
        )

        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            with self.assertRaisesRegex(
                DriverError,
                r"deterministic regeneration: \.undeclared-sidecar",
            ):
                verify_projection(self.workspace, self.runtime)

    def test_double_failure_preserves_recovery_backup(self) -> None:
        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            update_projection(self.workspace, self.runtime)
        real_replace = os.replace
        replacements = 0

        def fail_install_and_rollback(source, destination):
            nonlocal replacements
            replacements += 1
            if replacements in {2, 3}:
                raise OSError(f"injected replace failure {replacements}")
            return real_replace(source, destination)

        with patch("orinoco_lite.projection.validate_semantics", return_value=self.semantic):
            with patch(
                "orinoco_lite.projection.os.replace",
                side_effect=fail_install_and_rollback,
            ):
                with self.assertRaisesRegex(DriverError, "original is preserved"):
                    update_projection(self.workspace, self.runtime)
        backups = list((self.root / "generated").glob(".projection-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "records.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
