from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
POOL_UI = ROOT / "submodules" / "pool.psychoinformatics.de-ui"


class LocalStackContractTests(unittest.TestCase):
    def test_pixi_exposes_all_local_services(self) -> None:
        pixi = (ROOT / "pixi.toml").read_text(encoding="utf-8")
        for task in (
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


if __name__ == "__main__":
    unittest.main()
