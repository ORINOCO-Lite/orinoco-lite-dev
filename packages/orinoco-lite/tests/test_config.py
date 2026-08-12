from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from orinoco_lite.config import (
    ConfigurationError,
    find_workspace_root,
    load_lock,
    load_workspace,
)


CONFIG = """\
contract_version: 1
site:
  name: Test Orinoco downstream
  base_url: https://example.invalid/test-site/
"""


LOCK = """\
lock_version: 1
engine:
  distribution: orinoco-lite
  version: 0.1.0
  url: https://example.invalid/releases/orinoco_lite-0.1.0-py3-none-any.whl
  sha256: cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
runtime:
  version: 0.1.0
  path: vendor/orinoco-runtime.tar.gz
  sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
  manifest_sha256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
"""


class WorkspaceConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
        (self.root / "orinoco.lock").write_text(LOCK, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_defaults_resolve_relative_to_consumer(self) -> None:
        workspace = load_workspace(self.root)
        self.assertEqual(
            workspace.path("canonical").resolve(),
            (self.root / "metadata/records").resolve(),
        )
        self.assertEqual(workspace.path("site").resolve(), (self.root / "site").resolve())
        self.assertEqual(
            workspace.environment()["ORINOCO_CANONICAL_ROOT"],
            str((self.root / "metadata/records").resolve()),
        )

    def test_nearest_ancestor_discovers_workspace(self) -> None:
        nested = self.root / "metadata" / "records"
        nested.mkdir(parents=True)
        self.assertEqual(find_workspace_root(nested), self.root.resolve())

    def test_paths_cannot_escape_or_collide(self) -> None:
        (self.root / "orinoco.yaml").write_text(
            CONFIG + "paths:\n  canonical: ../outside\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(ConfigurationError, "normalized relative"):
            load_workspace(self.root)
        (self.root / "orinoco.yaml").write_text(
            CONFIG
            + "paths:\n"
            + "  canonical: metadata\n"
            + "  reference: metadata\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "distinct"):
            load_workspace(self.root)

    def test_lock_requires_one_immutable_runtime_location(self) -> None:
        lock = load_lock(self.root / "orinoco.lock")
        self.assertEqual(lock.runtime.path, "vendor/orinoco-runtime.tar.gz")
        (self.root / "orinoco.lock").write_text(
            LOCK.replace(
                "  path: vendor/orinoco-runtime.tar.gz\n",
                "  path: vendor/orinoco-runtime.tar.gz\n"
                "  url: https://example.invalid/runtime.tar.gz\n",
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "exactly one"):
            load_lock(self.root / "orinoco.lock")

    def test_lock_rejects_placeholder_digests_and_mismatched_wheel(self) -> None:
        for digest in ("c" * 64, "a" * 64, "b" * 64):
            value = LOCK.replace(digest, "0" * 64)
            (self.root / "orinoco.lock").write_text(value, encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "sha256"):
                load_lock(self.root / "orinoco.lock")
        (self.root / "orinoco.lock").write_text(
            LOCK.replace("orinoco_lite-0.1.0-", "orinoco_lite-0.1.1-"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ConfigurationError, "exact locked.*wheel"):
            load_lock(self.root / "orinoco.lock")


if __name__ == "__main__":
    unittest.main()
