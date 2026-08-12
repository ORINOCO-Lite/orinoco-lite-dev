from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

import yaml


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


PAGES = load_tool("build_con_pages")


def write_editor(root: Path) -> None:
    root.mkdir(parents=True)
    root.joinpath("index.html").write_text(
        "<!doctype html><title>Patch editor</title>\n",
        encoding="utf-8",
    )
    root.joinpath("config.json").write_text(
        json.dumps(
            {
                "class_url": "dlschemas_owl.ttl",
                "data_url": "records.ttl",
                "external_config_url": "config_default_xyzri.yaml",
                "review_bundle_catalog": "record-sources.json",
                "review_bundle_mode": "patch-download",
                "shapes_url": "dlschemas_shacl.ttl",
                "use_service": False,
                "use_token": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    for filename in (
        "config_default_xyzri.yaml",
        "dlschemas_owl.ttl",
        "dlschemas_shacl.ttl",
        "records.ttl",
    ):
        root.joinpath(filename).write_text("# fixture\n", encoding="utf-8")
    contract = {
        "authentication": "none",
        "backend": "none",
        "mode": "patch-download",
        "version": 1,
        **PAGES.expected_editor_metadata(),
        "input_sha256": PAGES.editor_input_digest(root),
    }
    root.joinpath("editor-contract.json").write_text(
        json.dumps(contract, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_auditable_site(root: Path, *, local_url: bool = False) -> None:
    root.mkdir(parents=True)
    root.joinpath("index.html").write_text(
        "<!doctype html><title>CON</title>\n"
        '<a href="https://con.github.io/orinoco-lite-dev/edit/'
        '?sh%3ANodeShape=dlthings%3AThing&pid=xyzrins%3A.&edit=true">'
        "Edit</a>\n",
        encoding="utf-8",
    )
    root.joinpath(".nojekyll").write_bytes(b"")
    editor = root / "edit"
    write_editor(editor)
    editor.joinpath("record-sources.json").write_text(
        json.dumps(PAGES.canonical_record_catalog(), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if local_url:
        root.joinpath("leak.js").write_text(
            'fetch("http://127.0.0.1:8111/api")\n', encoding="utf-8"
        )


class CONPagesTests(unittest.TestCase):
    def test_pages_url_requires_credential_free_https(self) -> None:
        self.assertEqual(
            PAGES.normalized_pages_url("https://con.github.io/orinoco-lite-dev"),
            (
                "https://con.github.io/orinoco-lite-dev/",
                "/orinoco-lite-dev/",
            ),
        )
        for value in (
            "http://con.github.io/orinoco-lite-dev/",
            "https://user@example.test/orinoco-lite-dev/",
            "https://example.test/orinoco-lite-dev/?token=secret",
            "https://example.test/../escape/",
        ):
            with self.subTest(value=value):
                with self.assertRaises((PAGES.BuildError, ValueError)):
                    PAGES.normalized_pages_url(value)

    def test_editor_contract_rejects_service_mode_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            editor = Path(temporary) / "editor"
            write_editor(editor)
            contract = editor / "editor-contract.json"
            value = json.loads(contract.read_text(encoding="utf-8"))
            value["backend"] = "dump-things"
            contract.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(PAGES.BuildError, "no backend"):
                PAGES.validate_editor_source(editor)

            value["backend"] = "none"
            contract.write_text(json.dumps(value), encoding="utf-8")
            editor.joinpath("unsafe").symlink_to(Path(temporary))
            with self.assertRaisesRegex(PAGES.BuildError, "symlink"):
                PAGES.validate_editor_source(editor)

    def test_editor_config_rejects_service_and_token_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            editor = Path(temporary) / "editor"
            write_editor(editor)
            config_path = editor / "config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["use_service"] = True
            config_path.write_text(json.dumps(config), encoding="utf-8")
            contract_path = editor / "editor-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["input_sha256"] = PAGES.editor_input_digest(editor)
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(PAGES.BuildError, "disable service/token"):
                PAGES.validate_editor_source(editor)

    def test_editor_config_rejects_remote_or_missing_static_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            editor = Path(temporary) / "editor"
            write_editor(editor)
            config_path = editor / "config.json"
            contract_path = editor / "editor-contract.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["data_url"] = "https://example.test/records.ttl"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["input_sha256"] = PAGES.editor_input_digest(editor)
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(PAGES.BuildError, "normalized relative"):
                PAGES.validate_editor_source(editor)

            config["data_url"] = "missing.ttl"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            contract["input_sha256"] = PAGES.editor_input_digest(editor)
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(PAGES.BuildError, "is missing"):
                PAGES.validate_editor_source(editor)

    def test_editor_contract_rejects_stale_inputs_and_gitlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            editor = Path(temporary) / "editor"
            write_editor(editor)
            editor.joinpath("index.html").write_text(
                "<!doctype html><title>changed</title>\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(PAGES.BuildError, "digest is stale"):
                PAGES.validate_editor_source(editor)

            write_editor(Path(temporary) / "fresh")
            fresh = Path(temporary) / "fresh"
            contract_path = fresh / "editor-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["site_commit"] = "0" * 40
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(PAGES.BuildError, "pinned pool UI"):
                PAGES.validate_editor_source(fresh)

    def test_public_audit_rejects_loopback_service_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "site"
            write_auditable_site(destination, local_url=True)
            with self.assertRaisesRegex(PAGES.BuildError, "local URL"):
                PAGES.audit_pages_artifact(
                    destination,
                    PAGES.DEFAULT_BASE_URL,
                    require_editor=True,
                )

    def test_public_audit_rejects_symlinks_and_token_shaped_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "site"
            write_auditable_site(destination)
            destination.joinpath("outside").symlink_to(Path(temporary))
            destination.joinpath("secret.js").write_text(
                'const token = "ghp_abcdefghijklmnopqrstuvwxyz123456";\n',
                encoding="utf-8",
            )
            with self.assertRaises(PAGES.BuildError) as context:
                PAGES.audit_pages_artifact(
                    destination,
                    PAGES.DEFAULT_BASE_URL,
                    require_editor=True,
                )
            self.assertIn("public artifact symlink", str(context.exception))
            self.assertIn("GitHub token-shaped value", str(context.exception))

    def test_public_audit_rejects_catalog_drift_and_custom_domain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "site"
            write_auditable_site(destination)
            catalog_path = destination / "edit/record-sources.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["records"] = []
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            destination.joinpath("CNAME").write_text(
                "www.centerforopenneuroscience.org\n", encoding="utf-8"
            )
            with self.assertRaises(PAGES.BuildError) as context:
                PAGES.audit_pages_artifact(
                    destination,
                    PAGES.DEFAULT_BASE_URL,
                    require_editor=True,
                )
            self.assertIn("does not match canonical YAML", str(context.exception))
            self.assertIn("custom-domain", str(context.exception))

    def test_publication_metadata_is_bound_to_payload_and_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "site"
            write_auditable_site(destination)
            payload_entries, site_entries = PAGES.publication_manifest_entries(
                destination
            )
            publication = {
                "base_path": "/orinoco-lite-dev/",
                "base_url": PAGES.DEFAULT_BASE_URL,
                "editor": "patch-download",
                "files": len(payload_entries),
                "parent_commit": PAGES.git_commit(ROOT),
                "payload_manifest_sha256": PAGES.manifest_digest(payload_entries),
                "site_commit": PAGES.git_commit(PAGES.SITE),
                "site_manifest_sha256": PAGES.manifest_digest(site_entries),
                "version": 1,
            }
            PAGES.write_json(destination / PAGES.PUBLICATION_NAME, publication)
            self.assertEqual(
                PAGES.publication_violations(
                    destination,
                    PAGES.DEFAULT_BASE_URL,
                    "patch-download",
                ),
                [],
            )

            publication["parent_commit"] = "0" * 40
            PAGES.write_json(destination / PAGES.PUBLICATION_NAME, publication)
            self.assertIn(
                "site: publication.json parent_commit is stale",
                PAGES.publication_violations(
                    destination,
                    PAGES.DEFAULT_BASE_URL,
                    "patch-download",
                ),
            )

    def test_build_embeds_editor_and_exact_record_catalog(self) -> None:
        build_root = ROOT / "build"
        build_root.mkdir(exist_ok=True)
        with (
            tempfile.TemporaryDirectory(dir=build_root) as temporary,
            tempfile.TemporaryDirectory() as editor_temporary,
        ):
            destination = Path(temporary) / "site"
            editor = Path(editor_temporary) / "editor"
            write_editor(editor)

            def build_site(path: Path, base_url: str):
                self.assertEqual(base_url, PAGES.DEFAULT_BASE_URL)
                self.assertEqual(
                    os.environ["SHACL_VUE_URL"],
                    "https://con.github.io/orinoco-lite-dev/edit/",
                )
                path.mkdir(parents=True)
                path.joinpath("index.html").write_text(
                    "<!doctype html><title>CON</title>\n"
                    '<a href="https://con.github.io/orinoco-lite-dev/edit/'
                    "?sh%3ANodeShape=dlthings%3AThing&pid=xyzrins%3A."
                    '&edit=true">Edit</a>\n',
                    encoding="utf-8",
                )
                entries = PAGES.manifest_entries(path)
                return {"manifest_sha256": PAGES.manifest_digest(entries)}

            catalog = {
                "format": "con-static-record-sources",
                "records": [{"pid": "xyzrins:."}],
                "site_commit": "b" * 40,
                "version": 1,
            }
            with (
                mock.patch.object(PAGES, "build_site", side_effect=build_site),
                mock.patch.object(
                    PAGES, "canonical_record_catalog", return_value=catalog
                ),
            ):
                report = PAGES.build_pages_artifact(
                    destination,
                    PAGES.DEFAULT_BASE_URL,
                    editor_source=editor,
                    require_editor=True,
                )

            self.assertEqual(report["editor"], "patch-download")
            self.assertTrue((destination / ".nojekyll").is_file())
            self.assertEqual(
                json.loads(
                    (destination / "edit/record-sources.json").read_text(
                        encoding="utf-8"
                    )
                ),
                catalog,
            )
            publication = json.loads(
                (destination / "publication.json").read_text(encoding="utf-8")
            )
            _, site_entries = PAGES.publication_manifest_entries(destination)
            self.assertEqual(
                publication["site_manifest_sha256"],
                PAGES.manifest_digest(site_entries),
            )
            self.assertRegex(publication["payload_manifest_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(
                destination.parent.joinpath("site-pages-manifest.sha256").is_file()
            )

    def test_pixi_pages_tasks_build_con_and_require_editor(self) -> None:
        manifest = tomllib.loads((ROOT / "pixi.toml").read_text(encoding="utf-8"))
        tasks = manifest["tasks"]
        self.assertIn("build-pages-editor", tasks["build-pages"]["depends-on"])
        self.assertIn("verify-pages-editor", tasks["verify-pages"]["depends-on"])
        self.assertIn(
            "build_con_pages.py --require-editor", tasks["build-pages"]["cmd"]
        )
        self.assertIn("--repeat-destination", tasks["verify-pages"]["cmd"])
        self.assertNotIn("build_upstream_site", tasks["build-pages"]["cmd"])
        self.assertIn("build-pages", tasks["test-browser"]["depends-on"])
        self.assertIn("verify-pages", tasks["test-pages-browser"]["depends-on"])
        self.assertEqual(
            tasks["test-pages-browser"]["env"]["PLAYWRIGHT_STATIC_ONLY"],
            "1",
        )

    def test_workflow_never_deploys_pull_request_code(self) -> None:
        workflow = ROOT / ".github/workflows/con-pages-preview.yml"
        text = workflow.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        build = parsed["jobs"]["build"]
        deploy = parsed["jobs"]["deploy"]
        self.assertEqual(build["permissions"], {"contents": "read"})
        self.assertEqual(
            deploy["permissions"],
            {"contents": "read", "id-token": "write", "pages": "write"},
        )
        self.assertNotIn("pull_request", deploy["if"])
        self.assertFalse(
            any(
                str(step.get("uses", "")).startswith("actions/checkout@")
                for step in deploy["steps"]
            )
        )
        self.assertIn("pull_request:", text)
        self.assertIn("pixi run test-pages-browser", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("cache-write: ${{ github.event_name != 'pull_request' }}", text)
        self.assertIn("submodules: recursive", text)
        self.assertIn("github.event_name == 'push'", text)
        self.assertNotIn("github.event_name == 'pull_request' ||", text)
        for action in (
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "prefix-dev/setup-pixi@f00437f565399d418b0acc85936d12c1fb668347",
            "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9",
            "actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d",
            "actions/deploy-pages@cd2ce8fcbc39b97be8ca5fce6e763baed58fa128",
        ):
            self.assertIn(action, text)

    def test_workflow_fetches_and_verifies_accepted_checkpoints(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/con-pages-preview.yml").read_text(
                encoding="utf-8"
            )
        )
        steps = workflow["jobs"]["build"]["steps"]
        names = [step["name"] for step in steps]
        checkpoint_index = names.index(
            "Verify the accepted clean-migration checkpoints"
        )
        self.assertLess(
            names.index("Check out the pinned recursive source tree"),
            checkpoint_index,
        )
        self.assertLess(checkpoint_index, names.index("Run focused contracts"))

        command = steps[checkpoint_index]["run"]
        self.assertIn(
            "parent_checkpoint=f54cf5fdb2b5ae4bf03fe6939246316fd9ec818d",
            command,
        )
        self.assertIn(
            "site_checkpoint=a122e506de9e4a13473edbe8d74a950d74032a16",
            command,
        )
        self.assertEqual(
            command.count("refs/heads/codex/clean-migration:${checkpoint_ref}"),
            2,
        )
        self.assertEqual(command.count("--no-recurse-submodules"), 2)
        self.assertIn(
            'test "$(git rev-parse "${checkpoint_ref}")" = '
            '"${parent_checkpoint}"',
            command,
        )
        self.assertIn(
            'rev-parse "${checkpoint_ref}")" = "${site_checkpoint}"',
            command,
        )


if __name__ == "__main__":
    unittest.main()
