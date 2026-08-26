"""Create reproducible projection and Pages commits for one site build."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile


PROJECTION_REF = "refs/orinoco-publication/latest-hugo-projection"
PAGES_REF = "refs/orinoco-publication/gh-pages"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


class PublicationError(RuntimeError):
    """Report a publication input or Git-history contract failure."""


def _run(
    command: list[str | Path],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> str:
    result = subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        env=None if env is None else dict(os.environ, **env),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise PublicationError(f"{' '.join(map(str, command))}: {detail}")
    return result.stdout.strip()


def _relative_directory(root: Path, value: str, label: str) -> Path:
    relative = PurePosixPath(value)
    if (
        not value
        or value != relative.as_posix()
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        raise PublicationError(f"{label} must be a safe repository-relative path")
    path = root.joinpath(*relative.parts)
    if not path.is_dir():
        raise PublicationError(f"{label} directory is missing: {value}")
    return path


def _files(root: Path) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PublicationError(f"Publication input cannot contain symlinks: {path}")
        if path.is_file():
            files.append(path)
    return files


def _commit_tree(
    root: Path,
    tree: str,
    *,
    parent: str,
    message: str,
    date: str,
) -> str:
    identity = {
        "GIT_AUTHOR_NAME": BOT_NAME,
        "GIT_AUTHOR_EMAIL": BOT_EMAIL,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_NAME": BOT_NAME,
        "GIT_COMMITTER_EMAIL": BOT_EMAIL,
        "GIT_COMMITTER_DATE": date,
    }
    return _run(
        ["git", "commit-tree", tree, "-p", parent],
        cwd=root,
        env=identity,
        input_text=message,
    )


def _tree_with_projection(
    root: Path,
    projection_relative: str,
    source: str,
    index: Path,
) -> str:
    env = {"GIT_INDEX_FILE": str(index)}
    _run(["git", "read-tree", source], cwd=root, env=env)
    _run(
        ["git", "add", "--force", "--all", "--", projection_relative],
        cwd=root,
        env=env,
    )
    return _run(["git", "write-tree"], cwd=root, env=env)


def _tree_from_directory(root: Path, source: Path, index: Path) -> str:
    env = {"GIT_INDEX_FILE": str(index)}
    git_dir = _run(["git", "rev-parse", "--absolute-git-dir"], cwd=root)
    _run(["git", "read-tree", "--empty"], cwd=root, env=env)
    _run(
        [
            "git",
            f"--git-dir={git_dir}",
            f"--work-tree={source}",
            "add",
            "--all",
            ".",
        ],
        cwd=source,
        env=env,
    )
    return _run(["git", "write-tree"], cwd=root, env=env)


def prepare(
    repository: Path,
    projection_relative: str,
    site_relative: str,
    bundle_relative: str,
    metadata_relative: str,
) -> dict[str, object]:
    root = repository.resolve()
    if not (root / ".git").exists():
        raise PublicationError(f"Not a Git worktree: {root}")
    projection = _relative_directory(root, projection_relative, "projection")
    site = _relative_directory(root, site_relative, "site")
    projection_files = _files(projection)
    site_files = _files(site)
    required_projection = {
        "SHA256SUMS",
        "records.jsonl",
    }
    names = {path.relative_to(projection).as_posix() for path in projection_files}
    missing = sorted(required_projection - names)
    if missing or not any(name.startswith("content/") for name in names):
        detail = ", ".join(missing or ["content/**"])
        raise PublicationError(f"Projection is incomplete; missing {detail}")
    if not any(path.relative_to(site).as_posix() == "index.html" for path in site_files):
        raise PublicationError("Site is incomplete; missing index.html")

    source = _run(["git", "rev-parse", "HEAD^{commit}"], cwd=root)
    if _run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root):
        raise PublicationError("Tracked worktree changes would make publication ambiguous")
    date = _run(["git", "show", "-s", "--format=%cI", source], cwd=root)
    bundle = root.joinpath(*PurePosixPath(bundle_relative).parts)
    metadata = root.joinpath(*PurePosixPath(metadata_relative).parts)
    bundle.parent.mkdir(parents=True, exist_ok=True)
    metadata.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="orinoco-pages-publication-") as temporary:
        temporary_root = Path(temporary)
        projection_tree = _tree_with_projection(
            root,
            projection_relative,
            source,
            temporary_root / "projection.index",
        )
        projection_commit = _commit_tree(
            root,
            projection_tree,
            parent=source,
            message=(
                "chore(pages): record Hugo projection\n\n"
                f"Source-Commit: {source}\n"
            ),
            date=date,
        )
        pages_tree = _tree_from_directory(
            root,
            site,
            temporary_root / "pages.index",
        )
        pages_commit = _commit_tree(
            root,
            pages_tree,
            parent=projection_commit,
            message=(
                "chore(pages): publish generated site\n\n"
                f"Source-Commit: {source}\n"
                f"Projection-Commit: {projection_commit}\n"
            ),
            date=date,
        )

    try:
        _run(["git", "update-ref", PROJECTION_REF, projection_commit], cwd=root)
        _run(["git", "update-ref", PAGES_REF, pages_commit], cwd=root)
        bundle.unlink(missing_ok=True)
        _run(
            [
                "git",
                "bundle",
                "create",
                bundle,
                PROJECTION_REF,
                PAGES_REF,
                f"^{source}",
            ],
            cwd=root,
        )
    finally:
        _run(["git", "update-ref", "-d", PROJECTION_REF], cwd=root)
        _run(["git", "update-ref", "-d", PAGES_REF], cwd=root)

    result: dict[str, object] = {
        "bundle": bundle.relative_to(root).as_posix(),
        "pages": {
            "commit": pages_commit,
            "files": len(site_files),
            "ref": "refs/heads/gh-pages",
            "tree": pages_tree,
        },
        "projection": {
            "commit": projection_commit,
            "files": len(projection_files),
            "ref": "refs/heads/latest-hugo-projection",
            "tree": projection_tree,
        },
        "source": {"commit": source},
        "version": 1,
    }
    metadata.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--projection", default="generated/projection")
    parser.add_argument("--site", default="build/pages")
    parser.add_argument("--bundle", default="build/pages-publication.bundle")
    parser.add_argument("--metadata", default="build/pages-publication.json")
    args = parser.parse_args()
    try:
        result = prepare(
            args.repository,
            args.projection,
            args.site,
            args.bundle,
            args.metadata,
        )
    except PublicationError as error:
        parser.exit(1, f"prepare-pages-publication: {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
