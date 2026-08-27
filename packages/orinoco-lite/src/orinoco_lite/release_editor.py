"""Build a generic editor shell and complete dependency-license inventory."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping, Sequence

from .errors import DriverError


GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Orinoco release",
    "GIT_AUTHOR_EMAIL": "release@example.invalid",
    "GIT_COMMITTER_NAME": "Orinoco release",
    "GIT_COMMITTER_EMAIL": "release@example.invalid",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
}
SUBMISSION_ARIA_BINDING = ':aria-label="accessibleRecordSubmissionLabel(r)"'
REVIEW_BUNDLE_DISPATCH = "dispatchReviewBundle(bundle);"
REVIEW_BUNDLE_PROPOSAL = "beginReviewBundleProposal("
DOWNLOAD_AND_DISPATCH = (
    "dlJSON(bundle, reviewBundleFilename(bundle.records));\n"
    "            dispatchReviewBundle(bundle);"
)
POOL_UI_COMMIT = "668175a11e10f6f8f6eb1a9c9df25aaac58c5b83"
SHACL_VUE_COMMIT = "2d3673e0a3bd1054f41c303bc7faa4111277c2d0"


def _run(
    arguments: Sequence[str | Path],
    cwd: Path,
    *,
    environment: Mapping[str, str] | None = None,
) -> None:
    process_environment = os.environ.copy()
    if environment is not None:
        process_environment.update(environment)
    try:
        result = subprocess.run(
            [str(item) for item in arguments],
            cwd=cwd,
            env=process_environment,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise DriverError(f"Editor build command is missing: {arguments[0]}") from error
    if result.returncode:
        raise DriverError((result.stderr or result.stdout).strip())


def _git(repository: Path, *arguments: str) -> None:
    _run(
        [
            "git",
            "-c",
            "user.name=Orinoco release",
            "-c",
            "user.email=release@example.invalid",
            *arguments,
        ],
        repository,
        environment=GIT_IDENTITY,
    )


def _initialize_repository(repository: Path, source_commit: str) -> str:
    """Create deterministic Git metadata for one copied editor component."""

    git_marker = repository / ".git"
    if git_marker.exists():
        git_marker.unlink() if git_marker.is_file() else shutil.rmtree(git_marker)
    _run(["git", "init", "-q"], repository, environment=GIT_IDENTITY)
    _git(repository, "add", ".")
    _git(repository, "commit", "-qm", f"pinned source {source_commit}")
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        env={**os.environ, **GIT_IDENTITY},
        capture_output=True,
        text=True,
        check=False,
    )
    commit = result.stdout.strip()
    if result.returncode or len(commit) != 40:
        raise DriverError("Could not create deterministic editor Git metadata")
    return commit


def _apply_submission_accessibility_patch(
    shacl: Path,
    component: Path,
    patch_path: Path,
) -> None:
    """Apply and verify the reviewed, source-level submission overlay."""

    if patch_path.is_symlink() or not patch_path.is_file():
        raise DriverError("Editor submission accessibility patch is missing")
    _run(["git", "apply", "--unidiff-zero", "--check", patch_path], shacl)
    _run(["git", "apply", "--unidiff-zero", patch_path], shacl)
    source = component.read_text(encoding="utf-8")
    if (
        source.count(SUBMISSION_ARIA_BINDING) != 1
        or source.count(REVIEW_BUNDLE_DISPATCH) != 2
        or source.count(REVIEW_BUNDLE_PROPOSAL) != 1
        or source.count("Propose via GitHub") != 1
        or "return recordSubmissionLabel({" not in source
        or "recordIri: record.node_iri" not in source
        or "prefixes: allPrefixes" not in source
        or DOWNLOAD_AND_DISPATCH not in source
    ):
        raise DriverError("Editor submission patch is incomplete")


def _dependency_inventory(node_modules: Path, destination: Path) -> dict[str, Any]:
    packages: list[dict[str, Any]] = []
    licenses = destination / "texts"
    licenses.mkdir(parents=True, exist_ok=True)
    for manifest in sorted(node_modules.glob("*/package.json")) + sorted(
        node_modules.glob("@*/*/package.json")
    ):
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DriverError(f"Editor dependency manifest is invalid: {manifest}") from error
        name = value.get("name")
        version = value.get("version")
        license_value = value.get("license") or value.get("licenses")
        if not isinstance(name, str) or not isinstance(version, str):
            raise DriverError(f"Editor dependency lacks identity metadata: {manifest}")
        package_licenses: list[str] = []
        for pattern in (
            "LICENSE*",
            "license*",
            "LICENCE*",
            "licence*",
            "COPYING*",
            "NOTICE*",
        ):
            for source in sorted(manifest.parent.glob(pattern)):
                if not source.is_file() or source.is_symlink():
                    continue
                safe_name = "".join(
                    character if character.isalnum() or character in ".-_" else "-"
                    for character in name
                )
                target_name = f"{safe_name}-{version}-{source.name}"
                target = licenses / target_name
                if not target.exists():
                    shutil.copyfile(source, target)
                package_licenses.append(f"texts/{target_name}")
        if not license_value and not package_licenses:
            raise DriverError(
                f"Editor dependency has no declared license or license text: {manifest}"
            )
        if not license_value:
            license_value = "SEE-LICENSE-FILE"
        packages.append(
            {
                "license": license_value,
                "license_files": sorted(set(package_licenses)),
                "name": name,
                "version": version,
            }
        )
    packages.sort(key=lambda item: (item["name"], item["version"]))
    inventory = {
        "format": "orinoco-editor-dependency-inventory",
        "packages": packages,
        "version": 1,
    }
    (destination / "inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return inventory


def build_editor(
    pool_ui: Path,
    overlay: Path,
    shell: Path,
    licenses: Path,
) -> dict[str, Any]:
    shacl = pool_ui / "shacl-vue"
    module = shacl / "src" / "modules" / "review-bundle.js"
    submit_component = shacl / "src" / "components" / "SubmitComp.vue"
    test = shacl / "tests" / "orinoco-review-bundle-v2.test.js"
    if (
        not module.is_file()
        or not submit_component.is_file()
        or not overlay.is_dir()
    ):
        raise DriverError("Pinned pool UI or Orinoco editor overlay is missing")
    # The release workflow operates only on a copied source tree. Give each
    # copied component deterministic Git metadata because the reviewed Vite
    # configuration records `git rev-parse` values in the generic shell.
    for repository, commit in (
        (shacl, SHACL_VUE_COMMIT),
        (pool_ui, POOL_UI_COMMIT),
    ):
        _initialize_repository(repository, commit)
    shutil.copyfile(overlay / "review-bundle.js", module)
    shutil.copyfile(overlay / "review-bundle.test.js", test)
    _apply_submission_accessibility_patch(
        shacl,
        submit_component,
        overlay / "SubmitComp.vue.patch",
    )
    _run(["npm", "ci"], shacl)
    _run(["npm", "run", "test", "--", "--run", test], shacl)
    _run(["make", "build-ui"], pool_ui)
    if shell.exists():
        shutil.rmtree(shell)
    shutil.copytree(pool_ui / "dist" / "ui", shell)
    for name in (
        "config.json",
        "config.yaml",
        "dlschemas_data.ttl",
        "dlschemas_owl.ttl",
        "dlschemas_shacl.ttl",
        "config_default_xyzri.yaml",
    ):
        (shell / name).unlink(missing_ok=True)
    if licenses.exists():
        shutil.rmtree(licenses)
    licenses.mkdir(parents=True)
    inventory = _dependency_inventory(shacl / "node_modules", licenses)
    return {"dependencies": len(inventory["packages"]), "shell": str(shell)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool-ui", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--shell", type=Path, required=True)
    parser.add_argument("--licenses", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_editor(
            args.pool_ui.resolve(),
            args.overlay.resolve(),
            args.shell.resolve(),
            args.licenses.resolve(),
        )
    except DriverError as error:
        parser.exit(1, f"orinoco editor release: {error}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
