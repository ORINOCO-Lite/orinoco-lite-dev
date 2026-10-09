#!/usr/bin/env python3
"""Regenerate the submodule divergence CSV from Git history."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

CSV_PATH = "docs/agents/submodule-divergence.csv"
FIELDS = (
    "path",
    "upstream_url",
    "upstream_ref",
    "selected_commit",
    "selected_description",
    "merge_base",
    "merge_base_description",
    "upstream_commit",
    "upstream_description",
    "local_commits",
    "upstream_commits",
    "local_commit_subjects",
    "comparison_pr",
)
SUBJECT = re.compile(
    r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\([^()\n]+\))?!?: \S.* "
    r"\[intent:(?:general|integration|deployment|undecided)\]"
)


class ReportError(RuntimeError):
    pass


def command(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode:
        raise ReportError(result.stderr.strip() or f"{args[0]} failed")
    return result.stdout


def git(path: Path, *args: str) -> str:
    return command("git", "-C", str(path), *args, cwd=path)


def links(parent: Path, revision: str | None):
    """Read pins and clone URLs from the same committed tree or index."""
    entries = (
        git(parent, "ls-tree", "-r", "-z", revision)
        if revision
        else git(parent, "ls-files", "--stage", "-z")
    )
    pins = []
    for entry in entries.split("\0"):
        if not entry:
            continue
        metadata, name = entry.split("\t", 1)
        fields = metadata.split()
        if not revision and fields[2] != "0":
            raise ReportError(f"Unresolved index entry: {name}")
        if fields[0] == "160000":
            pins.append((name, fields[2] if revision else fields[1]))
    if not pins:
        return
    blob = f"{revision or ''}:.gitmodules"
    config = git(
        parent,
        "config",
        f"--blob={blob}",
        "--null",
        "--get-regexp",
        r"^submodule\..*\.(path|url)$",
    )
    values = dict(item.split("\n", 1) for item in config.split("\0") if item)
    urls = {
        value: values.get(key[:-4] + "url", "")
        for key, value in values.items()
        if key.endswith(".path")
    }
    for name, commit in pins:
        yield name, commit, urls.get(name, "")


def selected_modules(root: Path, staged: bool, prepare: bool):
    def visit(parent, revision, prefix):
        for name, commit, url in links(parent, revision):
            relative = prefix / name
            checkout = root / relative
            if (
                not checkout.is_dir()
                or Path(git(checkout, "rev-parse", "--show-toplevel").strip()).resolve()
                != checkout.resolve()
            ):
                raise ReportError(
                    f"Initialize {relative}: git submodule update --init --recursive"
                )
            if (
                prepare
                and git(checkout, "rev-parse", "--is-shallow-repository").strip()
                == "true"
            ):
                git(checkout, "fetch", "--unshallow", "origin")
            yield relative.as_posix(), checkout, commit, url
            yield from visit(checkout, commit, relative)

    yield from visit(root, None if staged else "HEAD", Path())


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


def comparison_pr(root: Path, url: str, selected: str, base: str) -> str:
    match = re.fullmatch(
        r"(?:https://github.com/|git@github.com:)([^/]+/[^/]+?)(?:\.git)?", url
    )
    if not match:
        return ""
    pulls = json.loads(
        command(
            "gh",
            "pr",
            "list",
            "--repo",
            match[1],
            "--state",
            "open",
            "--base",
            "main",
            "--head",
            "orinoco-lite-diff",
            "--json",
            "url,headRefOid,baseRefOid",
            cwd=root,
        )
    )
    return next(
        (
            pull["url"]
            for pull in pulls
            if pull["headRefOid"] == selected and pull["baseRefOid"] == base
        ),
        "",
    )


def generate(root: Path, rows, *, staged=False, fetch=False, prepare=False):
    result, invalid = [], []
    for name, checkout, selected, url in selected_modules(
        root, staged, prepare or fetch
    ):
        if name not in rows:
            raise ReportError(
                f"Add a CSV row for {name} with upstream_url and upstream_ref, then regenerate"
            )
        row = rows[name].copy()
        if not row["upstream_url"] or not row["upstream_ref"]:
            raise ReportError(f"{name}: upstream_url and upstream_ref are required")
        if fetch:
            git(checkout, "fetch", "--tags", row["upstream_url"], row["upstream_ref"])
            row["upstream_commit"] = git(checkout, "rev-parse", "FETCH_HEAD").strip()
        elif prepare:
            git(
                checkout, "fetch", "--tags", row["upstream_url"], row["upstream_commit"]
            )
        upstream = row["upstream_commit"]
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", upstream):
            raise ReportError(f"{name}: run with --fetch to record an upstream commit")
        if git(checkout, "rev-parse", "--is-shallow-repository").strip() == "true":
            raise ReportError(
                f"{name}: complete history is required; rerun with --prepare"
            )
        base = git(checkout, "merge-base", selected, upstream).strip()
        local_range = f"{base}..{selected}"
        subjects = git(
            checkout, "log", "--reverse", "--topo-order", "--format=%s", local_range
        ).splitlines()
        for line in git(
            checkout, "log", "--reverse", "--format=%h %s", local_range
        ).splitlines():
            commit, subject = line.split(" ", 1)
            if not SUBJECT.fullmatch(subject):
                invalid.append(f"{name} {commit}: {subject}")
        row.update(
            selected_commit=selected,
            merge_base=base,
            selected_description=git(
                checkout, "describe", "--tags", "--always", "--abbrev=12", selected
            ).strip(),
            merge_base_description=git(
                checkout, "describe", "--tags", "--always", "--abbrev=12", base
            ).strip(),
            upstream_description=git(
                checkout, "describe", "--tags", "--always", "--abbrev=12", upstream
            ).strip(),
            local_commits=git(checkout, "rev-list", "--count", local_range).strip(),
            upstream_commits=git(
                checkout, "rev-list", "--count", f"{base}..{upstream}"
            ).strip(),
            local_commit_subjects="\n".join(subjects),
        )
        if not subjects:
            row["comparison_pr"] = ""
        elif fetch:
            row["comparison_pr"] = comparison_pr(root, url, selected, base)
        result.append(row)
    return render(sorted(result, key=lambda row: row["path"])), invalid


def write_csv(path: Path, content: str):
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as output:
        output.write(content)
        temporary = Path(output.name)
    temporary.replace(path)


def fix_csv(path: Path, staged: str, generated: str):
    working = path.read_bytes()
    if working == generated.encode("utf-8"):
        print(
            f"CSV fixes are already in the working file. Review and git add {CSV_PATH}, then retry.",
            file=sys.stderr,
        )
    elif working != staged.encode("utf-8"):
        print(
            "CSV has unstaged edits; no files changed. Preserve those edits, then reconcile or stage the CSV and rerun the hook. To regenerate explicitly, run python tools/submodule_divergence.py --staged after preserving your edits.",
            file=sys.stderr,
        )
    else:
        write_csv(path, generated)
        print(
            f"Updated {CSV_PATH} for staged pins. Review the diff, git add {CSV_PATH}, and retry. Nothing was staged.",
            file=sys.stderr,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="package checkout (default: this script’s repository)",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="use staged parent pins; --check also reads staged CSV",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="fetch current upstream heads/tags and refresh comparison PR links using gh",
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="fetch complete histories and recorded upstream commits; do not advance the snapshot",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail on stale CSV or any local commit subject outside the prescribed convention; never write (exit 1 for violations, 2 for errors)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="local hook: repair working CSV from staged pins and staged CSV, never stage; fail after repairs or title violations; refuse conflicting unstaged CSV edits (offline)",
    )
    args = parser.parse_args(argv)
    if args.fix and (args.check or args.fetch or args.prepare):
        parser.error(
            "--fix is offline and cannot be combined with --check, --fetch, or --prepare"
        )
    if args.fix:
        args.staged = True
    if args.fetch and args.check:
        parser.error("--fetch writes a new snapshot; use --check separately")
    try:
        root = args.root.resolve()
        csv_path = root / CSV_PATH
        text = (
            git(root, "show", f":{CSV_PATH}")
            if args.staged and (args.check or args.fix)
            else csv_path.read_text(encoding="utf-8")
        )
        rows = read_rows(text)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from orinoco_lite.progress import progress

        with progress("Calculating submodule divergence with Git"):
            generated, invalid = generate(
                root, rows, staged=args.staged, fetch=args.fetch, prepare=args.prepare
            )
        if args.check or args.fix:
            stale = generated != text
            if stale and args.fix:
                fix_csv(csv_path, text, generated)
            elif stale:
                print(
                    "Submodule CSV is stale. Run python tools/submodule_divergence.py"
                    + (" --staged" if args.staged else "")
                    + " and stage the CSV.",
                    file=sys.stderr,
                )
            if invalid:
                print(
                    "Local commit subjects must use <type>(<scope>): <purpose> [intent:general|integration|deployment|undecided]\n"
                    + "\n".join(invalid)
                    + "\nThese titles cannot be fixed automatically. Review intent, deliberately reword the listed submodule commits, update/stage parent pins, and rerun the hook. No history was rewritten.",
                    file=sys.stderr,
                )
            return int(stale or bool(invalid))
        if generated != text:
            write_csv(csv_path, generated)
        return 0
    except (OSError, ReportError, csv.Error, ValueError) as error:
        print(f"Submodule divergence: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
