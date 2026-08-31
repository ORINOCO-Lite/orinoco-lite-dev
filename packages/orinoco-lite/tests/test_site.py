from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite import site
from orinoco_lite.config import load_config_path
from orinoco_lite.errors import ConfigurationError, DriverError


CONFIG = """\
contract_version: 2
site:
  name: Hugo compatibility fixture
  base_url: https://example.invalid/orinoco/
"""


class HugoCompatibilityTests(unittest.TestCase):
    def test_framework_copy_and_template_roots_reject_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            external = root / "external"
            external.mkdir()
            (external / "secret.txt").write_text("secret\n", encoding="utf-8")

            static_source = root / "static-source"
            static_source.symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(DriverError, "cannot be a symlink"):
                site._copy_tree(static_source, root / "static-output")
            self.assertFalse((root / "static-output/secret.txt").exists())

            template_source = root / "template-source"
            template_source.symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(DriverError, "cannot be a symlink"):
                site._render_template_tree(
                    template_source,
                    root / "template-output",
                    site_data={},
                    records={},
                    route_for_record=lambda _pid: "",
                )

    def test_structured_site_data_renders_template_owned_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(
                CONFIG
                + "paths:\n"
                + "  editorial: site-specific/content/pages\n"
                + "  framework: .orinoco-lite/site\n"
                + "  records: site-specific/metadata/records\n"
                + "  site: site-specific\n",
                encoding="utf-8",
            )
            site_root = root / "site-specific"
            site_root.mkdir()
            (site_root / "site.yaml").write_text(
                "version: 1\n"
                "record_prefix: 'example:'\n"
                "identity:\n"
                "  title: Example Site\n"
                "  description: Structured example\n",
                encoding="utf-8",
            )
            (site_root / "projection-templates").mkdir()
            (site_root / "projection-tools").mkdir()
            (site_root / "projection-templates/homepage.md.j2").write_text(
                "homepage\n", encoding="utf-8"
            )
            (site_root / "projection-templates/project.md.j2").write_text(
                "project\n", encoding="utf-8"
            )
            (site_root / "projection-tools/graph.py").write_text(
                "print('{}')\n", encoding="utf-8"
            )
            (site_root / "projection.yaml").write_text(
                "version: 2\n"
                "routing:\n"
                "  strip_prefix: 'example:'\n"
                "homepage:\n"
                "  pid: example:site-root\n"
                "  template: site-specific/projection-templates/homepage.md.j2\n"
                "pages:\n"
                "  xyzri:XYZProject:\n"
                "    template: site-specific/projection-templates/project.md.j2\n"
                "unrendered_classes: []\n"
                "graph:\n"
                "  producer: site-specific/projection-tools/graph.py\n"
                "  node_classes: []\n"
                "  relationship_fields: []\n",
                encoding="utf-8",
            )
            (site_root / "static").mkdir(parents=True)
            records = site_root / "metadata/records/XYZProject"
            records.mkdir(parents=True)
            (records / "example.yaml").write_text(
                "pid: example:projects/example\n"
                "schema_type: xyzri:XYZProject\n"
                "formatted_name: Example Project\n",
                encoding="utf-8",
            )
            framework = root / ".orinoco-lite/site"
            (framework / "config-templates").mkdir(parents=True)
            (framework / "content-templates/section").mkdir(parents=True)
            (framework / "static-templates").mkdir(parents=True)
            (framework / "config-templates/hugo.toml.j2").write_text(
                "title = {{ site.identity.title | json_string }}\n",
                encoding="utf-8",
            )
            (framework / "content-templates/section/_index.md.j2").write_text(
                "---\ntitle: {{ site.identity.title }}\n---\n"
                "[{{ record_label('example:projects/example') }}]"
                "({{ record_ref('example:projects/example') }})\n",
                encoding="utf-8",
            )
            (framework / "static-templates/site.webmanifest.j2").write_text(
                '{"name": {{ site.identity.title | json_string }}}\n',
                encoding="utf-8",
            )
            assembly = root / "build/assembly"
            workspace = load_config_path(config)

            site._assemble(workspace, root / "runtime", assembly)

            self.assertEqual(
                'title = "Example Site"\n',
                (assembly / "config/con/hugo.toml").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "title: Example Site",
                (assembly / "content/section/_index.md").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "[Example Project]({{< ref \"/projects/example\" >}})",
                (assembly / "content/section/_index.md").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                '{"name": "Example Site"}\n',
                (assembly / "static/site.webmanifest").read_text(encoding="utf-8"),
            )

    def test_structured_site_prefix_must_match_projection_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(
                CONFIG
                + "paths:\n"
                + "  framework: .orinoco-lite/site\n"
                + "  records: site-specific/metadata/records\n"
                + "  site: site-specific\n",
                encoding="utf-8",
            )
            site_root = root / "site-specific"
            (site_root / "metadata/records").mkdir(parents=True)
            (site_root / "projection-templates").mkdir()
            (site_root / "projection-tools").mkdir()
            (site_root / "site.yaml").write_text(
                "version: 1\n"
                "record_prefix: 'wrong:'\n"
                "identity:\n"
                "  title: Example Site\n"
                "  description: Structured example\n",
                encoding="utf-8",
            )
            for relative in ("homepage.md.j2", "project.md.j2"):
                (site_root / "projection-templates" / relative).write_text(
                    "fixture\n", encoding="utf-8"
                )
            (site_root / "projection-tools/graph.py").write_text(
                "print('{}')\n", encoding="utf-8"
            )
            (site_root / "projection.yaml").write_text(
                "version: 2\n"
                "routing:\n"
                "  strip_prefix: 'example:'\n"
                "homepage:\n"
                "  pid: example:site-root\n"
                "  template: site-specific/projection-templates/homepage.md.j2\n"
                "pages:\n"
                "  xyzri:XYZProject:\n"
                "    template: site-specific/projection-templates/project.md.j2\n"
                "unrendered_classes: []\n"
                "graph:\n"
                "  producer: site-specific/projection-tools/graph.py\n"
                "  node_classes: []\n"
                "  relationship_fields: []\n",
                encoding="utf-8",
            )
            framework = root / ".orinoco-lite/site/content-templates"
            framework.mkdir(parents=True)
            (framework / "_index.md.j2").write_text("home\n", encoding="utf-8")
            workspace = load_config_path(config)

            with self.assertRaisesRegex(ConfigurationError, "record_prefix"):
                site._render_site_surfaces(
                    workspace,
                    root / ".orinoco-lite/site",
                    root / "build/assembly",
                )

    def test_assembly_copies_site_static_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(
                CONFIG
                + "paths:\n"
                + "  site: site-specific\n",
                encoding="utf-8",
            )
            source = root / "site-specific/static/example.txt"
            source.parent.mkdir(parents=True)
            source.write_text("static\n", encoding="utf-8")
            assembly = root / "build/assembly"
            workspace = load_config_path(config)

            site._assemble(workspace, root / "runtime", assembly)
            self.assertEqual(
                (assembly / "static/example.txt").read_text(encoding="utf-8"),
                "static\n",
            )

    def test_layout_override_applies_only_from_site_specific(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(CONFIG, encoding="utf-8")
            framework = root / ".orinoco-lite/site/layouts"
            framework.mkdir(parents=True)
            (framework / "term.html").write_text("template\n", encoding="utf-8")
            override = root / "site-specific/overrides/layouts/term.html"
            override.parent.mkdir(parents=True)
            override.write_text("downstream\n", encoding="utf-8")
            forbidden = root / "extensions/layouts/term.html"
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text("extension\n", encoding="utf-8")
            assembly = root / "build/assembly"

            site._assemble(load_config_path(config), root / "runtime", assembly)

            self.assertEqual(
                "downstream\n",
                (assembly / "layouts/term.html").read_text(encoding="utf-8"),
            )
            self.assertNotIn("extension", (assembly / "layouts/term.html").read_text())

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
                        patch.object(site, "_assemble"),
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
