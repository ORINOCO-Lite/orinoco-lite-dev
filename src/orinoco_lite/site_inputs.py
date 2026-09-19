"""Import authored site data without converting records or copying presentation."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
import subprocess
import tomllib

import tomlkit

import yaml

from .errors import DriverError

ENTITY_SECTIONS = frozenset({
    "datasets", "instruments", "objectives", "persons", "projects",
    "publications", "topics",
})
IDENTITY_IMAGES = frozenset({"fzj.svg", "hhu.svg", "logo.png"})


def _source_bytes(source: Path, relative: Path) -> bytes:
    path = source / relative
    try:
        value = path.read_bytes()
    except OSError as error:
        raise DriverError(
            f"Site input is unavailable: {path}. Prepare the selected upstream "
            "content in the maintainer checkout before importing it."
        ) from error
    if value.strip().startswith((b"/annex/objects/", b".git/annex/objects/")):
        raise DriverError(f"Site input contains an Annex pointer, not file bytes: {path}")
    return value


def selected_site_files(source: Path) -> dict[Path, bytes]:
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
    files: dict[Path, bytes] = {}
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
        files[relative] = _source_bytes(source, relative)
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
    if overrides:
        files[Path("overrides/config/params.toml")] = tomlkit.dumps(overrides).encode()
    if "copyright" in language:
        files[Path("overrides/config/languages.en.toml")] = tomlkit.dumps({"copyright": language["copyright"]}).encode()
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


def import_site_inputs(source: Path, destination: Path) -> dict:
    """Copy only imported paths; preserve records, captures and unrelated edits."""
    files = selected_site_files(source)
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
    destination.mkdir(parents=True, exist_ok=True)
    for relative, value in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
    return {"files": len(files), "source": str(source), "output": str(destination)}
