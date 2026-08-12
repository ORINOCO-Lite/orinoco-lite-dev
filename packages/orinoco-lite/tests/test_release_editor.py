from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.release_editor import GIT_IDENTITY, _initialize_repository


class DeterministicEditorGitTests(unittest.TestCase):
    def test_independent_source_copies_have_identical_git_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repositories = [root / "first", root / "second"]
            commits = []
            with patch.dict(
                os.environ,
                {
                    "GIT_AUTHOR_DATE": "2035-01-01T00:00:00Z",
                    "GIT_COMMITTER_DATE": "2040-01-01T00:00:00Z",
                    "GIT_AUTHOR_NAME": "Hostile inherited author",
                },
            ):
                for repository in repositories:
                    repository.mkdir()
                    (repository / "source.txt").write_text(
                        "reviewed editor source\n", encoding="utf-8"
                    )
                    commits.append(_initialize_repository(repository, "a" * 40))
            self.assertEqual(commits[0], commits[1])
            for repository in repositories:
                result = subprocess.run(
                    [
                        "git",
                        "show",
                        "-s",
                        "--format=%aI%x00%cI%x00%an%x00%ae%x00%cn%x00%ce",
                        "HEAD",
                    ],
                    cwd=repository,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(
                    result.stdout.strip().split("\0"),
                    [
                        "2000-01-01T00:00:00Z",
                        "2000-01-01T00:00:00Z",
                        GIT_IDENTITY["GIT_AUTHOR_NAME"],
                        GIT_IDENTITY["GIT_AUTHOR_EMAIL"],
                        GIT_IDENTITY["GIT_COMMITTER_NAME"],
                        GIT_IDENTITY["GIT_COMMITTER_EMAIL"],
                    ],
                )


if __name__ == "__main__":
    unittest.main()
