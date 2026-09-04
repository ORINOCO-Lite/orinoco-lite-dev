from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, sentinel

from orinoco_lite.config import WorkspaceConfig
from orinoco_lite.errors import ConfigurationError
from orinoco_lite.driver import driver_environment, invoke_driver
from orinoco_lite.resources import PackageResources


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
                raw={},
            )
            resources = PackageResources(root=root / "resources")
            with patch.dict(os.environ, {"PYTHONPATH": "/tmp/hostile"}):
                environment = driver_environment(workspace, resources)
            self.assertNotIn("PYTHONPATH", environment)

    def test_explicit_development_package_selects_candidate_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            package = candidate / "packages/orinoco-lite/src/orinoco_lite"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            workspace = WorkspaceConfig(
                root=root,
                config_path=root / "orinoco.yaml",
                lock_path=root / "orinoco.lock",
                site_name="fixture",
                base_url="https://example.invalid/",
                paths={"build": "build"},
                raw={},
            )
            resources = PackageResources(root=root / "resources")
            enabled = {
                "ORINOCO_UNSAFE_DEVELOPMENT_PACKAGE": "1",
                "ORINOCO_CANDIDATE_PACKAGE_ROOT": str(candidate),
                "ORINOCO_CANDIDATE_EDITOR_SHELL": str(root / "editor-shell"),
            }
            with patch.dict(os.environ, enabled, clear=False):
                environment = driver_environment(workspace, resources)

            self.assertEqual(
                str(candidate.resolve() / "packages/orinoco-lite/src"),
                environment["PYTHONPATH"],
            )
            self.assertEqual(
                environment["ORINOCO_CANDIDATE_PACKAGE_ROOT"],
                str(candidate.resolve()),
            )
            self.assertEqual(
                environment["ORINOCO_UNSAFE_DEVELOPMENT_PACKAGE"],
                "1",
            )
            self.assertEqual(
                environment["ORINOCO_CANDIDATE_EDITOR_SHELL"],
                str(root / "editor-shell"),
            )

    def test_invalid_explicit_development_package_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = WorkspaceConfig(
                root=root,
                config_path=root / "orinoco.yaml",
                lock_path=root / "orinoco.lock",
                site_name="fixture",
                base_url="https://example.invalid/",
                paths={"build": "build"},
                raw={},
            )
            resources = PackageResources(root=root / "resources")
            enabled = {
                "ORINOCO_UNSAFE_DEVELOPMENT_PACKAGE": "1",
                "ORINOCO_CANDIDATE_PACKAGE_ROOT": str(root / "missing"),
            }
            with patch.dict(os.environ, enabled, clear=False):
                with self.assertRaisesRegex(ConfigurationError, "does not contain"):
                    driver_environment(workspace, resources)

    def test_driver_runs_the_installed_module_without_a_shell(self) -> None:
        root = Path("/tmp/site")
        workspace = WorkspaceConfig(
            root=root, config_path=root / "orinoco.yaml", lock_path=root / "orinoco.lock",
            site_name="fixture", base_url="https://example.invalid/",
            paths={"build": "build"}, raw={},
        )
        resources = PackageResources(root=Path("/package/_resources"))
        with patch("orinoco_lite.driver.subprocess.run") as run:
            run.return_value.returncode = 0
            self.assertEqual(invoke_driver("projection-update", workspace, sentinel.lock, resources), 0)
        command = run.call_args.args[0]
        self.assertEqual(command[1:4], ["-m", "orinoco_lite.projection_cli", "--config"])
        self.assertEqual(command[-1], "update")
        self.assertNotIn("shell", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
