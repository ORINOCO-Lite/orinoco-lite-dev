"""Create a local downstream from a template and captured site inputs."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import yaml

from .development import PACKAGE_REPOSITORY, enable, git, run
from .errors import ConfigurationError
from .upstream_orinoco_records import project


def snapshot_site(engineering: Path, snapshot: Path, destination: Path) -> None:
    """Convert the cached pool and selected website inputs once, without fetching."""
    if not snapshot.is_file():
        raise ConfigurationError(f"Cached pool snapshot is missing: {snapshot}. Supply --snapshot or --site-specific.")
    website = engineering / "submodules/www-from-model"
    revision = git(engineering, "rev-parse", "HEAD:submodules/www-from-model")

    def read(path: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(website), "show", f"{revision}:{path}"])

    language = tomllib.loads(read("config/_default/languages.en.toml").decode())
    config = tomllib.loads(read("config/_default/hugo.toml").decode())
    theme = tomllib.loads(read("config/_default/params.toml").decode())
    menu = tomllib.loads(read("config/_default/menus.en.toml").decode())
    navigation = []
    for entry in menu.get("main", []):
        name = entry.get("name", entry.get("title"))
        if not name:  # Theme actions, such as search, are not content navigation.
            continue
        item = {"name": name}
        for source, target in (("pageRef", "page_ref"), ("url", "url"),
                               ("identifier", "identifier"), ("parent", "parent"), ("weight", "weight")):
            if source in entry:
                item[target] = entry[source]
        for name in ("icon", "target"):
            if name in entry.get("params", {}):
                item[name] = entry["params"][name]
        navigation.append(item)
    project(snapshot, destination)
    # The conversion's audit report is not downstream configuration or history.
    (destination / "manifest.json").unlink()
    site = {
        "version": 1,
        "record_prefix": "xyzrins:",
        "identity": {"title": language["title"],
                     "description": language["params"]["description"],
                     "base_url": config["baseURL"].rstrip("/") + "/"},
        "navigation": navigation,
        "footer_navigation": [
            {"name": entry["name"], "page_ref": entry["pageRef"]}
            for entry in menu.get("footer", [])
            if "name" in entry and "pageRef" in entry
        ],
        "presentation": {"color_scheme": theme["colorScheme"],
                         "default_appearance": theme["defaultAppearance"],
                         "header_layout": theme["header"]["layout"]},
    }
    (destination / "site.yaml").write_text(yaml.safe_dump(site, sort_keys=False, allow_unicode=True))
    editorial = destination / "content"
    editorial.mkdir()
    # Section introductions are authored inputs, unlike the generated home
    # and record pages. Keep those introductions and top-level editorial pages.
    for path in git(website, "ls-tree", "-r", "--name-only", revision, "content/").splitlines():
        relative = Path(path).relative_to("content")
        if relative.suffix == ".md" and (
            (len(relative.parts) == 1 and relative.name != "_index.md")
            or (len(relative.parts) == 2 and relative.name == "_index.md")
        ):
            target = editorial / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(read(path))


def setup(destination: Path | None = None, *, template: Path | None = None,
          site_specific: Path | None = None, snapshot: Path | None = None,
          populate: bool = False, force: bool = False) -> None:
    engineering = Path(__file__).resolve().parents[2]
    if not (engineering / "release/package-resources.yaml").is_file():
        engineering = Path.cwd().parent / "orinoco-lite-dev"
    destination = (destination or engineering.parent / "orinoco-lite-test-downstream").absolute()
    if not destination.is_symlink():
        destination = destination.resolve()
    if destination == engineering or destination in engineering.parents:
        raise ConfigurationError("The downstream destination must not contain the engineering checkout.")
    if (destination.exists() or destination.is_symlink()) and not force:
        raise ConfigurationError(f"Destination already exists: {destination}. Use --force to recreate it.")
    if not engineering.exists():
        run("git", "clone", PACKAGE_REPOSITORY, engineering, cwd=Path.cwd())
    template = (template or engineering.parent / "orinoco-lite-template").resolve()
    if not template.exists():
        if not populate:
            raise ConfigurationError(f"Missing template: {template}. Use --populate to clone it.")
        run("git", "clone", "git@github.com:ORINOCO-Lite/orinoco-lite-template.git", template, cwd=engineering)
    if site_specific is not None:
        site_specific = site_specific.resolve()
        if not site_specific.is_dir():
            if not populate:
                raise ConfigurationError(f"Missing site-specific repository: {site_specific}. Use --populate to clone it.")
            run("git", "clone", "git@github.com:ORINOCO-Lite/con-site-specific.git", site_specific, cwd=engineering)
    snapshot = (snapshot or engineering / "build/upstream-stack/pool/public-thing.jsonl").resolve()
    if site_specific is None and not snapshot.is_file():
        raise ConfigurationError(f"Cached pool snapshot is missing: {snapshot}. Supply --snapshot or --site-specific.")
    for source in (engineering, template, site_specific, snapshot):
        if source is not None and (destination == source or destination in source.parents):
            raise ConfigurationError("The downstream destination must not contain a setup input.")
    if site_specific is None and not (engineering / "submodules/www-from-model/.git").exists():
        run("git", "submodule", "update", "--init", "--", "submodules/www-from-model", cwd=engineering)
    # Check inputs before honoring a destructive recreation request.
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif destination.exists():
        shutil.rmtree(destination)
    run("pixi", "exec", "--spec", "datalad", "--", "datalad", "create", "--no-annex", destination, cwd=engineering)
    run("pixi", "exec", "--spec", "datalad", "--spec", "copier", "--", "datalad", "run",
        "-m", "chore: instantiate local template", "--", "copier", "copy", "--vcs-ref", "HEAD",
        "-d", "include_site_specific=false", template, ".", cwd=destination)
    if site_specific is not None:
        run("pixi", "exec", "--spec", "datalad", "--", "datalad", "run",
            "-m", "chore: install site-specific subdataset", "--", "datalad", "install",
            "--dataset", ".", "--source", site_specific, "site-specific", cwd=destination)
    else:
        print("Converting the cached pool snapshot into site-specific inputs...", flush=True)
        run("pixi", "exec", "--spec", "datalad", "--", "datalad", "run",
            "-m", "chore: convert captured upstream site inputs", "--", sys.executable,
            "-m", "orinoco_lite.instantiate", engineering, snapshot, "site-specific", cwd=destination, quiet=True)
    enable(destination, engineering)
    print(f"\nSetup complete.\n\ncd {destination}\ngit log --oneline\ngit status\n"
          "\nBuild when ready: pixi run orinoco-lite build\nServe afterward: pixi run orinoco-lite serve")


if __name__ == "__main__":
    snapshot_site(*(Path(value) for value in sys.argv[1:]))
