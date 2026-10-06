"""Build wheels and source archives with prepared resources."""

from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from setuptools import build_meta as _setuptools


_PACKAGE = Path(__file__).resolve().parent


def package_dependencies():
    """Resolve package-owned Python sources from HEAD, never submodule worktrees."""
    document = tomllib.loads((_PACKAGE / "pyproject.toml").read_text())
    if "dependencies" in document["project"]:
        return document["project"]["dependencies"]  # Prepared source archive.

    def git(*arguments):
        return subprocess.check_output(
            ["git", "-C", str(_PACKAGE), *arguments], text=True, stderr=subprocess.PIPE
        ).strip()

    sources = document.get("tool", {}).get("uv", {}).get("sources", {})
    sources = {canonicalize_name(name): spec for name, spec in sources.items()}
    result = []
    for value in document["dependency-groups"]["runtime"]:
        requirement = Requirement(value)
        source = sources.get(canonicalize_name(requirement.name))
        if source is None:
            result.append(value)
            continue
        path = source["path"]
        try:
            entries = git("ls-tree", "HEAD", "--", path).split("\t", 1)
            mode, kind, commit = entries[0].split()
            if mode != "160000" or kind != "commit" or entries[1] != path:
                raise ValueError(path)
            paths = git("config", "--blob", "HEAD:.gitmodules", "--get-regexp", r"^submodule\..*\.path$")
            key = next(line.split(None, 1)[0] for line in paths.splitlines()
                       if line.split(None, 1)[1] == path)
            url = git("config", "--blob", "HEAD:.gitmodules", "--get", key[:-4] + "url")
            if url.startswith("git@"):
                host, remote_path = url.split(":", 1)
                url = f"ssh://{host}/{remote_path}"
            if not url.startswith(("https://", "ssh://")):
                raise ValueError(url)
        except (subprocess.CalledProcessError, ValueError, StopIteration, IndexError) as error:
            raise RuntimeError(f"Cannot resolve committed Python source {path}; build from a Git checkout or prepared source archive") from error
        extras = "[" + ",".join(sorted(requirement.extras)) + "]" if requirement.extras else ""
        marker = f" ; {requirement.marker}" if requirement.marker else ""
        result.append(f"{requirement.name}{extras} @ git+{url}@{commit}{marker}")
    return result


def archive_metadata(directory):
    """Bake Git-derived requirements into the sdist copy, leaving sources intact."""
    import tomlkit

    manifest = Path(directory) / "pyproject.toml"
    document = tomlkit.parse(manifest.read_text())
    document["project"]["dependencies"] = package_dependencies()
    document["project"]["dynamic"] = [name for name in document["project"]["dynamic"] if name != "dependencies"]
    document.get("dependency-groups", {}).pop("runtime", None)
    document.get("tool", {}).get("uv", {}).pop("sources", None)
    # Setuptools can hardlink files into its release tree.
    manifest.unlink()
    manifest.write_text(tomlkit.dumps(document))


def _checkout():
    if (_PACKAGE / "release/package-resources.yaml").is_file():
        return _PACKAGE
    return None


def _resources():
    root = _checkout()
    if root is None:
        if not (_PACKAGE / "src/orinoco_lite/_resources/source-commit.txt").is_file():
            raise RuntimeError(
                "Orinoco Lite source resources are missing. Install from the full "
                "orinoco-lite-dev checkout or a published source archive."
            )
        return
    sys.path.insert(0, str(_PACKAGE / "src"))
    try:
        from orinoco_lite.build_resources import build_resources

        build_resources(root, _PACKAGE / "src/orinoco_lite/_resources")
    finally:
        sys.path.pop(0)


def _requirements(base, config_settings):
    requirements = base(config_settings)
    if _checkout() is not None:
        # Node and npm compile the bundled UIs; they are not Python runtime deps.
        requirements.extend(["nodejs-wheel>=24.15,<25", "git-annex"])
    return requirements


def get_requires_for_build_wheel(config_settings=None):
    return _requirements(_setuptools.get_requires_for_build_wheel, config_settings)


def get_requires_for_build_sdist(config_settings=None):
    return _requirements(_setuptools.get_requires_for_build_sdist, config_settings)


def get_requires_for_build_editable(config_settings=None):
    return _setuptools.get_requires_for_build_editable(config_settings)


prepare_metadata_for_build_wheel = _setuptools.prepare_metadata_for_build_wheel
prepare_metadata_for_build_editable = _setuptools.prepare_metadata_for_build_editable


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    _resources()
    # Setuptools copies incrementally; obsolete hashed UI assets must not survive.
    copied_resources = _PACKAGE / "build/lib/orinoco_lite/_resources"
    if copied_resources.exists():
        shutil.rmtree(copied_resources)
    return _setuptools.build_wheel(wheel_directory, config_settings, metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    _resources()
    return _setuptools.build_sdist(sdist_directory, config_settings)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    return _setuptools.build_editable(wheel_directory, config_settings, metadata_directory)
