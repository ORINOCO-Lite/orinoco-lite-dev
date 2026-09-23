"""Default data paths and explicit command paths."""

from pathlib import Path

from .errors import ConfigurationError

DEFAULT_DIRECTORY = Path("sourcedata")


def options(parser, *, replace=True):
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY,
                        help="source-data directory (default: %(default)s)")
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


def explicit_path(args, path):
    """Resolve an explicit path from --root or the caller's working directory."""
    root = getattr(args, "root", None) or Path.cwd()
    # Keep the final symlink visible to output safety checks.
    return (root / path).absolute() if not path.is_absolute() else path
