"""Enable and undo a downstream's editable package connection."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import tomlkit

from .errors import ConfigurationError


PACKAGE_REPOSITORY = "git@github.com:ORINOCO-Lite/orinoco-lite-dev.git"
LINK = ".orinoco-lite/dev"
FILES = ("pixi.toml", "pixi.lock", LINK)
EDITABLE = {"path": f"./{LINK}", "editable": True}


def run(*arguments: str | Path, cwd: Path) -> None:
    subprocess.run([str(value) for value in arguments], cwd=cwd, check=True)


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def check_workspace(root: Path) -> None:
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ConfigurationError("Run development commands at the downstream repository root.")
    if git(root, "status", "--porcelain", "--", *FILES):
        raise ConfigurationError("Commit or discard changes to pixi.toml, pixi.lock, and the development link first.")
    if not (root / "pixi.toml").is_file():
        raise ConfigurationError("The downstream has no pixi.toml.")


def record(root: Path, action: str, *arguments: str | Path) -> None:
    """Record only the package connection; leave unrelated site edits alone."""
    command = ["pixi", "exec", "--spec", "datalad", "--", "datalad", "--report-status", "failure", "run",
               "--explicit", "-m", f"chore: {action} editable Orinoco Lite"]
    for path in FILES:
        command.extend(("--output", path))
    run(*command, "--", sys.executable, "-m", "orinoco_lite.development",
        action, *arguments, "--apply", cwd=root)


def previous_selection(root: Path) -> object:
    commits = git(root, "log", "--first-parent", "--diff-filter=A", "--format=%H", "--", LINK).splitlines()
    if not commits:
        raise ConfigurationError("Cannot find the development link's introduction in Git history.")
    try:
        before = tomllib.loads(git(root, "show", f"{commits[0]}^:pixi.toml"))
        return before["pypi-dependencies"]["orinoco-lite"]
    except (subprocess.CalledProcessError, KeyError) as error:
        raise ConfigurationError("Cannot recover the previous package selection from Git history.") from error


def apply(root: Path, action: str, checkout: Path | None) -> None:
    manifest = root / "pixi.toml"
    document = tomlkit.parse(manifest.read_text())
    link = root / LINK
    selection = document.get("pypi-dependencies", {}).get("orinoco-lite")
    if action == "disable":
        if selection != EDITABLE or not link.is_symlink():
            raise ConfigurationError("The package connection changed; refusing to overwrite its current selection.")
        replacement = previous_selection(root)
    else:
        if link.exists() or link.is_symlink():
            raise ConfigurationError("A development link already exists. Disable it before selecting another checkout.")
        if selection is None:
            raise ConfigurationError("pixi.toml does not select an orinoco-lite package.")
        replacement = EDITABLE
    # Pixi can write the manifest before a solve fails. Restore only our files.
    saved = {name: (root / name).read_bytes() if (root / name).exists() else None
             for name in FILES[:2]}
    old_link = os.readlink(link) if link.is_symlink() else None
    try:
        if action == "enable":
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(os.path.relpath(checkout, link.parent))
        document["pypi-dependencies"]["orinoco-lite"] = replacement
        manifest.write_text(tomlkit.dumps(document))
        run("pixi", "install", "--manifest-path", manifest, cwd=root)
        if action == "disable":
            link.unlink()
    except BaseException:
        for name, content in saved.items():
            path = root / name
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        if link.is_symlink():
            link.unlink()
        if old_link is not None:
            link.symlink_to(old_link)
        raise


def enable(root: Path, path: Path | None = None) -> None:
    root = root.resolve()
    check_workspace(root)
    print("Enabling editable Orinoco Lite...", flush=True)
    checkout = (path if path is not None else root.parent / "orinoco-lite-dev").resolve()
    if not checkout.exists():
        source = Path(__file__).resolve().parents[2]
        if (source / ".git").exists() and (source / "src/orinoco_lite").is_dir():
            revision = git(source, "rev-parse", "HEAD")
        else:
            from .resources import resolve_resources, source_commit
            revision = source_commit(resolve_resources().root)
        run("git", "clone", PACKAGE_REPOSITORY, checkout, cwd=root)
        run("git", "checkout", "--detach", revision, cwd=checkout)
    if not (checkout / "pyproject.toml").is_file() or not (checkout / "src/orinoco_lite").is_dir():
        raise ConfigurationError(f"Not an Orinoco Lite source checkout: {checkout}")
    link = root / LINK
    if link.is_symlink() and link.resolve() == checkout:
        selection = tomllib.loads((root / "pixi.toml").read_text())["pypi-dependencies"]["orinoco-lite"]
        if selection != EDITABLE:
            raise ConfigurationError("The development link and package selection disagree.")
    else:
        record(root, "enable", checkout)
    # Compilation tools belong to the source checkout, not the site environment.
    for submodule, required in (
        ("submodules/pool.psychoinformatics.de-ui", "shacl-vue/package-lock.json"),
        ("submodules/things-schemas", "src/demo-research-information/unreleased.yaml"),
    ):
        if not (checkout / submodule / required).is_file():
            run("git", "submodule", "update", "--init", "--recursive", "--", submodule, cwd=checkout)
    run("pixi", "run", "--manifest-path", checkout / "pixi.toml",
        "orinoco-lite", "dev", "prepare-resources", cwd=checkout)


def disable(root: Path) -> None:
    root = root.resolve()
    check_workspace(root)
    if not (root / LINK).is_symlink():
        raise ConfigurationError("This downstream has no editable development connection.")
    print("Restoring the previous package selection...", flush=True)
    record(root, "disable")


def main() -> None:
    # Invoked by DataLad to record the actual mutation, not resource compilation.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "disable"))
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--apply", action="store_true", required=True)
    args = parser.parse_args()
    apply(Path.cwd(), args.action, args.path)


if __name__ == "__main__":
    main()
