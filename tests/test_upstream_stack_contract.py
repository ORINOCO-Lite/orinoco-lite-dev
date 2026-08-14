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

    def test_upstream_profile_excludes_con_sources(self) -> None:
        preparation = (ROOT / "tools" / "prepare_upstream_stack.py").read_text()
        seed = (ROOT / "tools" / "seed_upstream_pool.py").read_text()
        for source in (preparation, seed):
            self.assertNotIn("CON_RECORDS", source)
            self.assertNotIn("con-public", source)
            self.assertNotIn("con-protected", source)
        self.assertIn('(\"public\", \"protected\")', preparation)
        self.assertIn('(\"public\", \"protected\")', seed)

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
