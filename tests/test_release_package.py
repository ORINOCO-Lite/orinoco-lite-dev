from __future__ import annotations

import gzip
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from orinoco_lite.release_package import normalize_sdist


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


if __name__ == "__main__":
    unittest.main()
