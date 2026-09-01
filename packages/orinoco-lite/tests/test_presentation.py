from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.errors import IntegrityError
from orinoco_lite.presentation import resolve_presentation
from orinoco_lite.runtime import assemble_runtime


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class PresentationResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

        self.leaf = self._repository(
            "leaf",
            {"assets/leaf.txt": "nested dependency\n"},
        )
        self.leaf_commit = _git(self.leaf, "rev-parse", "HEAD")
        self.congo = self._repository(
            "congo",
            {"layouts/base.html": "Congo fixture\n"},
            modules=(("vendor/leaf", self.leaf, self.leaf_commit),),
        )
        self.congo_commit = _git(self.congo, "rev-parse", "HEAD")
        self.website = self._repository(
            "www-from-model",
            {
                "content/german.md": "German fixture must remain upstream\n",
                "page_templates/record.md": "Presentation fixture\n",
            },
            modules=(("themes/congo", self.congo, self.congo_commit),),
        )
        self.website_commit = _git(self.website, "rev-parse", "HEAD")
        self.engineering = self._repository(
            "engineering",
            {
                "packages/orinoco-lite/src/orinoco_lite/__init__.py": "",
                "README.md": "Engineering fixture\n",
            },
            modules=(
                (
                    "submodules/www-from-model",
                    self.website,
                    self.website_commit,
                ),
            ),
        )
        self.engineering_commit = _git(self.engineering, "rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _repository(
        self,
        name: str,
        files: dict[str, str],
        *,
        modules: tuple[tuple[str, Path, str], ...] = (),
    ) -> Path:
        repository = self.sources / name
        repository.mkdir()
        _git(repository, "init", "--quiet")
        _git(repository, "config", "user.name", "Presentation Test")
        _git(repository, "config", "user.email", "presentation@example.invalid")
        for relative, value in files.items():
            path = repository.joinpath(*relative.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
        if files:
            _git(repository, "add", "--", *sorted(files))
        if modules:
            declarations = "".join(
                f'[submodule "{path}"]\n'
                f"\tpath = {path}\n"
                f"\turl = {source}\n"
                for path, source, _commit in modules
            )
            (repository / ".gitmodules").write_text(
                declarations, encoding="utf-8"
            )
            _git(repository, "add", ".gitmodules")
            for path, _source, commit in modules:
                _git(
                    repository,
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    "160000",
                    commit,
                    path,
                )
        _git(repository, "commit", "--quiet", "-m", f"create {name}")
        return repository

    def _runtime(self, *, repository: Path | None = None) -> Path:
        source = self.root / f"runtime-source-{len(list(self.root.glob('runtime-*')))}"
        (source / "licenses").mkdir(parents=True)
        (source / "licenses/LICENSE.txt").write_text(
            "Fixture license\n", encoding="utf-8"
        )
        provenance = {
            "source_commit": self.engineering_commit,
        }
        if repository is not None:
            provenance["source_repository"] = str(repository)
        spec = source / "runtime.yaml"
        spec.write_text(
            "format: orinoco-lite-runtime-source\n"
            "spec_version: 1\n"
            "release: 0.2.0\n"
            "source_root: .\n"
            "compatibility:\n"
            "  config: [2]\n"
            '  hugo: ">=0.154,<0.155"\n'
            "commands:\n"
            '  build: ["{python}", "-c", "pass"]\n'
            "licenses:\n"
            "  - licenses/LICENSE.txt\n"
            "resources:\n"
            "  - source: licenses\n"
            "    destination: licenses\n"
            f"provenance: {json.dumps(provenance, sort_keys=True)}\n",
            encoding="utf-8",
        )
        archive = source / "runtime.tar.gz"
        assemble_runtime(spec, archive)
        extracted = source / "extracted"
        with tarfile.open(archive, "r:gz") as stream:
            stream.extractall(extracted, filter="data")
        return extracted / "orinoco-runtime"

    def _candidate_environment(self) -> dict[str, str]:
        return {
            "ORINOCO_UNSAFE_DEVELOPMENT_RUNTIME": "1",
            "ORINOCO_CANDIDATE_ENGINE_ROOT": str(self.engineering),
        }

    def test_candidate_uses_committed_gitlink_and_resolves_recursively(self) -> None:
        (self.engineering / ".gitmodules").write_text(
            "working-tree tampering must not select the presentation\n",
            encoding="utf-8",
        )

        with patch.dict(os.environ, self._candidate_environment()):
            source = resolve_presentation(self.workspace)

        self.assertEqual(
            (source / "page_templates/record.md").read_text(encoding="utf-8"),
            "Presentation fixture\n",
        )
        self.assertEqual(
            (source / "themes/congo/vendor/leaf/assets/leaf.txt").read_text(
                encoding="utf-8"
            ),
            "nested dependency\n",
        )
        self.assertEqual(_git(source, "rev-parse", "HEAD"), self.website_commit)
        self.assertEqual(
            _git(source / "themes/congo", "rev-parse", "HEAD"),
            self.congo_commit,
        )

    def test_corrupt_cache_is_repaired(self) -> None:
        with patch.dict(os.environ, self._candidate_environment()):
            first = resolve_presentation(self.workspace)
            (first / "page_templates/record.md").write_text(
                "tampered\n", encoding="utf-8"
            )
            repaired = resolve_presentation(self.workspace)
            self.assertEqual(
                (repaired / "page_templates/record.md").read_text(
                    encoding="utf-8"
                ),
                "Presentation fixture\n",
            )

    def test_verified_runtime_cache_supports_offline_reuse_and_rejects_tampering(
        self,
    ) -> None:
        runtime = self._runtime(repository=self.engineering)

        with patch.dict(
            os.environ,
            {"ORINOCO_UNSAFE_DEVELOPMENT_RUNTIME": "0"},
        ):
            first = resolve_presentation(self.workspace, runtime)
            offline_sources = self.root / "offline-sources"
            self.sources.rename(offline_sources)
            second = resolve_presentation(self.workspace, runtime)

            self.assertEqual(first, second)
            self.assertEqual(
                (second / "themes/congo/layouts/base.html").read_text(
                    encoding="utf-8"
                ),
                "Congo fixture\n",
            )

            (second / "page_templates/record.md").write_text(
                "offline tampering\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(IntegrityError, "repair failed"):
                resolve_presentation(self.workspace, runtime)

    def test_runtime_requires_only_the_engineering_coordinate(self) -> None:
        runtime = self._runtime()
        with patch.dict(
            os.environ,
            {"ORINOCO_UNSAFE_DEVELOPMENT_RUNTIME": "0"},
        ):
            with self.assertRaisesRegex(IntegrityError, "source_repository"):
                resolve_presentation(self.workspace, runtime)


if __name__ == "__main__":
    unittest.main()
