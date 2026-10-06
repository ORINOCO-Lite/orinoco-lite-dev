"""Compile the package's resources from an engineering checkout at install time."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml

from .errors import DriverError
from .progress import progress
from .release_editor import build_editor
from .release_review import build_review_shell
from .release_schema import localize_schema
from .stage_resources import stage_package_resources


def selected_upstream(checkout: Path, commit: str) -> dict[str, str]:
    """Derive runtime source coordinates from committed Git declarations."""
    def git(*args):
        return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()

    path = "submodules/www-from-model"
    entry = git("ls-tree", commit, "--", path).split()
    if len(entry) != 4 or entry[:2] != ["160000", "commit"] or entry[3] != path:
        raise DriverError("Package commit must select www-from-model as a Git submodule")
    declarations = git("config", "--blob", f"{commit}:.gitmodules", "--get-regexp", r"^submodule\..*\.path$")
    key = next(line.split(None, 1)[0] for line in declarations.splitlines()
               if line.split(None, 1)[1] == path)
    repository = git("config", "--blob", f"{commit}:.gitmodules", "--get", key[:-4] + "url")
    if repository.startswith(("./", "../")):
        raise DriverError("www-from-model requires an absolute repository URL for installed builds")
    return {"repository": repository, "commit": entry[2]}


def distribution_upstream(checkout: Path, commit: str) -> tuple[Path, dict]:
    """Require the committed source closure before labeling a packaged payload."""
    upstream = checkout / "submodules/www-from-model"
    selection = selected_upstream(checkout, commit)
    if not (upstream / ".git").exists():
        raise DriverError("Initialize the www-from-model submodule and its nested dependencies before building a distribution")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(upstream), *args], text=True).strip()
    if git("rev-parse", "HEAD") != selection["commit"]:
        raise DriverError("Initialize www-from-model at the package gitlink before building a distribution")
    if any(not line.startswith(" ") for line in subprocess.check_output(
        ["git", "-C", str(upstream), "submodule", "status", "--recursive"], text=True,
    ).splitlines()):
        raise DriverError("Initialize www-from-model dependencies at their gitlinks before building a distribution")
    if git("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"):
        raise DriverError("Commit or remove www-from-model working changes before building a distribution; editable builds use them directly")
    selection["dependencies"] = {"themes/congo": git("rev-parse", "HEAD:themes/congo")}
    return upstream, selection


def build_resources(checkout: Path, destination: Path, *, editable: bool = False) -> None:
    pool = checkout / "submodules/pool.psychoinformatics.de-ui"
    schema = checkout / "submodules/things-schemas/src"
    if not (pool / "shacl-vue/package-lock.json").is_file() or not (
        schema / "demo-research-information/unreleased.yaml"
    ).is_file():
        raise DriverError(
            "Package sources are incomplete. Run git submodule update --init "
            "--recursive submodules/pool.psychoinformatics.de-ui "
            "submodules/things-schemas in the orinoco-lite-dev checkout, then reinstall."
        )
    for command in ("git", "make", "node", "npm"):
        if shutil.which(command) is None:
            raise DriverError(f"Building Orinoco Lite resources requires {command}")
    commit = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    description = subprocess.check_output(
        ["git", "-C", str(checkout), "describe", "--always"], text=True
    ).strip()
    if not editable:
        upstream, selection = distribution_upstream(checkout, commit)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Work beside the destination so the finished resource directory can be renamed.
    # Compiler patches and npm output must never modify the developer's sources.
    # Finder can recreate .DS_Store during cleanup; do not fail a completed build.
    with tempfile.TemporaryDirectory(prefix=".resources-", dir=destination.parent,
                                     ignore_cleanup_errors=True) as tmp:
        scratch = Path(tmp)
        source = scratch / "source"
        build = source / "build"
        ignore = shutil.ignore_patterns(
            ".git", "node_modules", "dist", "dist-review", ".wrangler",
            ".env*", ".dev.vars*", "__pycache__",
        )
        editor_source = scratch / "editor-source"
        with progress("Copying editor build inputs"):
            shutil.copytree(pool, editor_source, ignore=ignore)
        build_editor(
            editor_source, checkout / "release/editor-v2",
            build / "resources-editor-shell", build / "resources-editor-licenses",
        )
        localize_schema(
            schema, schema / "demo-research-information/unreleased.yaml",
            build / "resources-schema",
        )
        application = scratch / "review-source"
        with progress("Copying source-review build inputs"):
            shutil.copytree(checkout / "packages/curation-review-app", application, ignore=ignore)
        build_review_shell(
            application, build / "resources-review-shell", build / "resources-review-licenses",
        )
        spec = checkout / "release/package-resources.yaml"
        for resource in yaml.safe_load(spec.read_text())["resources"]:
            relative = Path(resource["source"])
            if relative.parts[0] == "build":
                continue
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(checkout / relative, target)
        staged_spec = source / "release/package-resources.yaml"
        shutil.copyfile(spec, staged_spec)
        ready = scratch / "resources"
        stage_package_resources(
            staged_spec, ready, source_commit=commit, source_description=description,
        )
        if not editable:
            from .upstream_runtime import stage_upstream_runtime
            stage_upstream_runtime(upstream, ready / "www-from-model")
            (ready / "www-from-model.json").write_text(
                json.dumps(selection) + "\n", encoding="utf-8",
            )
        previous = scratch / "previous"
        if destination.exists():
            destination.rename(previous)
        try:
            ready.rename(destination)
        except OSError:
            if previous.exists():
                previous.rename(destination)
            raise
