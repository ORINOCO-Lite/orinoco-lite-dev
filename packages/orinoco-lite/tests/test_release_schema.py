from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from linkml_runtime import SchemaView

from orinoco_lite.release_schema import localize_schema


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SOURCE = PACKAGE_ROOT / "submodules/things-schemas/src"


@unittest.skipUnless(SCHEMA_SOURCE.is_dir(), "pinned schema fixture is unavailable")
class LocalizedSchemaTests(unittest.TestCase):
    def test_source_import_closure_loads_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "schema"
            report = localize_schema(
                SCHEMA_SOURCE,
                SCHEMA_SOURCE / "demo-research-information/unreleased.yaml",
                destination,
            )
            self.assertEqual(report["sources"], 12)
            entry = destination / report["entrypoint"]
            with patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("schema attempted network access"),
            ):
                view = SchemaView(str(entry))
                self.assertIn("XYZPerson", view.all_classes())


if __name__ == "__main__":
    unittest.main()
