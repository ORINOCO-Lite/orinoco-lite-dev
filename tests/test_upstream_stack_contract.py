from __future__ import annotations

from pathlib import Path
import tempfile
import tomllib
import unittest

from tests.test_checkout_submodules import NestedFixture, git
from tools.upstream_checkout import UpstreamCheckoutError, prepare_gitlink


ROOT = Path(__file__).resolve().parents[1]


class UpstreamStackContractTests(unittest.TestCase):
    def test_recorded_mode_restores_a_clean_mismatched_gitlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = NestedFixture(Path(temporary))
            clone = fixture.clone(Path(temporary) / "checkout", shallow=False)
            child = clone / "modules/child"
            git(child, "checkout", fixture.child_newer)

            prepare_gitlink(
                clone,
                Path("modules/child"),
                display=Path("modules/child"),
                mode="recorded",
            )

            self.assertEqual(
                git(child, "rev-parse", "HEAD").stdout.strip(),
                fixture.child_pin,
            )

    def test_worktree_mode_preserves_current_commit_and_modifications(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = NestedFixture(Path(temporary))
            clone = fixture.clone(Path(temporary) / "checkout", shallow=False)
            child = clone / "modules/child"
            git(child, "checkout", fixture.child_newer)
            marker = child / "candidate.txt"
            marker.write_text("candidate change\n", encoding="utf-8")

            prepare_gitlink(
                clone,
                Path("modules/child"),
                display=Path("modules/child"),
                mode="worktree",
            )

            self.assertEqual(
                git(child, "rev-parse", "HEAD").stdout.strip(),
                fixture.child_newer,
            )
            self.assertEqual(marker.read_text(encoding="utf-8"), "candidate change\n")

    def test_recorded_mode_rejects_modified_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = NestedFixture(Path(temporary))
            clone = fixture.clone(Path(temporary) / "checkout", shallow=False)
            child = clone / "modules/child"
            (child / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            with self.assertRaisesRegex(
                UpstreamCheckoutError,
                "use worktree mode",
            ):
                prepare_gitlink(
                    clone,
                    Path("modules/child"),
                    display=Path("modules/child"),
                    mode="recorded",
                )

    def test_full_tasks_and_inline_environment_are_scoped(self) -> None:
        tasks = tomllib.loads((ROOT / "pixi.toml").read_text())["tasks"]
        self.assertEqual(
            tasks["serve-upstream"],
            "python tools/upstream_full_launcher.py serve recorded",
        )
        self.assertEqual(
            tasks["serve-upstream-worktree"],
            "python tools/upstream_full_launcher.py serve worktree",
        )
        self.assertEqual(
            tasks["check-upstream"],
            "python tools/upstream_full_launcher.py check recorded",
        )
        self.assertEqual(
            tasks["check-upstream-worktree"],
            "python tools/upstream_full_launcher.py check worktree",
        )
        self.assertEqual(
            tasks["diff-upstream-pool"],
            "python tools/upstream_pool_diff.py",
        )
        self.assertEqual(
            tasks["snapshot-upstream-records"],
            "python tools/prepare_upstream_snapshot.py",
        )
        self.assertEqual(
            tasks["refresh-upstream-records"],
            "python tools/prepare_upstream_snapshot.py --refresh",
        )
        self.assertEqual(
            tasks["instantiate-upstream-orinoco"]["depends-on"],
            ["prepare-upstream-orinoco-presentation"],
        )
        self.assertEqual(
            tasks["check-upstream-orinoco"]["depends-on"],
            ["instantiate-upstream-orinoco"],
        )
        source = (ROOT / "tools" / "upstream_full.py").read_text()
        self.assertIn("[tool.pixi.pypi-dependencies]", source)
        self.assertIn(
            'dump-things-service = { path = "../submodules/dump-things-service"',
            source,
        )
        self.assertIn('nodejs = ">=22,<23"', source)
        self.assertTrue((ROOT / "tools" / "upstream_full.py.pixi.lock").is_file())
        lock = (ROOT / "tools" / "upstream_full.py.pixi.lock").read_text()
        for package, version in (
            ("linkml", "1.11.1"),
            ("linkml-runtime", "1.11.1"),
            ("pydantic", "2.13.4"),
            ("rdflib", "7.6.0"),
        ):
            self.assertIn(f"name: {package}\n  version: {version}", lock)

    def test_snapshot_is_materialized_once_for_both_runtime_paths(self) -> None:
        preparation = (ROOT / "tools" / "prepare_upstream_snapshot.py").read_text()
        full_stack = (ROOT / "tools" / "prepare_upstream_stack.py").read_text()
        fixture = (ROOT / "tools" / "upstream_orinoco.py").read_text()
        for source in (preparation, full_stack):
            self.assertIn("upstream_snapshot.materialize", source)
            self.assertIn("upstream_snapshot.export_records", source)
        self.assertIn("ORINOCO_RECORDS", fixture)
        self.assertIn("copy_regular_tree(ORINOCO_RECORDS", fixture)
        self.assertIn('git\", \"init\", \"--initial-branch\", \"main\"', fixture)

    def test_direct_scripts_do_not_depend_on_the_tools_namespace(self) -> None:
        for relative in (
            "prepare_upstream_snapshot.py",
            "prepare_upstream_stack.py",
            "upstream_orinoco_records.py",
        ):
            source = (ROOT / "tools" / relative).read_text()
            self.assertIn("if __package__:", source)
            self.assertNotIn("from tools import upstream_snapshot", source)

    def test_live_check_retains_upstream_ui_and_schema_contracts(self) -> None:
        check = (ROOT / "tools" / "check_upstream_stack.py").read_text()
        for contract in (
            "use_service: true",
            "use_token: true",
            "dlschemas_data.ttl",
            "dlschemas_owl.ttl",
            "XYZDataset",
            "prove_write_isolation",
        ):
            self.assertIn(contract, check)

    def test_checkout_provenance_is_written_to_ignored_runtime_state(self) -> None:
        source = (ROOT / "tools" / "upstream_full.py").read_text()
        self.assertIn('STACK / "checkout.json"', source)
        self.assertIn('"checkout_mode": checkout', source)
        ignore = (ROOT / ".gitignore").read_text()
        self.assertIn("build/", ignore)


if __name__ == "__main__":
    unittest.main()
