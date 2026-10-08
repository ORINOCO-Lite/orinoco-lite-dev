"""Connect Versioneer and Git-derived dependencies to setuptools."""

from setuptools import setup
import versioneer
from _build_backend import archive_metadata, package_dependencies


commands = versioneer.get_cmdclass()


class SourceArchive(commands["sdist"]):
    def make_release_tree(self, base_dir, files):
        super().make_release_tree(base_dir, files)
        archive_metadata(base_dir)


commands["sdist"] = SourceArchive
setup(version=versioneer.get_version(), cmdclass=commands,
      install_requires=package_dependencies())
