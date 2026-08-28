from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from orinoco_lite.annotations import (
    annotation_semantic_view,
    annotation_companion,
    assertion_sha256,
    compact_enrichment_view,
    join_annotations,
    reconcile_annotation_companion,
    split_enrichment_view,
)
from orinoco_lite.canonical import canonical_yaml
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.schema_conversion import build_format_converters


AGENT = "xyzrins:source-adapters/example/v1"
SOURCE = "https://source.example/records/one"
SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "submodules/things-schemas/src/demo-research-information/unreleased.yaml"
)


def assertion(path: str, value: object, **changes: str) -> dict[str, str]:
    result = {
        "path": path,
        "assertion_sha256": assertion_sha256(value),
        "pav:importedBy": AGENT,
        "pav:importedFrom": SOURCE,
    }
    result.update(changes)
    return result


def record() -> dict[str, object]:
    return {
        "pid": "xyzrins:records/one",
        "schema_type": "xyzri:XYZPublication",
        "title": "A title",
        "identifiers": [
            {
                "notation": "doi:10.1/example",
                "schema_type": "dlthings:Identifier",
            }
        ],
    }


class AssertionFingerprintTests(unittest.TestCase):
    def test_hash_uses_unicode_sorted_compact_json_and_omits_annotations(self):
        value = {
            "z": ["é", {"z": 1, "a": 2}],
            "a": True,
            "annotations": {"ignored": "top"},
            "nested": {"annotations": {"ignored": "nested"}, "value": None},
        }
        changed = deepcopy(value)
        changed["annotations"] = {"different": "still ignored"}
        changed["nested"]["annotations"] = {"different": "still ignored"}

        self.assertEqual(assertion_sha256(value), assertion_sha256(changed))
        self.assertEqual(
            assertion_sha256(value),
            "sha256:d71bf20270adeb3f42c6323d808e81b3fe082bd736c9d2fcc001bb5db090aed2",
        )

    def test_non_json_values_fail_closed(self):
        with self.assertRaisesRegex(ConfigurationError, "deterministic JSON"):
            assertion_sha256({"bad": {1, 2}})


class CompanionTests(unittest.TestCase):
    def test_builder_sorts_entries_and_canonicalizer_sorts_mapping_keys(self):
        source = record()
        companion = annotation_companion(
            source["pid"],
            [
                assertion("/title", source["title"]),
                assertion("/identifiers", source["identifiers"][0]),
            ],
        )

        self.assertEqual(
            [item["path"] for item in companion["assertions"]],
            ["/identifiers", "/title"],
        )
        rendered = canonical_yaml(companion)
        self.assertTrue(rendered.startswith("assertions:\n"))
        self.assertIn("record: xyzrins:records/one\n", rendered)

    def test_builder_rejects_duplicate_selectors_and_private_fields(self):
        item = assertion("/title", "A title")
        with self.assertRaisesRegex(ConfigurationError, "repeats"):
            annotation_companion("xyzrins:records/one", [item, item])
        with self.assertRaisesRegex(ConfigurationError, "unexpected fields"):
            annotation_companion(
                "xyzrins:records/one",
                [{**item, "private_id": "not allowed"}],
            )
        with self.assertRaisesRegex(ConfigurationError, "non-empty single line"):
            annotation_companion(
                "xyzrins:records/one",
                [{**item, "pav:importedBy": "   "}],
            )


class JoinTests(unittest.TestCase):
    def test_compact_and_expanded_human_annotations_have_one_semantic_view(self):
        compact = record()
        compact["identifiers"][0]["annotations"] = {"ex:reviewed": "yes"}
        expanded = deepcopy(compact)
        expanded["identifiers"][0]["annotations"] = {
            "ex:reviewed": {
                "annotation_tag": "ex:reviewed",
                "annotation_value": "yes",
            }
        }

        self.assertEqual(
            annotation_semantic_view(compact),
            annotation_semantic_view(expanded),
        )

    def test_stored_object_and_qualified_assertions_join_as_expanded_pav(self):
        stored = record()
        stored["attributes"] = [
            {
                "predicate": "dlthings:title",
                "schema_type": "dlthings:AttributeSpecification",
                "value": "A title",
            }
        ]
        stored["characterized_by"] = [
            {"object": "bibo:AcademicArticle", "predicate": "dcterms:type"}
        ]
        original = deepcopy(stored)
        companion = annotation_companion(
            stored["pid"],
            [
                assertion("/attributes", stored["attributes"][0]),
                assertion("/characterized_by", stored["characterized_by"][0]),
                assertion("/identifiers", stored["identifiers"][0]),
            ],
        )

        joined = join_annotations(stored, companion)

        self.assertEqual(stored, original)
        for selected in (
            joined["attributes"][0],
            joined["characterized_by"][0],
            joined["identifiers"][0],
        ):
            self.assertEqual(
                selected["annotations"]["pav:importedBy"]["annotation_value"],
                AGENT,
            )

    def test_scalar_selectors_are_rejected_instead_of_synthesizing_objects(self):
        stored = record()
        companion = annotation_companion(
            stored["pid"], [assertion("/title", stored["title"])]
        )

        with self.assertRaisesRegex(ConfigurationError, "scalar selectors"):
            join_annotations(stored, companion)

    def test_typed_attribute_is_selected_without_changing_topical_type(self):
        stored = record()
        stored["byte_size"] = 123
        stored["attributes"] = [
            {
                "predicate": "dlthings:byte_size",
                "range": "xsd:nonNegativeInteger",
                "schema_type": "dlthings:AttributeSpecification",
                "value": "123",
            }
        ]
        companion = annotation_companion(
            stored["pid"], [assertion("/attributes", stored["attributes"][0])]
        )

        joined = join_annotations(stored, companion)

        self.assertEqual(joined["byte_size"], 123)
        self.assertEqual(joined["attributes"][0]["value"], "123")

    def test_existing_human_annotations_expand_and_survive(self):
        stored = record()
        stored["identifiers"][0]["annotations"] = {"ex:reviewed": "yes"}
        item = stored["identifiers"][0]
        companion = annotation_companion(
            stored["pid"], [assertion("/identifiers", item)]
        )

        joined = join_annotations(stored, companion)

        self.assertEqual(
            joined["identifiers"][0]["annotations"]["ex:reviewed"],
            {"annotation_tag": "ex:reviewed", "annotation_value": "yes"},
        )

    def test_rfc6901_escaping_is_resolved_for_mapping_assertions(self):
        stored = record()
        stored["literal/items"] = {"schema_type": "dlthings:Identifier"}
        companion = annotation_companion(
            stored["pid"],
            [assertion("/literal~1items", stored["literal/items"])],
        )

        joined = join_annotations(stored, companion)

        self.assertEqual(
            joined["literal/items"]["annotations"]["pav:importedFrom"][
                "annotation_value"
            ],
            SOURCE,
        )

    def test_array_index_pointer_cannot_bypass_collection_uniqueness(self):
        stored = record()
        stored["identifiers"].append(deepcopy(stored["identifiers"][0]))
        companion = annotation_companion(
            stored["pid"],
            [assertion("/identifiers/0", stored["identifiers"][0])],
        )

        with self.assertRaisesRegex(ConfigurationError, "identify a collection"):
            join_annotations(stored, companion)

    def test_missing_mismatched_and_ambiguous_selectors_fail(self):
        stored = record()
        duplicate = deepcopy(stored["identifiers"][0])
        stored["identifiers"].append(duplicate)
        cases = (
            (assertion("/missing", {"value": "missing"}), "zero assertions"),
            (assertion("/identifiers", {"value": "different"}), "zero assertions"),
            (assertion("/identifiers", duplicate), "2 assertions"),
        )
        for item, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                ConfigurationError, message
            ):
                join_annotations(
                    stored, annotation_companion(stored["pid"], [item])
                )

    def test_reconciliation_drops_missing_but_rejects_ambiguous_selector(self):
        stored = record()
        companion = annotation_companion(
            stored["pid"],
            [assertion("/identifiers", stored["identifiers"][0])],
        )
        changed = deepcopy(stored)
        changed["identifiers"] = []
        self.assertEqual(
            reconcile_annotation_companion(changed, companion)["assertions"], []
        )

        duplicated = deepcopy(stored)
        duplicated["identifiers"].append(deepcopy(stored["identifiers"][0]))
        with self.assertRaisesRegex(ConfigurationError, "2 assertions"):
            reconcile_annotation_companion(duplicated, companion)

    def test_companion_identity_order_and_shape_fail_closed(self):
        stored = record()
        first = assertion("/identifiers", stored["identifiers"][0])
        stored["other"] = {"schema_type": "dlthings:Identifier"}
        second = assertion("/other", stored["other"])
        cases = (
            ({"record": "wrong", "assertions": []}, "does not match"),
            (
                {"record": stored["pid"], "assertions": [second, first]},
                "must be ordered",
            ),
            (
                {"record": stored["pid"], "assertions": [], "extra": True},
                "unexpected top-level",
            ),
        )
        for companion, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                ConfigurationError, message
            ):
                join_annotations(stored, companion)

    def test_compact_split_is_an_inverse_for_supported_machine_pav(self):
        stored = record()
        stored["identifiers"][0]["annotations"] = {"ex:reviewed": "yes"}
        companion = annotation_companion(
            stored["pid"],
            [assertion("/identifiers", stored["identifiers"][0])],
        )

        working = compact_enrichment_view(stored, companion)
        split_record, split_companion = split_enrichment_view(working)

        self.assertEqual(split_record, stored)
        self.assertEqual(split_companion, companion)
        self.assertEqual(
            working["identifiers"][0]["annotations"]["pav:importedBy"], AGENT
        )

    def test_compact_split_accepts_uri_aliases_and_normalizes_the_companion(self):
        working = record()
        working["identifiers"][0]["annotations"] = {
            "http://purl.org/pav/importedBy": AGENT,
            "http://purl.org/pav/importedFrom": SOURCE,
            "ex:reviewed": "yes",
        }

        stored, companion = split_enrichment_view(working)
        reconstructed = compact_enrichment_view(stored, companion)

        self.assertEqual(
            stored["identifiers"][0]["annotations"], {"ex:reviewed": "yes"}
        )
        self.assertEqual(companion["assertions"][0]["pav:importedBy"], AGENT)
        self.assertEqual(companion["assertions"][0]["pav:importedFrom"], SOURCE)
        self.assertEqual(
            reconstructed["identifiers"][0]["annotations"],
            {
                "ex:reviewed": "yes",
                "pav:importedBy": AGENT,
                "pav:importedFrom": SOURCE,
            },
        )

    def test_split_accepts_expanded_machine_annotations(self):
        working = record()
        working["identifiers"][0]["annotations"] = {
            "pav:importedBy": {
                "annotation_tag": "pav:importedBy",
                "annotation_value": AGENT,
            },
            "pav:importedFrom": {
                "annotation_tag": "http://purl.org/pav/importedFrom",
                "annotation_value": SOURCE,
            },
        }

        stored, companion = split_enrichment_view(working)
        reconstructed = compact_enrichment_view(stored, companion)

        self.assertNotIn("annotations", stored["identifiers"][0])
        self.assertEqual(
            reconstructed["identifiers"][0]["annotations"],
            {"pav:importedBy": AGENT, "pav:importedFrom": SOURCE},
        )

    def test_split_rejects_malformed_expanded_machine_annotation(self):
        working = record()
        working["identifiers"][0]["annotations"] = {
            "pav:importedBy": {
                "annotation_tag": "ex:not-imported-by",
                "annotation_value": AGENT,
            },
            "pav:importedFrom": SOURCE,
        }

        with self.assertRaisesRegex(ConfigurationError, "tag is malformed"):
            split_enrichment_view(working)

    def test_compact_split_rejects_duplicate_curie_and_uri_aliases(self):
        working = record()
        working["identifiers"][0]["annotations"] = {
            "pav:importedBy": AGENT,
            "http://purl.org/pav/importedBy": AGENT,
            "pav:importedFrom": SOURCE,
        }

        with self.assertRaisesRegex(ConfigurationError, "both CURIE and URI"):
            split_enrichment_view(working)

    def test_existing_machine_annotation_is_never_overwritten(self):
        stored = record()
        stored["identifiers"][0]["annotations"] = {
            "pav:importedBy": "xyzrins:source-adapters/other/v1"
        }
        companion = annotation_companion(
            stored["pid"],
            [assertion("/identifiers", stored["identifiers"][0])],
        )

        with self.assertRaisesRegex(
            ConfigurationError, "configured annotation companion tree"
        ):
            join_annotations(stored, companion)

    def test_inline_machine_pav_curie_or_uri_is_rejected(self):
        for tag in (
            "pav:importedBy",
            "pav:importedFrom",
            "http://purl.org/pav/importedBy",
            "http://purl.org/pav/importedFrom",
        ):
            with self.subTest(tag=tag):
                stored = record()
                stored["identifiers"][0]["annotations"] = {tag: AGENT}
                with self.assertRaisesRegex(
                    ConfigurationError, "configured annotation companion tree"
                ):
                    join_annotations(stored, None)


@unittest.skipUnless(SCHEMA.is_file(), "pinned Things Schema fixture is unavailable")
class RdfRoundTripTests(unittest.TestCase):
    def test_object_and_qualified_data_pav_survive_locked_rdf_round_trip(self):
        stored = record()
        stored["attributes"] = [
            {
                "predicate": "dlthings:title",
                "schema_type": "dlthings:AttributeSpecification",
                "value": "A title",
            }
        ]
        companion = annotation_companion(
            stored["pid"],
            [
                assertion("/attributes", stored["attributes"][0]),
                assertion("/identifiers", stored["identifiers"][0]),
            ],
        )
        joined = join_annotations(stored, companion)
        to_rdf, to_json = build_format_converters(SCHEMA)

        turtle = to_rdf.convert(joined, "XYZPublication")
        round_trip = to_json.convert(turtle, "XYZPublication")

        self.assertEqual(round_trip["title"], stored["title"])
        self.assertEqual(
            round_trip["identifiers"][0]["annotations"],
            joined["identifiers"][0]["annotations"],
        )
        title_attribute = next(
            item
            for item in round_trip["attributes"]
            if item.get("predicate") == "dlthings:title"
        )
        self.assertEqual(title_attribute, joined["attributes"][0])

    def test_class_range_statement_survives_locked_rdf_round_trip(self):
        stored = record()
        stored["kind"] = "bibo:AcademicArticle"
        stored["characterized_by"] = [
            {"object": stored["kind"], "predicate": "dcterms:type"}
        ]
        companion = annotation_companion(
            stored["pid"],
            [assertion("/characterized_by", stored["characterized_by"][0])],
        )
        joined = join_annotations(stored, companion)
        to_rdf, to_json = build_format_converters(SCHEMA)

        turtle = to_rdf.convert(joined, "XYZPublication")
        round_trip = to_json.convert(turtle, "XYZPublication")

        self.assertEqual(round_trip["kind"], stored["kind"])
        self.assertEqual(round_trip["characterized_by"], joined["characterized_by"])

    def test_typed_data_pav_survives_locked_rdf_round_trip(self):
        stored = {
            "pid": "xyzrins:files/one",
            "schema_type": "xyzri:XYZFile",
            "byte_size": 123,
            "attributes": [
                {
                    "predicate": "dlthings:byte_size",
                    "range": "xsd:nonNegativeInteger",
                    "schema_type": "dlthings:AttributeSpecification",
                    "value": "123",
                }
            ],
        }
        companion = annotation_companion(
            stored["pid"],
            [assertion("/attributes", stored["attributes"][0])],
        )
        joined = join_annotations(stored, companion)
        to_rdf, to_json = build_format_converters(SCHEMA)

        turtle = to_rdf.convert(joined, "XYZFile")
        round_trip = to_json.convert(turtle, "XYZFile")

        self.assertEqual(round_trip, joined)


if __name__ == "__main__":
    unittest.main()
