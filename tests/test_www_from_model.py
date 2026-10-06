from __future__ import annotations

import json
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
        editable = patch("orinoco_lite.www_from_model.editable_package_checkout", return_value=None)
        editable.start()
        self.addCleanup(editable.stop)
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
        from orinoco_lite.build_resources import selected_upstream
        root = self.root / "resources"
        root.mkdir()
        (root / "www-from-model.json").write_text(json.dumps(
            selected_upstream(self.engineering, self.engineering_commit)))
        return root

    def test_package_resolves_upstream_directly_and_recursively(self) -> None:
        (self.engineering / ".gitmodules").write_text(
            "working-tree tampering must not select www-from-model\n",
            encoding="utf-8",
        )

        with patch("orinoco_lite.www_from_model.upstream_source", return_value=(str(self.website), self.website_commit)):
            source = resolve_www_from_model(self.workspace, self.root / "resources")

        self.assertFalse((source / "src/orinoco_lite").exists())
        self.assertEqual(_git(source, "remote", "get-url", "origin"), str(self.website))
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
        _git(self.website, "checkout", "--detach", "--quiet")
        _git(self.website, "commit", "--allow-empty", "--quiet", "-m", "PR merge")
        merge_commit = _git(self.website, "rev-parse", "HEAD")
        _git(self.website, "update-ref", "refs/pull/148/merge", merge_commit)
        _git(self.website, "checkout", "--quiet", "-")

        with patch(
            "orinoco_lite.www_from_model.upstream_source",
            return_value=(str(self.website), merge_commit),
        ):
            source = resolve_www_from_model(self.workspace, self.root / "resources")

        self.assertEqual(_git(source, "rev-parse", "HEAD"), merge_commit)
        self.assertTrue((source / "themes/congo/vendor/leaf/assets/leaf.txt").is_file())

    def test_corrupt_cache_is_repaired(self) -> None:
        with patch("orinoco_lite.www_from_model.upstream_source", return_value=(str(self.website), self.website_commit)):
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

    def test_fixed_annex_cache_is_reused_and_can_be_repaired(self):
        from orinoco_lite.annex_media import prepare_hugo_assets

        _git(self.website, "annex", "init", "fixture")
        asset = self.website / "static/graph.js"
        asset.parent.mkdir()
        asset.write_text("selected graph code\n")
        _git(self.website, "annex", "add", "static/graph.js")
        _git(self.website, "commit", "-qm", "test: add Annex asset")
        _git(self.engineering, "update-index", "--cacheinfo", "160000",
             _git(self.website, "rev-parse", "HEAD"), "submodules/www-from-model")
        _git(self.engineering, "commit", "-qm", "test: select Annex source")
        with patch("orinoco_lite.www_from_model.upstream_source", return_value=(
            str(self.website), _git(self.website, "rev-parse", "HEAD"),
        )):
            source = resolve_www_from_model(self.workspace, self.root)
            files = prepare_hugo_assets(source)
            self.assertEqual(files[source / "static/graph.js"].read_text(), "selected graph code\n")
            inode = (source / ".git").stat().st_ino
            self.assertEqual(resolve_www_from_model(self.workspace, self.root), source)
            self.assertEqual((source / ".git").stat().st_ino, inode)
            (source / "page_templates/record.md").write_text("tampered\n")
            repaired = resolve_www_from_model(self.workspace, self.root)
            self.assertEqual((repaired / "page_templates/record.md").read_text(), "www-from-model fixture\n")

    def test_editable_uses_nested_working_source_without_resource_stamp(self):
        _git(self.engineering, "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive")
        source = self.engineering / "submodules/www-from-model"
        (source / "page_templates/record.md").write_text("local edit\n")
        with patch("orinoco_lite.www_from_model.editable_package_checkout", return_value=self.engineering):
            resolved = resolve_www_from_model(self.workspace, self.root / "missing-resources")
        self.assertEqual(resolved, source.resolve())
        self.assertEqual((resolved / "page_templates/record.md").read_text(), "local edit\n")
        self.assertFalse((self.workspace / ".orinoco-lite").exists())

    def test_missing_package_source_commit_is_rejected(self) -> None:
        resources = self._resources()
        (resources / "www-from-model.json").unlink()
        with patch.dict(
            os.environ,
            {},
        ):
            with self.assertRaisesRegex(IntegrityError, "source selection"):
                resolve_www_from_model(self.workspace, resources)



if __name__ == "__main__":
    unittest.main()


def test_build_metadata_uses_committed_source_without_initialized_submodules(tmp_path):
    from orinoco_lite.build_resources import selected_upstream
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Fixture")
    _git(tmp_path, "config", "user.email", "fixture@example.invalid")
    (tmp_path / ".gitmodules").write_text('[submodule "website"]\npath = submodules/www-from-model\nurl = https://example.org/our-www.git\n')
    _git(tmp_path, "add", ".gitmodules")
    _git(tmp_path, "update-index", "--add", "--cacheinfo", "160000", "a" * 40, "submodules/www-from-model")
    _git(tmp_path, "commit", "-qm", "fixture")
    commit = _git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / ".gitmodules").write_text("uncommitted change")
    _git(tmp_path, "update-index", "--cacheinfo", "160000", "b" * 40, "submodules/www-from-model")
    assert selected_upstream(tmp_path, commit) == {"repository": "https://example.org/our-www.git", "commit": "a" * 40}
