"""Apply Copier updates and record the actual transformation with DataLad."""

from pathlib import Path
import os
import re
import subprocess
import tempfile
import tomllib

import yaml

from .errors import ConfigurationError
from . import package_update


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def answers(root: Path) -> dict:
    path = root / ".copier-answers.yml"
    if not path.is_file():
        raise ConfigurationError("Run template update in a Copier-generated downstream.")
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict) or not value.get("_src_path") or not value.get("_commit"):
        raise ConfigurationError("Copier answers must contain _src_path and _commit.")
    return value


def require_clean(root: Path) -> None:
    if git(root, "status", "--porcelain"):
        raise ConfigurationError("Commit or stash downstream changes before updating the template.")


def conflicts(root: Path) -> list[str]:
    """Find unresolved Copier markers, including after the update was committed."""
    result = subprocess.run(
        ["git", "-C", str(root), "grep", "-l", "-E",
         "^(<<<<<<< before updating|>>>>>>> after updating)$", "--", "."],
        text=True, capture_output=True,
    )
    if result.returncode not in (0, 1):
        raise ConfigurationError(result.stderr.strip())
    return result.stdout.splitlines()


def template_environment(root: Path, source: str, revision: str) -> tuple[str, str, bytes]:
    from copier import run_copy

    data = {key: value for key, value in answers(root).items()
            if not key.startswith("_") and key not in {"package_repository", "package_revision"}}
    with tempfile.TemporaryDirectory(prefix="orinoco-template-") as temporary:
        run_copy(source, temporary, vcs_ref=revision, data=data, defaults=True, quiet=True)
        declaration = tomllib.loads((Path(temporary) / "pixi.toml").read_text())
        selection = declaration["pypi-dependencies"]["orinoco-lite"]
        return selection["git"], selection["rev"], (Path(temporary) / "pixi.lock").read_bytes()


def apply(root: Path, revision: str, package_repository: str, package_revision: str) -> None:
    """The public, non-recording operation stored in the DataLad run record."""
    from copier import run_update

    for selection in (revision, package_revision):
        if not re.fullmatch(r"[0-9a-f]{40}", selection):
            raise ConfigurationError("template apply requires full template and package commit SHAs.")
    require_clean(root)
    # The lock is derived from the merged manifest. Merging generated lock text
    # would manufacture conflicts unrelated to the maintainer's dependency choices.
    run_update(root, vcs_ref=revision, defaults=True, overwrite=True, conflict="inline",
               data={"package_repository": package_repository, "package_revision": package_revision},
               skip_if_exists=["pixi.lock"])
    unmerged = git(root, "diff", "--name-only", "--diff-filter=U").splitlines()
    if unmerged:
        # Keep the conflict text as ordinary Git content so a browser can edit it.
        subprocess.run(["git", "add", "--", *unmerged], cwd=root, check=True)
    unresolved = conflicts(root)
    if "pixi.toml" not in unresolved:
        # Start from the target's retained dependency choices, not a fresh solve
        # against whatever versions happen to be available on the update day.
        _, _, lock = template_environment(root, answers(root)["_src_path"], revision)
        (root / "pixi.lock").write_bytes(lock)
        environment = dict(os.environ)
        environment.pop("PIXI_LOCKED", None)
        subprocess.run(["pixi", "lock", "--manifest-path", "pixi.toml"],
                       cwd=root, env=environment, check=True)
    if unresolved:
        print("Template update conflicts (recorded for deliberate resolution):")
        print("\n".join(unresolved))


def record_apply(root: Path, revision: str, repository: str, package_revision: str, message: str) -> None:
    environment = os.environ.get("ORINOCO_UPDATE_ENVIRONMENT")
    replay = (f"Execution environment: {environment} (pixi.toml and pixi.lock).\n"
              if environment else "Restore the parent commit's Pixi environment before historical replay.\n")
    subprocess.run([
        "datalad", "run", "--explicit", "--input", ".copier-answers.yml",
        "--input", "pixi.toml", "--input", "pixi.lock", "--output", ".",
        "-m", message + "\n\n"
        + replay +
        "Conflict markers, when present, require a separate human resolution.",
        "--", "orinoco-lite", "template", "apply", "--revision", revision,
        "--package-repository", repository, "--package-revision", package_revision,
    ], cwd=root, check=True)


def resolve_template(source: str, revision: str) -> str:
    if revision != "latest":
        return package_update.resolve_commit(source, revision)
    # Use Copier's release ordering, including this project's release candidates.
    from copier import run_copy

    with tempfile.TemporaryDirectory(prefix="orinoco-release-") as temporary:
        result = run_copy(source, temporary, defaults=True, quiet=True,
                          use_prereleases=True, skip_tasks=True)
        # Copier falls back to HEAD without a version tag. Do not silently turn
        # the release choice into the development choice in that case.
        release = result.template.commit
        if not release or re.fullmatch(r"[0-9a-f]{7,40}", release):
            raise ConfigurationError("The template has no release tag; select main or an explicit commit.")
        return package_update.resolve_commit(source, release)


def update(root: Path, revision: str = "latest", package_repository: str | None = None,
           package_revision: str | None = None) -> int:
    root = root.resolve()
    require_clean(root)
    previous = answers(root)
    # Copier accepts its gh: shorthand; Git's resolver needs the corresponding URL.
    source = previous["_src_path"]
    if source.startswith("gh:"):
        source = "https://github.com/" + source[3:] + ".git"
    commit = resolve_template(source, revision)
    repository, default_revision, _ = template_environment(root, source, commit)
    default_commit = package_update.resolve_commit(repository, default_revision)
    # Resolve overrides before changing the repository, but apply them separately.
    override_repository = package_repository or repository
    override_commit = (package_update.resolve_commit(override_repository, package_revision or default_commit)
                       if package_repository or package_revision else None)
    if not (root / ".datalad/config").exists():
        subprocess.run(["datalad", "create", "--force", "--no-annex", "."], cwd=root, check=True)
    subprocess.run(["datalad", "status"], cwd=root, check=True)
    record_apply(root, commit, repository, default_commit, "chore: update downstream template")
    unresolved = conflicts(root)
    if unresolved:
        print("Resolve template update conflicts, commit, and run template update again:\n"
              + "\n".join(unresolved))
        return 1
    if override_commit is not None:
        # Updating the same template with Copier also records the override in
        # its answers, so the next update sees the correct regeneration baseline.
        record_apply(root, commit, override_repository, override_commit,
                     "chore: select downstream package override")
    print("Template update recorded. Start a fresh pixi run to validate and build.")
    return 0


def register(commands):
    template = commands.add_parser("template", help="update the downstream using Copier and DataLad")
    actions = template.add_subparsers(dest="template_command", required=True)
    for name, description in (
        ("update", "resolve selections and record a Copier update with DataLad"),
        ("apply", "apply resolved selections without creating another DataLad run"),
    ):
        parser = actions.add_parser(name, help=description, description=description)
        parser.add_argument("--revision", required=name == "apply", default="latest",
                            help="template revision (default: latest release; full commit SHA for apply)")
        parser.add_argument("--package-repository", required=name == "apply",
                            help="package repository (default: selected template declaration)")
        parser.add_argument("--package-revision", required=name == "apply",
                            help="package revision (default: selected template declaration)")


def execute(args) -> int:
    from copier.errors import UserMessageError

    root = args.root or Path.cwd()
    try:
        if args.template_command == "apply":
            apply(root, args.revision, args.package_repository, args.package_revision)
            return 0
        return update(root, args.revision, args.package_repository, args.package_revision)
    except (UserMessageError, ValueError, KeyError) as error:
        raise ConfigurationError(str(error)) from error
