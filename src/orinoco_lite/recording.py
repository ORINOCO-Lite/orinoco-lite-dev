"""Record public CLI operations with the downstream's locked tools."""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Sequence

from .errors import ConfigurationError


def relative_path(root: Path, path: str | Path) -> str:
    """Return a portable path without allowing writes outside the repository."""
    root = root.resolve()
    path = Path(path)
    target = path if path.is_absolute() else root / path
    try:
        relative = target.absolute().relative_to(root)
        target.resolve().relative_to(root)
    except ValueError as error:
        raise ConfigurationError(f"Recorded paths must remain inside {root}: {path}") from error
    if not relative.parts or ".." in relative.parts or relative.parts[0] == ".git":
        raise ConfigurationError(f"Not an operation-owned recorded path: {path}")
    return relative.as_posix()


def record(
    root: Path,
    command: Sequence[str],
    *,
    inputs: Sequence[str | Path] = (),
    outputs: Sequence[str | Path],
    message: str,
) -> None:
    """Run and record only declared outputs, including subdataset Gitlinks.

    ``command`` contains public ``orinoco-lite`` arguments and ``--no-datalad``.
    URLs belong in those arguments; retained file inputs belong in ``inputs``.
    DataLad saves the explicit outputs recursively, so a site-specific subdataset
    and its parent pointer are recorded together without enabling Git Annex.
    """
    root = root.resolve()
    try:
        repository = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            text=True, stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ConfigurationError("Recording requires a Git repository; use --no-datalad for a scratch run.") from error
    if Path(repository).resolve() != root:
        raise ConfigurationError("Run recorded operations from the repository root.")
    for name in ("pixi.toml", "pixi.lock"):
        if not (root / name).is_file():
            raise ConfigurationError(f"Recording requires {name} and the locked DataLad tool; use --no-datalad for a scratch run.")
    if "--no-datalad" not in command:
        raise ConfigurationError("The recorded public command must include --no-datalad.")
    if not outputs:
        raise ConfigurationError("A recorded operation must declare its outputs.")
    # Import from the locked Python environment: Pixi's command lookup otherwise
    # also accepts a host ``datalad`` that the downstream never selected.
    invocation = [
        "pixi", "run", "--locked", "python", "-c",
        "from datalad.cli.main import main; main()",
        "run", "--explicit", "-m", message,
    ]
    for path in dict.fromkeys(("pixi.toml", "pixi.lock", *inputs)):
        invocation.extend(("--input", relative_path(root, path)))
    for path in dict.fromkeys(outputs):
        invocation.extend(("--output", relative_path(root, path)))
    invocation.extend(("--", "pixi", "run", "--locked", "orinoco-lite", *command))
    try:
        subprocess.run(invocation, cwd=root, check=True)
    except OSError as error:
        raise ConfigurationError(f"Could not run the locked DataLad tool: {error}") from error
    except subprocess.CalledProcessError as error:
        raise ConfigurationError(
            "DataLad recording failed. Inspect its diagnostics and declared outputs; "
            "the command uses the downstream's locked environment."
        ) from error
