from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name: str):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(ROOT / "tools"))
BUILD = load_tool("build_con_site")


class CONAssemblyTests(unittest.TestCase):
    def test_con_layout_overrides_are_preferred_digest_bound_and_static(self) -> None:
        profile_layouts = BUILD.SITE / "profiles/con/layouts"
        expected = {
            Path("term.html"),
            Path("_partials/article-link.html"),
            Path("_partials/picture.html"),
            Path("_partials/taxonomy-list-grid.html"),
            Path("_partials/taxonomy-list-vertical-item.html"),
            Path("_shortcodes/artwork-preview.html"),
        }
        actual = {
            path.relative_to(profile_layouts)
            for path in profile_layouts.rglob("*.html")
        }
        self.assertEqual(actual, expected)

        module = tomllib.loads(
            (BUILD.SITE / "config/con/module.toml").read_text(encoding="utf-8")
        )
        layout_sources = [
            mount["source"]
            for mount in module["mounts"]
            if mount.get("target") == "layouts"
        ]
        self.assertEqual(layout_sources, ["profiles/con/layouts", "layouts"])

        params = tomllib.loads(
            (BUILD.SITE / "config/con/params.toml").read_text(encoding="utf-8")
        )
        self.assertIs(params.get("enableQuicklink"), False)

        assembly = BUILD.load_yaml(BUILD.ASSEMBLY_SPEC)
        self.assertIn(
            "profiles/con/layouts",
            assembly["digest"]["scope"],
        )

        transformations = re.compile(r"\.(?:Resize|Fit|Fill|Crop|Process)\b")
        for relative in sorted(expected):
            text = (profile_layouts / relative).read_text(encoding="utf-8")
            self.assertIsNone(
                transformations.search(text),
                f"CON layout invokes platform-dependent image processing: {relative}",
            )

    def test_quicklink_artifact_scan_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            (site / "index.html").write_text("<main>CON</main>\n", encoding="utf-8")
            self.assertEqual(BUILD.quicklink_references(site), [])

            script = site / "js/main.js"
            script.parent.mkdir()
            script.write_text("quicklink.listen();\n", encoding="utf-8")
            self.assertEqual(BUILD.quicklink_references(site), ["js/main.js"])

    def test_manifest_tracks_site_parent_and_component_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = root / "site"
            profile = site / "profiles/con"
            parent_input = root / "tools/builder.py"
            editorial = profile / "editorial/content/about.md"
            output = profile / "assembly/SHA256SUMS"
            for path, content in (
                (parent_input, "builder\n"),
                (editorial, "about\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            (profile / "profile.yaml").write_text(
                yaml.safe_dump(
                    {
                        "paths": {
                            "assembly": "profiles/con/assembly.yaml",
                            "assembly_digest": ("profiles/con/assembly/SHA256SUMS"),
                        }
                    }
                ),
                encoding="utf-8",
            )
            assembly = {
                "digest": {
                    "algorithm": "sha256",
                    "output": "profiles/con/assembly/SHA256SUMS",
                    "scope": [
                        "profiles/con/assembly.yaml",
                        "profiles/con/editorial/content",
                        "parent:tools/builder.py",
                        "component-commit-pins",
                    ],
                }
            }
            spec_path = profile / "assembly.yaml"
            spec_path.write_text(yaml.safe_dump(assembly), encoding="utf-8")
            with (
                mock.patch.object(BUILD, "ROOT", root),
                mock.patch.object(BUILD, "SITE", site),
                mock.patch.object(BUILD, "PROFILE_ROOT", profile),
                mock.patch.object(BUILD, "ASSEMBLY_SPEC", spec_path),
                mock.patch.object(
                    BUILD,
                    "declared_component_pins",
                    return_value=[("site", "a" * 40)],
                ),
                mock.patch.object(BUILD, "verify_declared_pins"),
            ):
                first = BUILD.assembly_manifest()
                BUILD.update_assembly_manifest()
                BUILD.verify_assembly_manifest()
                editorial.write_text("changed\n", encoding="utf-8")
                second = BUILD.assembly_manifest()
                self.assertNotEqual(first, second)
                with self.assertRaisesRegex(BUILD.BuildError, "stale"):
                    BUILD.verify_assembly_manifest()
                self.assertTrue(output.is_file())

    def test_manifest_hashes_a_link_without_reading_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.txt"
            outside.write_text("secret-one\n", encoding="utf-8")
            link = root / "asset.jpg"
            link.symlink_to(outside)
            first = BUILD.assembly_input_bytes(link)
            outside.write_text("secret-two\n", encoding="utf-8")
            self.assertEqual(first, BUILD.assembly_input_bytes(link))
            self.assertEqual(first, b"symlink\0" + os.readlink(link).encode())

    def test_copy_sources_reject_undeclared_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "outside").symlink_to(root)
            with self.assertRaisesRegex(BUILD.BuildError, "directory symlink"):
                BUILD.reject_source_symlinks(source)

    def test_generated_output_rejects_a_symlinked_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir()
            linked = root / "site" / "profiles"
            linked.parent.mkdir()
            linked.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(BUILD.BuildError, "symlinked ancestor"):
                BUILD.reject_output_symlink_ancestors(
                    linked / "con/assembly/SHA256SUMS",
                    root / "site",
                )

    def test_manifest_update_ignores_a_predictable_temp_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary) / "site"
            output = site / "profiles/con/assembly/SHA256SUMS"
            output.parent.mkdir(parents=True)
            outside = Path(temporary) / "outside.txt"
            outside.write_text("unchanged\n", encoding="utf-8")
            predictable = output.with_suffix(output.suffix + ".tmp")
            predictable.symlink_to(outside)
            with (
                mock.patch.object(BUILD, "SITE", site),
                mock.patch.object(
                    BUILD,
                    "assembly_manifest_path",
                    return_value=output,
                ),
                mock.patch.object(
                    BUILD,
                    "assembly_manifest",
                    return_value="reviewed\n",
                ),
            ):
                BUILD.update_assembly_manifest()
            self.assertEqual(output.read_text(encoding="utf-8"), "reviewed\n")
            self.assertTrue(predictable.is_symlink())
            self.assertEqual(outside.read_text(encoding="utf-8"), "unchanged\n")


if __name__ == "__main__":
    unittest.main()
