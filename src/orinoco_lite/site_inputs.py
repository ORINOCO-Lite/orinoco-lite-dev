"""Import authored site data without converting records or copying Hugo layouts or themes."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
import subprocess
import tomllib

import tomlkit


from .progress import progress
from .errors import DriverError
from .annex_media import annex_files, retrieve_and_verify

ENTITY_SECTIONS = frozenset({
    "datasets", "instruments", "objectives", "persons", "projects",
    "publications", "topics",
})
IDENTITY_IMAGES = frozenset({"fzj.svg", "hhu.svg", "logo.png"})


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


def _source_bytes(source: Path, relative: Path, *, media: dict[Path, Path] | None = None) -> bytes:
    path = source / relative
    if media and relative in media:
        return media[relative].read_bytes()
    key = _annex_key(path)
    if key:
        raise DriverError(f"Site input contains an Annex pointer, not file bytes: {path}. Use dev upstream import-from-www to retrieve media.")
    return path.read_bytes()


def selected_site_files(source: Path, *, retrieve_media: bool = False, media_remote: str | None = None,
                        include_homepage: bool = False) -> dict[Path, bytes]:
    """Return the explicitly owned site-input paths and source bytes.

    Generated record pages are omitted; importing the homepage requires an explicit choice. Section pages,
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
        path = source / relative
        if path.name == ".DS_Store" and path.is_file() and not path.is_symlink():
            continue
        if relative.parts[0] == "content":
            local = relative.relative_to("content")
            if local.name == "_index.md" and (
                (len(local.parts) == 1 and not include_homepage) or
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
    media = {}
    if retrieve_media:
        managed = annex_files(source, initialize=any(_annex_key(source / path) for path in paths))
        selected = {path: managed[path] for path in paths if path in managed}
        media = retrieve_and_verify(source, selected, remote=media_remote)
    files = {path: _source_bytes(source, path, media=media) for path in paths}
    # These source-owned values are deliberately cleared by the generic
    # template. Keep their real upstream settings as site overrides; fields
    # already mapped into tool.orinoco.site remain owned only by that document.
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
        "record_prefix": "xyzrins:",
        "identity": {
            "title": language["title"],
            "description": language["params"]["description"],
            "base_url": config["baseURL"].rstrip("/") + "/",
        },
        "navigation": navigation,
        "appearance": {
            "color_scheme": theme["colorScheme"],
            "default_appearance": theme["defaultAppearance"],
            "header_layout": theme["header"]["layout"],
        },
    }


@progress("Importing upstream site files and media")
def import_site_inputs(source: Path, destination: Path, *, config_path: Path, retrieve_media: bool = False,
                       media_remote: str | None = None, force: bool = False, include_homepage: bool = False) -> dict:
    """Synchronize imported site surfaces, preserving metadata and other config."""
    files = selected_site_files(source, retrieve_media=retrieve_media, media_remote=media_remote,
                                include_homepage=include_homepage)
    if config_path.is_symlink() or not config_path.is_file():
        raise DriverError(f"Import requires the downstream pyproject.toml: {config_path}")
    try:
        document = tomlkit.parse(config_path.read_text())
    except (OSError, ValueError) as error:
        raise DriverError(f"Cannot read TOML configuration: {config_path}") from error
    tool = document.setdefault("tool", tomlkit.table())
    if not isinstance(tool, Mapping):
        raise DriverError("pyproject.toml tool must be a table")
    orinoco = tool.setdefault("orinoco", tomlkit.table())
    if not isinstance(orinoco, Mapping):
        raise DriverError("pyproject.toml tool.orinoco must be a table")
    site = orinoco.setdefault("site", tomlkit.table())
    if not isinstance(site, Mapping):
        raise DriverError("pyproject.toml tool.orinoco.site must be a table")
    imported = site_settings(source)
    for key, setting in imported.items():
        if isinstance(setting, dict):
            section = site.setdefault(key, tomlkit.table())
            if not isinstance(section, Mapping):
                raise DriverError(f"tool.orinoco.site.{key} must be a table")
            for field, value in setting.items():
                section[field] = value
        else:
            site[key] = setting
    manifest = tomlkit.dumps(document)
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
            if target.name == ".DS_Store" and target.is_file():
                continue
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
    print("Convert config/_default/{languages.en,hugo,params,menus.en}.toml -> tool.orinoco.site in pyproject.toml")
    print("  Map title, description, base URL, navigation, color scheme, appearance, and header layout.")
    config_path.write_text(manifest)
    destination.mkdir(parents=True, exist_ok=True)
    for relative, value in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Write {target}")
        target.write_bytes(value)
    for target in stale:
        print(f"  Delete {target}")
        target.unlink()
    return {"files": len(files) + 1, "source": str(source), "output": str(destination)}
