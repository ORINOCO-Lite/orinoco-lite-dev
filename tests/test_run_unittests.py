from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools/run_unittests.py"


class StrictUnittestRunnerTests(unittest.TestCase):
    def run_fixture(self, source: str, *, strict: bool) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            (fixture / "test_fixture.py").write_text(source, encoding="utf-8")
            command = [sys.executable, str(RUNNER)]
            if strict:
                command.append("--fail-on-skip")
            command.extend(("--discover", str(fixture)))
            return subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_successful_suite_passes_in_strict_mode(self) -> None:
        result = self.run_fixture(
            "import unittest\n"
            "class Example(unittest.TestCase):\n"
            "    def test_passes(self): self.assertTrue(True)\n",
            strict=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("rejected skipped tests", result.stderr)

    def test_skipped_test_passes_in_default_mode(self) -> None:
        result = self.run_fixture(
            "import unittest\n"
            "class Example(unittest.TestCase):\n"
            "    @unittest.skip('fixture unavailable')\n"
            "    def test_skips(self): pass\n",
            strict=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped=1", result.stderr)

    def test_skipped_test_fails_in_strict_mode(self) -> None:
        result = self.run_fixture(
            "import unittest\n"
            "class Example(unittest.TestCase):\n"
            "    @unittest.skip('fixture unavailable')\n"
            "    def test_skips(self): pass\n",
            strict=True,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Strict test run rejected skipped tests", result.stderr)
        self.assertIn("fixture unavailable", result.stderr)


if __name__ == "__main__":
    unittest.main()
