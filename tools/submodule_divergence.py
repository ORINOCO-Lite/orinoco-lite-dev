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
SUBJECT = re.compile(
    r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\([^()\n]+\))?!?: \S.* "
    r"\[intent:(?:general|integration|deployment|undecided)\]"
)


# Both scripts traverse the same selected gitlinks; setup owns initialization.
try:
    from .setup_submodule_remotes import ReportError, git, selected_modules
except ImportError:
    from setup_submodule_remotes import ReportError, git, selected_modules


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
    # A fork follows its authoritative source's default. An unmodified dependency
    # retains the owning project's declared update branch (e.g. Congo stable).
    branch = declared_branch if remote == "origin" else ""
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
            "-c",
            f"remote.{remote}.followRemoteHEAD=always",
            "fetch",
            "--tags",
            "--recurse-submodules=no",
            *(["--unshallow"] if shallow and remote == "origin" else []),
            remote,
        )
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


def generate(root: Path, *, fetch=False):
    result, invalid = [], []
    modules = list(selected_modules(root))
    observations = observe_upstreams(modules, fetch=fetch)
    for (name, checkout, selected, url, _), observation in zip(modules, observations):
        upstream_url, branch, upstream, fork = observation
        base = git(checkout, "merge-base", selected, upstream).strip()
        local_range = f"{upstream}..{selected}"
        subjects = git(
            checkout, "log", "--reverse", "--topo-order", "--format=%s", local_range
        ).splitlines()
        for line in git(
            checkout, "log", "--reverse", "--format=%h %s", local_range
        ).splitlines():
            commit, subject = line.split(" ", 1)
            if not SUBJECT.fullmatch(subject):
                invalid.append(f"{name} {commit}: {subject}")
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
    return render(sorted(result, key=lambda row: row["path"])), invalid


def write_csv(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as output:
        output.write(content)
        temporary = Path(output.name)
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        allow_abbrev=False,
        epilog="Uses staged parent pins and selected nested gitlinks. Exit 0: unchanged and valid; 1: CSV repairs made/needed or invalid titles; 2: operational error. Never stages files or repins dependencies.",
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="use locally available upstream refs; remote changes may be missing",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check the working CSV without repairs or Git changes; implies --no-fetch",
    )
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        path = root / CSV_PATH
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        if args.no_fetch or args.check:
            os.environ["GIT_NO_LAZY_FETCH"] = "1"
            print(
                "Using local upstream refs; remote changes may be missing. Run without --no-fetch or --check to refresh, then review and stage the CSV.",
                file=sys.stderr,
            )
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from orinoco_lite.progress import progress

        with progress("Calculating submodule divergence with Git"):
            generated, invalid = generate(root, fetch=not (args.no_fetch or args.check))
        changed = generated != previous
        if changed:
            if args.check:
                print(
                    "Submodule CSV is stale; regenerate and stage it.", file=sys.stderr
                )
            else:
                write_csv(path, generated)
                print(
                    f"Updated {CSV_PATH}. Review and stage the CSV, then retry. Nothing was staged.",
                    file=sys.stderr,
                )
        if invalid:
            print(
                "Local commit subjects must use <type>(<scope>): <purpose> [intent:general|integration|deployment|undecided]\n"
                + "\n".join(invalid)
                + "\nTitles cannot be fixed automatically; deliberately review and reword them. No history was rewritten.",
                file=sys.stderr,
            )
        return int(changed or bool(invalid))
    except (OSError, ReportError, csv.Error, ValueError) as error:
        print(f"Submodule divergence: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
