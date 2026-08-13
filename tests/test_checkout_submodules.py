from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "checkout_submodules.py"


def command_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_ALLOW_PROTOCOL"] = "file"
    return environment


def run(
    *arguments: str,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        env=command_environment(),
    )


def git(
    repository: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run("git", "-C", str(repository), *arguments, check=check)


def init_repository(path: Path) -> Path:
    path.mkdir()
    run("git", "init", "-b", "main", str(path))
    git(path, "config", "user.name", "Checkout Test")
    git(path, "config", "user.email", "checkout@example.invalid")
    return path


def commit_file(
    repository: Path,
    relative_path: str,
    content: str,
    message: str,
) -> str:
    path = repository / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(repository, "add", relative_path)
    git(repository, "commit", "-m", message)
    return git(repository, "rev-parse", "HEAD").stdout.strip()


def add_submodule(parent: Path, source: Path, path: str) -> None:
    git(
        parent,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        source.resolve().as_uri(),
        path,
    )


def is_shallow(repository: Path) -> bool:
    result = git(
        repository,
        "rev-parse",
        "--is-shallow-repository",
    )
    return result.stdout.strip() == "true"


class NestedFixture:
    def __init__(self, root: Path) -> None:
        self.nested = init_repository(root / "nested-source")
        self.nested_pin = commit_file(
            self.nested,
            "nested.txt",
            "pinned nested content\n",
            "add pinned nested content",
        )
        commit_file(
            self.nested,
            "nested.txt",
            "newer nested content\n",
            "update nested content",
        )

        self.child = init_repository(root / "child-source")
        add_submodule(self.child, self.nested, "vendor/nested")
        git(self.child / "vendor/nested", "checkout", self.nested_pin)
        git(self.child, "add", "vendor/nested")
        git(self.child, "commit", "-m", "pin nested dependency")
        self.child_pin = git(
            self.child,
            "rev-parse",
            "HEAD",
        ).stdout.strip()
        self.child_newer = commit_file(
            self.child,
            "child.txt",
            "newer child content\n",
            "update child content",
        )

        self.parent = init_repository(root / "parent-source")
        add_submodule(self.parent, self.child, "modules/child")
        git(self.parent / "modules/child", "checkout", self.child_pin)
        git(self.parent, "add", "modules/child")
        git(self.parent, "commit", "-m", "pin child dependency")

    def clone(self, destination: Path, *, shallow: bool) -> Path:
        arguments = ["git", "clone", "--recurse-submodules"]
        if shallow:
            arguments.extend(["--depth", "1", "--shallow-submodules"])
        arguments.extend([self.parent.resolve().as_uri(), str(destination)])
        run(*arguments)
        return destination


class CheckoutSubmodulesTests(unittest.TestCase):
    def run_helper(
        self,
        repository: Path,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return run(
            sys.executable,
            str(SCRIPT),
            str(repository),
            check=check,
        )

    def test_unshallows_top_level_and_nested_submodules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = NestedFixture(root)
            clone = fixture.clone(root / "checkout", shallow=True)
            child = clone / "modules/child"
            nested = child / "vendor/nested"

            self.assertTrue(is_shallow(child))
            self.assertTrue(is_shallow(nested))

            result = self.run_helper(clone)

            self.assertFalse(is_shallow(child))
            self.assertFalse(is_shallow(nested))
            self.assertEqual(
                git(child, "rev-parse", "HEAD").stdout.strip(),
                fixture.child_pin,
            )
            self.assertEqual(
                git(nested, "rev-parse", "HEAD").stdout.strip(),
                fixture.nested_pin,
            )
            self.assertIn("Verified 2 recursive submodule gitlinks", result.stdout)

    def test_restores_the_exact_parent_gitlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = NestedFixture(root)
            clone = fixture.clone(root / "checkout", shallow=False)
            child = clone / "modules/child"

            git(child, "checkout", fixture.child_newer)
            self.assertNotEqual(
                git(child, "rev-parse", "HEAD").stdout.strip(),
                fixture.child_pin,
            )

            self.run_helper(clone)

            self.assertEqual(
                git(child, "rev-parse", "HEAD").stdout.strip(),
                fixture.child_pin,
            )

    def test_fails_clearly_when_remote_lacks_the_gitlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected_source = init_repository(root / "expected-source")
            expected = commit_file(
                expected_source,
                "expected.txt",
                "expected content\n",
                "add expected content",
            )
            wrong_source = init_repository(root / "wrong-source")
            commit_file(
                wrong_source,
                "wrong.txt",
                "wrong content\n",
                "add wrong content",
            )

            parent = init_repository(root / "parent-source")
            add_submodule(parent, expected_source, "dependency")
            git(
                parent,
                "config",
                "-f",
                ".gitmodules",
                "submodule.dependency.url",
                wrong_source.resolve().as_uri(),
            )
            git(parent, "add", ".gitmodules", "dependency")
            git(parent, "commit", "-m", "record unavailable dependency")

            clone = root / "checkout"
            run("git", "clone", parent.resolve().as_uri(), str(clone))
            result = self.run_helper(clone, check=False)

            self.assertEqual(result.returncode, 1)
            self.assertIn(
                "Unable to check out every recorded recursive gitlink",
                result.stderr,
            )
            self.assertIn("dependency", result.stderr)
            self.assertIn(expected, result.stderr)


if __name__ == "__main__":
    unittest.main()
