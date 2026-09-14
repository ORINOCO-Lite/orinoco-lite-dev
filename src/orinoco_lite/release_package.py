"""Normalize Python source archives for byte-reproducible releases."""

from __future__ import annotations

import argparse
import gzip
import io
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
from typing import Sequence

from .errors import DriverError


def normalize_sdist(path: Path, *, epoch: int = 0) -> None:
    """Replace a setuptools sdist with a canonical tar+gzip representation."""

    if path.is_symlink() or not path.is_file() or epoch < 0:
        raise DriverError("Source archive and epoch must be valid")
    entries: list[tuple[tarfile.TarInfo, bytes | None]] = []
    names: set[str] = set()
    try:
        with tarfile.open(path, "r:gz") as source:
            for member in source.getmembers():
                name = PurePosixPath(member.name)
                if (
                    name.is_absolute()
                    or ".." in name.parts
                    or name.as_posix() != member.name
                    or member.name in names
                    or not (member.isfile() or member.isdir())
                ):
                    raise DriverError("Source archive contains an unsafe member")
                names.add(member.name)
                payload = source.extractfile(member).read() if member.isfile() else None
                entries.append((member, payload))
    except (OSError, tarfile.TarError) as error:
        raise DriverError(f"Could not read source archive: {path}") from error

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".normalized", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        tar_buffer = io.BytesIO()
        with tarfile.open(
            fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT
        ) as target:
            for original, payload in sorted(entries, key=lambda item: item[0].name):
                normalized = tarfile.TarInfo(original.name)
                normalized.type = tarfile.DIRTYPE if original.isdir() else tarfile.REGTYPE
                normalized.size = 0 if payload is None else len(payload)
                normalized.mode = 0o755 if original.isdir() or original.mode & 0o111 else 0o644
                normalized.mtime = epoch
                normalized.uid = normalized.gid = 0
                normalized.uname = normalized.gname = ""
                target.addfile(
                    normalized,
                    None if payload is None else io.BytesIO(payload),
                )
        with temporary.open("wb") as raw:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=epoch, compresslevel=9
            ) as compressed:
                compressed.write(tar_buffer.getvalue())
            raw.flush()
            os.fsync(raw.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--epoch", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        normalize_sdist(args.archive.resolve(), epoch=args.epoch)
    except DriverError as error:
        parser.exit(1, f"orinoco package release: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
