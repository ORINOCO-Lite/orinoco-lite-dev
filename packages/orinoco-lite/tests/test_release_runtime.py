from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ENGINE_ROOT = Path(__file__).resolve().parents[3]
ENGINE_SOURCE = ENGINE_ROOT / "packages/orinoco-lite/src"
RELEASE_WORKFLOW = ENGINE_ROOT / ".github/workflows/orinoco-release.yml"


class MinimalRuntimeReleaseTests(unittest.TestCase):
    def test_release_module_runs_without_the_broad_cli_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            guard = root / "guard"
            guard.mkdir()
            marker = root / "import-guard-loaded"
            guard_source = """\
import builtins
from pathlib import Path

Path(__MARKER__).write_text("loaded\\n", encoding="utf-8")
blocked = (
    "dump_things_service",
    "jinja2",
    "linkml",
    "linkml_runtime",
    "orinoco_lite.annotations",
    "orinoco_lite.asset_cli",
    "orinoco_lite.assets",
    "orinoco_lite.canonical",
    "orinoco_lite.cli",
    "orinoco_lite.driver",
    "orinoco_lite.editor",
    "orinoco_lite.validation",
    "pydantic",
    "rdflib",
    "things_enrichment_tools",
)
original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if any(name == item or name.startswith(item + ".") for item in blocked):
        raise ImportError(f"release-minimal import guard rejected {name}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
"""
            (guard / "sitecustomize.py").write_text(
                guard_source.replace("__MARKER__", repr(str(marker))),
                encoding="utf-8",
            )
            source = root / "source"
            (source / "licenses").mkdir(parents=True)
            (source / "licenses/LICENSE.txt").write_text(
                "Fixture license\n", encoding="utf-8"
            )
            spec = root / "runtime.yaml"
            spec.write_text(
                """\
format: orinoco-lite-runtime-source
spec_version: 1
release: 0.2.0rc2
source_root: source
compatibility:
  config: [2]
  hugo: ">=0.154,<0.155"
commands:
  validate: ["{python}", "-c", "pass"]
licenses:
  - licenses/LICENSE.txt
resources:
  - source: licenses
    destination: licenses
provenance:
  source_commit: 0123456789012345678901234567890123456789
""",
                encoding="utf-8",
            )
            archive = root / "runtime.tar.gz"
            environment = {
                **os.environ,
                "PYTHONNOUSERSITE": "1",
                "PYTHONPATH": os.pathsep.join((str(guard), str(ENGINE_SOURCE))),
            }

            blocked_cli = subprocess.run(
                [sys.executable, "-c", "import orinoco_lite.cli"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(blocked_cli.returncode, 0)
            self.assertIn("release-minimal import guard rejected", blocked_cli.stderr)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "orinoco_lite.release_runtime",
                    "--spec",
                    str(spec),
                    "--source-commit",
                    "a" * 40,
                    "--output",
                    str(archive),
                ],
                cwd=ENGINE_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(marker.is_file())
            self.assertTrue(archive.is_file())
            report = json.loads(result.stdout)
            self.assertEqual(report["release"], "0.2.0rc2")
            self.assertEqual(report["provenance"]["source_commit"], "a" * 40)

    def test_release_workflow_uses_only_the_narrow_entrypoint(self) -> None:
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(
            workflow.count("python -m orinoco_lite.release_runtime"),
            2,
        )
        self.assertNotIn("python -m orinoco_lite release assemble", workflow)


if __name__ == "__main__":
    unittest.main()
