from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.build_resources import build_resources
from orinoco_lite.errors import DriverError


class SourceInstallationTests(unittest.TestCase):
    def test_incomplete_checkout_explains_how_to_initialize_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(DriverError, "git submodule update --init"):
                build_resources(root, root / "resources")
            self.assertFalse((root / "resources").exists())

    def test_failed_compilation_preserves_existing_resources_and_upstream_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pool = root / "submodules/pool.psychoinformatics.de-ui"
            (pool / "shacl-vue").mkdir(parents=True)
            (pool / "shacl-vue/package-lock.json").write_text("{}")
            schema = root / "submodules/things-schemas/src/demo-research-information"
            schema.mkdir(parents=True)
            (schema / "unreleased.yaml").write_text("{}")
            resources = root / "package/_resources"
            resources.mkdir(parents=True)
            (resources / "index.html").write_text("previous installation")

            def failed_editor(copied_pool, *_args):
                (copied_pool / "shacl-vue/package-lock.json").write_text("changed")
                raise DriverError("compiler failed")

            with (
                patch("orinoco_lite.build_resources.shutil.which", return_value="tool"),
                patch("orinoco_lite.build_resources.subprocess.check_output", return_value="a" * 40),
                patch("orinoco_lite.build_resources.build_editor", side_effect=failed_editor),
                self.assertRaisesRegex(DriverError, "compiler failed"),
            ):
                build_resources(root, resources)

            self.assertEqual((resources / "index.html").read_text(), "previous installation")
            self.assertEqual((pool / "shacl-vue/package-lock.json").read_text(), "{}")
            self.assertEqual(list(resources.parent.iterdir()), [resources])
