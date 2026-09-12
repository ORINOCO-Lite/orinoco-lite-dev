from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.config import WorkspaceConfig
from orinoco_lite.driver import driver_environment, invoke_driver
from orinoco_lite.resources import PackageResources


class DriverEnvironmentTests(unittest.TestCase):
    def test_hostile_inherited_pythonpath_is_not_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = WorkspaceConfig(
                root=root,
                config_path=root / "orinoco.yaml",

                site_name="fixture",
                base_url="https://example.invalid/",
                paths={"build": "build"},
                raw={},
            )
            resources = PackageResources(root=root / "resources")
            with patch.dict(os.environ, {"PYTHONPATH": "/tmp/hostile"}):
                environment = driver_environment(workspace, resources)
            self.assertNotIn("PYTHONPATH", environment)

    def test_candidate_preview_coordinates_reach_the_installed_driver(self) -> None:
        root = Path("/tmp/site")
        workspace = WorkspaceConfig(
            root=root,
            config_path=root / "orinoco.yaml",
            site_name="fixture",
            base_url="https://example.invalid/",
            paths={"build": "build"},
            raw={},
        )
        resources = PackageResources(root=Path("/package/_resources"))
        expected = {
            "ORINOCO_CANDIDATE_CONTENT_COMMIT": "a" * 40,
            "ORINOCO_CANDIDATE_PULL_REQUEST": "8",
            "ORINOCO_UNSAFE_DEVELOPMENT_PACKAGE": "1",
        }
        with patch.dict(os.environ, expected, clear=False):
            environment = driver_environment(workspace, resources)

        for name, value in expected.items():
            self.assertEqual(value, environment[name])

    def test_driver_runs_the_installed_module_without_a_shell(self) -> None:
        root = Path("/tmp/site")
        workspace = WorkspaceConfig(
            root=root, config_path=root / "orinoco.yaml",
            site_name="fixture", base_url="https://example.invalid/",
            paths={"build": "build"}, raw={},
        )
        resources = PackageResources(root=Path("/package/_resources"))
        with patch("orinoco_lite.driver.subprocess.run") as run:
            run.return_value.returncode = 0
            self.assertEqual(invoke_driver("projection-update", workspace, resources), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[1:4], ["-m", "orinoco_lite.projection_cli", "--config"])
        self.assertEqual(command[-1], "update")
        self.assertNotIn("shell", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
