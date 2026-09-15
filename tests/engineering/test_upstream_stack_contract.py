from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tests.engineering.test_checkout_submodules import NestedFixture, git
from tools.upstream_checkout import UpstreamCheckoutError, prepare_gitlink


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


if __name__ == "__main__":
    unittest.main()
