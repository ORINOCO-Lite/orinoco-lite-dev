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


if __name__ == "__main__":
    unittest.main()
