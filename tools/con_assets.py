#!/usr/bin/env python3
"""Hydrate and materialize assets declared by the CON profile."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import sys
from typing import Any, Mapping, Sequence
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[1]
SITE = Path(
    os.environ.get(
        "CON_SITE_ROOT",
        ROOT / "submodules" / "centerforopenneuroscience.org",
    )
).resolve()
UPSTREAM = Path(
    os.environ.get(
        "UPSTREAM_SITE_ROOT",
        ROOT / "submodules" / "www-from-model",
    )
).resolve()
ASSET_MANIFEST = SITE / "profiles" / "con" / "assets.yaml"
BASELINE_MANIFEST = ROOT / "provenance" / "full-con-migration" / "baseline.yaml"
UPSTREAM_BASELINE_MANIFEST = (
    ROOT / "provenance" / "upstream-psychoinformatics" / "baseline.yaml"
)
CACHE = ROOT / "build" / "con-assets"
EXPECTED_ANNEX_VERSION = "10.20260601"
ASSET_PREFIX = PurePosixPath("profiles/con/assets")
LINK_PREFIXES = {
    "projection_links": PurePosixPath("profiles/con/projection/content"),
    "static_links": PurePosixPath("profiles/con/static"),
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MD5 = re.compile(r"^[0-9a-f]{32}$")
GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
MEDIA_TYPE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/" r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$"
)
ANNEX_KEY = re.compile(
    r"^(?P<backend>MD5E|SHA256E)-s(?P<size>[0-9]+)--"
    r"(?P<digest>[0-9a-f]+)(?P<extension>\..+)?$"
)


class AssetError(RuntimeError):
    """Report a manifest, retrieval, or integrity failure."""


@dataclass(frozen=True)
class AssetSpec:
    """A validated asset entry keyed by its site-relative destination."""

    destination: str
    source_repository: str
    source_commit: str
    source_path: str
    availability: str
    storage: str
    media_type: str
    mode: int
    sha256: str
    size: int | None
    md5: str | None
    annex_key: str | None
    retrieval: Mapping[str, str] | None
    role: str | None


@dataclass(frozen=True)
class GitIndexEntry:
    """One stage-zero asset entry from the site Git index."""

    mode: str
    object_id: str
    path: str


def run(
    arguments: Sequence[str | Path],
    *,
    action: str,
    check: bool = True,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(argument) for argument in arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise AssetError(f"{action} failed ({result.returncode}): {detail}")
    return result


def git(repository: Path, *arguments: str, action: str) -> str:
    return run(["git", "-C", repository, *arguments], action=action).stdout.strip()


def annex_command(repository: Path, *arguments: str) -> list[str]:
    """Build a Pixi-scoped annex command for one explicit worktree."""
    git_dir = git(
        repository,
        "rev-parse",
        "--absolute-git-dir",
        action="Locate the git-annex repository",
    )
    return [
        "pixi",
        "run",
        "git",
        f"--git-dir={git_dir}",
        f"--work-tree={repository.resolve()}",
        "annex",
        *arguments,
    ]


def annex(
    repository: Path,
    *arguments: str,
    action: str,
    check: bool = True,
) -> str:
    return run(
        annex_command(repository, *arguments),
        action=action,
        check=check,
    ).stdout.strip()


def annex_from_url(
    repository: Path,
    name: str,
    url: str,
    *arguments: str,
    action: str,
) -> str:
    """Use a read-only annex transport without adding a shared remote."""
    url = validate_git_repository_url(
        f"Temporary annex remote {name!r}",
        url,
    )
    command = annex_command(repository)
    command[3:3] = [
        "-c",
        f"remote.{name}.url={url}",
        "-c",
        f"remote.{name}.fetch=+refs/heads/*:refs/remotes/{name}/*",
    ]
    command.extend(arguments)
    return run(command, action=action).stdout.strip()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssetError(f"Asset manifest is absent: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssetError(f"Asset manifest must be a mapping: {path}")
    return value


def normalized_relative_path(value: object, *, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise AssetError(f"{label} must be a non-empty relative path")
    path = PurePosixPath(value)
    if (
        value.startswith("/")
        or "\\" in value
        or ".." in path.parts
        or path.as_posix() != value
    ):
        raise AssetError(f"{label} is not a normalized relative path: {value!r}")
    return path


def parse_mode(value: object, *, destination: str) -> int:
    if value != "0644":
        raise AssetError(f"{destination}: asset mode must be the string '0644'")
    return int(value, 8)


def validate_https_url(label: str, value: object) -> str:
    """Validate one credential-free HTTPS URL."""
    if (
        not isinstance(value, str)
        or not value
        or any(character.isspace() for character in value)
    ):
        raise AssetError(f"{label} must be a credential-free HTTPS URL")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        parsed.port
    except ValueError as error:
        raise AssetError(f"{label} must be a credential-free HTTPS URL") from error
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AssetError(f"{label} must be a credential-free HTTPS URL")
    return value


def validate_git_repository_url(label: str, value: object) -> str:
    """Validate an HTTPS Git transport without embedded credentials."""
    return validate_https_url(f"{label} Git repository", value)


def validate_retrieval(
    destination: str,
    value: object,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise AssetError(f"{destination}: annex retrieval must be a mapping")
    required = {"remote", "repository", "object_url", "mode"}
    if set(value) != required or not all(
        isinstance(value.get(key), str) and value[key] for key in required
    ):
        raise AssetError(
            f"{destination}: annex retrieval must declare exactly {sorted(required)!r}"
        )
    retrieval = {key: value[key] for key in required}
    if retrieval["mode"] != "read-only":
        raise AssetError(f"{destination}: annex retrieval must be read-only")
    repository_value = validate_git_repository_url(
        f"{destination} retrieval", retrieval["repository"]
    )
    object_url_value = validate_https_url(
        f"{destination} object URL", retrieval["object_url"]
    )
    repository = urlsplit(repository_value)
    object_url = urlsplit(object_url_value)
    if (repository.scheme, repository.netloc) != (
        object_url.scheme,
        object_url.netloc,
    ) or not object_url.path.startswith(repository.path.rstrip("/") + "/"):
        raise AssetError(
            f"{destination}: object URL is outside its HTTPS read-only remote"
        )
    return retrieval


def validate_source_repository(destination: str, value: object) -> str:
    return validate_git_repository_url(
        f"{destination}: source_repository",
        value,
    )


def parse_annex_key(key: object, *, label: str) -> tuple[str, int, str]:
    """Return the hash algorithm, payload size, and digest for a safe key."""
    if not isinstance(key, str):
        raise AssetError(f"{label}: annex key is invalid")
    match = ANNEX_KEY.fullmatch(key)
    if match is None:
        raise AssetError(
            f"{label}: only canonical MD5E and SHA256E annex keys are supported"
        )
    backend = match.group("backend")
    algorithm = {"MD5E": "md5", "SHA256E": "sha256"}[backend]
    digest = match.group("digest")
    expected_digest = MD5 if algorithm == "md5" else SHA256
    if expected_digest.fullmatch(digest) is None:
        raise AssetError(f"{label}: annex key digest is invalid")
    return algorithm, int(match.group("size")), digest


def validate_fallback_policy(manifest: Mapping[str, Any]) -> None:
    """Require an explicit no-broken-image policy for unavailable evidence."""
    expected = {
        "mode": "upstream-neutral",
        "person": "meerkat-person",
        "project": "meerkat-project",
        "render_image": True,
    }
    if manifest.get("fallback_policy") != expected:
        raise AssetError(
            "fallback_policy must declare the upstream neutral depiction behavior"
        )
    omissions = manifest.get("omissions")
    if not isinstance(omissions, dict):
        raise AssetError("omissions must be a PID-to-policy mapping")
    projection_links = manifest.get("projection_links", {})
    if not isinstance(projection_links, dict):
        raise AssetError("projection_links must be a mapping")
    for pid, raw in sorted(omissions.items()):
        if not isinstance(pid, str) or not isinstance(raw, dict):
            raise AssetError("Every asset omission must map one PID to a policy")
        kind = raw.get("kind")
        availability = raw.get("availability")
        fallback = raw.get("fallback")
        if kind == "portrait":
            prefix = "xyzrins:persons/"
            expected_fallback = "meerkat-person"
            route = f"persons/{pid.removeprefix(prefix)}/portrait."
        elif kind == "logo":
            prefix = "xyzrins:projects/"
            expected_fallback = "meerkat-project"
            route = f"projects/{pid.removeprefix(prefix)}/logo."
        else:
            raise AssetError(f"{pid}: omission kind must be portrait or logo")
        if not pid.startswith(prefix):
            raise AssetError(f"{pid}: omission PID and kind disagree")
        if availability not in {"unavailable", "absent-in-source"}:
            raise AssetError(f"{pid}: omission availability is invalid")
        if raw.get("projection_link", object()) is not None:
            raise AssetError(f"{pid}: omitted assets must declare no projection link")
        if fallback != expected_fallback:
            raise AssetError(f"{pid}: omission fallback disagrees with policy")
        if any(route in destination for destination in projection_links):
            raise AssetError(f"{pid}: omitted asset has a projection link")
        if availability == "unavailable":
            source = normalized_relative_path(
                raw.get("source_path"), label=f"{pid} omitted source_path"
            )
            key = raw.get("annex_key")
            size = raw.get("expected_size")
            if not source.parts or not isinstance(key, str) or "--" not in key:
                raise AssetError(f"{pid}: unavailable annex evidence is incomplete")
            if not isinstance(size, int) or size < 0 or f"-s{size}--" not in key:
                raise AssetError(f"{pid}: unavailable annex size/key disagree")
        elif any(
            field in raw for field in ("source_path", "annex_key", "expected_size")
        ):
            raise AssetError(
                f"{pid}: absent-in-source omission cannot claim source payload fields"
            )


def asset_specs(manifest: Mapping[str, Any]) -> dict[str, AssetSpec]:
    validate_fallback_policy(manifest)
    raw_assets = manifest.get("assets")
    if not isinstance(raw_assets, dict) or not raw_assets:
        raise AssetError("CON asset entries must be a non-empty mapping")
    specs: dict[str, AssetSpec] = {}
    for destination, raw in sorted(raw_assets.items()):
        path = normalized_relative_path(destination, label="Asset destination")
        if ASSET_PREFIX not in (path, *path.parents):
            raise AssetError(
                f"Asset destination is outside {ASSET_PREFIX}: {destination}"
            )
        if not isinstance(raw, dict):
            raise AssetError(f"{destination}: asset entry must be a mapping")
        source_repository = validate_source_repository(
            destination, raw.get("source_repository")
        )
        source_commit = raw.get("source_commit")
        if not isinstance(source_commit, str) or not GIT_COMMIT.fullmatch(
            source_commit
        ):
            raise AssetError(f"{destination}: source_commit must be a full Git ID")
        source_path = normalized_relative_path(
            raw.get("source_path"), label=f"{destination} source_path"
        ).as_posix()
        if raw.get("availability") != "available":
            raise AssetError(f"{destination}: declared assets must be available")
        storage = raw.get("storage")
        if storage not in {"git", "git-annex"}:
            raise AssetError(f"{destination}: storage must be 'git' or 'git-annex'")
        media_type = raw.get("media_type")
        if not isinstance(media_type, str) or not MEDIA_TYPE.fullmatch(media_type):
            raise AssetError(f"{destination}: media_type is invalid")
        sha256 = raw.get("sha256")
        if not isinstance(sha256, str) or not SHA256.fullmatch(sha256):
            raise AssetError(f"{destination}: sha256 digest is invalid")
        size = raw.get("size")
        if not isinstance(size, int) or size < 0:
            raise AssetError(f"{destination}: size must be a non-negative integer")
        md5 = raw.get("md5")
        if md5 is not None and (not isinstance(md5, str) or not MD5.fullmatch(md5)):
            raise AssetError(f"{destination}: md5 digest is invalid")
        mode = parse_mode(raw.get("mode"), destination=destination)
        annex_key = raw.get("annex_key")
        retrieval = raw.get("retrieval")
        if storage == "git-annex":
            algorithm, key_size, key_digest = parse_annex_key(
                annex_key,
                label=destination,
            )
            retrieval = validate_retrieval(destination, retrieval)
            if size != key_size:
                raise AssetError(f"{destination}: annex key and declared size disagree")
            if algorithm == "md5" and md5 != key_digest:
                raise AssetError(f"{destination}: annex key and md5 disagree")
            if algorithm == "sha256" and sha256 != key_digest:
                raise AssetError(f"{destination}: annex key and sha256 disagree")
        elif annex_key is not None or retrieval is not None:
            raise AssetError(f"{destination}: ordinary Git asset has annex-only fields")
        role = raw.get("role")
        if role is not None and (not isinstance(role, str) or not role):
            raise AssetError(f"{destination}: role must be a non-empty string")
        specs[destination] = AssetSpec(
            destination=destination,
            source_repository=source_repository,
            source_commit=source_commit,
            source_path=source_path,
            availability="available",
            storage=storage,
            media_type=media_type,
            mode=mode,
            sha256=sha256,
            size=size,
            md5=md5,
            annex_key=annex_key,
            retrieval=retrieval,
            role=role,
        )
    return specs


def verify_annex_runtime() -> None:
    """Require the pinned git-annex executable from the Pixi environment."""
    baseline = load_yaml(BASELINE_MANIFEST)
    toolchain = baseline.get("toolchain", {})
    expected = toolchain.get("git_annex") if isinstance(toolchain, dict) else None
    if expected != EXPECTED_ANNEX_VERSION:
        raise AssetError(
            f"Expected full-migration provenance to pin git-annex "
            f"{EXPECTED_ANNEX_VERSION}, found {expected!r}"
        )
    executable = run(
        [
            "pixi",
            "run",
            "python",
            "-c",
            "import shutil; print(shutil.which('git-annex') or '')",
        ],
        action="Locate the Pixi git-annex runtime",
    ).stdout.strip()
    environment_root = (ROOT / ".pixi" / "envs").resolve()
    try:
        executable_path = Path(executable).resolve()
        executable_path.relative_to(environment_root)
    except (OSError, ValueError) as error:
        raise AssetError(
            f"git-annex is not provided by this project's Pixi environment: "
            f"{executable!r}"
        ) from error
    output = run(
        ["pixi", "run", "git", "annex", "version"],
        action="Inspect the Pixi git-annex runtime",
    ).stdout
    first_line = output.splitlines()[0] if output else ""
    actual = first_line.removeprefix("git-annex version: ").split("-", 1)[0]
    if actual != expected:
        raise AssetError(f"Expected git-annex {expected}, found {first_line!r}")


def upstream_annex_entries() -> dict[str, str]:
    baseline = load_yaml(UPSTREAM_BASELINE_MANIFEST)
    annex_info = baseline.get("annex", {})
    entries = (
        annex_info.get("upstream_annex_only") if isinstance(annex_info, dict) else None
    )
    if not isinstance(entries, list):
        raise AssetError("Upstream annex inventory is incomplete")
    result: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise AssetError("Invalid upstream annex inventory entry")
        path = normalized_relative_path(
            entry.get("path"), label="Upstream annex path"
        ).as_posix()
        key = entry.get("key")
        if not isinstance(key, str) or not key:
            raise AssetError(f"Upstream annex key is invalid for {path}")
        if path.startswith(("assets/", "static/")):
            result[path] = key
    if not result:
        raise AssetError("Upstream annex inventory declares no Hugo assets")
    return result


def annex_path_available(repository: Path, path: str) -> bool:
    present = annex(
        repository,
        "find",
        path,
        "--in=here",
        action=f"Inspect annex availability for {path}",
    )
    return bool(present)


def temporary_remote_config(repository: Path, name: str) -> str:
    pattern = rf"^remote\.{re.escape(name)}\."
    result = run(
        ["git", "-C", repository, "config", "--local", "--get-regexp", pattern],
        action="Inspect temporary annex remote configuration",
        check=False,
    )
    if result.returncode not in {0, 1}:
        detail = (result.stderr or result.stdout).strip()
        raise AssetError(f"Could not inspect temporary remote config: {detail}")
    return result.stdout


def remove_temporary_remote_config(repository: Path, name: str) -> None:
    """Remove only metadata git-annex inferred for our ephemeral remote."""
    result = run(
        [
            "git",
            "-C",
            repository,
            "config",
            "--local",
            "--remove-section",
            f"remote.{name}",
        ],
        action="Remove temporary annex remote configuration",
        check=False,
    )
    if result.returncode not in {0, 5}:
        detail = (result.stderr or result.stdout).strip()
        raise AssetError(f"Could not remove temporary remote config: {detail}")


def hydrate_upstream() -> None:
    """Hydrate declared upstream Hugo pointers through a temporary transport."""
    baseline = load_yaml(UPSTREAM_BASELINE_MANIFEST)
    website = baseline.get("website", {})
    if not isinstance(website, dict):
        raise AssetError("Invalid upstream annex baseline manifest")
    commit = website.get("annex_metadata_commit")
    if not isinstance(commit, str) or not GIT_COMMIT.fullmatch(commit):
        raise AssetError("Upstream annex provenance is incomplete")
    url = validate_git_repository_url(
        "Upstream annex metadata",
        website.get("upstream_repository"),
    )
    entries = upstream_annex_entries()

    annex(UPSTREAM, "init", action="Initialize upstream annex")
    for path, expected_key in entries.items():
        actual_key = annex(
            UPSTREAM,
            "lookupkey",
            path,
            action=f"Inspect upstream annex key for {path}",
        )
        if actual_key != expected_key:
            raise AssetError(
                f"Upstream annex key changed for {path}: "
                f"expected {expected_key}, found {actual_key!r}"
            )
    missing = [
        path for path in sorted(entries) if not annex_path_available(UPSTREAM, path)
    ]
    if missing:
        name = "full-con-migration-upstream"
        remote_ref = f"refs/remotes/{name}/git-annex"
        before = temporary_remote_config(UPSTREAM, name)
        if before:
            raise AssetError(f"Temporary annex remote already exists: {name}")
        try:
            git(
                UPSTREAM,
                "fetch",
                "--no-write-fetch-head",
                "--depth",
                "1",
                url,
                f"+{commit}:{remote_ref}",
                action="Fetch pinned upstream annex metadata",
            )
            annex_from_url(
                UPSTREAM,
                name,
                url,
                "get",
                "--from",
                name,
                "--",
                *missing,
                action="Hydrate upstream Hugo assets",
            )
        finally:
            try:
                git(
                    UPSTREAM,
                    "update-ref",
                    "-d",
                    remote_ref,
                    action="Remove temporary upstream annex ref",
                )
            finally:
                remove_temporary_remote_config(UPSTREAM, name)
        after = temporary_remote_config(UPSTREAM, name)
        if after:
            raise AssetError(f"Annex hydration persisted temporary remote {name!r}")
    unavailable = [
        path for path in sorted(entries) if not annex_path_available(UPSTREAM, path)
    ]
    if unavailable:
        raise AssetError(
            "Required upstream annex paths remain unavailable:\n"
            + "\n".join(unavailable)
        )
    for path, key in sorted(entries.items()):
        verify_payload_against_annex_key(
            UPSTREAM / path,
            key,
            label=f"Upstream annex payload {path}",
        )


def file_digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def detected_media_type(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(65536)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith(b"\x00\x00\x01\x00"):
        return "image/vnd.microsoft.icon"
    guessed = mimetypes.guess_type(path.name)[0]
    if guessed == "image/svg+xml":
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as error:
            raise AssetError(f"{path}: invalid SVG content") from error
        if root.tag.rsplit("}", 1)[-1] != "svg":
            raise AssetError(f"{path}: XML root is not SVG")
        return guessed
    if guessed and guessed.startswith("text/"):
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise AssetError(f"{path}: declared text asset is not UTF-8") from error
        return guessed
    raise AssetError(f"{path}: unsupported or unrecognized asset media type")


def verify_file(path: Path, spec: AssetSpec) -> None:
    if not path.is_file():
        raise AssetError(f"Required asset is absent: {path}")
    actual_mode = stat.S_IMODE(path.stat().st_mode)
    if actual_mode != spec.mode:
        raise AssetError(
            f"{path}: expected mode {spec.mode:04o}, found {actual_mode:04o}"
        )
    if spec.size is not None and path.stat().st_size != spec.size:
        raise AssetError(
            f"{path}: expected {spec.size} bytes, found {path.stat().st_size}"
        )
    if file_digest(path, "sha256") != spec.sha256:
        raise AssetError(f"{path}: sha256 digest does not match")
    if spec.md5 and file_digest(path, "md5") != spec.md5:
        raise AssetError(f"{path}: md5 digest does not match")
    actual_media_type = detected_media_type(path)
    if actual_media_type != spec.media_type:
        raise AssetError(
            f"{path}: expected media type {spec.media_type}, found {actual_media_type}"
        )


def git_index_entry(repository: Path, destination: str) -> GitIndexEntry:
    """Read exactly one stage-zero entry for an asset destination."""
    result = run(
        [
            "git",
            "-C",
            repository,
            "ls-files",
            "--stage",
            "-z",
            "--",
            destination,
        ],
        action=f"Inspect the Git index entry for {destination}",
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise AssetError(f"Could not inspect the Git index for {destination}: {detail}")
    records = [record for record in result.stdout.split("\0") if record]
    if len(records) != 1 or "\t" not in records[0]:
        raise AssetError(f"{destination}: asset must have exactly one Git index entry")
    header, indexed_path = records[0].split("\t", 1)
    fields = header.split()
    if len(fields) != 3 or fields[2] != "0" or indexed_path != destination:
        raise AssetError(f"{destination}: Git index entry is not stage zero")
    mode, object_id, _stage = fields
    return GitIndexEntry(mode=mode, object_id=object_id, path=indexed_path)


def annex_hashdir(key: str) -> PurePosixPath:
    """Return the canonical mixed-hash object directory for an annex key."""
    value = annex(
        SITE,
        "examinekey",
        "--format=${hashdirmixed}",
        key,
        action=f"Calculate the annex object directory for {key}",
    )
    if not value.endswith("/"):
        raise AssetError(f"{key}: git-annex returned an invalid object directory")
    path = normalized_relative_path(
        value.removesuffix("/"),
        label=f"{key} annex object directory",
    )
    if len(path.parts) != 2:
        raise AssetError(f"{key}: git-annex returned an invalid object directory")
    return path


def canonical_annex_pointer_target(spec: AssetSpec) -> str:
    """Calculate the exact symlink text git-annex uses for this worktree."""
    if not spec.annex_key:
        raise AssetError(f"{spec.destination}: annex key is absent")
    pointer = SITE.joinpath(*PurePosixPath(spec.destination).parts)
    git_dir = Path(
        git(
            SITE,
            "rev-parse",
            "--git-dir",
            action="Locate the site Git directory",
        )
    )
    if not git_dir.is_absolute():
        git_dir = SITE / git_dir
    object_path = (
        git_dir
        / "annex"
        / "objects"
        / Path(*annex_hashdir(spec.annex_key).parts)
        / spec.annex_key
        / spec.annex_key
    )
    return Path(os.path.relpath(object_path, pointer.parent)).as_posix()


def verify_git_index_contract(spec: AssetSpec) -> str | None:
    """Require the committed representation promised by the manifest."""
    entry = git_index_entry(SITE, spec.destination)
    expected_mode = "100644" if spec.storage == "git" else "120000"
    if entry.mode != expected_mode:
        raise AssetError(
            f"{spec.destination}: expected Git index mode {expected_mode}, "
            f"found {entry.mode}"
        )
    if spec.storage == "git":
        return None
    target = canonical_annex_pointer_target(spec)
    indexed_target = run(
        ["git", "-C", SITE, "cat-file", "blob", entry.object_id],
        action=f"Inspect the indexed annex pointer for {spec.destination}",
    ).stdout
    if indexed_target != target:
        raise AssetError(f"{spec.destination}: indexed annex pointer is not canonical")
    return target


def verify_annex_pointer(
    spec: AssetSpec,
    expected_target: str | None = None,
) -> None:
    path = SITE.joinpath(*PurePosixPath(spec.destination).parts)
    if not path.is_symlink():
        raise AssetError(f"{spec.destination}: annex asset is not a symlink")
    target = os.readlink(path)
    expected = expected_target or canonical_annex_pointer_target(spec)
    if target != expected:
        raise AssetError(
            f"{spec.destination}: working-tree annex pointer is not canonical"
        )


def verify_payload_against_annex_key(
    path: Path,
    key: str,
    *,
    label: str,
) -> None:
    """Verify payload bytes and the Pixi git-annex calculation for one key."""
    algorithm, expected_size, expected_digest = parse_annex_key(key, label=label)
    if not path.is_file():
        raise AssetError(f"{label}: payload is absent: {path}")
    actual_size = path.stat().st_size
    if actual_size != expected_size:
        raise AssetError(
            f"{label}: expected {expected_size} bytes, found {actual_size}"
        )
    if file_digest(path, algorithm) != expected_digest:
        raise AssetError(f"{label}: {algorithm} digest does not match its annex key")
    backend = key.split("-", 1)[0]
    actual = run(
        [
            "pixi",
            "run",
            "git",
            "annex",
            "calckey",
            f"--backend={backend}",
            path,
        ],
        action=f"Validate annex key for {label}",
    ).stdout.strip()
    if actual != key:
        raise AssetError(f"{label}: expected annex key {key}, found {actual!r}")


def verify_annex_key(path: Path, spec: AssetSpec) -> None:
    if not spec.annex_key:
        raise AssetError(f"{spec.destination}: annex key is absent")
    verify_payload_against_annex_key(
        path,
        spec.annex_key,
        label=spec.destination,
    )


def cache_path(spec: AssetSpec) -> Path:
    root = Path(os.path.abspath(CACHE))
    return root.joinpath(*PurePosixPath(spec.destination).parts)


def ensure_safe_directory_chain(root: Path, parent: Path, *, label: str) -> None:
    """Create a directory chain without accepting symlinked components."""
    root = Path(os.path.abspath(root))
    parent = Path(os.path.abspath(parent))
    try:
        relative = parent.relative_to(root)
    except ValueError as error:
        raise AssetError(f"{label}: destination escapes its root") from error
    if root.is_symlink():
        raise AssetError(f"{label}: root directory is a symlink: {root}")
    root.mkdir(parents=True, exist_ok=True)
    root_status = os.lstat(root)
    if stat.S_ISLNK(root_status.st_mode) or not stat.S_ISDIR(root_status.st_mode):
        raise AssetError(f"{label}: root is not a safe directory: {root}")
    current = root
    for part in relative.parts:
        current = current / part
        try:
            current_status = os.lstat(current)
        except FileNotFoundError:
            try:
                os.mkdir(current, 0o755)
            except FileExistsError:
                current_status = os.lstat(current)
            else:
                current_status = os.lstat(current)
        if stat.S_ISLNK(current_status.st_mode):
            raise AssetError(f"{label}: directory ancestor is a symlink: {current}")
        if not stat.S_ISDIR(current_status.st_mode):
            raise AssetError(f"{label}: ancestor is not a directory: {current}")


def inspect_safe_cache_destination(destination: Path) -> bool:
    """Prepare cache parents and report whether a safe regular file exists."""
    root = Path(os.path.abspath(CACHE))
    ensure_safe_directory_chain(root, destination.parent, label="Asset cache")
    try:
        destination_status = os.lstat(destination)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(destination_status.st_mode):
        raise AssetError(f"Asset cache destination is a symlink: {destination}")
    if not stat.S_ISREG(destination_status.st_mode):
        raise AssetError(f"Asset cache destination is not a file: {destination}")
    return True


def open_exclusive_download(path: Path) -> int:
    """Open a new temporary payload without following or replacing a path."""
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    if not no_follow:
        raise AssetError("This platform cannot create no-follow asset downloads")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        return os.open(path, flags, 0o600)
    except OSError as error:
        raise AssetError(
            f"Could not create exclusive asset download {path}: {error}"
        ) from error


def hydrate_annex_asset(spec: AssetSpec) -> Path:
    if spec.retrieval is None or spec.annex_key is None:
        raise AssetError(f"{spec.destination}: annex retrieval is incomplete")
    destination = cache_path(spec)
    if inspect_safe_cache_destination(destination):
        verify_file(destination, spec)
        verify_annex_key(destination, spec)
        return destination

    temporary = destination.with_name(
        f".{destination.name}.download-{os.getpid()}-{secrets.token_hex(8)}"
    )
    request = Request(
        spec.retrieval["object_url"],
        headers={"User-Agent": "full-con-migration/1"},
    )
    temporary_created = False
    try:
        descriptor = open_exclusive_download(temporary)
        temporary_created = True
        with (
            os.fdopen(
                descriptor,
                "wb",
            ) as out,
            urlopen(request, timeout=120) as response,
        ):
            shutil.copyfileobj(response, out)
            os.fchmod(out.fileno(), spec.mode)
        verify_file(temporary, spec)
        verify_annex_key(temporary, spec)
        inspect_safe_cache_destination(destination)
        os.replace(temporary, destination)
    except (OSError, URLError) as error:
        raise AssetError(
            f"Could not hydrate annex key {spec.annex_key} from "
            f"{spec.retrieval['remote']}: {error}"
        ) from error
    finally:
        if temporary_created:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return destination


def verify_git_assets(specs: Mapping[str, AssetSpec]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for destination, spec in sorted(specs.items()):
        if spec.storage != "git":
            continue
        path = SITE.joinpath(*PurePosixPath(destination).parts)
        verify_git_index_contract(spec)
        if path.is_symlink():
            raise AssetError(f"{destination}: ordinary Git asset is a symlink")
        verify_file(path, spec)
        files[destination] = path
    return files


def hydrate_manifest_assets(
    manifest: Mapping[str, Any],
) -> dict[str, Path]:
    """Validate every entry and return its materialized local file."""
    specs = asset_specs(manifest)
    files = verify_git_assets(specs)
    for destination, spec in sorted(specs.items()):
        if spec.storage != "git-annex":
            continue
        target = verify_git_index_contract(spec)
        verify_annex_pointer(spec, target)
        files[destination] = hydrate_annex_asset(spec)
    if set(files) != set(specs):
        raise AssetError("Not every declared asset was materialized")
    return files


def materialization_plan(
    manifest: Mapping[str, Any],
    specs: Mapping[str, AssetSpec],
) -> dict[str, str]:
    """Validate all projection/static destinations and their declared sources."""
    plan: dict[str, str] = {}
    for group, prefix in LINK_PREFIXES.items():
        links = manifest.get(group, {})
        if not isinstance(links, dict):
            raise AssetError(f"{group} must be a destination-to-source mapping")
        for destination, source in sorted(links.items()):
            destination_path = normalized_relative_path(
                destination, label=f"{group} destination"
            )
            if prefix not in (destination_path, *destination_path.parents):
                raise AssetError(
                    f"{group} destination is outside {prefix}: {destination}"
                )
            source_path = normalized_relative_path(
                source, label=f"{group} source"
            ).as_posix()
            if source_path not in specs:
                raise AssetError(
                    f"{group} source is not a declared asset: {source_path}"
                )
            if destination in plan:
                raise AssetError(
                    f"Materialization destination is declared twice: {destination}"
                )
            guessed = mimetypes.guess_type(destination_path.name)[0]
            expected = specs[source_path].media_type
            if guessed != expected:
                raise AssetError(
                    f"{destination}: extension implies {guessed}, "
                    f"but source is {expected}"
                )
            plan[destination] = source_path
    return plan


def copy_materialized_file(
    root: Path,
    destination: str,
    source: Path,
    spec: AssetSpec,
) -> Path:
    root = Path(os.path.abspath(root))
    target = Path(os.path.abspath(root.joinpath(*PurePosixPath(destination).parts)))
    try:
        target.relative_to(root)
    except ValueError as error:
        raise AssetError(f"Materialization escapes its root: {destination}") from error
    ensure_safe_directory_chain(
        root,
        target.parent,
        label=f"Asset materialization {destination}",
    )
    try:
        target_status = os.lstat(target)
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(target_status.st_mode):
            if destination != spec.destination or spec.storage != "git-annex":
                raise AssetError(f"Materialization destination is a symlink: {target}")
            actual_pointer = os.readlink(target)
            expected_pointer = canonical_annex_pointer_target(spec)
            if actual_pointer != expected_pointer:
                raise AssetError(
                    "Materialization destination is not the declared canonical "
                    f"annex pointer: {target}"
                )
            os.unlink(target)
        elif not stat.S_ISREG(target_status.st_mode):
            raise AssetError(f"Materialization destination is not a file: {target}")
        else:
            os.unlink(target)
    shutil.copyfile(source, target)
    target.chmod(spec.mode)
    verify_file(target, spec)
    return target


def materialize_declared_assets(
    destination_root: Path,
    manifest: Mapping[str, Any],
    files: Mapping[str, Path],
) -> list[Path]:
    """Replace every declared asset destination in an assembly tree."""
    specs = asset_specs(manifest)
    root = Path(os.path.abspath(destination_root))
    materialized: list[Path] = []
    for destination, spec in sorted(specs.items()):
        source = files.get(destination)
        if source is None:
            raise AssetError(f"Declared asset is unavailable: {destination}")
        materialized.append(copy_materialized_file(root, destination, source, spec))
    return materialized


def materialize_declared_links(
    destination_root: Path,
    manifest: Mapping[str, Any],
    files: Mapping[str, Path],
) -> list[Path]:
    """Copy each declared projection/static link into an assembly root."""
    specs = asset_specs(manifest)
    plan = materialization_plan(manifest, specs)
    root = Path(os.path.abspath(destination_root))
    materialized: list[Path] = []
    for destination, source in sorted(plan.items()):
        source_path = files.get(source)
        if source_path is None:
            raise AssetError(f"Materialized source is unavailable: {source}")
        materialized.append(
            copy_materialized_file(
                root,
                destination,
                source_path,
                specs[source],
            )
        )
    return materialized


def materialize_all_assets(
    destination_root: Path,
    manifest: Mapping[str, Any],
    files: Mapping[str, Path],
) -> list[Path]:
    """Materialize all sources and declared copies into an assembly tree."""
    return [
        *materialize_declared_assets(destination_root, manifest, files),
        *materialize_declared_links(destination_root, manifest, files),
    ]


def hydrate_all_assets() -> dict[str, Path]:
    """Hydrate every declared dependency and return all CON asset files."""
    verify_annex_runtime()
    hydrate_upstream()
    manifest = load_yaml(ASSET_MANIFEST)
    specs = asset_specs(manifest)
    files = hydrate_manifest_assets(manifest)
    materialization_plan(manifest, specs)
    return files


def main() -> int:
    try:
        manifest = load_yaml(ASSET_MANIFEST)
        hydrate_all_assets()
        specs = asset_specs(manifest)
        print(f"Hydrated {len(specs)} manifest assets")
    except AssetError as error:
        print(f"full-migration assets: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
