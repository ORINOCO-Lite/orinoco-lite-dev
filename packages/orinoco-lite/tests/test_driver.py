from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, sentinel

from orinoco_lite.config import WorkspaceConfig
from orinoco_lite.driver import driver_environment, invoke_driver
from orinoco_lite.integrity import (
    canonical_json_bytes,
    resource_checksum_lines,
    sha256_file,
    tree_sha256,
)
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

    def test_runtime_imports_do_not_write_bytecode_or_change_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime_root = root / "runtime"
            engine = runtime_root / "engine" / "fixture_driver"
            engine.mkdir(parents=True)
            module = engine / "__init__.py"
            module.write_text("VALUE = 'verified'\n", encoding="utf-8")
            license_file = runtime_root / "LICENSE.txt"
            license_file.write_text("Fixture license\n", encoding="utf-8")
            resources = []
            for path in (module, license_file):
                resources.append(
                    {
                        "path": path.relative_to(runtime_root).as_posix(),
                        "sha256": sha256_file(path),
                        "size": path.stat().st_size,
                        "mode": 0o644,
                    }
                )
            manifest_path = runtime_root / "runtime-manifest.json"
            manifest_path.write_bytes(
                canonical_json_bytes(
                    {
                        "format": "orinoco-lite-runtime",
                        "manifest_version": 1,
                        "release": "0.1.5",
                        "compatibility": {
                            "config": [2],
                            "hugo": ">=0.154,<0.155",
                        },
                        "commands": {
                            "validate": [
                                "{python}",
                                "-c",
                                "import fixture_driver; "
                                "assert fixture_driver.VALUE == 'verified'",
                            ]
                        },
                        "files": resources,
                        "licenses": ["LICENSE.txt"],
                        "provenance": {},
                    }
                )
            )
            checksums = [
                (entry["path"], entry["sha256"]) for entry in resources
            ]
            checksums.append(("runtime-manifest.json", sha256_file(manifest_path)))
            (runtime_root / "SHA256SUMS").write_text(
                resource_checksum_lines(checksums), encoding="utf-8"
            )
            workspace_root = root / "consumer"
            workspace_root.mkdir()
            workspace = WorkspaceConfig(
                root=workspace_root,
                config_path=workspace_root / "orinoco.yaml",
                lock_path=workspace_root / "orinoco.lock",
                site_name="fixture",
                base_url="https://example.invalid/",
                paths={"build": "build"},
                command_aliases={},
                raw={},
            )
            runtime = RuntimeReport(
                root=runtime_root,
                release="0.1.5",
                manifest_sha256=sha256_file(manifest_path),
                tree_sha256=tree_sha256(runtime_root),
                files=2,
                commands=("validate",),
            )
            lock = sentinel.lock

            for _ in range(2):
                self.assertEqual(
                    0,
                    invoke_driver(
                        "validate",
                        workspace,
                        lock,
                        runtime,
                        environment={"PYTHONDONTWRITEBYTECODE": "0"},
                    ),
                )
            self.assertEqual([], list(runtime_root.rglob("*.pyc")))
            self.assertEqual([], list(runtime_root.rglob("__pycache__")))
            self.assertEqual(runtime.tree_sha256, tree_sha256(runtime_root))


if __name__ == "__main__":
    unittest.main()
