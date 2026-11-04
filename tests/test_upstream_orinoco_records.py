from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock


from orinoco_lite import upstream_orinoco_records as storage
from orinoco_lite import upstream_snapshot as snapshot


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
