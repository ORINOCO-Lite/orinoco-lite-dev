from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from orinoco_lite.config import load_workspace
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.validation import validate_workspace


CONFIG = """\
contract_version: 1
site:
  name: Complete fixture
  base_url: https://example.invalid/complete/
"""


class DownstreamValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
        for relative in (
            "metadata/records/XYZPerson",
            "metadata/reference/XYZAgentRole",
            "metadata/provenance",
            "editorial",
            "assets/files",
            "site",
            "integrations/zotero",
            "generated",
            "extensions",
            "build",
        ):
            (self.root / relative).mkdir(parents=True)
        (self.root / "metadata/records/XYZPerson/person.yaml").write_text(
            "pid: xyzrins:persons/test\nschema_type: xyzri:XYZPerson\n",
            encoding="utf-8",
        )
        (self.root / "metadata/reference/XYZAgentRole/role.yaml").write_text(
            "pid: xyzrins:roles/test\nschema_type: xyzri:XYZAgentRole\n",
            encoding="utf-8",
        )
        (self.root / "metadata/provenance/selection.yaml").write_text(
            "version: 1\n", encoding="utf-8"
        )
        (self.root / "assets/manifest.yaml").write_text(
            "version: 1\nassets: []\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_complete_flattened_layout_passes(self) -> None:
        report = validate_workspace(load_workspace(self.root))
        self.assertEqual(report["canonical_records"], 1)
        self.assertEqual(report["reference_records"], 1)
        self.assertEqual(report["canonical_classes"], {"xyzri:XYZPerson": 1})

    def test_duplicate_pid_across_reference_closure_fails(self) -> None:
        (self.root / "metadata/reference/XYZAgentRole/role.yaml").write_text(
            "pid: xyzrins:persons/test\nschema_type: xyzri:XYZAgentRole\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "duplicated"):
            validate_workspace(load_workspace(self.root))

    def test_full_uri_discriminator_fails_closed(self) -> None:
        (self.root / "metadata/records/XYZPerson/person.yaml").write_text(
            "pid: xyzrins:persons/test\n"
            "schema_type: https://example.invalid/XYZPerson\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "CURIE"):
            validate_workspace(load_workspace(self.root))

    def test_gitlink_fails_downstream_contract(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "update-index",
                "--add",
                "--cacheinfo",
                "160000,0123456789012345678901234567890123456789,component",
            ],
            check=True,
        )
        with self.assertRaisesRegex(ConfigurationError, "gitlinks"):
            validate_workspace(load_workspace(self.root))


if __name__ == "__main__":
    unittest.main()
