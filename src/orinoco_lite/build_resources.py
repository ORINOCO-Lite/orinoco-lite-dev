"""Compile the package's resources from an engineering checkout at install time."""

from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml

from .errors import DriverError
from .release_editor import build_editor
from .release_review import build_review_shell
from .release_schema import localize_schema
from .stage_resources import stage_package_resources


def build_resources(checkout: Path, destination: Path) -> None:
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
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Work beside the destination so the finished resource directory can be renamed.
    # Compiler patches and npm output must never modify the developer's sources.
    with tempfile.TemporaryDirectory(prefix=".resources-", dir=destination.parent) as tmp:
        scratch = Path(tmp)
        source = scratch / "source"
        build = source / "build"
        ignore = shutil.ignore_patterns(
            ".git", "node_modules", "dist", "dist-review", ".wrangler",
            ".env*", ".dev.vars*", "__pycache__",
        )
        editor_source = scratch / "editor-source"
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
        previous = scratch / "previous"
        if destination.exists():
            destination.rename(previous)
        try:
            ready.rename(destination)
        except OSError:
            if previous.exists():
                previous.rename(destination)
            raise
