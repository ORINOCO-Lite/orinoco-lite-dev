from __future__ import annotations

from pathlib import Path
import tempfile
import tomllib
import unittest

from tests.engineering.test_checkout_submodules import NestedFixture, git
from tools.upstream_checkout import UpstreamCheckoutError, prepare_gitlink


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "pixi.toml"


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


    def test_snapshot_is_materialized_for_snapshot_and_full_stack_tasks(self) -> None:
        preparation = (ROOT / "tools" / "prepare_upstream_snapshot.py").read_text()
        full_stack = (ROOT / "tools" / "prepare_upstream_stack.py").read_text()
        for source in (preparation, full_stack):
            self.assertIn("upstream_snapshot.materialize", source)
            self.assertIn("upstream_snapshot.export_records", source)


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

    def test_checkout_provenance_is_written_to_ignored_local_state(self) -> None:
        source = (ROOT / "tools" / "upstream_full.py").read_text()
        self.assertIn('STACK / "checkout.json"', source)
        self.assertIn('"checkout_mode": checkout', source)
        ignore = (ROOT / ".gitignore").read_text()
        self.assertIn("build/", ignore)


if __name__ == "__main__":
    unittest.main()
