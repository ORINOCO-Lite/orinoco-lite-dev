from __future__ import annotations

import gzip
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import subprocess
import tomllib

from orinoco_lite.errors import DriverError

from orinoco_lite.release_package import normalize_sdist, release_environment


class ReproducibleSourceArchiveTests(unittest.TestCase):
    def test_normalization_removes_archive_metadata_variance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archives = []
            for index, timestamp in enumerate((100, 200)):
                archive = root / f"source-{index}.tar.gz"
                buffer = io.BytesIO()
                with tarfile.open(fileobj=buffer, mode="w") as stream:
                    member = tarfile.TarInfo("example-1.0/file.txt")
                    member.size = 8
                    member.uid = timestamp
                    member.mtime = timestamp
                    stream.addfile(member, io.BytesIO(b"payload\n"))
                with archive.open("wb") as raw:
                    with gzip.GzipFile(
                        filename=f"source-{index}.tar",
                        mode="wb",
                        fileobj=raw,
                        mtime=timestamp,
                    ) as stream:
                        stream.write(buffer.getvalue())
                normalize_sdist(archive)
                archives.append(archive)
            self.assertEqual(archives[0].read_bytes(), archives[1].read_bytes())


class ReleaseEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Release test fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("commit", "--allow-empty", "-qm", "test: source commit")
        self.source = self.git("rev-parse", "HEAD")
        (self.root / ".gitmodules").write_text(
            '[submodule "client"]\npath = submodules/client\n'
            'url = https://example.org/client.git\n'
        )
        (self.root / "pixi.toml").write_text("""
[workspace]
name = "fixture"
channels = ["conda-forge"]
platforms = ["linux-64"]
[dependencies]
python = "3.12.*"
hugo = "==0.154.5"
[pypi-dependencies]
orinoco-lite = {path = ".", editable = true}
client = {path = "submodules/client", editable = true, extras = ["extra"]}
published = "==1.2.3"
[pypi-options.dependency-overrides]
client = {path = "submodules/client", editable = true}
[feature.dev.pypi-dependencies]
pytest = "*"
[environments]
default = ["dev"]
""")
        self.git("add", "pixi.toml", ".gitmodules")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.source},submodules/client")
        self.git("commit", "-qm", "test: release manifest")
        self.release = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def test_uses_committed_sources_and_preserves_requirements(self):
        # Neither a staged repin nor uncommitted metadata may change this release.
        self.git("update-index", "--cacheinfo", f"160000,{self.release},submodules/client")
        (self.root / ".gitmodules").write_text("invalid working copy")
        (self.root / "pixi.toml").write_text("invalid working copy")
        result = tomllib.loads(release_environment(self.root, self.release, "https://example.org/lite.git"))
        self.assertEqual(result["dependencies"]["hugo"], "==0.154.5")
        deps = result["pypi-dependencies"]
        self.assertEqual(deps["published"], "==1.2.3")
        self.assertEqual(deps["client"], {"git": "https://example.org/client.git", "rev": self.source, "extras": ["extra"]})
        self.assertEqual(deps["orinoco-lite"]["rev"], self.release)
        self.assertEqual(result["pypi-options"]["dependency-overrides"]["client"]["rev"], self.source)
        self.assertNotIn("feature", result)
        self.assertNotIn("editable", deps["client"])

    def test_rejects_unresolved_local_source(self):
        manifest = self.root / "pixi.toml"
        manifest.write_text(manifest.read_text().replace("submodules/client", "../untracked"))
        self.git("add", "pixi.toml")
        self.git("commit", "-qm", "test: unresolved source")
        with self.assertRaisesRegex(DriverError, "Unresolved release source"):
            release_environment(self.root, "HEAD", "https://example.org/lite.git")


if __name__ == "__main__":
    unittest.main()
