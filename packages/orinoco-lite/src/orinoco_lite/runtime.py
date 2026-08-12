"""Build, install, and verify immutable Orinoco Lite runtime releases."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile
from typing import Any, Mapping, Sequence
from urllib.request import Request, urlopen

import yaml

from .config import CONFIG_CONTRACT_VERSION, EngineLock, WorkspaceConfig
from .errors import ConfigurationError, IntegrityError
from .integrity import (
    canonical_json_bytes,
    resource_checksum_lines,
    sha256_file,
    tree_sha256,
)


RUNTIME_FORMAT = "orinoco-lite-runtime"
RUNTIME_MANIFEST_VERSION = 1
RUNTIME_SPEC_FORMAT = "orinoco-lite-runtime-source"
RUNTIME_SPEC_VERSION = 1
RUNTIME_ROOT_NAME = "orinoco-runtime"
MANIFEST_NAME = "runtime-manifest.json"
CHECKSUMS_NAME = "SHA256SUMS"
MAX_RUNTIME_BYTES = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class RuntimeManifest:
    path: Path
    release: str
    commands: Mapping[str, tuple[str, ...]]
    files: tuple[Mapping[str, Any], ...]
    raw: Mapping[str, Any]
    sha256: str


@dataclass(frozen=True)
class RuntimeReport:
    root: Path
    release: str
    manifest_sha256: str
    tree_sha256: str
    files: int
    commands: tuple[str, ...]


def _relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise IntegrityError(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", "..", ".git"} for part in path.parts)
    ):
        raise IntegrityError(f"{label} must be a normalized safe relative path")
    return path.as_posix()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise IntegrityError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IntegrityError(f"{label} is not valid UTF-8 JSON: {path}") from error
    if not isinstance(value, dict):
        raise IntegrityError(f"{label} must be a JSON object")
    return value


def load_runtime_manifest(path: Path) -> RuntimeManifest:
    raw = _read_json(path, "Runtime manifest")
    if raw.get("format") != RUNTIME_FORMAT:
        raise IntegrityError(f"Runtime manifest format must be {RUNTIME_FORMAT}")
    if raw.get("manifest_version") != RUNTIME_MANIFEST_VERSION:
        raise IntegrityError(
            f"Runtime manifest version must be {RUNTIME_MANIFEST_VERSION}"
        )
    release = raw.get("release")
    if not isinstance(release, str) or not release:
        raise IntegrityError("Runtime manifest release must be a string")
    compatibility = raw.get("compatibility")
    if not isinstance(compatibility, dict):
        raise IntegrityError("Runtime manifest compatibility must be an object")
    contracts = compatibility.get("config")
    if (
        not isinstance(contracts, list)
        or not contracts
        or not all(isinstance(item, int) for item in contracts)
    ):
        raise IntegrityError("Runtime compatibility.config must be integer versions")
    if CONFIG_CONTRACT_VERSION not in contracts:
        raise IntegrityError(
            f"Runtime does not support config contract {CONFIG_CONTRACT_VERSION}"
        )

    commands_value = raw.get("commands")
    if not isinstance(commands_value, dict):
        raise IntegrityError("Runtime manifest commands must be an object")
    commands: dict[str, tuple[str, ...]] = {}
    for name, command in commands_value.items():
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(command, list)
            or not command
            or not all(
                isinstance(token, str) and token and "\0" not in token
                for token in command
            )
        ):
            raise IntegrityError(f"Runtime command is malformed: {name!r}")
        commands[name] = tuple(command)

    files_value = raw.get("files")
    if not isinstance(files_value, list) or not files_value:
        raise IntegrityError("Runtime manifest files must be a non-empty array")
    files: list[Mapping[str, Any]] = []
    names: set[str] = set()
    for entry in files_value:
        if not isinstance(entry, dict):
            raise IntegrityError("Runtime manifest file entries must be objects")
        name = _relative(entry.get("path"), "Runtime resource path")
        digest = entry.get("sha256")
        size = entry.get("size")
        mode = entry.get("mode")
        if name in names:
            raise IntegrityError(f"Runtime resource is declared twice: {name}")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(size, int)
            or size < 0
            or mode not in {0o644, 0o755}
        ):
            raise IntegrityError(f"Runtime resource metadata is invalid: {name}")
        names.add(name)
        files.append({"path": name, "sha256": digest, "size": size, "mode": mode})

    licenses = raw.get("licenses")
    if (
        not isinstance(licenses, list)
        or not licenses
        or not all(isinstance(item, str) and item in names for item in licenses)
    ):
        raise IntegrityError(
            "Runtime manifest must identify at least one included license resource"
        )
    return RuntimeManifest(
        path=path.resolve(),
        release=release,
        commands=commands,
        files=tuple(files),
        raw=raw,
        sha256=sha256_file(path),
    )


def verify_runtime_directory(
    root: Path,
    *,
    expected_release: str | None = None,
    expected_manifest_sha256: str | None = None,
    expected_tree_sha256: str | None = None,
) -> RuntimeReport:
    root = root.resolve()
    if root.name == RUNTIME_ROOT_NAME and root.is_dir():
        runtime_root = root
    elif (root / RUNTIME_ROOT_NAME).is_dir():
        runtime_root = (root / RUNTIME_ROOT_NAME).resolve()
    else:
        raise IntegrityError(f"Runtime root is missing {RUNTIME_ROOT_NAME}/: {root}")
    manifest = load_runtime_manifest(runtime_root / MANIFEST_NAME)
    if expected_release is not None and manifest.release != expected_release:
        raise IntegrityError(
            f"Runtime release is {manifest.release}, expected {expected_release}"
        )
    if (
        expected_manifest_sha256 is not None
        and manifest.sha256 != expected_manifest_sha256
    ):
        raise IntegrityError("Runtime manifest does not match orinoco.lock")

    expected_files = {entry["path"]: entry for entry in manifest.files}
    actual_files: dict[str, Path] = {}
    for candidate in runtime_root.rglob("*"):
        if candidate.is_symlink():
            raise IntegrityError(
                f"Runtime contains a forbidden symlink: {candidate.relative_to(runtime_root)}"
            )
        if candidate.is_file():
            actual_files[candidate.relative_to(runtime_root).as_posix()] = candidate
        elif not candidate.is_dir():
            raise IntegrityError(
                f"Runtime contains a non-regular resource: {candidate.relative_to(runtime_root)}"
            )
    metadata_files = {MANIFEST_NAME, CHECKSUMS_NAME}
    expected_inventory = set(expected_files) | metadata_files
    if set(actual_files) != expected_inventory:
        raise IntegrityError(
            "Runtime file inventory differs from its manifest: "
            f"missing={sorted(expected_inventory - set(actual_files))}, "
            f"undeclared={sorted(set(actual_files) - set(expected_files) - metadata_files)}"
        )
    checksum_entries: list[tuple[str, str]] = []
    for name, entry in expected_files.items():
        path = actual_files[name]
        digest = sha256_file(path)
        if digest != entry["sha256"] or path.stat().st_size != entry["size"]:
            raise IntegrityError(f"Runtime resource failed integrity verification: {name}")
        mode = stat.S_IMODE(path.stat().st_mode)
        expected_executable = entry["mode"] == 0o755
        if bool(mode & 0o111) != expected_executable:
            raise IntegrityError(f"Runtime resource mode is wrong: {name}")
        checksum_entries.append((name, digest))
    checksum_entries.append((MANIFEST_NAME, manifest.sha256))
    expected_checksums = resource_checksum_lines(checksum_entries)
    try:
        actual_checksums = actual_files[CHECKSUMS_NAME].read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise IntegrityError("Runtime SHA256SUMS is not UTF-8 text") from error
    if actual_checksums != expected_checksums:
        raise IntegrityError("Runtime SHA256SUMS does not match the manifest")
    tree_digest = tree_sha256(runtime_root)
    if expected_tree_sha256 is not None and tree_digest != expected_tree_sha256:
        raise IntegrityError("Runtime directory tree does not match orinoco.lock")
    return RuntimeReport(
        root=runtime_root,
        release=manifest.release,
        manifest_sha256=manifest.sha256,
        tree_sha256=tree_digest,
        files=len(expected_files),
        commands=tuple(sorted(manifest.commands)),
    )


def _safe_extract(archive: Path, destination: Path) -> Path:
    total_size = 0
    names: set[str] = set()
    try:
        stream = tarfile.open(archive, mode="r:gz")
    except (OSError, tarfile.TarError) as error:
        raise IntegrityError(f"Runtime archive is not a valid tar.gz: {archive}") from error
    with stream:
        members = stream.getmembers()
        for member in members:
            posix = PurePosixPath(member.name)
            if (
                posix.is_absolute()
                or not posix.parts
                or posix.parts[0] != RUNTIME_ROOT_NAME
                or any(part in {"", ".", ".."} for part in posix.parts)
                or member.name in names
                or not (member.isdir() or member.isreg())
            ):
                raise IntegrityError(f"Runtime archive has an unsafe member: {member.name}")
            names.add(member.name)
            if member.isreg():
                total_size += member.size
                if total_size > MAX_RUNTIME_BYTES:
                    raise IntegrityError("Runtime archive expands beyond the 2 GiB limit")
        stream.extractall(destination, filter="data")
    root = destination / RUNTIME_ROOT_NAME
    if not root.is_dir():
        raise IntegrityError("Runtime archive has no orinoco-runtime root")
    return root


def verify_runtime_archive(
    archive: Path,
    *,
    expected_archive_sha256: str | None = None,
    expected_release: str | None = None,
    expected_manifest_sha256: str | None = None,
) -> RuntimeReport:
    archive = archive.resolve()
    if archive.is_symlink() or not archive.is_file():
        raise IntegrityError(f"Runtime archive is missing: {archive}")
    archive_digest = sha256_file(archive)
    if expected_archive_sha256 is not None and archive_digest != expected_archive_sha256:
        raise IntegrityError("Runtime archive does not match orinoco.lock")
    with tempfile.TemporaryDirectory(prefix="orinoco-runtime-verify-") as temporary:
        root = _safe_extract(archive, Path(temporary))
        return verify_runtime_directory(
            root,
            expected_release=expected_release,
            expected_manifest_sha256=expected_manifest_sha256,
        )


def _download_runtime(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "orinoco-lite-runtime/1"})
    try:
        with urlopen(request, timeout=120) as response, destination.open("xb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_RUNTIME_BYTES:
                    raise IntegrityError("Runtime download exceeds the 2 GiB limit")
                output.write(chunk)
    except IntegrityError:
        destination.unlink(missing_ok=True)
        raise
    except Exception as error:
        destination.unlink(missing_ok=True)
        raise IntegrityError(f"Could not download runtime release: {url}") from error


def resolve_runtime(workspace: WorkspaceConfig, lock: EngineLock) -> RuntimeReport:
    """Resolve one lock pin to an exact verified runtime directory."""

    pin = lock.runtime
    if pin.path is not None:
        source = workspace.root.joinpath(*PurePosixPath(pin.path).parts)
        if source.is_dir():
            return verify_runtime_directory(
                source,
                expected_release=pin.version,
                expected_manifest_sha256=pin.manifest_sha256,
                expected_tree_sha256=pin.sha256,
            )
        archive = source
    else:
        download_root = workspace.root / ".orinoco" / "downloads"
        download_root.mkdir(parents=True, exist_ok=True)
        archive = download_root / f"runtime-{pin.sha256}.tar.gz"
        if not archive.exists():
            temporary = download_root / f".{archive.name}.{os.getpid()}.tmp"
            _download_runtime(pin.url or "", temporary)
            if sha256_file(temporary) != pin.sha256:
                temporary.unlink(missing_ok=True)
                raise IntegrityError("Downloaded runtime archive does not match orinoco.lock")
            os.replace(temporary, archive)

    if sha256_file(archive) != pin.sha256:
        raise IntegrityError("Runtime archive does not match orinoco.lock")
    cache = workspace.root / ".orinoco" / "runtime"
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / f"{pin.version}-{pin.sha256[:12]}"
    if destination.exists():
        return verify_runtime_directory(
            destination,
            expected_release=pin.version,
            expected_manifest_sha256=pin.manifest_sha256,
        )
    with tempfile.TemporaryDirectory(prefix=".install-", dir=cache) as temporary_name:
        temporary = Path(temporary_name)
        extracted = _safe_extract(archive, temporary)
        report = verify_runtime_directory(
            extracted,
            expected_release=pin.version,
            expected_manifest_sha256=pin.manifest_sha256,
        )
        os.replace(extracted, destination)
    return RuntimeReport(
        root=destination,
        release=report.release,
        manifest_sha256=report.manifest_sha256,
        tree_sha256=tree_sha256(destination),
        files=report.files,
        commands=report.commands,
    )


def _copy_resource(source: Path, destination: Path) -> list[Path]:
    if source.is_symlink():
        raise IntegrityError(f"Runtime source cannot be a symlink: {source}")
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return [destination]
    if not source.is_dir():
        raise IntegrityError(f"Runtime source is missing: {source}")
    copied: list[Path] = []
    for candidate in sorted(source.rglob("*")):
        relative = candidate.relative_to(source)
        if (
            ".git" in relative.parts
            or "__pycache__" in relative.parts
            or candidate.suffix in {".pyc", ".pyo"}
            or candidate.name.endswith(".egg-info")
        ):
            continue
        target = destination / relative
        if candidate.is_symlink():
            raise IntegrityError(f"Runtime source cannot contain symlinks: {candidate}")
        if candidate.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif candidate.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, target)
            copied.append(target)
        else:
            raise IntegrityError(f"Runtime source is not regular: {candidate}")
    return copied


def _tar_info(path: Path, arcname: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(arcname)
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    if path.is_dir():
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.size = 0
    else:
        info.type = tarfile.REGTYPE
        info.mode = 0o755 if stat.S_IMODE(path.stat().st_mode) & 0o111 else 0o644
        info.size = path.stat().st_size
    return info


def _write_deterministic_archive(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                paths = [root, *sorted(root.rglob("*"))]
                for path in paths:
                    arcname = path.relative_to(root.parent).as_posix()
                    info = _tar_info(path, arcname)
                    if path.is_file():
                        with path.open("rb") as source:
                            tar.addfile(info, source)
                    else:
                        tar.addfile(info)


def assemble_runtime(
    spec_path: Path,
    output: Path,
    *,
    force: bool = False,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Assemble one deterministic runtime archive from an explicit source map."""

    spec_path = spec_path.resolve()
    if spec_path.is_symlink() or not spec_path.is_file():
        raise ConfigurationError(f"Runtime source specification is missing: {spec_path}")
    try:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigurationError("Runtime source specification is invalid YAML") from error
    if not isinstance(spec, dict):
        raise ConfigurationError("Runtime source specification must be a mapping")
    if spec.get("format") != RUNTIME_SPEC_FORMAT or spec.get("spec_version") != 1:
        raise ConfigurationError(
            f"Runtime source specification must be {RUNTIME_SPEC_FORMAT} version 1"
        )
    release = spec.get("release")
    compatibility = spec.get("compatibility")
    commands = spec.get("commands")
    resources = spec.get("resources")
    licenses = spec.get("licenses")
    if not isinstance(release, str) or not release:
        raise ConfigurationError("Runtime source release must be a string")
    if not isinstance(compatibility, dict):
        raise ConfigurationError("Runtime source compatibility must be a mapping")
    if not isinstance(commands, dict) or not commands:
        raise ConfigurationError("Runtime source commands must be a non-empty mapping")
    if not isinstance(resources, list) or not resources:
        raise ConfigurationError("Runtime source resources must be a non-empty list")
    if not isinstance(licenses, list) or not licenses:
        raise ConfigurationError("Runtime source licenses must be a non-empty list")
    if output.exists() and not force:
        raise IntegrityError(f"Runtime archive already exists: {output}")
    if source_commit is not None and (
        len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise ConfigurationError("Runtime source commit must be a full lowercase Git SHA")

    source_root_value = spec.get("source_root")
    if source_root_value is None:
        source_root = spec_path.parent.parent
    else:
        source_root_relative = _relative(source_root_value, "Runtime source_root")
        source_root = spec_path.parent.joinpath(
            *PurePosixPath(source_root_relative).parts
        )
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise ConfigurationError(f"Runtime source_root is missing: {source_root}")

    with tempfile.TemporaryDirectory(prefix="orinoco-runtime-assemble-") as temporary:
        runtime_root = Path(temporary) / RUNTIME_ROOT_NAME
        runtime_root.mkdir()
        copied: list[Path] = []
        destination_roots: set[str] = set()
        for item in resources:
            if not isinstance(item, dict):
                raise ConfigurationError("Runtime resource entries must be mappings")
            source_name = _relative(item.get("source"), "Runtime resource source")
            destination_name = _relative(
                item.get("destination"), "Runtime resource destination"
            )
            if destination_name in destination_roots:
                raise ConfigurationError(
                    f"Runtime resource destination is repeated: {destination_name}"
                )
            destination_roots.add(destination_name)
            source = source_root.joinpath(*PurePosixPath(source_name).parts)
            destination = runtime_root.joinpath(*PurePosixPath(destination_name).parts)
            copied.extend(_copy_resource(source, destination))

        file_entries: list[dict[str, Any]] = []
        seen: set[str] = set()
        for path in sorted(copied):
            relative = path.relative_to(runtime_root).as_posix()
            if relative in seen or relative in {MANIFEST_NAME, CHECKSUMS_NAME}:
                raise ConfigurationError(f"Runtime output path is repeated: {relative}")
            seen.add(relative)
            executable = bool(stat.S_IMODE(path.stat().st_mode) & 0o111)
            mode = 0o755 if executable else 0o644
            path.chmod(mode)
            file_entries.append(
                {
                    "path": relative,
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                    "mode": mode,
                }
            )

        normalized_licenses = [
            _relative(item, "Runtime license path") for item in licenses
        ]
        if not all(item in seen for item in normalized_licenses):
            missing = sorted(set(normalized_licenses) - seen)
            raise ConfigurationError(
                f"Runtime license resources are absent: {', '.join(missing)}"
            )
        normalized_commands: dict[str, list[str]] = {}
        for name, command in commands.items():
            if (
                not isinstance(name, str)
                or not name
                or not isinstance(command, list)
                or not command
                or not all(isinstance(token, str) and token for token in command)
            ):
                raise ConfigurationError(f"Runtime source command is invalid: {name!r}")
            normalized_commands[name] = command
        provenance = spec.get("provenance", {})
        if not isinstance(provenance, dict):
            raise ConfigurationError("Runtime source provenance must be a mapping")
        provenance = dict(provenance)
        if source_commit is not None:
            provenance["source_commit"] = source_commit
            source_inventory = provenance.get("source_inventory")
            if isinstance(source_inventory, dict):
                engine = source_inventory.get("engine")
                if isinstance(engine, dict):
                    engine["commit"] = source_commit
                for name, component in source_inventory.items():
                    if (
                        name != "engine"
                        and isinstance(component, dict)
                        and component.get("commit") == "release-source"
                    ):
                        component["commit"] = source_commit
        recorded_commit = provenance.get("source_commit")
        if (
            not isinstance(recorded_commit, str)
            or len(recorded_commit) != 40
            or any(character not in "0123456789abcdef" for character in recorded_commit)
        ):
            raise ConfigurationError("Runtime provenance requires a full source commit")
        manifest = {
            "format": RUNTIME_FORMAT,
            "manifest_version": RUNTIME_MANIFEST_VERSION,
            "release": release,
            "compatibility": compatibility,
            "commands": normalized_commands,
            "licenses": normalized_licenses,
            "files": file_entries,
            "provenance": provenance,
        }
        manifest_path = runtime_root / MANIFEST_NAME
        manifest_path.write_bytes(canonical_json_bytes(manifest))
        checksum_entries = [
            (entry["path"], entry["sha256"]) for entry in file_entries
        ]
        checksum_entries.append((MANIFEST_NAME, sha256_file(manifest_path)))
        (runtime_root / CHECKSUMS_NAME).write_text(
            resource_checksum_lines(checksum_entries), encoding="utf-8"
        )
        report = verify_runtime_directory(runtime_root, expected_release=release)

        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_archive = output.parent / f".{output.name}.{os.getpid()}.tmp"
        temporary_archive.unlink(missing_ok=True)
        _write_deterministic_archive(runtime_root, temporary_archive)
        if output.exists():
            output.unlink()
        os.replace(temporary_archive, output)
    return {
        "archive": str(output),
        "archive_sha256": sha256_file(output),
        "files": report.files,
        "manifest_sha256": report.manifest_sha256,
        "provenance": provenance,
        "release": report.release,
        "tree_sha256": report.tree_sha256,
    }
