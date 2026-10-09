#!/usr/bin/env python3
"""Initialize selected submodules and configure their authoritative remotes."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

# Confirmed original repositories for the Orinoco Lite mirrors.
UPSTREAMS = {
    "dump-things-pyclient": "orinoco/dump-things-pyclient",
    "dump-things-service": "orinoco/dump-things-service",
    "query-things": "orinoco/query-things",
    "things-enrichment-tools": "orinoco/things-enrichment-tools",
    "things-schemas": "orinoco/things-schemas",
    "www-from-model": "www/www-from-model",
    "pool.psychoinformatics.de-ui": "www/pool.psychoinformatics.de-ui",
    "shacl-vue": "orinoco/shacl-vue",
}


class ReportError(RuntimeError):
    pass


def git(root, *args, missing_ok=False):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode and not (missing_ok and result.returncode == 1):
        raise ReportError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def links(parent: Path, revision: str | None):
    """Read dependency declarations from the selected tree (or root index)."""
    entries = (
        git(parent, "ls-tree", "-r", "-z", revision)
        if revision
        else git(parent, "ls-files", "--stage", "-z")
    )
    pins = []
    for entry in entries.split("\0"):
        if not entry:
            continue
        metadata, path = entry.split("\t", 1)
        fields = metadata.split()
        if not revision and fields[2] != "0":
            raise ReportError(f"Resolve the index conflict: {path}")
        if fields[0] == "160000":
            pins.append((path, fields[2] if revision else fields[1]))
    if not pins:
        return
    config = git(
        parent,
        "config",
        f"--blob={revision or ''}:.gitmodules",
        "--null",
        "--get-regexp",
        r"^submodule\..*\.(path|url|branch)$",
    )
    values = dict(item.split("\n", 1) for item in config.split("\0") if item)
    declarations = {
        value: (
            key[:-5].removeprefix("submodule."),
            values.get(key[:-4] + "url", ""),
            values.get(key[:-4] + "branch", ""),
        )
        for key, value in values.items()
        if key.endswith(".path")
    }
    for path, commit in pins:
        if path not in declarations:
            raise ReportError(f"Missing .gitmodules declaration: {path}")
        name, url, branch = declarations[path]
        yield path, commit, name, url, branch


def selected_modules(root: Path, *, initialize=False, repairs=None):
    def visit(parent, revision, prefix):
        for path, commit, name, url, branch in links(parent, revision):
            relative = prefix / path
            checkout = root / relative
            if not checkout.resolve().is_relative_to(root.resolve()):
                raise ReportError(f"Submodule path escapes repository: {relative}")
            if not (checkout / ".git").exists():
                if not initialize:
                    raise ReportError(
                        f"Initialize {relative}: run tools/setup_submodule_remotes.py"
                    )
                # Git's initializer reads the index and working .gitmodules. Never
                # let a different checkout initialize the wrong selected dependency.
                indexed = {p: (c, n, u, b) for p, c, n, u, b in links(parent, None)}
                if indexed.get(path) != (commit, name, url, branch):
                    raise ReportError(
                        f"{relative}: initialize from parent revision {revision}; "
                        "its current index selects different dependencies"
                    )
                working_url = git(
                    parent,
                    "config",
                    "-f",
                    ".gitmodules",
                    "--get",
                    f"submodule.{name}.url",
                    missing_ok=True,
                ).strip()
                if working_url != url:
                    raise ReportError(
                        f"{relative}: reconcile unstaged .gitmodules before initialization"
                    )
                git(
                    parent,
                    "submodule",
                    "update",
                    "--init",
                    "--checkout",
                    "--no-recommend-shallow",
                    "--",
                    path,
                )
                repairs.append(f"initialized {relative}")
            if (
                Path(git(checkout, "rev-parse", "--show-toplevel").strip()).resolve()
                != checkout.resolve()
            ):
                raise ReportError(f"{relative}: Git resolves to a different checkout")
            yield relative.as_posix(), checkout, commit, url, branch
            yield from visit(checkout, commit, relative)

    yield from visit(root, None, Path())


def configure(root: Path, *, check=False):
    repairs = []
    try:
        for path, checkout, _, url, _ in selected_modules(
            root, initialize=not check, repairs=repairs
        ):
            match = re.fullmatch(
                r"(?:https://github.com/|git@github.com:)([^/]+)/([^/]+?)(?:\.git)?",
                url,
            )
            repository = match[2] if match else ""
            maintained = repository in UPSTREAMS
            if match and match[1] == "ORINOCO-Lite" and not maintained:
                raise ReportError(
                    f"{path}: add its confirmed German repository to UPSTREAMS"
                )
            if maintained:
                expected = (
                    f"https://hub.psychoinformatics.de/{UPSTREAMS[repository]}.git"
                )
                current = git(
                    checkout,
                    "config",
                    "--local",
                    "--get-all",
                    "remote.upstream.url",
                    missing_ok=True,
                ).splitlines()
                if current != [expected]:
                    if not check:
                        git(
                            checkout,
                            "config",
                            "--local",
                            "--replace-all",
                            "remote.upstream.url",
                            expected,
                        )
                    repairs.append(f"{path}: upstream URL = {expected}")
            remote = (
                "upstream"
                if maintained or "upstream" in git(checkout, "remote").splitlines()
                else "origin"
            )
            if not (check and maintained):
                git(checkout, "remote", "get-url", remote)
            mapping = f"+refs/heads/*:refs/remotes/{remote}/*"
            mappings = git(
                checkout,
                "config",
                "--get-all",
                f"remote.{remote}.fetch",
                missing_ok=True,
            ).splitlines()
            if mapping not in mappings:
                if not check:
                    git(
                        checkout,
                        "config",
                        "--local",
                        "--add",
                        f"remote.{remote}.fetch",
                        mapping,
                    )
                repairs.append(f"{path}: added {remote} fetch mapping")
    finally:
        for repair in repairs:
            print(f"{'Required' if check else 'Repaired'}: {repair}", file=sys.stderr)
    return bool(repairs)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        allow_abbrev=False,
        epilog="Exit 0: unchanged and valid; 1: repairs made or needed; 2: unresolved error. Never repins initialized checkouts or fetches upstream updates.",
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report required repairs without changing files or Git state",
    )
    args = parser.parse_args(argv)
    if args.check:
        os.environ["GIT_NO_LAZY_FETCH"] = "1"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from orinoco_lite.progress import progress

        with progress("Initializing submodules and configuring Git remotes"):
            return int(configure(args.root.resolve(), check=args.check))
    except (OSError, ReportError) as error:
        print(f"Submodule setup: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
