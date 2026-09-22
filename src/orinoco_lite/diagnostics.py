"""Conventional paths for an explicit upstream investigation."""

from pathlib import Path
import shutil

from .errors import ConfigurationError

DEFAULT_DIRECTORY = Path("upstream-diffing")


def options(parser, *, replace=True):
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY,
                        help="investigation directory (default: %(default)s)")
    if replace:
        parser.add_argument("--force", action="store_true",
                            help="replace this command's existing output; preserve its inputs")


def directory(args):
    root = (getattr(args, "root", None) or Path.cwd()).resolve()
    path = args.directory
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def require(path, command):
    if not path.exists():
        raise ConfigurationError(f"Missing input: {path}. Run 'orinoco-lite dev {command}' with the same --directory first.")
    return path


def prepare_output(path, force=False):
    if path.is_symlink():
        raise ConfigurationError(f"Output must not be a symbolic link: {path}")
    if path.exists():
        if not force:
            raise ConfigurationError(f"Output already exists: {path}. Use --force to replace it, or --directory for another investigation.")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    return path


def record_path(root, name):
    if name == "downloaded":
        path, command = root / name / "records.jsonl", "records get"
    elif name == "yaml":
        path, command = root / name, "records jsonl-to-yaml"
    elif name == "yaml-jsonl":
        path, command = root / name / "records.jsonl", "records yaml-to-jsonl"
    else:
        raise ConfigurationError(f"Unknown record state: {name}")
    return require(path, command)


def explicit_path(args, path):
    """Resolve an explicit path from --root or the caller's working directory."""
    root = getattr(args, "root", None) or Path.cwd()
    # Keep the final symlink visible to output safety checks.
    return (root / path).absolute() if not path.is_absolute() else path
