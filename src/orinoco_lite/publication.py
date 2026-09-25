"""Retain successful deployments outside the source branch."""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

from .errors import OrinocoError


PROJECTION_REF = "refs/orinoco-publication/latest-hugo-projection"
PAGES_REF = "refs/orinoco-publication/gh-pages"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"


class PublicationError(OrinocoError):
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
    parent: str | None,
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
        ["git", "commit-tree", tree, *(["-p", parent] if parent else [])],
        cwd=root,
        env=identity,
        input_text=message,
    )


def _clone_inputs(source: Path, destination: Path, revision: str) -> None:
    """Reuse the checked-out input repositories, including private submodules."""
    _run(["git", "clone", "--quiet", "--shared", "--no-checkout", source, destination], cwd=source)
    _run(["git", "checkout", "--quiet", "--detach", revision], cwd=destination)
    for entry in _run(["git", "ls-files", "--stage", "-z"], cwd=destination).split("\0"):
        if entry.startswith("160000 "):
            metadata, path = entry.split("\t", 1)
            _clone_inputs(source / path, destination / path, metadata.split()[1])


def record_projection(repository: Path) -> str:
    """Run the projection once in an isolated source checkout and retain its commit."""
    root = repository.resolve()
    source = require_clean_source(root)
    with tempfile.TemporaryDirectory(prefix="orinoco-projection-run-") as temporary:
        checkout = Path(temporary) / "source"
        _clone_inputs(root, checkout, source)
        identity = {"GIT_AUTHOR_NAME": BOT_NAME, "GIT_AUTHOR_EMAIL": BOT_EMAIL,
                    "GIT_COMMITTER_NAME": BOT_NAME, "GIT_COMMITTER_EMAIL": BOT_EMAIL}
        datalad = str(Path(sys.executable).with_name("datalad"))
        _run([datalad, "status"], cwd=checkout, env=identity)
        # Generated files are ignored in the source checkout. Stage precisely
        # this output so DataLad saves it together with the actual run record.
        _run([datalad, "run", "--explicit", "--input", ".",
              "--output", "generated/projection", "--sidecar", "no",
              "-m", "chore(pages): record Hugo projection", "--", "sh", "-c",
              "orinoco-lite projection update --no-cache && "
              "git add --force --all -- generated/projection"], cwd=checkout, env=identity)
        commit = _run(["git", "rev-parse", "HEAD"], cwd=checkout)
        if commit == source:
            raise PublicationError("Projection run did not create a DataLad commit")
        _run(["git", "fetch", "--quiet", checkout, commit], cwd=root)
        projection = root / "generated/projection"
        if projection.exists():
            shutil.rmtree(projection)
        shutil.copytree(checkout / "generated/projection", projection)
        return commit


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


def require_clean_source(root: Path) -> str:
    """Reject uncommitted publication inputs before an expensive build."""
    if not (root / ".git").exists():
        raise PublicationError(f"Not a Git worktree: {root}")
    source = _run(["git", "rev-parse", "HEAD^{commit}"], cwd=root)
    if _run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root):
        raise PublicationError("Tracked worktree changes would make publication ambiguous")
    return source


def prepare(
    repository: Path,
    projection_commit: str,
    site_relative: str,
    bundle_relative: str,
) -> None:
    root = repository.resolve()
    if not (root / ".git").exists():
        raise PublicationError(f"Not a Git worktree: {root}")
    projection = _relative_directory(root, "generated/projection", "projection")
    site = _relative_directory(root, site_relative, "site")
    projection_files = _files(projection)
    site_files = _files(site)
    required_projection = {"records.jsonl"}
    names = {path.relative_to(projection).as_posix() for path in projection_files}
    missing = sorted(required_projection - names)
    if missing or not any(name.startswith("content/") for name in names):
        detail = ", ".join(missing or ["content/**"])
        raise PublicationError(f"Projection is incomplete; missing {detail}")
    if not any(path.relative_to(site).as_posix() == "index.html" for path in site_files):
        raise PublicationError("Site is incomplete; missing index.html")

    source = require_clean_source(root)
    if _run(["git", "rev-parse", f"{projection_commit}^"], cwd=root) != source:
        raise PublicationError("Projection does not belong to this source commit")
    date = _run(["git", "show", "-s", "--format=%cI", source], cwd=root)
    bundle = root.joinpath(*PurePosixPath(bundle_relative).parts)
    bundle.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="orinoco-pages-publication-") as temporary:
        temporary_root = Path(temporary)
        pages_tree = _tree_from_directory(
            root,
            site,
            temporary_root / "pages.index",
        )
        pages_commit = _commit_tree(
            root,
            pages_tree,
            parent=None,
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

def _bounded_pages(root: Path, latest: str, previous: str | None, limit: int) -> str:
    commits = [latest]
    while previous and len(commits) < limit:
        # The old publication format has a website -> projection -> source
        # chain. Stop at the projection instead of retaining source history.
        message = _run(["git", "show", "-s", "--format=%B", previous], cwd=root)
        if not any(line.startswith("Projection-Commit: ") for line in message.splitlines()):
            break
        commits.append(previous)
        parents = _run(["git", "show", "-s", "--format=%P", previous], cwd=root).split()
        previous = parents[0] if parents else None
    parent = None
    for commit in reversed(commits):
        tree = _run(["git", "rev-parse", f"{commit}^{{tree}}"], cwd=root)
        message = _run(["git", "show", "-s", "--format=%B", commit], cwd=root)
        date = _run(["git", "show", "-s", "--format=%cI", commit], cwd=root)
        parent = _commit_tree(root, tree, parent=parent, message=message + "\n", date=date)
    return parent


def publish(root: Path, bundle_name: str, history_limit: int = 3) -> None:
    """Record the deployed output without changing the source branch."""
    if history_limit < 1:
        raise PublicationError("History limit must be at least 1")
    root = root.resolve()
    bundle = root / bundle_name
    source = _run(["git", "rev-parse", "HEAD"], cwd=root)
    _run(["git", "bundle", "verify", bundle], cwd=root)
    projection_ref = "refs/remotes/orinoco-publication/latest-hugo-projection"
    pages_ref = "refs/remotes/orinoco-publication/gh-pages"
    _run(["git", "fetch", bundle, f"+{PROJECTION_REF}:{projection_ref}",
          f"+{PAGES_REF}:{pages_ref}"], cwd=root)
    projection = _run(["git", "rev-parse", projection_ref], cwd=root)
    pages = _run(["git", "rev-parse", pages_ref], cwd=root)
    if _run(["git", "rev-parse", f"{projection}^"], cwd=root) != source:
        raise PublicationError("Publication bundle does not belong to this source commit")
    message = _run(["git", "show", "-s", "--format=%B", pages], cwd=root).splitlines()
    if (f"Projection-Commit: {projection}" not in message
            or f"Source-Commit: {source}" not in message
            or _run(["git", "show", "-s", "--format=%P", pages], cwd=root)):
        raise PublicationError("Pages commit does not belong to this projection")

    branches = ("refs/heads/latest-hugo-projection", "refs/heads/gh-pages")
    remote = dict(line.split()[::-1] for line in
                  _run(["git", "ls-remote", "--heads", "origin", *branches], cwd=root).splitlines())
    previous = remote.get(branches[1])
    if previous:
        _run(["git", "fetch", "--quiet", "origin", previous], cwd=root)
        # Retrying the record job must not count the same deployment twice.
        previous_message = _run(["git", "show", "-s", "--format=%B", previous], cwd=root)
        if (previous_message.splitlines() == message
                and remote.get(branches[0]) == projection
                and _run(["git", "rev-parse", f"{previous}^{{tree}}"], cwd=root)
                == _run(["git", "rev-parse", f"{pages}^{{tree}}"], cwd=root)):
            parents = _run(["git", "show", "-s", "--format=%P", previous], cwd=root).split()
            previous = parents[0] if parents else None
    pages = _bounded_pages(root, pages, previous, history_limit)
    _run(["git", "push", "--atomic",
          *(f"--force-with-lease={branch}:{remote.get(branch, '')}" for branch in branches),
          "origin", f"{projection}:{branches[0]}", f"{pages}:{branches[1]}"], cwd=root)


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Record a successful deployment using the Git bundle saved by build "
                     "--publication-bundle. This pushes the generated projection and website "
                     "to latest-hugo-projection and gh-pages on origin, leaving your source "
                     "branch unchanged. It does not upload the website to a hosting service."),
        epilog=("Normally run by the Pages workflow after deployment succeeds. "
                "The repository must be checked out at the source commit used for the build."),
    )
    parser.add_argument("publication_command", choices=("record",), help="save the deployed build in Git")
    parser.add_argument("--repository", type=Path, default=Path.cwd(), help="website repository (default: current directory)")
    parser.add_argument("--bundle", default="build/pages-publication.bundle", help="build bundle, relative to the repository (default: build/pages-publication.bundle)")
    parser.add_argument("--history-limit", type=int, default=3, metavar="N",
                        help="maximum successful publications retained on gh-pages, including the current publication (default: 3)")
    return parser


def execute(args: argparse.Namespace) -> int:
    try:
        publish(args.repository, args.bundle, args.history_limit)
    except PublicationError as error:
        raise SystemExit(f"publication: {error}")
    return 0


def main() -> int:
    return execute(parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
