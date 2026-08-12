from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from dump_things_service import Format
from dump_things_service.converter import FormatConverter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def load_tool(name: str):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = load_tool("build_pages_editor")
APPLIER = load_tool("apply_editor_bundle")


class PagesEditorTests(unittest.TestCase):
    def test_builder_emits_explicit_backend_free_contract(self) -> None:
        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        with (
            tempfile.TemporaryDirectory() as source_temporary,
            tempfile.TemporaryDirectory(dir=build_root) as destination_temporary,
        ):
            source = Path(source_temporary)
            source.joinpath("index.html").write_text(
                "<!doctype html><title>editor</title>\n", encoding="utf-8"
            )
            source.joinpath("config.yaml").write_text(
                "use_service: true\n", encoding="utf-8"
            )
            source.joinpath("bundle.js.map").write_text("{}\n", encoding="utf-8")
            destination = Path(destination_temporary) / "editor"
            with (
                mock.patch.object(
                    BUILDER, "static_records_turtle", return_value=("# records\n", 2)
                ),
                mock.patch.object(BUILDER, "git_commit", return_value="a" * 40),
            ):
                contract = BUILDER.build_editor(destination, source)

            config = json.loads(
                destination.joinpath("config.json").read_text(encoding="utf-8")
            )
            self.assertFalse(config["use_service"])
            self.assertFalse(config["use_token"])
            self.assertEqual(config["review_bundle_mode"], "patch-download")
            self.assertEqual(config["review_bundle_catalog"], "record-sources.json")
            self.assertFalse(destination.joinpath("config.yaml").exists())
            self.assertFalse(destination.joinpath("bundle.js.map").exists())
            self.assertEqual(contract["backend"], "none")
            self.assertEqual(contract["authentication"], "none")

    def test_repeated_editor_builds_are_independent_and_byte_identical(self) -> None:
        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build_root) as temporary:
            temporary_root = Path(temporary)
            source = temporary_root / "source"
            source.mkdir()
            source.joinpath("index.html").write_text(
                "<!doctype html><title>editor</title>\n", encoding="utf-8"
            )
            first = temporary_root / "first"
            second = temporary_root / "second"
            build_number = 0

            def build_pool_ui() -> None:
                nonlocal build_number
                build_number += 1
                source.joinpath("build.txt").write_text(
                    "deterministic\n", encoding="utf-8"
                )

            with (
                mock.patch.object(BUILDER, "DEFAULT_SOURCE", source),
                mock.patch.object(
                    BUILDER, "static_records_turtle", return_value=("# records\n", 2)
                ),
                mock.patch.object(BUILDER, "git_commit", return_value="a" * 40),
                mock.patch.object(BUILDER, "build_pool_ui", side_effect=build_pool_ui),
            ):
                report = BUILDER.verify_editor_builds(first, second, source)

            self.assertEqual(build_number, 2)
            self.assertTrue(report["byte_identical"])
            self.assertEqual(
                BUILDER.manifest_entries(first),
                BUILDER.manifest_entries(second),
            )

            source.joinpath("build.txt").write_text("first\n", encoding="utf-8")
            build_number = 0

            def nondeterministic_build() -> None:
                nonlocal build_number
                build_number += 1
                source.joinpath("build.txt").write_text(
                    f"build {build_number}\n", encoding="utf-8"
                )

            with (
                mock.patch.object(BUILDER, "DEFAULT_SOURCE", source),
                mock.patch.object(
                    BUILDER, "static_records_turtle", return_value=("# records\n", 2)
                ),
                mock.patch.object(BUILDER, "git_commit", return_value="a" * 40),
                mock.patch.object(
                    BUILDER, "build_pool_ui", side_effect=nondeterministic_build
                ),
            ):
                with self.assertRaisesRegex(BUILDER.BuildError, "byte-identical"):
                    BUILDER.verify_editor_builds(first, second, source)

    def test_editor_build_identity_does_not_depend_on_checkout_branch(self) -> None:
        makefile = (BUILDER.UI / "Makefile").read_text(encoding="utf-8")
        vite = (BUILDER.UI / "shacl-vue/vite.config.app.mjs").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("rev-parse --abbrev-ref", makefile)
        self.assertNotIn("rev-parse --abbrev-ref", vite)
        self.assertIn('BUILD_GIT_BRANCH="pinned"', makefile)
        self.assertIn("const branch = 'pinned';", vite)

    def test_static_rdf_is_canonical_across_blank_node_order(self) -> None:
        first = """
            @prefix ex: <https://example.test/> .
            ex:root ex:values [ ex:name "second" ], [ ex:name "first" ] .
        """
        second = """
            @prefix ex: <https://example.test/> .
            ex:root ex:values [ ex:name "first" ], [ ex:name "second" ] .
        """

        self.assertEqual(
            BUILDER.canonical_turtle([first]),
            BUILDER.canonical_turtle([second]),
        )

    def test_bundle_reader_rejects_extra_fields_and_oversized_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bundle.json"
            path.write_text(
                json.dumps(
                    {
                        "format": APPLIER.FORMAT,
                        "records": [],
                        "site_commit": "a" * 40,
                        "unexpected": True,
                        "version": 1,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(APPLIER.BuildError, "unexpected"):
                APPLIER.read_bundle(path)
            path.write_bytes(b"x" * (APPLIER.MAX_BUNDLE_BYTES + 1))
            with self.assertRaisesRegex(APPLIER.BuildError, "10 MiB"):
                APPLIER.read_bundle(path)

    def test_applier_rejects_stale_commit_before_reading_sources(self) -> None:
        bundle = {
            "format": APPLIER.FORMAT,
            "records": [{}],
            "site_commit": "a" * 40,
            "version": 1,
        }
        with (
            mock.patch.object(APPLIER, "require_clean_checkout"),
            mock.patch.object(APPLIER, "git_commit", return_value="b" * 40),
        ):
            with self.assertRaisesRegex(APPLIER.BuildError, "stale"):
                APPLIER.validate_bundle(bundle)

    def test_applier_rejects_a_dirty_checkout_and_uses_full_diff_paths(self) -> None:
        with mock.patch.object(
            APPLIER.subprocess,
            "run",
            return_value=mock.Mock(stdout="?? untracked.yaml\n"),
        ):
            with self.assertRaisesRegex(APPLIER.BuildError, "tracked or untracked"):
                APPLIER.require_clean_checkout(APPLIER.SITE)

        with (
            mock.patch.object(
                APPLIER.subprocess, "run", return_value=mock.Mock(stdout="")
            ),
            mock.patch.object(
                APPLIER,
                "projection_require_no_ignored_files",
                side_effect=APPLIER.ProjectionError(
                    "The pinned static editor canonical inputs worktree has "
                    "ignored files"
                ),
            ),
        ):
            with self.assertRaisesRegex(APPLIER.BuildError, "ignored files"):
                APPLIER.require_clean_checkout(APPLIER.SITE)

        source = (
            APPLIER.SITE
            / "profiles/con/metadata/records/XYZPerson/yaroslav-halchenko.yaml"
        )
        difference = APPLIER.diff_updates(
            {source: source.read_text(encoding="utf-8") + "# changed\n"}
        )
        self.assertIn(
            "a/profiles/con/metadata/records/XYZPerson/yaroslav-halchenko.yaml",
            difference,
        )

    def test_valid_bundle_is_bound_to_source_digest_and_path(self) -> None:
        canonical, _, _ = APPLIER.canonical_index(APPLIER.SITE)
        source = sorted(canonical.values(), key=lambda item: item.record["pid"])[0]
        turtle = FormatConverter(str(APPLIER.SCHEMA), Format.json, Format.ttl).convert(
            source.record, source.class_name
        )
        content = source.path.read_bytes()
        record = {
            "pid": source.record["pid"],
            "rdf_turtle": turtle,
            "schema_type": source.record["schema_type"],
            "source_path": source.path.relative_to(APPLIER.SITE).as_posix(),
            "source_sha256": hashlib.sha256(content).hexdigest(),
        }
        bundle = {
            "format": APPLIER.FORMAT,
            "records": [record],
            "site_commit": APPLIER.git_commit(APPLIER.SITE),
            "version": 1,
        }
        updates = APPLIER.validate_bundle(bundle)
        self.assertEqual(set(updates), {source.path})

        stale = json.loads(json.dumps(bundle))
        stale["records"][0]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(APPLIER.BuildError, "digest is stale"):
            APPLIER.validate_bundle(stale)

        escaped = json.loads(json.dumps(bundle))
        escaped["records"][0]["source_path"] = "../outside.yaml"
        with self.assertRaisesRegex(APPLIER.BuildError, "path does not match"):
            APPLIER.validate_bundle(escaped)


if __name__ == "__main__":
    unittest.main()
