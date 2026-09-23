"""Select a remotely recoverable package commit and update its Pixi lock."""

from pathlib import Path
from importlib.metadata import distribution, PackageNotFoundError
import json
import tomllib
import os
import re
import subprocess
import tempfile
from urllib.parse import urlsplit

import tomlkit

from .errors import ConfigurationError
from .resources import SOURCE_REPOSITORY


def remote_url(value: str) -> str:
    """Use a remote Git URL that Pixi can also install."""
    if re.fullmatch(r"[^/@:]+@[^/:]+:.+", value):
        host, path = value.split(":", 1)
        value = f"ssh://{host}/{path}"
    parsed = urlsplit(value)
    if (parsed.scheme not in {"https", "ssh", "git"} or not parsed.hostname
            or parsed.password or (parsed.username and parsed.scheme != "ssh") or parsed.query or parsed.fragment):
        raise ConfigurationError("Package repository must be a remote HTTPS, SSH, or Git URL, without embedded secrets.")
    return value


def installed_git_source() -> tuple[str, str] | None:
    """Read the standard install metadata, without consulting another checkout."""
    try:
        raw = distribution("orinoco-lite").read_text("direct_url.json")
    except PackageNotFoundError:
        return None
    if not raw:
        return None
    try:
        value = json.loads(raw)
        vcs = value.get("vcs_info", {})
        if vcs.get("vcs") != "git":
            return None
        url, commit = value["url"], vcs["commit_id"]
        if not isinstance(url, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("invalid Git source")
        return url, commit
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ConfigurationError("Installed package has invalid direct_url.json metadata") from error


def check_environment(root: Path) -> None:
    """Refuse a transformation in a stale environment after changing a Git pin."""
    manifest = root / "pixi.toml"
    if not manifest.is_file():
        return
    selection = tomllib.loads(manifest.read_text()).get("pypi-dependencies", {}).get("orinoco-lite", {})
    if not isinstance(selection, dict) or "git" not in selection:
        return  # Explicit editable development and standalone exploration remain supported.
    installed = installed_git_source()
    expected = selection.get("rev", "")
    def repository_id(url):
        parsed = urlsplit(remote_url(url))
        return parsed.hostname, parsed.path.removesuffix(".git").rstrip("/")
    if (not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{40}", expected) or installed is None
            or installed[1] != expected
            or repository_id(installed[0]) != repository_id(selection["git"])):
        raise ConfigurationError(
            "The running package does not match the immutable selection in pixi.toml. "
            "Record the intended selection and lock, then start a fresh pixi run; "
            "historical replay must restore its environment before execution.")


def resolve_commit(repository: str, revision: str) -> str:
    """Fetch in an empty repository, so local-only commits cannot pass."""
    repository = remote_url(repository)
    if not revision or revision.startswith("-") or any(char.isspace() for char in revision):
        raise ConfigurationError("Supply a Git commit, tag, or branch as --revision.")
    with tempfile.TemporaryDirectory(prefix="orinoco-package-") as temporary:
        def git(*arguments):
            environment = {key: value for key, value in os.environ.items()
                           if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}}
            environment["GIT_TERMINAL_PROMPT"] = "0"
            result = subprocess.run(["git", "-C", temporary, *arguments], capture_output=True,
                                    text=True, env=environment)
            if result.returncode:
                raise ConfigurationError(
                    f"Cannot fetch package revision {revision!r} from {repository}. "
                    "Publish the commit or select an accessible revision before continuing.\n"
                    + result.stderr.strip())
            return result.stdout.strip()
        git("init", "--quiet")
        git("fetch", "--quiet", "--depth=1", "--no-tags", repository, revision)
        return git("rev-parse", "FETCH_HEAD^{commit}")


def update(root: Path, revision: str, repository: str | None = None, *, check: bool = False) -> str:
    root = root.resolve()
    manifest = root / "pixi.toml"
    if not manifest.is_file():
        raise ConfigurationError("Run package update in a directory containing pixi.toml.")
    document = tomlkit.parse(manifest.read_text())
    selection = document.get("pypi-dependencies", {}).get("orinoco-lite")
    if selection is None:
        raise ConfigurationError("pixi.toml does not select an orinoco-lite package.")
    previous_repository = selection.get("git") if isinstance(selection, dict) else None
    repository = remote_url(repository or previous_repository or SOURCE_REPOSITORY)
    commit = resolve_commit(repository, revision)
    if check:
        print(commit)
        return commit
    # Failures must leave the previous selection usable. Environment installation
    # happens only on the caller's next pixi run, not inside this running process.
    lock = root / "pixi.lock"
    before = {path: path.read_bytes() if path.exists() else None for path in (manifest, lock)}
    replacement = tomlkit.inline_table()
    replacement.update({"git": repository, "rev": commit})
    try:
        document["pypi-dependencies"]["orinoco-lite"] = replacement
        manifest.write_text(tomlkit.dumps(document))
        subprocess.run(["pixi", "lock", "--manifest-path", "pixi.toml"], cwd=root, check=True)
    except BaseException:
        for path, content in before.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    print(f"Selected {repository}@{commit}")
    print("Package selection and lock updated. Start a fresh pixi run to use this version.")
    return commit


def register(commands):
    package = commands.add_parser("package", help="manage the downstream's immutable package selection")
    actions = package.add_subparsers(dest="package_command", required=True)
    parser = actions.add_parser("update", help="select a fetchable Git revision and regenerate the Pixi lock")
    parser.add_argument("--revision", required=True, help="commit, release tag, or branch; stored as a full commit SHA")
    parser.add_argument("--repository", help="remote Git URL (default: current Git selection, or the official repository)")
    parser.add_argument("--check", action="store_true", help="verify remote availability and print the full SHA without changing files")
