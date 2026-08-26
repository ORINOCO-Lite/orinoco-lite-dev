from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.config import DEFAULT_PATHS, WorkspaceConfig
from orinoco_lite.errors import DriverError
from orinoco_lite.integrity import tree_sha256
from orinoco_lite.projection import (
    _is_historical_provenance,
    projection_manifest,
    render_projection,
    update_projection,
    verify_projection,
)
from orinoco_lite.release_schema import localize_schema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SOURCE = ROOT / "submodules/things-schemas/src"
CONSUMER_ENVIRONMENT = "ORINOCO_TEST_ACCEPTED_CONSUMER"
CONSUMER_COMMIT = "32c8df154fa11693efe9d20d298f553943b89096"
TRACKED_INPUTS = (
    "metadata",
    "site/projection.yaml",
    "site/projection-templates",
    "site/projection-tools",
)


class AcceptedConsumerCompatibilityTests(unittest.TestCase):
    """Exercise the engine against one frozen set of tracked consumer inputs."""

    @classmethod
    def setUpClass(cls) -> None:
        value = os.environ.get(CONSUMER_ENVIRONMENT)
        if not value:
            raise AssertionError(
                f"{CONSUMER_ENVIRONMENT} must name the frozen consumer checkout"
            )
        cls.accepted_consumer = Path(value).resolve()
        result = subprocess.run(
            ["git", "-C", str(cls.accepted_consumer), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise AssertionError(
                f"accepted consumer fixture is not a Git checkout: {detail}"
            )
        if result.stdout.strip() != CONSUMER_COMMIT:
            raise AssertionError(
                "accepted consumer fixture should be "
                f"{CONSUMER_COMMIT}, not {result.stdout.strip()}"
            )
        status = subprocess.run(
            [
                "git",
                "-C",
                str(cls.accepted_consumer),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if status.returncode or status.stdout:
            detail = (status.stderr or status.stdout).strip()
            raise AssertionError(f"accepted consumer fixture is modified: {detail}")
        required = [cls.accepted_consumer / item for item in TRACKED_INPUTS]
        required.append(
            SCHEMA_SOURCE / "demo-research-information/unreleased.yaml"
        )
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise AssertionError(
                "accepted compatibility inputs are missing: " + ", ".join(missing)
            )

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        temporary = Path(self.temporary.name)
        self.root = temporary / "consumer"
        self.runtime_010 = temporary / "runtime-0.1.0"
        self.runtime_011 = temporary / "runtime-0.1.1"
        self.root.mkdir()
        for relative in TRACKED_INPUTS:
            source = self.accepted_consumer / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copyfile(source, destination)
        localize_schema(
            SCHEMA_SOURCE,
            SCHEMA_SOURCE / "demo-research-information/unreleased.yaml",
            self.runtime_010 / "schema",
        )
        shutil.copytree(self.runtime_010 / "schema", self.runtime_011 / "schema")
        runtime_releases = (
            (self.runtime_010, "0.1.0"),
            (self.runtime_011, "0.1.1"),
        )
        for runtime, release in runtime_releases:
            (runtime / "runtime-manifest.json").write_text(
                json.dumps({"release": release}) + "\n", encoding="utf-8"
            )
        self.workspace = WorkspaceConfig(
            root=self.root,
            config_path=self.root / "orinoco.yaml",
            lock_path=self.root / "orinoco.lock",
            site_name="Full fixture",
            base_url="https://example.invalid/",
            paths=DEFAULT_PATHS,
            command_aliases={},
            raw={},
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _active_files(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
            and path.name not in {".gitattributes", "SHA256SUMS"}
            and not _is_historical_provenance(root, path)
        }

    def test_full_parity_stale_recovery_atomicity_and_patch_compatibility(self) -> None:
        temporary = Path(self.temporary.name)
        candidate = temporary / "candidate"
        repeated = temporary / "candidate-repeat"
        previous_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(1000)
            with self.assertNoLogs("dump_things_service", level="WARNING"):
                report = render_projection(
                    self.workspace, self.runtime_010, candidate
                )
                repeated_report = render_projection(
                    self.workspace, self.runtime_010, repeated
                )
            self.assertEqual(sys.getrecursionlimit(), 1000)
        finally:
            sys.setrecursionlimit(previous_limit)
        expected = {
            "records": 202,
            "pages": 188,
            "graph_nodes": 189,
            "graph_edges": 467,
        }
        self.assertEqual(report, expected)
        self.assertEqual(repeated_report, expected)
        self.assertEqual(
            self._active_files(candidate),
            self._active_files(repeated),
        )
        self.assertNotIn(
            "xyzri:XYZ",
            (
                ROOT / "packages/orinoco-lite/src/orinoco_lite/projection.py"
            ).read_text(encoding="utf-8"),
        )

        committed = self.root / "generated/projection"
        committed.parent.mkdir(parents=True)
        shutil.copytree(candidate, committed)

        semantic = {key: report[key] for key in report if key != "pages"}
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            verified = verify_projection(self.workspace, self.runtime_010)
        self.assertTrue(verified["deterministic"])
        self.assertEqual(
            projection_manifest(self.workspace, self.runtime_010, committed),
            projection_manifest(self.workspace, self.runtime_011, committed),
        )

        record = next(
            path
            for path in (self.root / "metadata/records").rglob("*.yaml")
            if not path.name.startswith(".")
        )
        record.write_text(
            record.read_text(encoding="utf-8") + "# stale edit\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(DriverError, "stale"):
            verify_projection(self.workspace, self.runtime_010)
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            update_projection(self.workspace, self.runtime_010)
            verify_projection(self.workspace, self.runtime_011)

        before = tree_sha256(committed)
        real_replace = os.replace
        replacements = 0

        def fail_install(source, destination):
            nonlocal replacements
            replacements += 1
            if replacements == 2:
                raise OSError("injected projection install failure")
            return real_replace(source, destination)

        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            with patch("orinoco_lite.projection.os.replace", side_effect=fail_install):
                with self.assertRaisesRegex(OSError, "injected"):
                    update_projection(self.workspace, self.runtime_010)
        self.assertEqual(tree_sha256(committed), before)

        producer = self.root / "site/projection-tools/pool2graph.py"
        producer.write_text(
            producer.read_text(encoding="utf-8")
            + "\nprint('missing node', file=sys.stderr)\n",
            encoding="utf-8",
        )
        with patch("orinoco_lite.projection.validate_semantics", return_value=semantic):
            with self.assertRaisesRegex(DriverError, "missing node"):
                render_projection(
                    self.workspace,
                    self.runtime_010,
                    temporary / "bad-graph",
                )


if __name__ == "__main__":
    unittest.main()
