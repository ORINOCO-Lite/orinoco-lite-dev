"""Select packaged rendering resources or the editable nested source."""
from pathlib import Path

from .errors import IntegrityError

_WWW_FROM_MODEL_GITLINK = "submodules/www-from-model"


def editable_package_checkout() -> Path | None:
    """Return the source selected by the installed package's editable metadata."""
    from importlib.metadata import distribution, PackageNotFoundError
    import json
    from urllib.parse import unquote, urlsplit

    try:
        raw = distribution("orinoco-lite").read_text("direct_url.json")
    except PackageNotFoundError:
        return None
    if not raw:
        return None
    value = json.loads(raw)
    if not value.get("dir_info", {}).get("editable"):
        return None
    url = urlsplit(value["url"])
    if url.scheme != "file":
        raise IntegrityError("Editable package source must be a local checkout")
    return Path(unquote(url.path)).resolve()


def resolve_www_from_model(workspace: Path, resources_root: Path | None = None) -> Path:
    """Use the installed package’s fixed revision or editable working source."""

    workspace = workspace.resolve()
    if workspace.is_symlink() or not workspace.is_dir():
        raise IntegrityError(f"www-from-model workspace is not a directory: {workspace}")
    if resources_root is None:
        raise IntegrityError("www-from-model resolution requires package resources")
    editable = editable_package_checkout()
    if editable is not None:
        selected = editable / _WWW_FROM_MODEL_GITLINK
        if not (selected / ".git").exists():
            raise IntegrityError(f"Initialize the package's www-from-model submodule: {selected}")
        return selected.resolve()
    selected = resources_root / "www-from-model"
    if not (selected / "page_templates").is_dir() or not (selected / "themes/congo/theme.toml").is_file():
        raise IntegrityError("Packaged www-from-model rendering resources are missing; reinstall orinoco-lite")
    return selected.resolve()
