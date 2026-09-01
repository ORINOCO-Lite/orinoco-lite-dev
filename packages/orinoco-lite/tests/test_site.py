from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite import site
from orinoco_lite.config import load_config_path
from orinoco_lite.errors import ConfigurationError, DriverError, IntegrityError


CONFIG = """\
contract_version: 2
"""


def _write_site_data(
    root: Path,
    *,
    title: str = "Hugo compatibility fixture",
    prefix: str = "xyzrins:",
    base_url: str = "https://example.invalid/orinoco/",
) -> None:
    site_root = root / "site-specific"
    site_root.mkdir(exist_ok=True)
    (site_root / "site.yaml").write_text(
        "version: 1\n"
        f"record_prefix: {prefix!r}\n"
        "identity:\n"
        f"  title: {title}\n"
        "  description: A site-build fixture.\n"
        f"  base_url: {base_url}\n",
        encoding="utf-8",
    )


def _presentation(root: Path) -> Path:
    upstream = root / "presentation" / "www-from-model"
    theme = upstream / "themes" / "congo"
    theme.mkdir(parents=True, exist_ok=True)
    (theme / "LICENSE").write_text("Congo MIT\n", encoding="utf-8")
    (theme / "theme.toml").write_text("name = 'Congo'\n", encoding="utf-8")
    templates = upstream / "page_templates"
    templates.mkdir(parents=True, exist_ok=True)
    for name in (
        "dataset",
        "homepage",
        "instrument",
        "objective",
        "page",
        "person",
        "project",
        "publication",
        "topic",
    ):
        (templates / f"{name}.md.j2").write_text(
            f"{name}\n", encoding="utf-8"
        )
    (upstream / "code").mkdir(exist_ok=True)
    (upstream / "code" / "pool2graph.py").write_text(
        "print('{\"nodes\": [], \"edges\": []}')\n",
        encoding="utf-8",
    )
    materialized = root / ".orinoco-lite" / "materialized-presentation"
    materialized.mkdir(parents=True, exist_ok=True)
    (materialized / "LICENSE").write_text("Template MIT\n", encoding="utf-8")
    return upstream


class HugoCompatibilityTests(unittest.TestCase):
    def test_composition_and_template_roots_reject_symlinks(self) -> None:
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
                )

    def test_composition_uses_overlay_and_excludes_upstream_content_and_git(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "orinoco.yaml").write_text(CONFIG, encoding="utf-8")
            _write_site_data(root)
            presentation = _presentation(root)
            for relative, value in (
                ("content/german.md", "German editorial content\n"),
                ("layouts/term.html", "upstream layout\n"),
                ("static/upstream-identity.png", "branded image\n"),
                ("static/graph.js", "/annex/objects/MD5E-s12--graph.js\n"),
                ("layouts/.git/config", "must not ship\n"),
            ):
                path = presentation / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value, encoding="utf-8")
            materialized = (
                root
                / ".orinoco-lite/materialized-presentation/upstream/static/graph.js"
            )
            materialized.parent.mkdir(parents=True)
            materialized.write_text("const graphClient = true;\n", encoding="utf-8")
            assembly = root / "build/assembly"

            site._assemble(
                load_config_path(root / "orinoco.yaml"),
                root / "runtime",
                assembly,
                presentation=presentation,
            )

            self.assertEqual(
                (assembly / "layouts/term.html").read_text(encoding="utf-8"),
                "upstream layout\n",
            )
            self.assertEqual(
                (assembly / "static/graph.js").read_text(encoding="utf-8"),
                "const graphClient = true;\n",
            )
            self.assertFalse((assembly / "content/german.md").exists())
            self.assertFalse((assembly / "static/upstream-identity.png").exists())
            self.assertFalse(any(path.name == ".git" for path in assembly.rglob("*")))

            materialized.unlink()
            with self.assertRaisesRegex(
                DriverError, "Materialized presentation assets are missing"
            ):
                site._assemble(
                    load_config_path(root / "orinoco.yaml"),
                    root / "runtime",
                    root / "build/unmaterialized",
                    presentation=presentation,
                )

    def test_site_data_renders_adapters_and_upstream_section_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(
                CONFIG
                + "paths:\n"
                + "  editorial: site-specific/content/pages\n"
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
                "  description: Structured example\n"
                "  base_url: https://example.invalid/example/\n",
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
            adapter = root / ".orinoco-lite/presentation"
            (adapter / "config-templates").mkdir(parents=True)
            (adapter / "static-templates").mkdir(parents=True)
            (adapter / "config-templates/hugo.toml.j2").write_text(
                "title = {{ site.identity.title | json_string }}\n",
                encoding="utf-8",
            )
            (adapter / "static-templates/site.webmanifest.j2").write_text(
                '{"name": {{ site.identity.title | json_string }}}\n',
                encoding="utf-8",
            )
            assembly = root / "build/assembly"
            workspace = load_config_path(config)
            presentation = _presentation(root)
            section = presentation / "content/section/_index.md"
            section.parent.mkdir(parents=True)
            section.write_text(
                "---\n"
                "title: Upstream Section\n"
                "params:\n"
                "  filter: true\n"
                "---\n\n"
                "German upstream editorial body.\n",
                encoding="utf-8",
            )

            site._assemble(
                workspace,
                root / "runtime",
                assembly,
                presentation=presentation,
            )

            self.assertEqual(
                'title = "Example Site"\n',
                (assembly / "config/con/hugo.toml").read_text(encoding="utf-8"),
            )
            section_output = (assembly / "content/section/_index.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("filter: true", section_output)
            self.assertNotIn("German upstream editorial body", section_output)
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
                "  description: Structured example\n"
                "  base_url: https://example.invalid/example/\n",
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
            adapter = root / ".orinoco-lite/presentation"
            templates = adapter / "content-templates"
            templates.mkdir(parents=True)
            (templates / "_index.md.j2").write_text("home\n", encoding="utf-8")
            workspace = load_config_path(config)

            with self.assertRaisesRegex(ConfigurationError, "record_prefix"):
                site._render_site_surfaces(
                    workspace,
                    adapter,
                    _presentation(root),
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
            _write_site_data(root)
            assembly = root / "build/assembly"
            workspace = load_config_path(config)

            site._assemble(
                workspace,
                root / "runtime",
                assembly,
                presentation=_presentation(root),
            )
            self.assertEqual(
                (assembly / "static/example.txt").read_text(encoding="utf-8"),
                "static\n",
            )

    def test_layout_override_applies_only_from_site_specific(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "orinoco.yaml"
            config.write_text(CONFIG, encoding="utf-8")
            _write_site_data(root)
            adapter = root / ".orinoco-lite/presentation/layouts"
            adapter.mkdir(parents=True)
            (adapter / "term.html").write_text("template\n", encoding="utf-8")
            override = root / "site-specific/overrides/layouts/term.html"
            override.parent.mkdir(parents=True)
            override.write_text("downstream\n", encoding="utf-8")
            forbidden = root / "extensions/layouts/term.html"
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text("extension\n", encoding="utf-8")
            assembly = root / "build/assembly"

            site._assemble(
                load_config_path(config),
                root / "runtime",
                assembly,
                presentation=_presentation(root),
            )

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
            _write_site_data(root)
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

    def test_site_adapter_prefers_explicit_engine_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime_adapter = root / "runtime/drivers/adapt_pages.py"
            runtime_adapter.parent.mkdir(parents=True)
            runtime_adapter.write_text("# released\n", encoding="utf-8")
            candidate_adapter = root / "engine/tools/adapt_upstream_pages.py"
            candidate_adapter.parent.mkdir(parents=True)
            candidate_adapter.write_text("# candidate\n", encoding="utf-8")

            with patch.object(
                site, "development_engine_root", return_value=root / "engine"
            ):
                self.assertEqual(
                    site._site_adapter(root / "runtime"), candidate_adapter
                )
            with patch.object(site, "development_engine_root", return_value=None):
                self.assertEqual(
                    site._site_adapter(root / "runtime"), runtime_adapter
                )

    def test_site_adapter_requires_candidate_driver(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(
                site, "development_engine_root", return_value=root / "engine"
            ):
                with self.assertRaisesRegex(IntegrityError, "no site adapter"):
                    site._site_adapter(root / "runtime")

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
            _write_site_data(root)
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
