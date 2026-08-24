from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from linkml_runtime import SchemaView
import things_enrichment_tools as upstream

from orinoco_lite.annotations import (
    compact_enrichment_view,
    join_annotations,
    split_enrichment_view,
)
from orinoco_lite.enrichment import (
    EnrichmentSlotSemantics,
    resolve_enrichment_slot,
    update_data_property,
    update_multivalued_object_property,
    update_object_property,
    update_schema_data_property,
)
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.schema_conversion import build_format_converters


AGENT = "xyzrins:source-adapters/example/v1"
OTHER_AGENT = "xyzrins:source-adapters/other/v2"
SOURCE = "https://source.example/records/one"
SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "submodules/things-schemas/src/demo-research-information/unreleased.yaml"
)


def base_record(**values: object) -> dict[str, object]:
    return {
        "pid": "xyzrins:records/one",
        "schema_type": "xyzri:XYZPublication",
        **values,
    }


def machine_annotations(
    owner: str = AGENT, source: str = SOURCE
) -> dict[str, str]:
    return {"pav:importedBy": owner, "pav:importedFrom": source}


def split(
    working: dict[str, object],
) -> tuple[dict[str, object], dict[str, object] | None]:
    return split_enrichment_view(working)


def helper_shape(
    record: dict[str, object],
    *,
    predicate: str | None = None,
    datatype: str | None = None,
) -> dict[str, object]:
    """Remove only the locked-schema normalization around upstream output."""

    normalized = deepcopy(record)
    for attribute in normalized.get("attributes", []):
        if not isinstance(attribute, dict):
            continue
        attribute.pop("schema_type", None)
        if datatype is not None and attribute.get("predicate") == predicate:
            if attribute.get("range") == datatype:
                attribute["value"] = json.loads(attribute["value"])
                del attribute["range"]
    return normalized


class DataPropertyParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = SchemaView(str(SCHEMA)) if SCHEMA.is_file() else None

    def assert_string_parity(
        self,
        baseline_working: dict[str, object],
        value: object,
    ):
        stored, companion = split(baseline_working)
        direct = deepcopy(baseline_working)
        direct_modified = upstream.update_data_property(
            direct,
            predicate="dlthings:title",
            value=deepcopy(value),
            topical_slot="title",
            owner_id=AGENT,
            source_id=SOURCE,
        )

        result = update_data_property(
            stored,
            companion,
            predicate="dlthings:title",
            value=value,
            topical_slot="title",
            owner_id=AGENT,
            source_id=SOURCE,
        )

        bridged = compact_enrichment_view(result.record, result.companion)
        self.assertEqual(helper_shape(bridged), helper_shape(direct))
        self.assertEqual(result.modified, direct_modified)
        return result

    def test_absent_equal_and_different_topical_values_match_upstream(self):
        absent = self.assert_string_parity(base_record(), "Source title")
        self.assertEqual(absent.record["title"], "Source title")
        self.assertEqual(absent.record["attributes"][0]["value"], "Source title")
        self.assertNotIn("range", absent.record["attributes"][0])

        equal = self.assert_string_parity(
            base_record(title="Source title"), "Source title"
        )
        self.assertTrue(equal.modified)

        different = self.assert_string_parity(
            base_record(title="Curated title"), "Source title"
        )
        self.assertEqual(different.record["title"], "Curated title")
        self.assertEqual(different.record["attributes"][0]["value"], "Source title")

    def test_same_owner_is_replaced_while_human_and_other_owner_survive(self):
        same_owner = {
            "predicate": "dlthings:title",
            "schema_type": "dlthings:AttributeSpecification",
            "value": "Old machine title",
            "annotations": machine_annotations(),
        }
        human = {
            "predicate": "dlthings:title",
            "schema_type": "dlthings:AttributeSpecification",
            "value": "Human assertion",
        }
        other_owner = {
            "predicate": "dlthings:title",
            "schema_type": "dlthings:AttributeSpecification",
            "value": "Other machine assertion",
            "annotations": machine_annotations(OTHER_AGENT),
        }
        baseline = base_record(
            title="Curated title",
            attributes=[same_owner, human, other_owner],
        )

        result = self.assert_string_parity(baseline, "New source title")

        self.assertEqual(
            [item["value"] for item in result.record["attributes"]],
            ["Human assertion", "Other machine assertion", "New source title"],
        )
        owners = {
            entry["pav:importedBy"]
            for entry in result.companion["assertions"]
        }
        self.assertEqual(owners, {AGENT, OTHER_AGENT})

    def test_multivalued_data_and_empty_update_match_upstream(self):
        first = self.assert_string_parity(base_record(), ["one", "two"])
        self.assertEqual(first.record["title"], ["one", "two"])
        self.assertEqual(
            [item["value"] for item in first.record["attributes"]],
            ["one", "two"],
        )
        self.assertTrue(
            all("range" not in item for item in first.record["attributes"])
        )

        working = compact_enrichment_view(first.record, first.companion)
        removed = self.assert_string_parity(working, [])
        self.assertNotIn("attributes", removed.record)
        self.assertEqual(removed.record["title"], ["one", "two"])

    @unittest.skipUnless(
        SCHEMA.is_file(), "pinned Things Schema fixture is unavailable"
    )
    def test_typed_value_is_native_topically_and_lexical_when_qualified(self):
        direct = base_record()
        direct_modified = upstream.update_data_property(
            direct,
            predicate="dlthings:byte_size",
            value=123,
            topical_slot="byte_size",
            owner_id=AGENT,
            source_id=SOURCE,
        )
        result = update_schema_data_property(
            base_record(),
            None,
            schema=self.schema,
            value=123,
            topical_slot="byte_size",
            owner_id=AGENT,
            source_id=SOURCE,
        )

        self.assertEqual(result.record["byte_size"], 123)
        self.assertEqual(
            result.record["attributes"],
            [
                {
                    "predicate": "dlthings:byte_size",
                    "range": "xsd:nonNegativeInteger",
                    "schema_type": "dlthings:AttributeSpecification",
                    "value": "123",
                }
            ],
        )
        bridged = compact_enrichment_view(result.record, result.companion)
        self.assertEqual(
            helper_shape(
                bridged,
                predicate="dlthings:byte_size",
                datatype="xsd:nonNegativeInteger",
            ),
            helper_shape(direct),
        )
        self.assertEqual(result.modified, direct_modified)

        rerun = update_schema_data_property(
            result.record,
            result.companion,
            schema=self.schema,
            value=123,
            topical_slot="byte_size",
            owner_id=AGENT,
            source_id=SOURCE,
        )
        self.assertFalse(rerun.modified)
        self.assertEqual(rerun.record, result.record)
        self.assertEqual(rerun.companion, result.companion)

    def test_non_string_values_require_a_locked_datatype_and_null_is_rejected(self):
        cases = (
            (123, None, "explicit locked datatype"),
            (True, None, "explicit locked datatype"),
            (1.5, None, "explicit locked datatype"),
            ([1, 2], None, "explicit locked datatype"),
            (None, None, "cannot be null"),
            ([1, None], "xsd:integer", "cannot be null"),
            ("123", "xsd:integer", "must not declare a datatype"),
            (["one", 2], "xsd:integer", "non-string JSON scalars"),
        )
        for value, datatype, message in cases:
            with self.subTest(value=value, datatype=datatype), self.assertRaisesRegex(
                ConfigurationError, message
            ):
                update_data_property(
                    base_record(),
                    None,
                    predicate="dlthings:byte_size",
                    value=value,
                    topical_slot="byte_size",
                    owner_id=AGENT,
                    source_id=SOURCE,
                    datatype=datatype,
                )

    @unittest.skipUnless(
        SCHEMA.is_file(), "pinned Things Schema fixture is unavailable"
    )
    def test_typed_wrapper_result_validates_and_round_trips_through_rdf(self):
        result = update_schema_data_property(
            {
                "pid": "xyzrins:files/one",
                "schema_type": "xyzri:XYZFile",
            },
            None,
            schema=self.schema,
            value=123,
            topical_slot="byte_size",
            owner_id=AGENT,
            source_id=SOURCE,
        )
        joined = join_annotations(result.record, result.companion)
        to_rdf, to_json = build_format_converters(SCHEMA)

        turtle = to_rdf.convert(joined, "XYZFile")
        round_trip = to_json.convert(turtle, "XYZFile")

        self.assertEqual(round_trip, joined)

    @unittest.skipUnless(
        SCHEMA.is_file(), "pinned Things Schema fixture is unavailable"
    )
    def test_class_range_statement_matches_upstream_without_schema_type(self):
        direct = base_record()
        direct_modified = upstream.update_data_property(
            direct,
            predicate="dcterms:type",
            value="bibo:AcademicArticle",
            collection_slot="characterized_by",
            value_key="object",
            topical_slot="kind",
            owner_id=AGENT,
            source_id=SOURCE,
        )
        result = update_schema_data_property(
            base_record(),
            None,
            schema=self.schema,
            value="bibo:AcademicArticle",
            topical_slot="kind",
            owner_id=AGENT,
            source_id=SOURCE,
        )

        self.assertNotIn("schema_type", result.record["characterized_by"][0])
        self.assertEqual(
            compact_enrichment_view(result.record, result.companion), direct
        )
        self.assertEqual(result.modified, direct_modified)

    @unittest.skipUnless(
        SCHEMA.is_file(), "pinned Things Schema fixture is unavailable"
    )
    def test_checked_slot_resolution_and_value_shape_mismatches(self):
        self.assertEqual(
            resolve_enrichment_slot(self.schema, "title"),
            EnrichmentSlotSemantics("dlthings:title", class_range=False),
        )
        self.assertEqual(
            resolve_enrichment_slot(self.schema, "byte_size"),
            EnrichmentSlotSemantics(
                "dlthings:byte_size",
                class_range=False,
                datatype="xsd:nonNegativeInteger",
            ),
        )
        self.assertEqual(
            resolve_enrichment_slot(self.schema, "kind"),
            EnrichmentSlotSemantics("dcterms:type", class_range=True),
        )
        cases = (
            ("byte_size", "123", "must not declare a datatype"),
            ("title", 123, "explicit locked datatype"),
            ("kind", 123, "explicit locked datatype"),
        )
        for slot, value, message in cases:
            with self.subTest(slot=slot, value=value), self.assertRaisesRegex(
                ConfigurationError, message
            ):
                update_schema_data_property(
                    base_record(),
                    None,
                    schema=self.schema,
                    topical_slot=slot,
                    value=value,
                    owner_id=AGENT,
                    source_id=SOURCE,
                )
        with self.assertRaisesRegex(ConfigurationError, "no range"):
            resolve_enrichment_slot(self.schema, "not_a_schema_slot")

    @unittest.skipUnless(
        SCHEMA.is_file(), "pinned Things Schema fixture is unavailable"
    )
    def test_empty_source_update_does_not_manufacture_a_topical_value(self):
        machine = {
            "predicate": "dlthings:title",
            "schema_type": "dlthings:AttributeSpecification",
            "value": "Old source title",
            "annotations": machine_annotations(),
        }
        for baseline in (
            base_record(attributes=[machine]),
            base_record(title="Curated title", attributes=[machine]),
        ):
            with self.subTest(topical="title" in baseline):
                stored, companion = split(baseline)
                direct = deepcopy(baseline)
                direct_modified = upstream.update_data_property(
                    direct,
                    predicate="dlthings:title",
                    value=[],
                    topical_slot=None,
                    owner_id=AGENT,
                    source_id=SOURCE,
                )

                result = update_schema_data_property(
                    stored,
                    companion,
                    schema=self.schema,
                    topical_slot="title",
                    value=[],
                    owner_id=AGENT,
                    source_id=SOURCE,
                    populate_topical=False,
                )

                self.assertEqual(
                    compact_enrichment_view(result.record, result.companion),
                    direct,
                )
                self.assertEqual(result.modified, direct_modified)
                self.assertNotIn("attributes", result.record)
                self.assertEqual(result.record.get("title"), baseline.get("title"))
                self.assertIsNone(result.companion)

        with self.assertRaisesRegex(ConfigurationError, "only for an empty"):
            update_schema_data_property(
                base_record(),
                None,
                schema=self.schema,
                topical_slot="title",
                value="Source title",
                owner_id=AGENT,
                source_id=SOURCE,
                populate_topical=False,
            )

    def test_missing_topical_copies_equivalent_human_assertion_without_pav(self):
        human = {
            "predicate": "dlthings:title",
            "schema_type": "dlthings:AttributeSpecification",
            "value": "Human assertion",
        }
        baseline = base_record(attributes=[human])

        result = self.assert_string_parity(baseline, "Human assertion")

        self.assertEqual(result.record["title"], "Human assertion")
        self.assertEqual(result.record["attributes"], [human])
        self.assertIsNone(result.companion)


class ObjectPropertyParityTests(unittest.TestCase):
    def test_multivalued_object_add_replace_and_empty_match_upstream(self):
        old = {
            "notation": "old",
            "schema_type": "dlthings:Identifier",
            "annotations": machine_annotations(),
        }
        human = {
            "notation": "human",
            "schema_type": "dlthings:Identifier",
        }
        baseline_working = base_record(identifiers=[old, human])
        stored, companion = split(baseline_working)
        desired = [{"notation": "new", "schema_type": "dlthings:Identifier"}]
        direct = deepcopy(baseline_working)
        direct_modified = upstream.update_multivalued_object_property(
            direct,
            slot="identifiers",
            values=deepcopy(desired),
            owner_id=AGENT,
            source_id=SOURCE,
        )

        result = update_multivalued_object_property(
            stored,
            companion,
            slot="identifiers",
            values=desired,
            owner_id=AGENT,
            source_id=SOURCE,
        )

        self.assertEqual(
            compact_enrichment_view(result.record, result.companion), direct
        )
        self.assertEqual(result.modified, direct_modified)
        self.assertEqual(
            [item["notation"] for item in result.record["identifiers"]],
            ["human", "new"],
        )

        direct_empty = deepcopy(direct)
        direct_empty_modified = upstream.update_multivalued_object_property(
            direct_empty,
            slot="identifiers",
            values=[],
            owner_id=AGENT,
            source_id=SOURCE,
        )
        empty = update_multivalued_object_property(
            result.record,
            result.companion,
            slot="identifiers",
            values=[],
            owner_id=AGENT,
            source_id=SOURCE,
        )
        self.assertEqual(
            compact_enrichment_view(empty.record, empty.companion), direct_empty
        )
        self.assertEqual(empty.modified, direct_empty_modified)
        self.assertEqual(empty.record["identifiers"], [human])

    def test_single_object_owner_behavior_matches_upstream(self):
        desired = {
            "object": "xyzrins:persons/one",
            "schema_type": "dlthings:Attribution",
        }
        direct = base_record()
        direct_modified = upstream.update_object_property(
            direct,
            slot="primary_attribution",
            value=deepcopy(desired),
            owner_id=AGENT,
            source_id=SOURCE,
        )
        result = update_object_property(
            base_record(),
            None,
            slot="primary_attribution",
            value=desired,
            owner_id=AGENT,
            source_id=SOURCE,
        )

        self.assertEqual(
            compact_enrichment_view(result.record, result.companion), direct
        )
        self.assertEqual(result.modified, direct_modified)

        joined = join_annotations(result.record, result.companion)
        self.assertEqual(
            joined["primary_attribution"]["annotations"]["pav:importedBy"][
                "annotation_value"
            ],
            AGENT,
        )


if __name__ == "__main__":
    unittest.main()
