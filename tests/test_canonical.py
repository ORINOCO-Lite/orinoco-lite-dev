from __future__ import annotations

from copy import deepcopy
import unittest

from dump_things_service.utils import json2yaml, order_dict
import yaml

from orinoco_lite.canonical import (
    canonical_mapping,
    canonical_yaml,
    canonical_yaml_bytes,
    canonicalize_yaml_text,
)


class CanonicalMappingTests(unittest.TestCase):
    def fixture(self) -> dict[str, object]:
        return {
            "z-slot": {"z": 1, "a": "last mapping sorts first"},
            "a-slot": [
                {"z": 2, "a": "first list item"},
                {"b": True, "a": None},
                "éclair",
            ],
            "middle": 1.25,
        }

    def test_recursively_matches_pinned_dump_things_order(self):
        source = self.fixture()
        original = deepcopy(source)

        actual = canonical_mapping(source)

        self.assertEqual(actual, order_dict(source))
        self.assertEqual(source, original)
        self.assertEqual(list(actual), ["a-slot", "middle", "z-slot"])
        self.assertEqual(list(actual["a-slot"][0]), ["a", "z"])
        self.assertEqual(
            [item["a"] for item in actual["a-slot"][:2]],
            ["first list item", None],
        )

    def test_requires_a_mapping(self):
        with self.assertRaisesRegex(TypeError, "must be a mapping"):
            canonical_mapping([{"a": 1}])  # type: ignore[arg-type]


class CanonicalYamlTests(unittest.TestCase):
    def fixture(self) -> dict[str, object]:
        return CanonicalMappingTests().fixture()

    def test_serialization_matches_pinned_dump_things_byte_for_byte(self):
        source = self.fixture()
        expected = json2yaml(order_dict(source))

        self.assertEqual(canonical_yaml(source), expected)
        self.assertEqual(canonical_yaml_bytes(source), expected.encode("utf-8"))
        self.assertIn("éclair", expected)
        self.assertTrue(expected.endswith("\n"))

    def test_serialization_is_idempotent_and_preserves_list_order(self):
        first = canonical_yaml(self.fixture())
        second = canonicalize_yaml_text(first)
        loaded = yaml.safe_load(second)

        self.assertEqual(second, first)
        self.assertEqual(
            [item["a"] for item in loaded["a-slot"][:2]],
            ["first list item", None],
        )

    def test_text_normalization_rejects_non_mapping_yaml(self):
        with self.assertRaisesRegex(TypeError, "must contain a mapping"):
            canonicalize_yaml_text("- one\n- two\n")


if __name__ == "__main__":
    unittest.main()
