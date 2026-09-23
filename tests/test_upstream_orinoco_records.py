from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from orinoco_lite.projection import load_contract

from orinoco_lite import upstream_orinoco_records as storage
from orinoco_lite import upstream_snapshot as snapshot


class UpstreamPresentationTests(unittest.TestCase):
    def test_default_projection_keeps_publication_authors_and_issued_date(self):
        from orinoco_lite.projection import _render_record
        import yaml

        presentation = Path(__file__).resolve().parents[1] / "submodules/www-from-model"
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Mock()
            workspace.path.return_value = Path(temporary)
            contract = load_contract(workspace, presentation)
        person = {
            "pid": "xyzrins:persons/example",
            "schema_type": "xyzri:XYZPerson",
            "given_name": "Example",
            "family_name": "Author",
        }
        publication = {
            "pid": "xyzrins:publications/example",
            "schema_type": "xyzri:XYZPublication",
            "title": "Example publication",
            "attributed_to": [{"object": person["pid"]}],
            "attributes": [{"predicate": "dcterms:issued", "value": "2024"}],
        }
        original = deepcopy(publication)
        rendered = _render_record(
            publication, contract.pages["xyzri:XYZPublication"],
            {person["pid"]: person}, [publication, person],
        )
        frontmatter = yaml.safe_load(rendered.split("---", 2)[1])
        self.assertEqual(frontmatter["persons"], ["example"])
        self.assertEqual(frontmatter["params"]["author"][0]["family_name"], "Author")
        self.assertEqual(frontmatter["params"]["date"], "2024")
        self.assertEqual(publication, original)


class UpstreamOrinocoRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_source(self, record: dict[str, object]) -> Path:
        path = self.root / "source.jsonl"
        path.write_text(
            json.dumps(
                {"class_name": "XYZPublication", "record": record},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_storage_projection_reconstructs_original_machine_pav_exactly(self) -> None:
        record = {
            "pid": "xyzrins:publications/one",
            "schema_type": "xyzri:XYZPublication",
            "attributes": [
                {
                    "schema_type": "dlthings:AttributeSpecification",
                    "predicate": "dlthings:title",
                    "value": "Source title",
                    "annotations": {
                        "http://purl.org/pav/importedBy": {
                            "annotation_tag": "http://purl.org/pav/importedBy",
                            "annotation_value": "xyzrins:adapters/example",
                        },
                        "http://purl.org/pav/importedFrom": {
                            "annotation_tag": "pav:importedFrom",
                            "annotation_value": "https://source.example/one",
                        },
                        "ex:reviewed": "yes",
                    },
                }
            ],
        }
        source = self.write_source(record)
        output = self.root / "projection"

        report = storage.project(source, output)

        self.assertEqual(report["record_count"], 1)
        self.assertEqual(report["annotation_companions"], 1)
        self.assertEqual(report["annotation_assertions"], 1)
        self.assertEqual(
            report["reconstructed_semantic_sha256"],
            report["source_semantic_sha256"],
        )
        stored = snapshot.load_records_tree(output / "metadata" / "records")[0]
        self.assertEqual(
            stored.record["attributes"][0]["annotations"],
            {"ex:reviewed": "yes"},
        )
        companion_path = next(
            (output / "metadata" / "overlays" / "machine-provenance-annotations").rglob("*.yaml")
        )
        companion = storage._load_companion(companion_path)
        self.assertEqual(
            companion["assertions"][0]["pav:importedBy"],
            "xyzrins:adapters/example",
        )
        from orinoco_lite.record_stages import yaml_to_jsonl
        returned = yaml_to_jsonl(output, self.root / "returned.jsonl")
        self.assertEqual(returned[0].record, record)
        self.assertEqual(storage.verify_projection(source, output), report)

    def test_records_without_machine_pav_remain_byte_semantically_equal(self) -> None:
        record = {
            "pid": "xyzrins:publications/plain",
            "schema_type": "xyzri:XYZPublication",
            "title": "Plain record",
        }
        source = self.write_source(record)
        output = self.root / "projection"

        report = storage.project(source, output)

        self.assertEqual(report["annotation_companions"], 0)
        self.assertEqual(
            report["source_semantic_sha256"],
            report["stored_records_semantic_sha256"],
        )

    def test_source_datetime_marker_is_preserved_without_inventing_a_date(self) -> None:
        record = {
            "pid": "xyzrins:publications/sentinel",
            "schema_type": "xyzri:XYZPublication",
            "generated_by": [
                {
                    "object": "obo:IAO_0000444",
                    "at_time": "-",
                    "schema_type": "dlthings:Generation",
                }
            ],
        }
        source = self.write_source(record)
        output = self.root / "projection"

        report = storage.project(source, output)

        stored = snapshot.load_records_tree(output / "metadata" / "records")[0]
        self.assertEqual(stored.record, record)
        self.assertEqual(
            report["source_semantic_sha256"],
            report["reconstructed_semantic_sha256"],
        )
        from orinoco_lite.record_stages import yaml_to_jsonl
        returned = yaml_to_jsonl(output, self.root / "returned.jsonl")
        self.assertEqual(returned[0].record, record)
        self.assertEqual(storage.verify_projection(source, output), report)


if __name__ == "__main__":
    unittest.main()
