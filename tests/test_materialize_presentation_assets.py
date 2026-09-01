from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import materialize_presentation_assets as materializer


class FakeGitAnnex:
    def __init__(
        self,
        engineering: Path,
        website: Path,
        selected_commit: str,
        annexed: dict[str, bytes],
        *,
        checkout_commit: str | None = None,
    ) -> None:
        self.engineering = engineering.resolve()
        self.website = website.resolve()
        self.git_dir = self.engineering / ".git/modules/submodules/www-from-model"
        self.selected_commit = selected_commit
        self.checkout_commit = checkout_commit or selected_commit
        self.annexed = annexed
        self.commands: list[tuple[str, ...]] = []
        self.fail_operation: str | None = None

    def __call__(self, command: list[str] | tuple[str, ...]) -> str:
        command = tuple(str(item) for item in command)
        self.commands.append(command)
        if command[0:2] == ("git", "-C"):
            repository = Path(command[2]).resolve()
            arguments = command[3:]
            if repository == self.engineering:
                if arguments == (
                    "ls-tree",
                    "HEAD",
                    "--",
                    "submodules/www-from-model",
                ):
                    return (
                        f"160000 commit {self.selected_commit}\t"
                        "submodules/www-from-model"
                    )
                raise AssertionError(
                    f"Unexpected engineering Git command: {arguments}"
                )
            if repository != self.website:
                raise AssertionError(f"Unexpected repository: {repository}")
            if arguments == ("rev-parse", "--absolute-git-dir"):
                return str(self.git_dir)
            if arguments == ("rev-parse", "--show-toplevel"):
                return str(self.website)
            if arguments == ("rev-parse", "HEAD"):
                return self.checkout_commit
            raise AssertionError(f"Unexpected website Git command: {arguments}")

        expected_environment = (
            "env",
            f"GIT_DIR={self.git_dir}",
            f"GIT_WORK_TREE={self.website}",
            "git",
        )
        if command[:4] != expected_environment:
            raise AssertionError(f"Unexpected command: {command}")
        arguments = command[4:]
        if arguments == (
            "status",
            "--porcelain",
            "--untracked-files=all",
        ):
            return ""
        if arguments == (
            "annex",
            "find",
            "--json",
            "--json-error-messages",
            "--anything",
        ):
            return "\n".join(
                json.dumps({"file": path}) for path in self.annexed
            )
        if arguments[0:2] == ("annex", "get"):
            if self.fail_operation == "get":
                raise materializer.MaterializationError("mock get failure")
            return ""
        if arguments[0:2] == ("annex", "fsck"):
            if self.fail_operation == "fsck":
                raise materializer.MaterializationError("mock fsck failure")
            return ""
        raise AssertionError(f"Unexpected website Git command: {arguments}")


class MaterializePresentationAssetsTests(unittest.TestCase):
    def fixture(
        self,
        root: Path,
        annexed: dict[str, bytes],
        *,
        commit: str = "a" * 40,
        checkout_commit: str | None = None,
    ) -> tuple[Path, Path, Path, FakeGitAnnex]:
        engineering = root / "engineering"
        website = engineering / "submodules/www-from-model"
        template = root / "template"
        website.mkdir(parents=True)
        copier = template / "copier-template"
        copier.mkdir(parents=True)
        overlay = copier / ".orinoco-lite/materialized-presentation"
        overlay.mkdir(parents=True)
        (overlay / "LICENSE").write_text(
            "Licensed overlay fixture.\n", encoding="utf-8"
        )
        for relative, content in annexed.items():
            path = website / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        fake = FakeGitAnnex(
            engineering,
            website,
            commit,
            annexed,
            checkout_commit=checkout_commit,
        )
        return engineering, website, template, fake

    def test_derives_gitlink_and_materializes_generic_presentation_assets(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = b"new upstream runtime payload\n"
            static = b"retained client payload\n"
            german = b"upstream record depiction"
            generated = b'{"upstream": "graph"}\n'
            annexed = {
                "assets/novel/runtime-v9.bin": runtime,
                "static/clients/behavior.bin": static,
                "content/projects/german/depiction.bin": german,
                "static/graph.json": generated,
            }
            engineering, _website, template, fake = self.fixture(root, annexed)
            overlay = (
                template
                / "copier-template/.orinoco-lite/materialized-presentation"
            )
            old_upstream = overlay / "upstream"
            old_upstream.mkdir(parents=True)
            (old_upstream / "obsolete.bin").write_bytes(b"obsolete")
            (overlay / "NOTICE").write_text("preserve me\n", encoding="utf-8")

            result = materializer.materialize(
                engineering,
                template,
                runner=fake,
            )

            self.assertEqual(result.selected_commit, "a" * 40)
            self.assertEqual(result.asset_count, 2)
            self.assertEqual(
                (result.destination / "assets/novel/runtime-v9.bin").read_bytes(),
                runtime,
            )
            self.assertEqual(
                (result.destination / "static/clients/behavior.bin").read_bytes(),
                static,
            )
            self.assertFalse((result.destination / "obsolete.bin").exists())
            self.assertFalse(
                (result.destination / "content/projects/german/depiction.bin").exists()
            )
            self.assertFalse((result.destination / "static/graph.json").exists())
            self.assertEqual((overlay / "NOTICE").read_text(), "preserve me\n")
            self.assertEqual(
                (overlay / "LICENSE").read_text(),
                "Licensed overlay fixture.\n",
            )

    def test_hydration_failure_preserves_existing_materialized_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b"required payload"
            annexed = {"assets/runtime.bin": content}
            engineering, _website, template, fake = self.fixture(root, annexed)
            existing = (
                template
                / "copier-template/.orinoco-lite/materialized-presentation"
                / "upstream/assets/previous.bin"
            )
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"previous payload")
            fake.fail_operation = "get"

            with self.assertRaisesRegex(
                materializer.MaterializationError, "mock get failure"
            ):
                materializer.materialize(
                    engineering,
                    template,
                    runner=fake,
                )

            self.assertEqual(existing.read_bytes(), b"previous payload")

    def test_pointer_payload_is_never_published(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pointer = b"/annex/objects/WORM-s30--payload\n"
            annexed = {"assets/runtime.bin": pointer}
            engineering, _website, template, fake = self.fixture(root, annexed)
            existing = (
                template
                / "copier-template/.orinoco-lite/materialized-presentation"
                / "upstream/assets/previous.bin"
            )
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"previous payload")

            with self.assertRaisesRegex(
                materializer.MaterializationError, "Annex pointer"
            ):
                materializer.materialize(
                    engineering,
                    template,
                    runner=fake,
                )

            self.assertEqual(existing.read_bytes(), b"previous payload")

    def test_checkout_commit_must_match_the_selected_gitlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            engineering, _website, template, fake = self.fixture(
                root,
                {},
                commit="b" * 40,
                checkout_commit="c" * 40,
            )

            with self.assertRaisesRegex(
                materializer.MaterializationError, "should be"
            ):
                materializer.materialize(
                    engineering,
                    template,
                    runner=fake,
                )

            self.assertFalse(
                (
                    template
                    / "copier-template/.orinoco-lite/materialized-presentation/upstream"
                ).exists()
            )

if __name__ == "__main__":
    unittest.main()
