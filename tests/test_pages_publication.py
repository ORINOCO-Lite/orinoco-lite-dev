from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "prepare_pages_publication.py"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Publication Test",
    "GIT_AUTHOR_EMAIL": "publication-test@example.invalid",
    "GIT_COMMITTER_NAME": "Publication Test",
    "GIT_COMMITTER_EMAIL": "publication-test@example.invalid",
}


def run(
    command: list[str | Path], cwd: Path, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        env=dict(os.environ, **GIT_ENV),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode:
        raise AssertionError(
            f"command failed: {' '.join(map(str, command))}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result


class PagesPublicationTests(unittest.TestCase):
    def make_repository(self, temporary: str) -> tuple[Path, str]:
        repository = Path(temporary)
        run(["git", "init", "-b", "main"], repository)
        (repository / ".gitignore").write_text("/build/\n/generated/\n")
        (repository / "README.md").write_text("# Site source\n")
        run(["git", "add", "--all"], repository)
        run(["git", "commit", "-m", "feat: add site source"], repository)
        source = run(["git", "rev-parse", "HEAD"], repository).stdout.strip()

        projection = repository / "generated/projection"
        (projection / "content/people/one").mkdir(parents=True)
        (projection / "content/people/one/_index.md").write_text("# One\n")
        (projection / "static").mkdir()
        (projection / "static/graph.json").write_text("{}\n")
        (projection / "records.jsonl").write_text('{"pid":"example:one"}\n')
        (projection / "SHA256SUMS").write_text("projection manifest\n")
        pages = repository / "build/pages"
        pages.mkdir(parents=True)
        (pages / "index.html").write_text("<h1>Site</h1>\n")
        (pages / "graph.json").write_text("{}\n")
        return repository, source

    def test_bundle_records_exact_two_commit_publication_chain(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orinoco-pages-test-") as temporary:
            repository, source = self.make_repository(temporary)
            first = run(["python", SCRIPT], repository)
            first_result = json.loads(first.stdout)
            bundle = repository / "build/pages-publication.bundle"
            metadata = json.loads(
                (repository / "build/pages-publication.json").read_text()
            )
            self.assertEqual(first_result, metadata)
            run(["git", "bundle", "verify", bundle], repository)
            run(
                [
                    "git",
                    "fetch",
                    bundle,
                    "refs/orinoco-publication/latest-hugo-projection:"
                    "refs/remotes/publication/latest-hugo-projection",
                    "refs/orinoco-publication/gh-pages:"
                    "refs/remotes/publication/gh-pages",
                ],
                repository,
            )
            projection = "refs/remotes/publication/latest-hugo-projection"
            pages = "refs/remotes/publication/gh-pages"
            self.assertEqual(
                source,
                run(["git", "rev-parse", f"{projection}^"], repository).stdout.strip(),
            )
            self.assertEqual(
                run(["git", "rev-parse", projection], repository).stdout.strip(),
                run(["git", "rev-parse", f"{pages}^"], repository).stdout.strip(),
            )
            projection_paths = run(
                ["git", "ls-tree", "-r", "--name-only", projection], repository
            ).stdout.splitlines()
            self.assertIn("README.md", projection_paths)
            self.assertIn("generated/projection/records.jsonl", projection_paths)
            self.assertIn(
                "generated/projection/content/people/one/_index.md",
                projection_paths,
            )
            pages_paths = run(
                ["git", "ls-tree", "-r", "--name-only", pages], repository
            ).stdout.splitlines()
            self.assertEqual(["graph.json", "index.html"], pages_paths)
            self.assertEqual(source, run(["git", "rev-parse", "main"], repository).stdout.strip())

            second = run(["python", SCRIPT], repository)
            second_result = json.loads(second.stdout)
            self.assertEqual(
                first_result["projection"]["commit"],
                second_result["projection"]["commit"],
            )
            self.assertEqual(
                first_result["pages"]["commit"], second_result["pages"]["commit"]
            )

    def test_dirty_tracked_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="orinoco-pages-test-") as temporary:
            repository, _ = self.make_repository(temporary)
            (repository / "README.md").write_text("changed\n")
            result = run(["python", SCRIPT], repository, check=False)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Tracked worktree changes", result.stderr)


if __name__ == "__main__":
    unittest.main()
