from __future__ import annotations

import json
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import unittest

from orinoco_lite.config import EngineLock, RuntimePin, load_workspace
from orinoco_lite.errors import IntegrityError
from orinoco_lite.integrity import sha256_file
from orinoco_lite.runtime import (
    assemble_runtime,
    resolve_runtime,
    verify_runtime_archive,
    verify_runtime_directory,
)


class RuntimeReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source = self.root / "source"
        (source / "drivers").mkdir(parents=True)
        (source / "licenses").mkdir()
        driver = source / "drivers" / "validate.py"
        driver.write_text("print('validated')\n", encoding="utf-8")
        driver.chmod(0o755)
        (source / "licenses" / "LICENSE.txt").write_text(
            "Fixture license\n", encoding="utf-8"
        )
        (source / "drivers" / "__pycache__").mkdir()
        (source / "drivers" / "__pycache__" / "validate.cpython-312.pyc").write_bytes(
            b"cache"
        )
        self.spec = self.root / "runtime.yaml"
        self.spec.write_text(
            """\
format: orinoco-lite-runtime-source
spec_version: 1
release: 0.1.0
source_root: source
compatibility:
  config: [1]
  hugo: ">=0.154,<0.155"
commands:
  validate: ["{python}", "{runtime}/drivers/validate.py"]
licenses:
  - licenses/LICENSE.txt
resources:
  - source: drivers
    destination: drivers
  - source: licenses
    destination: licenses
provenance:
  source_commit: 0123456789012345678901234567890123456789
""",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_archive_is_reproducible_and_verifiable(self) -> None:
        first = self.root / "first.tar.gz"
        second = self.root / "second.tar.gz"
        first_report = assemble_runtime(self.spec, first)
        second_report = assemble_runtime(self.spec, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(first_report["archive_sha256"], sha256_file(first))
        self.assertEqual(
            first_report["provenance"]["source_commit"],
            "0123456789012345678901234567890123456789",
        )
        verified = verify_runtime_archive(
            first,
            expected_archive_sha256=first_report["archive_sha256"],
            expected_release="0.1.0",
            expected_manifest_sha256=first_report["manifest_sha256"],
        )
        self.assertEqual(verified.files, 2)
        self.assertEqual(verified.commands, ("validate",))

    def test_resolver_reopens_the_flattened_archive_install(self) -> None:
        archive = self.root / "runtime.tar.gz"
        assembled = assemble_runtime(self.spec, archive)
        consumer = self.root / "consumer"
        consumer.mkdir()
        (consumer / "orinoco.yaml").write_text(
            "contract_version: 1\n"
            "site:\n"
            "  name: Runtime cache fixture\n"
            "  base_url: https://example.invalid/runtime-cache/\n",
            encoding="utf-8",
        )
        shutil.copyfile(archive, consumer / archive.name)
        workspace = load_workspace(consumer)
        lock = EngineLock(
            path=consumer / "orinoco.lock",
            distribution="orinoco-lite",
            engine_version="0.1.4",
            engine_url=(
                "https://example.invalid/orinoco_lite-0.1.4-py3-none-any.whl"
            ),
            engine_sha256="a" * 64,
            runtime=RuntimePin(
                version="0.1.0",
                url=None,
                path=archive.name,
                sha256=assembled["archive_sha256"],
                manifest_sha256=assembled["manifest_sha256"],
            ),
            raw={},
        )

        installed = resolve_runtime(workspace, lock)
        reopened = resolve_runtime(workspace, lock)

        self.assertEqual(reopened, installed)
        self.assertEqual(
            installed.root,
            (
                consumer
                / ".orinoco"
                / "runtime"
                / f"0.1.0-{assembled['archive_sha256'][:12]}"
            ).resolve(),
        )
        self.assertTrue((installed.root / "runtime-manifest.json").is_file())
        self.assertFalse((installed.root / "orinoco-runtime").exists())

    def test_source_commit_override_updates_engine_inventory(self) -> None:
        value = self.spec.read_text(encoding="utf-8").replace(
            "  source_commit: 0123456789012345678901234567890123456789\n",
            "  source_commit: 0123456789012345678901234567890123456789\n"
            "  source_inventory:\n"
            "    engine:\n"
            "      commit: baseline\n",
        )
        self.spec.write_text(value, encoding="utf-8")
        archive = self.root / "runtime.tar.gz"
        commit = "a" * 40
        report = assemble_runtime(
            self.spec, archive, source_commit=commit
        )
        self.assertEqual(report["provenance"]["source_commit"], commit)
        self.assertEqual(
            report["provenance"]["source_inventory"]["engine"]["commit"], commit
        )

    def test_hugo_compatibility_requires_a_valid_specifier(self) -> None:
        original = self.spec.read_text(encoding="utf-8")
        for label, replacement in (
            ("missing", ""),
            ("empty", '  hugo: ""\n'),
            ("malformed", '  hugo: "not a version range"\n'),
        ):
            with self.subTest(label=label):
                self.spec.write_text(
                    original.replace('  hugo: ">=0.154,<0.155"\n', replacement),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(IntegrityError, "compatibility.hugo"):
                    assemble_runtime(self.spec, self.root / f"{label}.tar.gz")
        self.spec.write_text(original, encoding="utf-8")

    def test_directory_tampering_is_rejected(self) -> None:
        archive = self.root / "runtime.tar.gz"
        assemble_runtime(self.spec, archive)
        extracted = self.root / "extracted"
        with tarfile.open(archive, "r:gz") as stream:
            stream.extractall(extracted, filter="data")
        runtime = extracted / "orinoco-runtime"
        verify_runtime_directory(runtime)
        (runtime / "drivers" / "validate.py").write_text(
            "print('tampered')\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(IntegrityError, "integrity"):
            verify_runtime_directory(runtime)

    def test_undeclared_resource_is_rejected(self) -> None:
        archive = self.root / "runtime.tar.gz"
        assemble_runtime(self.spec, archive)
        extracted = self.root / "extracted"
        with tarfile.open(archive, "r:gz") as stream:
            stream.extractall(extracted, filter="data")
        runtime = extracted / "orinoco-runtime"
        (runtime / "surprise.txt").write_text("unexpected\n", encoding="utf-8")
        with self.assertRaisesRegex(IntegrityError, "inventory"):
            verify_runtime_directory(runtime)

    def test_archive_traversal_is_rejected(self) -> None:
        archive = self.root / "unsafe.tar.gz"
        payload = self.root / "payload"
        payload.write_text("bad", encoding="utf-8")
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(payload, arcname="../escape")
        with self.assertRaisesRegex(IntegrityError, "unsafe"):
            verify_runtime_archive(archive)


if __name__ == "__main__":
    unittest.main()
