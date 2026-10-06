"""Enable editable package development in a downstream environment."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import tomlkit

from .errors import ConfigurationError
from .progress import progress


PACKAGE_REPOSITORY = "https://github.com/ORINOCO-Lite/orinoco-lite-dev.git"
CHECKOUT = ".orinoco-lite/orinoco-lite-dev"
FILES = ("pixi.toml", "pixi.lock")
EDITABLE = {"path": CHECKOUT, "editable": True}
CLIENT = "dump-things-pyclient"


def run(*arguments: str | Path, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run([str(value) for value in arguments], cwd=cwd,
                   stdout=sys.stderr, env=env, check=True)


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def unlocked_environment() -> dict[str, str]:
    environment = dict(os.environ)
    environment.pop("PIXI_LOCKED", None)
    return environment


def check_workspace(root: Path) -> None:
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ConfigurationError("Run development commands at the downstream repository root.")
    if not (root / "pixi.toml").is_file():
        raise ConfigurationError("The downstream has no pixi.toml.")


def apply(root: Path) -> None:
    manifest = root / "pixi.toml"
    document = tomlkit.parse(manifest.read_text())
    document["pypi-dependencies"]["orinoco-lite"] = EDITABLE
    # Pixi may update a lock before installation fails. Restore our files and
    # retain the source checkout, including all of the developer's edits.
    saved = {name: (root / name).read_bytes() if (root / name).exists() else None for name in FILES}
    try:
        manifest.write_text(tomlkit.dumps(document))
        run("pixi", "install", "--manifest-path", manifest, cwd=root, env=unlocked_environment())
    except BaseException:
        for name, content in saved.items():
            if content is None:
                (root / name).unlink(missing_ok=True)
            else:
                (root / name).write_bytes(content)
        print("Restored pixi.toml and pixi.lock. Source edits were retained; "
              "run pixi install --locked to resynchronize the environment.", file=sys.stderr, flush=True)
        raise


def prepare_checkout(root: Path, repository: str | None, revision: str | None) -> Path:
    checkout = root / CHECKOUT
    if checkout.is_symlink():
        raise ConfigurationError(f"{CHECKOUT} must be a real source checkout, not a symlink.")
    if not git(root, "ls-files", "--", CHECKOUT):
        exclude = Path(git(root, "rev-parse", "--git-path", "info/exclude"))
        if not exclude.is_absolute():
            exclude = root / exclude
        pattern = f"/{CHECKOUT}/"
        content = exclude.read_text() if exclude.exists() else ""
        if pattern not in content.splitlines():
            exclude.parent.mkdir(parents=True, exist_ok=True)
            exclude.write_text(content + ("\n" if content and not content.endswith("\n") else "") + pattern + "\n")
    if not checkout.exists():
        document = tomlkit.parse((root / "pixi.toml").read_text())
        selection = document["pypi-dependencies"]["orinoco-lite"]
        if isinstance(selection, dict):
            repository = repository or selection.get("git")
            revision = revision or selection.get("rev")
        if revision is None:
            from .resources import resolve_resources, source_commit
            revision = source_commit(resolve_resources().root)
        if revision.startswith("-"):
            raise ConfigurationError("Supply a Git revision, not a command option.")
        with progress("Cloning Orinoco Lite source"):
            checkout.parent.mkdir(parents=True, exist_ok=True)
            run("git", "clone", "--quiet", "--", repository or PACKAGE_REPOSITORY,
                checkout, cwd=root)
        run("git", "checkout", "--quiet", "--detach", revision, cwd=checkout)
        with progress("Initializing pinned development dependencies"):
            run("git", "submodule", "update", "--quiet", "--init", "--recursive",
                cwd=checkout)
    elif repository is not None or revision is not None:
        raise ConfigurationError(f"{CHECKOUT} already exists; use Git inside it to select another revision.")
    if not (checkout / ".git").exists():
        raise ConfigurationError(f"Not a Git source checkout: {checkout}")
    # Do not reset existing source or nested dependency worktrees on re-enable.
    if any(line.startswith("-") for line in git(checkout, "submodule", "status", "--recursive").splitlines()):
        raise ConfigurationError(f"Initialize missing dependencies with git -C {CHECKOUT} "
                                 "submodule update --init --recursive before enabling development.")
    if not (checkout / "src/orinoco_lite").is_dir():
        raise ConfigurationError(f"Not an Orinoco Lite source checkout: {checkout}")
    metadata = tomlkit.parse((checkout / "pyproject.toml").read_text())
    expected = {"path": f"submodules/{CLIENT}", "editable": True}
    if metadata.get("tool", {}).get("uv", {}).get("sources", {}).get(CLIENT) != expected:
        raise ConfigurationError("The selected package predates nested editable dependency support. "
                                 f"Select an updated commit in {CHECKOUT} before enabling development.")
    return checkout


def prepare_resources(checkout: Path) -> None:
    # Build tools belong to the package's compilation environment. Website and
    # adapter commands continue to use only the downstream environment.
    print("Preparing editable package resources...", file=sys.stderr, flush=True)
    run("pixi", "run", "--manifest-path", checkout / "pixi.toml",
        "orinoco-lite", "dev", "prepare-resources", cwd=checkout,
        env=unlocked_environment())


def enable(root: Path, repository: str | None = None, revision: str | None = None) -> None:
    root = root.resolve()
    if (root / "src/orinoco_lite").is_dir():
        raise ConfigurationError("This is an Orinoco Lite source checkout. Run 'dev enable' from a downstream website.")
    check_workspace(root)
    document = tomlkit.parse((root / "pixi.toml").read_text())
    selection = document.get("pypi-dependencies", {}).get("orinoco-lite")
    if selection is None or (isinstance(selection, dict) and "path" in selection and selection != EDITABLE):
        raise ConfigurationError("Select a package revision or the development checkout before enabling development.")
    print("Enabling editable Orinoco Lite...", file=sys.stderr, flush=True)
    checkout = prepare_checkout(root, repository, revision)
    prepare_resources(checkout)
    with progress("Installing editable Orinoco Lite in the downstream Pixi environment"):
        apply(root)
    selected_revision = git(checkout, "rev-parse", "--short", "HEAD")
    branch = subprocess.run(
        ["git", "-C", str(checkout), "symbolic-ref", "--short", "-q", "HEAD"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    source = checkout.relative_to(root)
    state = f"{source} @ {selected_revision}"
    if not branch:
        state += " (detached HEAD)"
    print(f"Editable Orinoco Lite enabled: {state}\n"
          "Updated pixi.toml and pixi.lock locally.", file=sys.stderr, flush=True)
