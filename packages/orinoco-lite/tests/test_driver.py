from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.config import WorkspaceConfig
from orinoco_lite.driver import driver_environment
from orinoco_lite.runtime import RuntimeReport


class DriverEnvironmentTests(unittest.TestCase):
    def test_hostile_inherited_pythonpath_is_not_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = WorkspaceConfig(
                root=root,
                config_path=root / "orinoco.yaml",
                lock_path=root / "orinoco.lock",
                site_name="fixture",
                base_url="https://example.invalid/",
                paths={"build": "build"},
                command_aliases={},
                raw={},
            )
            runtime = RuntimeReport(
                root=root / "runtime",
                release="0.1.0",
                manifest_sha256="a" * 64,
                tree_sha256="b" * 64,
                files=1,
                commands=("validate",),
            )
            with patch.dict(os.environ, {"PYTHONPATH": "/tmp/hostile"}):
                environment = driver_environment(workspace, runtime)
            self.assertEqual(environment["PYTHONPATH"], str(runtime.root / "engine"))
            self.assertNotIn("hostile", environment["PYTHONPATH"])


if __name__ == "__main__":
    unittest.main()
