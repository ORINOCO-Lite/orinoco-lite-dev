from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POOL_UI = ROOT / "submodules" / "pool.psychoinformatics.de-ui"


class LocalStackContractTests(unittest.TestCase):
    def test_pixi_exposes_all_local_services(self) -> None:
        pixi = (ROOT / "pixi.toml").read_text(encoding="utf-8")
        self.assertIn(
            'serve = { depends-on = ["build", "prepare-local-stack"], '
            'cmd = "tools/serve_local_stack.sh" }',
            pixi,
        )
        self.assertIn(
            'prepare-local-stack = { depends-on = ["checkout-submodules", '
            '"build-pool-ui"], cmd = "python3 tools/prepare_local_stack.py" }',
            pixi,
        )
        self.assertIn(
            'refresh-local-pool = { depends-on = ["checkout-submodules", '
            '"build-pool-ui"], cmd = "REFRESH_UPSTREAM_POOL=1 python3 '
            'tools/prepare_local_stack.py" }',
            pixi,
        )
        self.assertIn(
            'serve-shacl-vue = { depends-on = ["prepare-local-stack"], '
            'cmd = "python3 -m http.server 3000 --directory '
            'build/local-stack/ui" }',
            pixi,
        )
        self.assertIn(
            'build = { depends-on = ["checkout-submodules"], cmd = '
            '"python3 tools/build_con_site.py --repeat-destination '
            'build/con-site-repeat" }',
            pixi,
        )
        self.assertIn(
            'serve-static = { depends-on = ["build"], cmd = '
            '"python3 -m http.server 8767 --directory build/con-site" }',
            pixi,
        )
        for task in (
            "build-upstream",
            "serve-upstream",
            "render-con-projection",
            "update-con-projection",
            "verify-con-projection",
            "prepare-local-stack",
            "refresh-local-pool",
            "serve-dump-things",
            "serve-git-annex",
            "seed-local-pool",
            "serve-shacl-vue",
            "check-local-stack",
        ):
            self.assertIn(f"{task} =", pixi)

    def test_pool_ui_points_at_local_upstream_services(self) -> None:
        config = (POOL_UI / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("use_service: true", config)
        self.assertIn("use_token: true", config)
        self.assertIn("http://127.0.0.1:8111/protected/", config)
        self.assertIn("http://127.0.0.1:8111/public/", config)
        self.assertIn("http://127.0.0.1:8122/git-annex", config)
        self.assertNotIn("https://hub.psychoinformatics.de/git-annex-p2phttp", config)

        external = (POOL_UI / "config_default_xyzri.yaml").read_text(encoding="utf-8")
        self.assertIn("data_url: ''", external)
        self.assertIn("get-record: 'record?pid={curie}&format=ttl'", external)
        self.assertIn("xyzrins:", external)

    def test_schema_data_asset_is_not_a_demo_record_bundle(self) -> None:
        data = (POOL_UI / "dlschemas_data.ttl").read_text(encoding="utf-8")
        self.assertNotIn(" a xyzri:", data)
        owl = (POOL_UI / "dlschemas_owl.ttl").read_text(encoding="utf-8")
        self.assertIn("XYZDataset", owl)

    def test_pixi_pins_local_dump_things_runtime(self) -> None:
        pixi = (ROOT / "pixi.toml").read_text(encoding="utf-8")
        self.assertIn(
            'dump-things-service = { path = "submodules/dump-things-service" }',
            pixi,
        )
        for package, version in (
            ("linkml", "1.11.1"),
            ("linkml-runtime", "1.11.1"),
            ("pydantic", "2.13.4"),
            ("rdflib", "7.6.0"),
        ):
            self.assertIn(f'{package} = "=={version}"', pixi)

        launcher = (ROOT / "tools" / "serve_local_dumpthings.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("uv run", launcher)
        self.assertIn("exec dump-things-service", launcher)

    def test_annex_hydration_does_not_persist_transport_configuration(self) -> None:
        assets = (ROOT / "tools" / "con_assets.py").read_text(encoding="utf-8")
        self.assertNotIn('"remote",\n            "add"', assets)
        self.assertNotIn('"config",\n        "core.worktree"', assets)
        self.assertIn("annex_from_url", assets)

        builder = (ROOT / "tools" / "build_upstream_site.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("remote add", builder)
        self.assertIn("restore_local_state", builder)
        self.assertIn("--no-write-fetch-head", builder)


if __name__ == "__main__":
    unittest.main()
