"""Prepare reproducible source archives and the release Pixi environment."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import gzip
import io
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
from typing import Sequence

from .progress import progress
from .errors import DriverError


def release_environment(root: Path, revision: str, repository_url: str) -> str:
    """Generate runtime Pixi TOML using only the selected commit's inputs."""
    import tomlkit

    def git(*args: str) -> str:
        try:
            return subprocess.check_output(
                ["git", "-C", str(root), *args], text=True, stderr=subprocess.PIPE
            ).strip()
        except subprocess.CalledProcessError as error:
            raise DriverError(error.stderr.strip()) from error

    def remote_url(url: str) -> str:
        if not url.startswith(("https://", "ssh://", "git@")):
            raise DriverError(f"Release sources require a remote repository URL: {url}")
        return url

    commit = git("rev-parse", "--verify", f"{revision}^{{commit}}")
    manifest = tomlkit.parse(git("show", f"{commit}:pixi.toml"))
    module_blob = f"{commit}:.gitmodules"
    paths = git("config", "--blob", module_blob, "--get-regexp", r"^submodule\..*\.path$")
    urls = {}
    for line in paths.splitlines():
        key, path = line.split(None, 1)
        urls[path] = git("config", "--blob", module_blob, "--get", key[:-4] + "url")
    # Features are explicitly development-only in this project's manifest.
    features = manifest.pop("feature", {})
    if set(features) - {"dev", "skills"}:
        raise DriverError("Classify new Pixi features before generating a release")
    manifest.pop("environments", None)

    def transform(table: Mapping) -> None:
        for key, value in list(table.items()):
            if key in {"pypi-dependencies", "dependency-overrides"}:
                for name, spec in list(value.items()):
                    if not isinstance(spec, Mapping) or "path" not in spec:
                        continue
                    path = spec["path"]
                    if name == "orinoco-lite" and path == ".":
                        url, sha = remote_url(repository_url), commit
                    else:
                        if path not in urls:
                            raise DriverError(f"Unresolved release source: {name} = {path}")
                        entry = git("ls-tree", "-z", commit, "--", path).split("\t", 1)[0].split()
                        if len(entry) != 3 or entry[:2] != ["160000", "commit"]:
                            raise DriverError(f"Release source is not a gitlink: {path}")
                        url, sha = remote_url(urls[path]), entry[2]
                    replacement = tomlkit.inline_table()
                    replacement.update({
                        k: v for k, v in spec.items() if k not in {"path", "editable"}
                    })
                    replacement.update(git=url, rev=sha)
                    value[name] = replacement
            elif isinstance(value, Mapping):
                transform(value)

    transform(manifest)
    return tomlkit.dumps(manifest)


@progress("Normalizing the source archive")
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
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("archive", type=Path, nargs="?")
    parser.add_argument("--epoch", type=int, default=0)
    parser.add_argument(
        "--environment", action="store_true",
        help="Write release Pixi TOML to stdout instead of normalizing an archive",
    )
    parser.add_argument(
        "--revision", default="HEAD",
        help="Commit supplying the manifest and gitlinks (default: HEAD)",
    )
    parser.add_argument(
        "--repository-url",
        help="Remote Orinoco Lite repository URL for the release environment",
    )
    args = parser.parse_args(argv)
    if args.environment and (args.archive or not args.repository_url):
        parser.error("--environment requires --repository-url and no archive")
    if not args.environment and not args.archive:
        parser.error("an archive or --environment is required")
    try:
        if args.environment:
            print(release_environment(Path.cwd(), args.revision, args.repository_url), end="")
        else:
            normalize_sdist(args.archive.resolve(), epoch=args.epoch)
    except DriverError as error:
        parser.exit(1, f"orinoco package release: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
