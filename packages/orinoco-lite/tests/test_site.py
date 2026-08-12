from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite import site
from orinoco_lite.errors import DriverError


CONFIG = """\
contract_version: 1
site:
  name: Hugo compatibility fixture
  base_url: https://example.invalid/orinoco/
"""


class HugoCompatibilityTests(unittest.TestCase):
    def test_supported_extended_hugo_is_accepted(self) -> None:
        version = site._require_compatible_hugo(
            "hugo v0.154.5+extended darwin/arm64 BuildDate=unknown "
            "VendorInfo=conda-forge",
            ">=0.154,<0.155",
            runtime_release="0.1.3",
        )
        self.assertEqual(str(version), "0.154.5")

    def test_unsupported_or_malformed_hugo_is_rejected(self) -> None:
        cases = (
            (
                "too old",
                "hugo v0.153.9+extended linux/amd64",
                "requires Hugo >=0.154,<0.155; found 0.153.9",
            ),
            (
                "too new",
                "hugo v0.155.0+extended linux/amd64",
                "requires Hugo >=0.154,<0.155; found 0.155.0",
            ),
            (
                "standard edition",
                "hugo v0.154.5 linux/amd64",
                "requires Hugo Extended",
            ),
            (
                "malformed",
                "hugo development+extended linux/amd64",
                "Could not determine Hugo version",
            ),
        )
        for label, output, message in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(DriverError, message):
                    site._require_compatible_hugo(
                        output,
                        ">=0.154,<0.155",
                        runtime_release="0.1.3",
                    )

    def test_build_preflight_preserves_existing_outputs_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
            destination = root / "build" / "site"
            destination.mkdir(parents=True)
            (destination / "index.html").write_text("existing\n", encoding="utf-8")
            assembly = root / "build" / "assembly"
            assembly.mkdir()
            (assembly / "sentinel").write_text("existing\n", encoding="utf-8")
            runtime = root / "runtime"
            runtime.mkdir()
            manifest = SimpleNamespace(
                compatibility={"hugo": ">=0.154,<0.155"},
                release="0.1.3",
            )
            with (
                patch.object(site, "load_runtime_manifest", return_value=manifest),
                patch.object(
                    site,
                    "_run",
                    return_value="hugo v0.155.0+extended linux/amd64",
                ) as run,
            ):
                with self.assertRaisesRegex(DriverError, "found 0.155.0"):
                    site.build_site(
                        root / "orinoco.yaml",
                        runtime,
                        destination,
                        "https://example.invalid/orinoco/",
                    )
            run.assert_called_once_with(["hugo", "version"], cwd=root.resolve())
            self.assertEqual(
                (destination / "index.html").read_text(encoding="utf-8"),
                "existing\n",
            )
            self.assertEqual(
                (assembly / "sentinel").read_text(encoding="utf-8"),
                "existing\n",
            )


if __name__ == "__main__":
    unittest.main()
