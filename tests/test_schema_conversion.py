from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from rdflib import Graph, Literal, URIRef

from orinoco_lite.schema_conversion import (
    PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT,
    build_format_converters,
)


class SchemaConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_limit = sys.getrecursionlimit()
        self.schema = Path("/tmp/orinoco-schema-conversion-test.yaml")

    def tearDown(self) -> None:
        sys.setrecursionlimit(self.previous_limit)

    def test_pair_uses_fixed_limit_and_restores_lower_caller_limit(self) -> None:
        observed: list[int] = []

        class Converter:
            def __init__(self, *_args):
                observed.append(sys.getrecursionlimit())

        sys.setrecursionlimit(1000)
        with patch("dump_things_service.converter.FormatConverter", Converter):
            converters = build_format_converters(self.schema)

        self.assertEqual(len(converters), 2)
        self.assertEqual(
            observed,
            [
                PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT,
                PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT,
            ],
        )
        self.assertEqual(sys.getrecursionlimit(), 1000)

    def test_pair_restores_limit_after_constructor_failure(self) -> None:
        observed: list[int] = []

        class FailingConverter:
            def __init__(self, *_args):
                observed.append(sys.getrecursionlimit())
                if len(observed) == 2:
                    raise RuntimeError("injected converter failure")

        sys.setrecursionlimit(1000)
        with patch(
            "dump_things_service.converter.FormatConverter", FailingConverter
        ):
            with self.assertRaisesRegex(RuntimeError, "injected converter failure"):
                build_format_converters(self.schema)

        self.assertEqual(
            observed,
            [
                PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT,
                PYDANTIC_MODEL_REBUILD_RECURSION_LIMIT,
            ],
        )
        self.assertEqual(sys.getrecursionlimit(), 1000)

    def test_pair_preserves_caller_limit_above_fixed_limit(self) -> None:
        observed: list[int] = []

        class Converter:
            def __init__(self, *_args):
                observed.append(sys.getrecursionlimit())

        sys.setrecursionlimit(2500)
        with patch("dump_things_service.converter.FormatConverter", Converter):
            build_format_converters(self.schema)

        self.assertEqual(observed, [2500, 2500])
        self.assertEqual(sys.getrecursionlimit(), 2500)

    def test_reader_adapts_only_the_exact_source_marker(self) -> None:
        class Converter:
            def __init__(self, *_args):
                pass

            def convert(self, data, _class_name):
                return data

        source = '''
@prefix t: <https://concepts.datalad.org/s/things/v2/> .
@prefix ex: <https://example.invalid/> .
ex:marker t:at_time "-"^^t:w3ctr-datetime .
ex:date t:at_time "2024-05-01"^^t:w3ctr-datetime .
ex:invalid t:at_time "not-a-date"^^t:w3ctr-datetime .
ex:predicate ex:other "-"^^t:w3ctr-datetime .
ex:datatype t:at_time "-"^^ex:other .
'''
        before = Graph().parse(data=source, format="turtle")
        with patch("dump_things_service.converter.FormatConverter", Converter):
            _, reader = build_format_converters(self.schema)
        parsed = Graph().parse(data=reader.convert(source, "Thing"), format="turtle")
        subject = URIRef("https://example.invalid/marker")
        predicate = URIRef("https://concepts.datalad.org/s/things/v2/at_time")
        original_value = next(before.objects(subject, predicate))
        expected = set(before) - {(subject, predicate, original_value)}
        expected.add((subject, predicate, Literal("-")))
        self.assertEqual(set(parsed), expected)
        # No marker means no rewrite, including for other invalid datetimes.
        unchanged = source.replace('ex:marker t:at_time "-"', 'ex:marker t:at_time "2024"')
        self.assertEqual(reader.convert(unchanged, "Thing"), unchanged)


if __name__ == "__main__":
    unittest.main()
