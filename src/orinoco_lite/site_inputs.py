"""Import authored site data without converting records or copying presentation."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
import subprocess
import shlex
import tomllib

import tomlkit

import yaml

from .errors import DriverError

ENTITY_SECTIONS = frozenset({
    "datasets", "instruments", "objectives", "persons", "projects",
    "publications", "topics",
})
IDENTITY_IMAGES = frozenset({"fzj.svg", "hhu.svg", "logo.png"})


def _annex(source: Path, *arguments: str, media_remote: str | None = None) -> str:
    # Only upstream preparation uses Annex. Keep it out of the site's dependencies.
    command = ["pixi", "exec", "--spec", "uv", "--", "uvx", "--from",
               "git-annex==10.20260601", "git-annex"]
    command.append(arguments[0])
    if media_remote:
        command.extend(["-c", f"remote.orinoco-media.url={media_remote}"])
    command.extend(arguments[1:])
    print(f"  In {source}: {shlex.join(command)}", flush=True)
    result = subprocess.run(command, cwd=source, capture_output=True, text=True)
    if result.returncode:
        raise DriverError(f"Upstream media retrieval failed: {result.stdout}{result.stderr}")
    return result.stdout.strip()


def _annex_key(path: Path) -> str | None:
    if path.is_symlink():
        value = str(path.readlink()).encode()
        if b"annex/objects/" not in value:
            raise DriverError(f"Site input is an unsupported symlink: {path}")
    else:
        try:
            with path.open("rb") as stream:
                value = stream.read(4096)
        except OSError as error:
            raise DriverError(f"Site input is unavailable: {path}") from error
    if (value.startswith((b"/annex/objects/", b".git/annex/objects/"))
            or (path.is_symlink() and b"annex/objects/" in value)):
        return value.strip().decode().rsplit("/", 1)[-1]
    return None


def _source_bytes(source: Path, relative: Path, *, retrieve_media: bool = False) -> bytes:
    path = source / relative
    key = _annex_key(path)
    if key:
        if not retrieve_media:
            raise DriverError(f"Site input contains an Annex pointer, not file bytes: {path}. Use dev upstream import-from-www to retrieve media.")
        location = _annex(source, "contentlocation", key)
        if not location:
            raise DriverError(f"Upstream media is unavailable after retrieval: {relative}")
        path = source / location
    return path.read_bytes()


def selected_site_files(source: Path, *, retrieve_media: bool = False, media_remote: str | None = None) -> dict[Path, bytes]:
    """Return the explicitly owned site-input paths and source bytes.

    Generated record pages and the homepage are omitted. Section pages,
    authored pages outside record sections, and page-bundle resources remain
    at their original content-relative paths.
    """
    result = subprocess.run(
        ["git", "-C", str(source), "ls-files", "-z", "--", "content", "assets/img", "static"],
        capture_output=True, check=False,
    )
    if result.returncode:
        raise DriverError(f"Cannot inspect selected site inputs: {source}")
    paths = []
    for name in result.stdout.decode().split("\0"):
        if not name:
            continue
        relative = Path(name)
        if relative.parts[0] == "content":
            local = relative.relative_to("content")
            if local.name == "_index.md" and (
                len(local.parts) == 1 or
                (local.parts[0] in ENTITY_SECTIONS and len(local.parts) > 2)
            ):
                continue
        elif relative.parts[0] == "assets":
            if relative.name not in IDENTITY_IMAGES:
                continue
        elif (relative.as_posix() != "static/site.webmanifest" and
              (len(relative.parts) != 2 or relative.suffix.lower() not in {
            ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp",
        })):
            continue
        paths.append(relative)
    if retrieve_media:
        annexed = [path.as_posix() for path in paths if _annex_key(source / path)]
        if annexed:
            _annex(source, "init")
            source_option = ("--from", "orinoco-media") if media_remote else ()
            _annex(source, "get", *source_option, "--", *annexed, media_remote=media_remote)
            _annex(source, "fsck", "--", *annexed, media_remote=media_remote)
    files = {path: _source_bytes(source, path, retrieve_media=retrieve_media) for path in paths}
    # These source-owned values are deliberately cleared by the generic
    # template. Keep their real upstream settings as site overrides; fields
    # already mapped into site.yaml remain owned only by that document.
    theme = tomllib.loads(_source_bytes(source, Path("config/_default/params.toml")).decode())
    language = tomllib.loads(_source_bytes(source, Path("config/_default/languages.en.toml")).decode())
    header = {key: value for key, value in theme.get("header", {}).items()
              if key in {"logo", "logoDark"}}
    footer = {key: value for key, value in theme.get("footer", {}).items()
              if key == "showCopyright"}
    overrides = {}
    if header:
        overrides["header"] = header
    if footer:
        overrides["footer"] = footer
    files[Path("overrides/config/params.toml")] = tomlkit.dumps(overrides).encode()
    files[Path("overrides/config/languages.en.toml")] = tomlkit.dumps(
        {"copyright": language["copyright"]} if "copyright" in language else {}).encode()
    return files


def site_settings(source: Path) -> dict:
    def read(name):
        return tomllib.loads(_source_bytes(source, Path("config/_default") / name).decode())
    language = read("languages.en.toml")
    config = read("hugo.toml")
    theme = read("params.toml")
    menu = read("menus.en.toml")
    navigation = []
    for entry in menu.get("main", []):
        name = entry.get("name", entry.get("title"))
        if not name:
            continue
        item = {"name": name}
        for old, new in (("pageRef", "page_ref"), ("url", "url"),
                         ("identifier", "identifier"), ("parent", "parent"),
                         ("weight", "weight")):
            if old in entry:
                item[new] = entry[old]
        if "icon" in entry.get("params", {}):
            item["icon"] = entry["params"]["icon"]
        navigation.append(item)
    return {
        "version": 1,
        "record_prefix": "xyzrins:",
        "identity": {
            "title": language["title"],
            "description": language["params"]["description"],
            "base_url": config["baseURL"].rstrip("/") + "/",
        },
        "navigation": navigation,
        "presentation": {
            "color_scheme": theme["colorScheme"],
            "default_appearance": theme["defaultAppearance"],
            "header_layout": theme["header"]["layout"],
        },
    }


def import_site_inputs(source: Path, destination: Path, *, retrieve_media: bool = False, media_remote: str | None = None, force: bool = False) -> dict:
    """Synchronize imported site surfaces, preserving metadata and other config."""
    files = selected_site_files(source, retrieve_media=retrieve_media, media_remote=media_remote)
    files[Path("site.yaml")] = yaml.safe_dump(
        site_settings(source), sort_keys=False, allow_unicode=True,
    ).encode()
    # Read all sources before writing, so an unavailable resource leaves the
    # existing downstream untouched.
    for relative in files:
        target = destination / relative
        if any(path.is_symlink() for path in (target, *target.parents)):
            raise DriverError(f"Imported site input must not traverse a symlink: {target}")
        if target.exists() and not target.is_file():
            raise DriverError(f"Imported site input is not a regular file: {target}")
        if relative.parts[:2] == ("overrides", "config") and target.exists():
            # Reimport owns just the fields mapped above. Preserve unrelated
            # authored settings in an existing override file.
            existing = tomlkit.parse(target.read_text())
            imported = tomllib.loads(files[relative].decode())
            owned = ({"header": ("logo", "logoDark"), "footer": ("showCopyright",)}
                     if relative.name == "params.toml" else {"copyright": None})
            for section, fields in owned.items():
                if fields is None:
                    existing.pop(section, None)
                elif section in existing:
                    if not isinstance(existing[section], Mapping):
                        raise DriverError(f"Imported override section {section} must be a TOML table: {target}")
                    for field in fields:
                        existing[section].pop(field, None)
            for key, setting in imported.items():
                if isinstance(setting, dict):
                    if key not in existing:
                        existing[key] = {}
                    if not isinstance(existing[key], Mapping):
                        raise DriverError(f"Imported override section {key} must be a TOML table: {target}")
                    for nested_key, nested_value in setting.items():
                        existing[key][nested_key] = nested_value
                else:
                    existing[key] = setting
            files[relative] = tomlkit.dumps(existing).encode()
    stale = []
    for name in ("content", "assets", "static"):
        surface = destination / name
        if surface.is_symlink():
            raise DriverError(f"Imported site surface must not be a symlink: {surface}")
        if surface.exists() and not surface.is_dir():
            raise DriverError(f"Imported site surface must be a directory: {surface}")
        for target in surface.rglob("*"):
            if target.is_symlink():
                raise DriverError(f"Imported site input must not be a symlink: {target}")
            if target.is_file() and target.relative_to(destination) not in files:
                stale.append(target)
    if not force:
        replaced = [destination / relative for relative in files if (destination / relative).exists()]
        conflicts = replaced + stale
        if conflicts:
            raise DriverError(
                f"Site import would replace or delete existing files, including {conflicts[0]}; "
                "use --force to synchronize imported site inputs."
            )
    print("Convert config/_default/{languages.en,hugo,params,menus.en}.toml -> site.yaml")
    print("  Map title, description, base URL, navigation, color scheme, appearance, and header layout.")
    destination.mkdir(parents=True, exist_ok=True)
    for relative, value in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Write {target}")
        target.write_bytes(value)
    for target in stale:
        print(f"  Delete {target}")
        target.unlink()
    return {"files": len(files), "source": str(source), "output": str(destination)}
