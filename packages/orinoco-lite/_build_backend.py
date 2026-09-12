"""Build complete wheels, source archives, and editable installations."""

from pathlib import Path
import shutil
import sys

from setuptools import build_meta as _setuptools


_PACKAGE = Path(__file__).resolve().parent


def _checkout():
    root = _PACKAGE.parent.parent
    if _PACKAGE == root / "packages/orinoco-lite" and (
        root / "release/package-resources.yaml"
    ).is_file():
        return root
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
        requirements.append("nodejs-wheel>=24.15,<25")
    return requirements


def get_requires_for_build_wheel(config_settings=None):
    return _requirements(_setuptools.get_requires_for_build_wheel, config_settings)


def get_requires_for_build_sdist(config_settings=None):
    return _requirements(_setuptools.get_requires_for_build_sdist, config_settings)


def get_requires_for_build_editable(config_settings=None):
    return _requirements(_setuptools.get_requires_for_build_editable, config_settings)


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
    _resources()
    return _setuptools.build_editable(wheel_directory, config_settings, metadata_directory)
