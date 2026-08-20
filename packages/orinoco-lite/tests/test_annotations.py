from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest

from linkml_runtime import SchemaView

from orinoco_lite.annotations import (
    SlotSemantics,
    annotation_companion,
    assertion_sha256,
    join_annotations,
    reconcile_annotation_companion,
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
ENRICHMENT_TOOLS = (
    Path(__file__).resolve().parents[3]
    / "submodules/things-enrichment-tools/things_enrichment_tools/__init__.py"
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


def predicate(slot: str) -> SlotSemantics:
    return SlotSemantics(
        predicate={
            "display_label": "skos:prefLabel",
            "literal/items": "ex:escaped",
            "title": "dlthings:title",
        }[slot],
        class_range=False,
    )


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
    def test_object_and_scalar_assertions_join_as_expanded_pav(self):
        stored = record()
        original = deepcopy(stored)
        companion = annotation_companion(
            stored["pid"],
            [
                assertion("/identifiers", stored["identifiers"][0]),
                assertion("/title", stored["title"]),
            ],
        )

        joined = join_annotations(stored, companion, predicate)

        self.assertEqual(stored, original)
        machine = {
            "pav:importedBy": {
                "annotation_tag": "pav:importedBy",
                "annotation_value": AGENT,
            },
            "pav:importedFrom": {
                "annotation_tag": "pav:importedFrom",
                "annotation_value": SOURCE,
            },
        }
        self.assertEqual(joined["identifiers"][0]["annotations"], machine)
        self.assertEqual(
            joined["attributes"],
            [
                {
                    "annotations": machine,
                    "predicate": "dlthings:title",
                    "schema_type": "dlthings:AttributeSpecification",
                    "value": "A title",
                }
            ],
        )
        self.assertEqual(joined["title"], "A title")

    def test_class_range_assertion_joins_as_an_annotated_statement(self):
        stored = record()
        stored["kind"] = "xyzrins:publication-types/article"
        companion = annotation_companion(
            stored["pid"], [assertion("/kind", stored["kind"])]
        )

        joined = join_annotations(
            stored,
            companion,
            lambda slot: SlotSemantics("dcterms:type", class_range=True),
        )

        self.assertEqual(joined["kind"], stored["kind"])
        statement = joined["characterized_by"][0]
        self.assertNotIn("schema_type", statement)
        self.assertEqual(statement["predicate"], "dcterms:type")
        self.assertEqual(statement["object"], stored["kind"])
        self.assertEqual(
            statement["annotations"]["pav:importedBy"]["annotation_value"],
            AGENT,
        )

    def test_typed_data_keeps_topical_value_and_uses_schema_range(self):
        stored = record()
        stored["byte_size"] = 123
        companion = annotation_companion(
            stored["pid"], [assertion("/byte_size", stored["byte_size"])]
        )

        joined = join_annotations(
            stored,
            companion,
            lambda slot: SlotSemantics(
                "dcat:byteSize",
                class_range=False,
                datatype="xsd:nonNegativeInteger",
            ),
        )

        self.assertEqual(joined["byte_size"], 123)
        self.assertEqual(joined["attributes"][0]["value"], "123")
        self.assertEqual(
            joined["attributes"][0]["range"], "xsd:nonNegativeInteger"
        )

    def test_non_string_data_without_a_schema_datatype_fails_closed(self):
        stored = record()
        stored["byte_size"] = 123
        companion = annotation_companion(
            stored["pid"], [assertion("/byte_size", stored["byte_size"])]
        )

        with self.assertRaisesRegex(ConfigurationError, "no CURIE datatype"):
            join_annotations(
                stored,
                companion,
                lambda slot: SlotSemantics("dcat:byteSize", class_range=False),
            )

    def test_existing_human_annotations_expand_and_survive(self):
        stored = record()
        stored["identifiers"][0]["annotations"] = {"ex:reviewed": "yes"}
        item = stored["identifiers"][0]
        companion = annotation_companion(
            stored["pid"], [assertion("/identifiers", item)]
        )

        joined = join_annotations(stored, companion, predicate)

        self.assertEqual(
            joined["identifiers"][0]["annotations"]["ex:reviewed"],
            {"annotation_tag": "ex:reviewed", "annotation_value": "yes"},
        )

    def test_rfc6901_escaping_is_resolved(self):
        stored = record()
        stored["literal/items"] = "escaped"
        companion = annotation_companion(
            stored["pid"], [assertion("/literal~1items", "escaped")]
        )

        joined = join_annotations(stored, companion, predicate)

        self.assertEqual(joined["attributes"][0]["predicate"], "ex:escaped")

    def test_array_index_pointer_cannot_bypass_collection_uniqueness(self):
        stored = record()
        stored["identifiers"].append(deepcopy(stored["identifiers"][0]))
        companion = annotation_companion(
            stored["pid"],
            [assertion("/identifiers/0", stored["identifiers"][0])],
        )

        with self.assertRaisesRegex(ConfigurationError, "identify a collection"):
            join_annotations(stored, companion, predicate)

    def test_missing_mismatched_and_ambiguous_selectors_fail(self):
        stored = record()
        duplicate = deepcopy(stored["identifiers"][0])
        stored["identifiers"].append(duplicate)
        cases = (
            (
                annotation_companion(
                    stored["pid"], [assertion("/missing", "value")]
                ),
                "zero assertions",
            ),
            (
                annotation_companion(
                    stored["pid"], [assertion("/title", "different")]
                ),
                "zero assertions",
            ),
            (
                annotation_companion(
                    stored["pid"], [assertion("/identifiers", duplicate)]
                ),
                "2 assertions",
            ),
        )
        for companion, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ConfigurationError, message):
                    join_annotations(stored, companion, predicate)

    def test_reconciliation_drops_missing_but_rejects_ambiguous_selector(self):
        stored = record()
        companion = annotation_companion(
            stored["pid"],
            [assertion("/identifiers", stored["identifiers"][0])],
        )
        changed = deepcopy(stored)
        changed["identifiers"] = []
        self.assertEqual(
            reconcile_annotation_companion(changed, companion)["assertions"],
            [],
        )

        duplicated = deepcopy(stored)
        duplicated["identifiers"].append(deepcopy(stored["identifiers"][0]))
        with self.assertRaisesRegex(ConfigurationError, "2 assertions"):
            reconcile_annotation_companion(duplicated, companion)

    def test_companion_identity_order_and_shape_fail_closed(self):
        stored = record()
        first = assertion("/title", stored["title"])
        second = assertion("/identifiers", stored["identifiers"][0])
        cases = (
            ({"record": "wrong", "assertions": []}, "does not match"),
            (
                {"record": stored["pid"], "assertions": [first, second]},
                "must be ordered",
            ),
            (
                {"record": stored["pid"], "assertions": [], "extra": True},
                "unexpected top-level",
            ),
        )
        for companion, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ConfigurationError, message):
                    join_annotations(stored, companion, predicate)

    def test_existing_machine_annotation_is_never_overwritten(self):
        stored = record()
        stored["identifiers"][0]["annotations"] = {
            "pav:importedBy": "xyzrins:source-adapters/other/v1"
        }
        companion = annotation_companion(
            stored["pid"],
            [assertion("/identifiers", stored["identifiers"][0])],
        )

        with self.assertRaisesRegex(ConfigurationError, "overlays/annotations"):
            join_annotations(stored, companion, predicate)

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
                    ConfigurationError, "metadata/overlays/annotations"
                ):
                    join_annotations(stored, None, predicate)


@unittest.skipUnless(SCHEMA.is_file(), "pinned Things Schema fixture is unavailable")
class RdfRoundTripTests(unittest.TestCase):
    def test_object_and_scalar_pav_survive_locked_rdf_round_trip(self):
        stored = record()
        companion = annotation_companion(
            stored["pid"],
            [
                assertion("/identifiers", stored["identifiers"][0]),
                assertion("/title", stored["title"]),
            ],
        )
        schema_view = SchemaView(str(SCHEMA))
        joined = join_annotations(
            stored,
            companion,
            lambda slot: SlotSemantics(
                str(schema_view.get_uri(slot, expand=False)),
                class_range=False,
            ),
        )
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
        companion = annotation_companion(
            stored["pid"], [assertion("/kind", stored["kind"])]
        )
        schema_view = SchemaView(str(SCHEMA))
        joined = join_annotations(
            stored,
            companion,
            lambda slot: SlotSemantics(
                str(schema_view.get_uri(slot, expand=False)),
                class_range=True,
            ),
        )
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
        }
        companion = annotation_companion(
            stored["pid"], [assertion("/byte_size", stored["byte_size"])]
        )
        schema_view = SchemaView(str(SCHEMA))
        slot = schema_view.get_slot("byte_size")
        datatype = schema_view.get_type(slot.range)
        joined = join_annotations(
            stored,
            companion,
            lambda name: SlotSemantics(
                str(schema_view.get_uri(name, expand=False)),
                class_range=False,
                datatype=str(datatype.uri),
            ),
        )
        to_rdf, to_json = build_format_converters(SCHEMA)

        turtle = to_rdf.convert(joined, "XYZFile")
        round_trip = to_json.convert(turtle, "XYZFile")

        self.assertEqual(round_trip, joined)


@unittest.skipUnless(
    SCHEMA.is_file() and ENRICHMENT_TOOLS.is_file(),
    "pinned enrichment-tools parity fixtures are unavailable",
)
class UpstreamParityTests(unittest.TestCase):
    @staticmethod
    def _upstream():
        return SimpleNamespace(**runpy.run_path(str(ENRICHMENT_TOOLS)))

    @staticmethod
    def _rdf_graph(record_value):
        from rdflib import Graph
        from rdflib.compare import to_isomorphic

        to_rdf, _ = build_format_converters(SCHEMA)
        class_name = record_value["schema_type"].rsplit(":", 1)[-1]
        turtle = to_rdf.convert(record_value, class_name)
        return to_isomorphic(Graph().parse(data=turtle, format="turtle"))

    def test_join_matches_pinned_object_scalar_and_statement_rdf(self):
        upstream = self._upstream()
        schema_view = SchemaView(str(SCHEMA))

        cases = []

        identifier = {
            "notation": "doi:10.1/example",
            "schema_type": "dlthings:Identifier",
        }
        inline_object = {
            "pid": "xyzrins:records/object",
            "schema_type": "xyzri:XYZPublication",
        }
        self.assertTrue(
            upstream.update_multivalued_object_property(
                inline_object,
                slot="identifiers",
                values=[deepcopy(identifier)],
                owner_id=AGENT,
                source_id=SOURCE,
            )
        )
        stored_object = {
            "pid": inline_object["pid"],
            "schema_type": inline_object["schema_type"],
            "identifiers": [identifier],
        }
        cases.append(
            (
                inline_object,
                stored_object,
                annotation_companion(
                    stored_object["pid"],
                    [assertion("/identifiers", identifier)],
                ),
            )
        )

        inline_scalar = {
            "pid": "xyzrins:records/scalar",
            "schema_type": "xyzri:XYZPublication",
        }
        self.assertTrue(
            upstream.update_data_property(
                inline_scalar,
                predicate="dlthings:title",
                value="A title",
                topical_slot="title",
                owner_id=AGENT,
                source_id=SOURCE,
            )
        )
        stored_scalar = {
            "pid": inline_scalar["pid"],
            "schema_type": inline_scalar["schema_type"],
            "title": "A title",
        }
        cases.append(
            (
                inline_scalar,
                stored_scalar,
                annotation_companion(
                    stored_scalar["pid"],
                    [assertion("/title", stored_scalar["title"])],
                ),
            )
        )

        inline_statement = {
            "pid": "xyzrins:records/statement",
            "schema_type": "xyzri:XYZPublication",
        }
        self.assertTrue(
            upstream.update_data_property(
                inline_statement,
                predicate="dcterms:type",
                value="bibo:AcademicArticle",
                collection_slot="characterized_by",
                value_key="object",
                topical_slot="kind",
                owner_id=AGENT,
                source_id=SOURCE,
            )
        )
        stored_statement = {
            "pid": inline_statement["pid"],
            "schema_type": inline_statement["schema_type"],
            "kind": "bibo:AcademicArticle",
        }
        cases.append(
            (
                inline_statement,
                stored_statement,
                annotation_companion(
                    stored_statement["pid"],
                    [assertion("/kind", stored_statement["kind"])],
                ),
            )
        )

        for inline, stored, companion in cases:
            with self.subTest(pid=stored["pid"]):
                def semantics(slot):
                    definition = schema_view.get_slot(slot)
                    slot_range = definition.range
                    datatype = schema_view.get_type(slot_range)
                    return SlotSemantics(
                        str(schema_view.get_uri(slot, expand=False)),
                        class_range=schema_view.get_class(slot_range) is not None,
                        datatype=(str(datatype.uri) if datatype is not None else None),
                    )

                joined = join_annotations(stored, companion, semantics)
                self.assertEqual(self._rdf_graph(joined), self._rdf_graph(inline))


if __name__ == "__main__":
    unittest.main()
