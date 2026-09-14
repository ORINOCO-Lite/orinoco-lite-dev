from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.errors import DriverError
from orinoco_lite.release_review import build_review_shell


class StaticReviewReleaseTests(unittest.TestCase):
    def test_incomplete_application_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(DriverError, "source is incomplete"):
                build_review_shell(root, root / "shell", root / "licenses")

    def test_build_copies_unconfigured_shell_and_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application = root / "application"
            (application / "review").mkdir(parents=True)
            for name in ("package.json", "package-lock.json"):
                (application / name).write_text("{}\n", encoding="utf-8")
            (application / "review/index.html").write_text(
                "<!doctype html>\n", encoding="utf-8"
            )
            dependency = application / "node_modules/example"
            dependency.mkdir(parents=True)
            (dependency / "package.json").write_text(
                '{"license":"MIT","name":"example","version":"1.0.0"}\n',
                encoding="utf-8",
            )
            (dependency / "LICENSE").write_text("MIT\n", encoding="utf-8")
            built = application / "dist-review"

            def fake_run(arguments, cwd, **_kwargs):
                self.assertEqual(cwd, application)
                if list(arguments[:3]) == ["npm", "run", "build:review"]:
                    built.mkdir()
                    (built / "index.html").write_text("review\n", encoding="utf-8")

            with patch("orinoco_lite.release_review._run", side_effect=fake_run):
                report = build_review_shell(
                    application,
                    root / "shell",
                    root / "licenses",
                )

            self.assertEqual(report["dependencies"], 1)
            self.assertEqual((root / "shell/index.html").read_text(), "review\n")
            inventory = (root / "licenses/inventory.json").read_text()
            self.assertIn('"format": "orinoco-review-dependency-inventory"', inventory)

    def test_build_rejects_a_shell_containing_site_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            application = root / "application"
            (application / "review").mkdir(parents=True)
            for name in ("package.json", "package-lock.json"):
                (application / name).write_text("{}\n", encoding="utf-8")
            (application / "review/index.html").write_text(
                "<!doctype html>\n", encoding="utf-8"
            )
            built = application / "dist-review"

            def fake_run(arguments, cwd, **_kwargs):
                self.assertEqual(cwd, application)
                if list(arguments[:3]) == ["npm", "run", "build:review"]:
                    built.mkdir()
                    (built / "index.html").write_text("review\n", encoding="utf-8")
                    (built / "config.json").write_text(
                        '{"repository":"example/site"}\n',
                        encoding="utf-8",
                    )

            with (
                patch("orinoco_lite.release_review._run", side_effect=fake_run),
                self.assertRaisesRegex(DriverError, "contains site configuration"),
            ):
                build_review_shell(
                    application,
                    root / "shell",
                    root / "licenses",
                )

            self.assertFalse((root / "shell").exists())
            self.assertFalse((root / "licenses").exists())


if __name__ == "__main__":
    unittest.main()
