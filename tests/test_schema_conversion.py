from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

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


def test_selected_conversion_uses_upstream_date_readback():
    from orinoco_lite.resources import resolve_resources
    schema = resolve_resources().root / "schema/demo-research-information/unreleased.yaml"
    writer, reader = build_format_converters(schema)
    record = {"pid": "xyzrins:publications/marker-test", "schema_type": "xyzri:XYZPublication",
              "generated_by": [{"object": "xyzrins:projects/example", "at_time": "-",
                                "schema_type": "dlthings:Generation"}]}
    returned = reader.convert(writer.convert(record, "XYZPublication"), "XYZPublication")
    assert "at_time" not in returned["generated_by"][0]
    assert record["generated_by"][0]["at_time"] == "-"


if __name__ == "__main__":
    unittest.main()


def test_placeholder_date_warning_is_concise_and_scoped(caplog, monkeypatch):
    import logging

    from dump_things_service.converter import TypeValidator
    from rdflib import Literal, URIRef
    from rdflib.term import _toPythonMapping

    from orinoco_lite.schema_conversion import concise_date_warning

    datatype = URIRef("https://concepts.datalad.org/s/things/v2/w3ctr-datetime")
    validator = TypeValidator(str(datatype), r"^\d{4}$")
    monkeypatch.setitem(_toPythonMapping, datatype, validator.validate)
    with caplog.at_level(logging.WARNING, logger="rdflib.term"):
        with concise_date_warning():
            assert str(Literal("-", datatype=datatype)) == "-"
            Literal("-", datatype=datatype)
        assert len(caplog.records) == 1
        assert caplog.messages == [
            "Known issue: placeholder date '-' in metadata; no action needed for now."
        ]
        assert "Traceback" not in caplog.text
        caplog.clear()
        with concise_date_warning():
            Literal("invalid", datatype=datatype)
        assert "Traceback" in caplog.text
        caplog.clear()
        Literal("-", datatype=datatype)
        assert "Traceback" in caplog.text


def test_date_warning_scope_preserves_failures():
    import pytest

    from orinoco_lite.schema_conversion import concise_date_warning

    with pytest.raises(RuntimeError, match="conversion failed"):
        with concise_date_warning():
            raise RuntimeError("conversion failed")
