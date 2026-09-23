"""Connect Versioneer to the setuptools build commands."""

from setuptools import setup
import versioneer

setup(version=versioneer.get_version(), cmdclass=versioneer.get_cmdclass())
