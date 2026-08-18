from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite import site
from orinoco_lite.assets import Asset
from orinoco_lite.config import load_config_path
from orinoco_lite.errors import ConfigurationError, DriverError
from orinoco_lite.integrity import sha256_file


CONFIG = """\
contract_version: 2
site:
  name: Hugo compatibility fixture
  base_url: https://example.invalid/orinoco/
"""


class HugoCompatibilityTests(unittest.TestCase):
    def test_assembly_respects_configured_asset_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(
                CONFIG
                + "paths:\n"
                + "  assets: custom/assets\n",
                encoding="utf-8",
            )
            source = root / "custom/assets/files/example.txt"
            source.parent.mkdir(parents=True)
            source.write_text("asset\n", encoding="utf-8")
            assembly = root / "build/assembly"
            asset = Asset(
                source="custom/assets/files/example.txt",
                sha256=sha256_file(source),
                size=source.stat().st_size,
                availability="available",
                object_url=None,
            )
            workspace = load_config_path(config)

            with patch.object(
                site,
                "load_assets",
                return_value=(
                    {asset.source: asset},
                    {"site/static/example.txt": asset.source},
                ),
            ):
                report = site._assemble(workspace, root / "runtime", assembly)

            self.assertEqual(report["copied_assets"], 1)
            self.assertEqual(
                (assembly / "assets/example.txt").read_text(encoding="utf-8"),
                "asset\n",
            )
            self.assertEqual(
                (assembly / "static/example.txt").read_text(encoding="utf-8"),
                "asset\n",
            )

    def test_build_base_url_accepts_host_neutral_and_public_forms(self) -> None:
        cases = {
            "/": "/",
            "/project": "/project/",
            "/project/": "/project/",
            "https://con.github.io/example": "https://con.github.io/example/",
            "http://127.0.0.1:8766/example/": (
                "http://127.0.0.1:8766/example/"
            ),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(site.normalize_build_base_url(value), expected)

    def test_build_base_url_rejects_ambiguous_or_unsafe_forms(self) -> None:
        for value in (
            "",
            "project",
            "//example.test/project/",
            "ftp://example.test/project/",
            "/../escape/",
            "/%2e%2e/escape/",
            "/project/?query=true",
            "/project/#fragment",
            "/project\\escape/",
            " /project/",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    site.normalize_build_base_url(value)

    def test_build_passes_host_neutral_and_public_urls_without_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(CONFIG, encoding="utf-8")
            runtime = root / "runtime"
            adapter = runtime / "drivers" / "adapt_pages.py"
            adapter.parent.mkdir(parents=True)
            adapter.write_text("# test adapter\n", encoding="utf-8")

            for name, base_url, expected_edit_url in (
                ("local", "/", "/edit/"),
                (
                    "pages",
                    "https://con.github.io/example/",
                    "https://con.github.io/example/edit/",
                ),
            ):
                with self.subTest(name=name):
                    commands: list[list[str]] = []

                    def run(command, *, cwd):
                        normalized = [str(item) for item in command]
                        commands.append(normalized)
                        if normalized[0] == "hugo":
                            destination = Path(
                                normalized[normalized.index("--destination") + 1]
                            )
                            destination.mkdir(parents=True)
                            (destination / "index.html").write_text(
                                "built\n", encoding="utf-8"
                            )
                        return ""

                    destination = root / "build" / name
                    with (
                        patch.object(site, "_preflight_hugo"),
                        patch.object(
                            site,
                            "_assemble",
                            return_value={
                                "copied_assets": 0,
                                "copied_links": 0,
                                "hydrated_assets": 0,
                            },
                        ),
                        patch.object(site, "_run", side_effect=run),
                        patch.object(
                            site,
                            "bind_editor",
                            return_value={"version": 2},
                        ),
                    ):
                        report = site.build_site(
                            config,
                            runtime,
                            destination,
                            base_url,
                        )

                    self.assertEqual(report["base_url"], base_url)
                    hugo = commands[0]
                    self.assertEqual(hugo[hugo.index("--baseURL") + 1], base_url)
                    adapter_command = commands[1]
                    self.assertEqual(
                        adapter_command[
                            adapter_command.index("--base-path") + 1
                        ],
                        "/" if name == "local" else "/example/",
                    )
                    self.assertEqual(
                        adapter_command[adapter_command.index("--edit-url") + 1],
                        expected_edit_url,
                    )

    def test_supported_extended_hugo_is_accepted(self) -> None:
        outputs = (
            "hugo v0.154.5+extended darwin/arm64 BuildDate=unknown "
            "VendorInfo=conda-forge",
            "hugo v0.154.5-conda-forge+extended linux/amd64 "
            "BuildDate=unknown VendorInfo=conda-forge",
        )
        for output in outputs:
            with self.subTest(output=output):
                version = site._require_compatible_hugo(
                    output,
                    ">=0.154,<0.155",
                    runtime_release="0.1.7",
                )
                self.assertEqual(str(version), "0.154.5")

    def test_unsupported_or_malformed_hugo_is_rejected(self) -> None:
        cases = (
            (
                "too old",
                "hugo v0.153.9+extended linux/amd64",
                "requires Hugo >=0.154,<0.155; found 0.153.9",
            ),
            (
                "too new",
                "hugo v0.155.0-conda-forge+extended linux/amd64",
                "requires Hugo >=0.154,<0.155; found 0.155.0",
            ),
            (
                "standard edition",
                "hugo v0.154.5-conda-forge linux/amd64",
                "requires Hugo Extended",
            ),
            (
                "malformed",
                "hugo v0.154.5-+extended linux/amd64",
                "Could not determine Hugo version",
            ),
        )
        for label, output, message in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(DriverError, message):
                    site._require_compatible_hugo(
                        output,
                        ">=0.154,<0.155",
                        runtime_release="0.1.7",
                    )

    def test_build_preflight_preserves_existing_outputs_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
            destination = root / "build" / "site"
            destination.mkdir(parents=True)
            (destination / "index.html").write_text("existing\n", encoding="utf-8")
            assembly = root / "build" / "assembly"
            assembly.mkdir()
            (assembly / "sentinel").write_text("existing\n", encoding="utf-8")
            runtime = root / "runtime"
            runtime.mkdir()
            manifest = SimpleNamespace(
                compatibility={"hugo": ">=0.154,<0.155"},
                release="0.1.3",
            )
            with (
                patch.object(site, "load_runtime_manifest", return_value=manifest),
                patch.object(
                    site,
                    "_run",
                    return_value="hugo v0.155.0+extended linux/amd64",
                ) as run,
            ):
                with self.assertRaisesRegex(DriverError, "found 0.155.0"):
                    site.build_site(
                        root / "orinoco.yaml",
                        runtime,
                        destination,
                        "https://example.invalid/orinoco/",
                    )
            run.assert_called_once_with(["hugo", "version"], cwd=root.resolve())
            self.assertEqual(
                (destination / "index.html").read_text(encoding="utf-8"),
                "existing\n",
            )
            self.assertEqual(
                (assembly / "sentinel").read_text(encoding="utf-8"),
                "existing\n",
            )


if __name__ == "__main__":
    unittest.main()
