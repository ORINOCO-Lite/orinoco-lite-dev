from pathlib import Path
from types import SimpleNamespace
from orinoco_lite import __version__
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.errors import ConfigurationError, IntegrityError
from orinoco_lite.resources import load_resources, resolve_resources, source_commit
from orinoco_lite.stage_resources import stage_package_resources


class PackageResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "LICENSE").write_text("License\n")
        (self.source / "driver.py").write_text("print('driver')\n")
        (self.source / "__pycache__").mkdir()
        (self.source / "__pycache__/driver.pyc").write_bytes(b"cache")
        self.spec = self.root / "resources.yaml"
        self.spec.write_text(
            "source_root: source\nlicenses: [data/LICENSE]\nresources:\n"
            "  - source: .\n    destination: data\n"
        )
        # Use a named resource directory, as production release inputs do.
        inputs = self.source / "inputs"
        inputs.mkdir()
        for name in ("LICENSE", "driver.py", "__pycache__"):
            (self.source / name).rename(inputs / name)
        self.spec.write_text(self.spec.read_text().replace("source: .", "source: inputs"))
        self.destination = self.root / "package/_resources"

    def stage(self):
        return stage_package_resources(self.spec, self.destination, source_commit="a" * 40)

    def test_stages_ordinary_resources_and_the_presentation_source_commit(self):
        self.stage()
        self.assertEqual((self.destination / "data/driver.py").read_text(), "print('driver')\n")
        self.assertEqual(source_commit(self.destination), "a" * 40)
        self.assertEqual(load_resources(self.destination).root, self.destination.resolve())
        self.assertFalse((self.destination / "data/__pycache__").exists())

    def test_missing_license_fails_before_a_package_can_be_built(self):
        (self.source / "inputs/LICENSE").unlink()
        with self.assertRaisesRegex(ConfigurationError, "license is absent"):
            self.stage()
        self.assertFalse(self.destination.exists())

    def test_symlink_or_traversal_cannot_import_outside_resources(self):
        outside = self.root / "outside"
        outside.write_text("outside\n")
        (self.source / "inputs/link").symlink_to(outside)
        with self.assertRaisesRegex(IntegrityError, "symlink"):
            self.stage()
        (self.source / "inputs/link").unlink()
        self.spec.write_text(self.spec.read_text().replace("destination: data", "destination: ../outside"))
        with self.assertRaisesRegex(ConfigurationError, "safe relative path"):
            self.stage()
        self.assertEqual(outside.read_text(), "outside\n")

    def test_candidate_resources_require_explicit_package_development(self):
        self.stage()
        with patch.dict("os.environ", {"ORINOCO_CANDIDATE_RESOURCE_ROOT": str(self.destination)}, clear=True):
            with patch("orinoco_lite.resources.load_resources") as load:
                resolve_resources(None, SimpleNamespace(package_version=__version__))
                self.assertNotEqual(load.call_args.args[0], self.destination)

    def test_duplicate_destination_and_invalid_source_pin_are_rejected(self):
        self.spec.write_text(self.spec.read_text() + "  - source: inputs\n    destination: data\n")
        with self.assertRaisesRegex(ConfigurationError, "repeated"):
            self.stage()
        with self.assertRaisesRegex(ConfigurationError, "Git SHA"):
            stage_package_resources(self.spec, self.destination, source_commit="main")


if __name__ == "__main__":
    unittest.main()
