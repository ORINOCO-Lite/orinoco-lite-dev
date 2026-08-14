from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.restore_annex_status import AnnexStatusError, refresh, write_snapshot


def run(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        check=True,
        text=True,
    )
    return result.stdout.strip()


class RestoreAnnexStatusTests(unittest.TestCase):
    def repository(self, root: Path) -> Path:
        repository = root / "repository"
        repository.mkdir()
        run(repository, "init", "-q")
        run(repository, "config", "user.name", "Fixture")
        run(repository, "config", "user.email", "fixture@example.invalid")
        (repository / "pointer").write_text("/annex/key\n", encoding="utf-8")
        run(repository, "add", "pointer")
        run(repository, "commit", "-qm", "fixture")
        return repository

    def test_refresh_preserves_preexisting_worktree_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self.repository(root)
            marker = repository / "candidate"
            marker.write_text("candidate\n", encoding="utf-8")
            snapshot = root / "status.json"
            write_snapshot(repository, snapshot)

            (repository / "pointer").touch()
            refresh(repository, snapshot)

            self.assertEqual(
                run(repository, "status", "--porcelain", "--untracked-files=all"),
                "?? candidate",
            )

    def test_refresh_rejects_real_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self.repository(root)
            snapshot = root / "status.json"
            write_snapshot(repository, snapshot)
            (repository / "pointer").write_text("changed\n", encoding="utf-8")

            with self.assertRaisesRegex(AnnexStatusError, "changed tracked content"):
                refresh(repository, snapshot)


if __name__ == "__main__":
    unittest.main()
