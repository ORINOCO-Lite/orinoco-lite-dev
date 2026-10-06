"""The reusable upstream rendering subset shared by wheels and editable builds."""
from pathlib import Path
import shutil

from .errors import DriverError

HUGO_SURFACES = (
    "archetypes",
    "assets",
    "config",
    "data",
    "i18n",
    "layouts",
    "static",
)


def _copy_tree(source: Path, destination: Path, *, media: dict[Path, Path] | None = None) -> None:
    if source.is_symlink():
        raise DriverError(f"Static source cannot be a symlink: {source}")
    if not source.is_dir():
        return
    for candidate in sorted(source.rglob("*")):
        relative = candidate.relative_to(source)
        if any(part in {".git", ".DS_Store", "__pycache__"} for part in relative.parts):
            continue
        target = destination / relative
        if media and candidate in media:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(media[candidate], target)
            continue
        if candidate.is_symlink():
            raise DriverError(f"Static source cannot contain symlinks: {candidate}")
        if candidate.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif candidate.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, target)


def _copy_file(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    if source.is_symlink() or not source.is_file():
        raise DriverError(f"Hugo source is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _is_annex_pointer(path: Path) -> bool:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        return False
    try:
        value = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError:
        return False
    return value.startswith(("/annex/objects/", ".git/annex/objects/"))


def _reject_annex_pointers(root: Path) -> None:
    pointers = [
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if _is_annex_pointer(path)
    ]
    if pointers:
        raise DriverError(
            "Materialized Hugo assets are missing for upstream Annex "
            "content: " + ", ".join(pointers[:10])
        )


def _copy_upstream_section_frontmatter(source: Path, destination: Path) -> None:
    """Retain section layout parameters without importing editorial bodies."""

    if source.is_symlink():
        raise DriverError(f"Upstream content root cannot be a symlink: {source}")
    if not source.is_dir():
        return
    for path in sorted(source.glob("*/_index.md")):
        if path.is_symlink() or not path.is_file():
            raise DriverError(f"Upstream section metadata is not a file: {path}")
        try:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        except UnicodeDecodeError as error:
            raise DriverError(f"Upstream section metadata is not UTF-8: {path}") from error
        if not lines or lines[0].strip() != "---":
            raise DriverError(f"Upstream section has no YAML front matter: {path}")
        closing = next(
            (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
            None,
        )
        if closing is None:
            raise DriverError(f"Upstream section front matter is unclosed: {path}")
        target = destination / path.parent.name / "_index.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(lines[: closing + 1]).rstrip() + "\n", encoding="utf-8")

# These are rendering inputs, not the upstream site's records or identity.
UPSTREAM_TREES = ("archetypes", "config", "data", "i18n", "layouts",
                  "assets/css", "assets/icons", "assets/js")
STATIC_FILES = ("filetree.css", "filetree.js", "filter-list.css", "filter-list.js",
                "graph.js", "grid-list.css")


def runtime_asset(path: Path) -> bool:
    return (path.parts[:2] in {("assets", "css"), ("assets", "icons"), ("assets", "js")}
            or path.parent == Path("assets/img") and path.name.startswith("meerkat") and path.suffix == ".png"
            or path.parent == Path("static") and path.name in STATIC_FILES)


def copy_hugo_runtime(source: Path, destination: Path, *, media=None) -> None:
    """Select the same Hugo inputs from working sources and packaged resources."""
    for name in UPSTREAM_TREES:
        _copy_tree(source / name, destination / name, media=media)
    for path in sorted((source / "assets/img").glob("meerkat*.png")):
        _copy_file((media or {}).get(path, path), destination / "assets/img" / path.name)
    for name in STATIC_FILES:
        path = source / "static" / name
        _copy_file((media or {}).get(path, path), destination / "static" / name)
    theme = source / "themes/congo"
    for name in HUGO_SURFACES:
        _copy_tree(theme / name, destination / "themes/congo" / name)
    for name in ("theme.toml", "LICENSE"):
        _copy_file(theme / name, destination / "themes/congo" / name)
    _copy_upstream_section_frontmatter(source / "content", destination / "content")
    for root, name in ((source, "www-from-model"), (theme, "congo")):
        if root.is_dir():
            for path in root.iterdir():
                if path.is_file() and path.name.lower().startswith(("license", "copying", "notice", "copyright")):
                    _copy_file(path, destination / "static/LICENSES" / name / path.name)


def stage_upstream_runtime(source: Path, destination: Path) -> None:
    from .annex_media import prepare_hugo_assets
    media = prepare_hugo_assets(source, remote="https://hub.psychoinformatics.de/www/www-from-model.git")
    copy_hugo_runtime(source, destination, media=media)
    _copy_tree(source / "page_templates", destination / "page_templates")
    _copy_file(source / "code/pool2graph.py", destination / "code/pool2graph.py")
    # Preserve source notices, without assigning our license to upstream work.
    for root, target in ((source, destination), (source / "themes/congo", destination / "themes/congo")):
        for path in root.iterdir():
            if path.name.lower().startswith(("license", "copying", "notice", "copyright")) or path.name == "README.md":
                if path.is_file():
                    _copy_file(path, target / path.name)
    _reject_annex_pointers(destination)
