#!/usr/bin/env python3
"""Regenerate the submodule divergence CSV from Git history."""

from __future__ import annotations

import argparse
import csv
import io
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import quote

CSV_PATH = "docs/agents/submodule-divergence.csv"
FIELDS = (
    "path",
    "local_commits",
    "upstream_commits",
    "local_commit_subjects",
    "upstream_url",
    "upstream_ref",
    "selected_commit",
    "selected_description",
    "merge_base",
    "merge_base_description",
    "upstream_commit",
    "upstream_description",
    "comparison_url",
)
# Both scripts traverse the same selected gitlinks; setup owns initialization.
try:
    from .setup_submodule_remotes import ReportError, git, links, selected_modules
except ImportError:
    from setup_submodule_remotes import ReportError, git, links, selected_modules


def read_rows(text: str):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != list(FIELDS):
        raise ReportError("CSV header must be: " + ",".join(FIELDS))
    rows = {}
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ReportError("Malformed CSV row")
        if row["path"] in rows:
            raise ReportError(f"Duplicate CSV path: {row['path']}")
        rows[row["path"]] = row
    return rows


def render(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def comparison_url(url: str, branch: str) -> str:
    """A stable link to the mirror comparison, available without a hosting API."""
    match = re.fullmatch(
        r"(?:https://github.com/|git@github.com:)([^/]+/[^/]+?)(?:\.git)?", url
    )
    if not match:
        return ""
    return f"https://github.com/{match[1]}/compare/{quote(branch, safe='')}...orinoco-lite-diff"


def upstream_selection(checkout, declared_branch, *, fetch):
    remote = (
        "upstream" if "upstream" in git(checkout, "remote").splitlines() else "origin"
    )
    url = git(checkout, "remote", "get-url", remote).strip()
    # Mirrors retain the branch selected by their owning project too.
    # Only an undeclared branch falls back to the authoritative default.
    branch = declared_branch
    if branch == ".":
        raise ReportError(
            f"{checkout}: branch '.' needs a parent branch; use an explicit dependency branch"
        )
    if fetch:
        shallow = (
            git(checkout, "rev-parse", "--is-shallow-repository").strip() == "true"
        )
        if shallow and remote != "origin":
            # The fork may contain selected local commits absent from upstream.
            git(checkout, "fetch", "--unshallow", "--recurse-submodules=no", "origin")
        git(
            checkout,
            "fetch",
            "--tags",
            "--recurse-submodules=no",
            *(["--unshallow"] if shallow and remote == "origin" else []),
            remote,
        )
        if not branch:
            git(checkout, "remote", "set-head", remote, "--auto")
    if not branch:
        try:
            branch = (
                git(checkout, "symbolic-ref", f"refs/remotes/{remote}/HEAD")
                .strip()
                .removeprefix(f"refs/remotes/{remote}/")
            )
        except ReportError as error:
            raise ReportError(
                f"{checkout}: missing {remote}/HEAD; run without --no-fetch to discover the default branch"
            ) from error
    if git(checkout, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise ReportError(
            f"{checkout}: complete history is required; run without --no-fetch"
        )
    try:
        commit = git(
            checkout,
            "rev-parse",
            "--verify",
            f"refs/remotes/{remote}/{branch}^{{commit}}",
        ).strip()
    except ReportError as error:
        raise ReportError(
            f"{checkout}: missing {remote}/{branch}; run without --no-fetch"
        ) from error
    return url, branch, commit, remote == "upstream"


def observe_upstreams(modules, *, fetch):
    """Observe independent repositories concurrently, retaining input order."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as workers:
        return list(
            workers.map(
                lambda module: upstream_selection(module[1], module[4], fetch=fetch),
                modules,
            )
        )


def generate(root: Path, *, fetch=False, modules=None):
    result = []
    if modules is None:
        modules = list(selected_modules(root))
    observations = observe_upstreams(modules, fetch=fetch)
    for (name, checkout, selected, url, _), observation in zip(modules, observations):
        upstream_url, branch, upstream, fork = observation
        base = git(checkout, "merge-base", selected, upstream).strip()
        local_range = f"{upstream}..{selected}"
        subjects = git(
            checkout, "log", "--reverse", "--topo-order", "--format=%s", local_range
        ).splitlines()
        row = dict(
            path=name,
            upstream_url=upstream_url,
            upstream_ref=f"refs/heads/{branch}",
            upstream_commit=upstream,
            selected_commit=selected,
            merge_base=base,
            local_commits=str(len(subjects)),
            upstream_commits=git(
                checkout, "rev-list", "--count", f"{selected}..{upstream}"
            ).strip(),
            local_commit_subjects="\n".join(subjects),
            comparison_url=comparison_url(url, branch) if fork and subjects else "",
        )
        for field, commit in (
            ("selected", selected),
            ("merge_base", base),
            ("upstream", upstream),
        ):
            row[f"{field}_description"] = git(
                checkout, "describe", "--tags", "--always", "--abbrev=12", commit
            ).strip()
        result.append(row)
    return render(sorted(result, key=lambda row: row["path"]))


def write_csv(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as output:
        output.write(content)
        temporary = Path(output.name)
    temporary.replace(path)


def snapshot(root: Path, revision: str, path: str) -> str:
    """Read an optional tracked file without consulting the working tree."""
    entries = git(root, "ls-tree", "--name-only", revision, "--", path)
    return git(root, "show", f"{revision}:{path}") if entries.strip() else ""


def staged_check(root: Path) -> bool:
    """Check changed declarations before opening their dependency checkouts."""

    def declarations(checkout, revision):
        return {
            path: (commit, url, branch)
            for path, commit, _, url, branch in links(checkout, revision)
        }

    before = declarations(root, "HEAD")
    after = declarations(root, None)
    old_text = snapshot(root, "HEAD", CSV_PATH)
    staged_paths = git(root, "ls-files", "--", CSV_PATH).splitlines()
    new_text = git(root, "show", f":{CSV_PATH}") if staged_paths else ""
    if before == after and old_text == new_text:
        return False
    # A malformed historical report cannot prevent its valid replacement.
    # With no usable baseline, every staged row must be checked.
    try:
        old_rows = read_rows(old_text) if old_text else {}
    except (ReportError, csv.Error):
        old_rows = {}
    new_rows = read_rows(new_text) if new_text else {}
    changed_rows = {
        path
        for path in old_rows.keys() | new_rows.keys()
        if old_rows.get(path) != new_rows.get(path)
    }
    checked = set(changed_rows)
    modules = []

    def contains(parent, child):
        return child == parent or child.startswith(parent + "/")

    def visit(before, after, prefix):
        for path in sorted(before.keys() | after.keys()):
            name = (prefix / path).as_posix()
            previous, selected = before.get(path), after.get(path)
            changed_descendants = any(
                row != name and contains(name, row) for row in changed_rows
            )
            if (
                previous == selected
                and name not in changed_rows
                and not changed_descendants
            ):
                continue
            if selected is None:
                # A removed subtree has no selected checkout to initialize.
                checked.update(row for row in new_rows if contains(name, row))
                continue
            checkout = root / name
            if not checkout.resolve().is_relative_to(root):
                raise ReportError(f"Submodule path escapes repository: {name}")
            if not (checkout / ".git").exists():
                raise ReportError(
                    f"Initialize {name}: run python3 tools/setup_submodule_remotes.py"
                )
            if (
                Path(git(checkout, "rev-parse", "--show-toplevel").strip()).resolve()
                != checkout.resolve()
            ):
                raise ReportError(f"{name}: Git resolves to a different checkout")
            if previous != selected or name in changed_rows:
                checked.add(name)
                modules.append((name, checkout, *selected))
            if previous is None or previous[0] != selected[0] or changed_descendants:
                visit(
                    declarations(checkout, previous[0]) if previous else {},
                    declarations(checkout, selected[0]),
                    Path(name),
                )

    visit(before, after, Path())
    expected = read_rows(generate(root, modules=modules))
    invalid = sorted(
        path for path in checked if new_rows.get(path) != expected.get(path)
    )
    if invalid:
        print(
            "Staged submodule report does not match changed dependencies: "
            + ", ".join(invalid)
            + f". Regenerate {CSV_PATH}, review it, and stage it with the pins.",
            file=sys.stderr,
        )
    return bool(invalid)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        allow_abbrev=False,
        epilog="Uses staged parent pins and selected nested gitlinks. Generation exits 0 on success; checks exit 1 for stale rows; operational errors exit 2. Never stages files or repins dependencies.",
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="use locally available upstream refs; remote changes may be missing",
    )
    checks = parser.add_mutually_exclusive_group()
    checks.add_argument(
        "--check",
        action="store_true",
        help="check the full working CSV without repairs; implies --no-fetch",
    )
    checks.add_argument(
        "--staged-check",
        action="store_true",
        help="check only staged dependency and CSV changes against HEAD; never fetches or repairs files",
    )
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.no_fetch or args.check or args.staged_check:
            os.environ["GIT_NO_LAZY_FETCH"] = "1"
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from orinoco_lite.progress import progress

        with progress("Calculating submodule divergence with Git"):
            if args.staged_check:
                return int(staged_check(root))
            generated = generate(root, fetch=not (args.no_fetch or args.check))
        path = root / CSV_PATH
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        if generated != previous:
            if args.check:
                print(
                    "Submodule CSV is stale; regenerate and stage it.", file=sys.stderr
                )
                return 1
            write_csv(path, generated)
            print(
                f"Updated {CSV_PATH}. Review and stage the CSV. Nothing was staged.",
                file=sys.stderr,
            )
        return 0
    except (OSError, ReportError, csv.Error, ValueError) as error:
        print(f"Submodule divergence: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
