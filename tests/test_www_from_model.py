from __future__ import annotations

import os
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from orinoco_lite.errors import IntegrityError
from orinoco_lite.www_from_model import resolve_www_from_model


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class WwwFromModelResolverTests(unittest.TestCase):
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
                ".gitattributes": "page_templates/record.md filter=annex\n",
                "content/german.md": "German fixture must remain upstream\n",
                "page_templates/record.md": "www-from-model fixture\n",
            },
            modules=(("themes/congo", self.congo, self.congo_commit),),
        )
        self.website_commit = _git(self.website, "rev-parse", "HEAD")
        self.engineering = self._repository(
            "engineering",
            {
                "src/orinoco_lite/__init__.py": "",
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
        _git(repository, "config", "user.name", "www-from-model Test")
        _git(repository, "config", "user.email", "www-from-model@example.invalid")
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

    def _resources(self, *, repository: Path | None = None) -> Path:
        root = self.root / "resources"
        root.mkdir()
        (root / "source-commit.txt").write_text(self.engineering_commit + "\n")
        self.source_repository = str(repository) if repository else ""
        source_patch = patch("orinoco_lite.www_from_model.SOURCE_REPOSITORY", self.source_repository)
        source_patch.start()
        self.addCleanup(source_patch.stop)
        return root

    def test_package_uses_committed_gitlink_and_resolves_recursively(self) -> None:
        (self.engineering / ".gitmodules").write_text(
            "working-tree tampering must not select www-from-model\n",
            encoding="utf-8",
        )

        with patch("orinoco_lite.www_from_model._package_source", return_value=(str(self.engineering), self.engineering_commit)):
            source = resolve_www_from_model(self.workspace, self.root / "resources")

        self.assertEqual(
            (source / "page_templates/record.md").read_text(encoding="utf-8"),
            "www-from-model fixture\n",
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

    def test_commit_on_pull_request_ref_is_fetched(self) -> None:
        _git(self.engineering, "checkout", "--detach", "--quiet")
        _git(self.engineering, "commit", "--allow-empty", "--quiet", "-m", "PR merge")
        merge_commit = _git(self.engineering, "rev-parse", "HEAD")
        _git(self.engineering, "update-ref", "refs/pull/148/merge", merge_commit)
        _git(self.engineering, "checkout", "--quiet", "-")

        with patch(
            "orinoco_lite.www_from_model._package_source",
            return_value=(str(self.engineering), merge_commit),
        ):
            source = resolve_www_from_model(self.workspace, self.root / "resources")

        self.assertEqual(_git(source.parent.parent, "rev-parse", "HEAD"), merge_commit)
        self.assertEqual(_git(source, "rev-parse", "HEAD"), self.website_commit)
        self.assertTrue((source / "themes/congo/vendor/leaf/assets/leaf.txt").is_file())

    def test_corrupt_cache_is_repaired(self) -> None:
        with patch("orinoco_lite.www_from_model._package_source", return_value=(str(self.engineering), self.engineering_commit)):
            first = resolve_www_from_model(self.workspace, self.root / "resources")
            (first / "page_templates/record.md").write_text(
                "tampered\n", encoding="utf-8"
            )
            repaired = resolve_www_from_model(self.workspace, self.root / "resources")
            self.assertEqual(
                (repaired / "page_templates/record.md").read_text(
                    encoding="utf-8"
                ),
                "www-from-model fixture\n",
            )

    def test_www_from_model_cache_supports_offline_reuse_and_rejects_tampering(
        self,
    ) -> None:
        resources = self._resources(repository=self.engineering)

        with patch.dict(
            os.environ,
            {},
        ):
            first = resolve_www_from_model(self.workspace, resources)
            offline_sources = self.root / "offline-sources"
            self.sources.rename(offline_sources)
            second = resolve_www_from_model(self.workspace, resources)

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
                resolve_www_from_model(self.workspace, resources)

    def test_registered_data_pin_can_differ_from_selected_software(self):
        _git(self.workspace, "init", "--quiet")
        _git(self.workspace, "-c", "protocol.file.allow=always", "submodule", "add",
             str(self.website), "sourcedata/www-from-model")
        prepared = self.workspace / "sourcedata/www-from-model"
        retained = _git(prepared, "rev-parse", "HEAD")
        # Advance both upstream software and its dependency closure.
        (self.congo / "layouts/base.html").write_text("New theme\n")
        _git(self.congo, "commit", "-qam", "test: new theme")
        _git(self.website, "update-index", "--cacheinfo", "160000",
             _git(self.congo, "rev-parse", "HEAD"), "themes/congo")
        _git(self.website, "commit", "-qm", "test: select theme")
        selected = _git(self.website, "rev-parse", "HEAD")
        _git(self.engineering, "update-index", "--cacheinfo", "160000",
             selected, "submodules/www-from-model")
        _git(self.engineering, "commit", "-qm", "test: select software")
        with patch("orinoco_lite.www_from_model._package_source", return_value=(
                str(self.engineering), _git(self.engineering, "rev-parse", "HEAD"))):
            source = resolve_www_from_model(self.workspace, self.root / "resources")
        self.assertNotEqual(source, prepared)
        self.assertEqual(_git(source, "rev-parse", "HEAD"), selected)
        self.assertEqual((source / "themes/congo/layouts/base.html").read_text(), "New theme\n")
        self.assertEqual(_git(prepared, "rev-parse", "HEAD"), retained)
        self.assertIn(retained, _git(self.workspace, "ls-files", "--stage", "sourcedata/www-from-model"))

    def test_matching_registered_checkout_is_reused_without_website_clone(self):
        _git(self.workspace, "init", "--quiet")
        _git(self.workspace, "-c", "protocol.file.allow=always", "submodule", "add",
             str(self.website), "sourcedata/www-from-model")
        prepared = self.workspace / "sourcedata/www-from-model"
        _git(prepared, "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive")
        invoked = self.root / "annex-invoked"
        _git(prepared, "config", "filter.annex.process", f"touch {shlex.quote(str(invoked))}; exit 1")
        # Force Git to inspect bytes instead of trusting the index's stat cache.
        os.utime(prepared / "page_templates/record.md", (0, 0))
        with patch("orinoco_lite.www_from_model._package_source", return_value=(
                str(self.engineering), self.engineering_commit)):
            source = resolve_www_from_model(self.workspace, self.root / "resources")
        self.assertEqual(source, prepared.resolve())
        self.assertFalse(invoked.exists())
        self.assertFalse(list((self.workspace / ".orinoco").rglob("themes")))

    def test_missing_package_source_commit_is_rejected(self) -> None:
        resources = self._resources()
        (resources / "source-commit.txt").unlink()
        with patch.dict(
            os.environ,
            {},
        ):
            with self.assertRaisesRegex(IntegrityError, "source commit"):
                resolve_www_from_model(self.workspace, resources)

    def _register_website(self):
        _git(self.workspace, "init", "-q")
        _git(self.workspace, "-c", "protocol.file.allow=always", "submodule", "add",
             str(self.website), "sourcedata/www-from-model")
        _git(self.workspace, "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive")
        return self.workspace / "sourcedata/www-from-model"

    def test_registered_source_reuses_prepared_checkout_without_duplicate(self):
        source = self._register_website()
        (self.workspace / ".orinoco-lite").mkdir()
        (self.workspace / ".orinoco-lite/dev").symlink_to(self.engineering)
        with patch("orinoco_lite.www_from_model._package_source",
                   return_value=(str(self.engineering), self.engineering_commit)):
            self.assertEqual(resolve_www_from_model(self.workspace, self.root), source.resolve())
        self.assertFalse((self.workspace / ".orinoco").exists())

    def test_incomplete_registered_dependencies_use_an_independent_checkout(self):
        source = self._register_website()
        _git(source / "themes/congo", "submodule", "deinit", "--force", "--all")
        with patch("orinoco_lite.www_from_model._package_source",
                   return_value=(str(self.engineering), self.engineering_commit)):
            resolved = resolve_www_from_model(self.workspace, self.root)
        self.assertNotEqual(resolved, source.resolve())
        self.assertTrue((resolved / "themes/congo/vendor/leaf/assets/leaf.txt").is_file())
        self.assertFalse((source / "themes/congo/vendor/leaf/assets/leaf.txt").exists())

    def test_selected_relative_url_uses_engineering_origin_without_website_checkout(self):
        from orinoco_lite.www_from_model import selected_www_from_model_source

        _git(self.engineering, "config", "--file", ".gitmodules",
             "submodule.submodules/www-from-model.url", "../www-from-model")
        _git(self.engineering, "add", ".gitmodules")
        _git(self.engineering, "commit", "-qm", "test: use relative upstream URL")
        commit = _git(self.engineering, "rev-parse", "HEAD")
        with patch("orinoco_lite.www_from_model._package_source",
                   return_value=(str(self.engineering), commit)):
            repository, revision = selected_www_from_model_source(self.workspace, self.root)
        self.assertEqual(Path(repository).resolve(), self.website.resolve())
        self.assertEqual(revision, self.website_commit)
        cache = next((self.workspace / ".orinoco/www-from-model").glob("engineering-*"))
        self.assertFalse((cache / "submodules/www-from-model/themes").exists())


if __name__ == "__main__":
    unittest.main()
