"""Print the exact setup selections before the shell starts modifying a dataset."""

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def git(root, *args, check=True):
    # Ignore caller repository overrides, but retain normal transport credentials.
    env = {key: value for key, value in os.environ.items()
           if key not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"}}
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", "-C", str(root), *args], env=env, check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def commit_checkout(stack, local, repository, commit):
    if git(local, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode == 0:
        return local
    root = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="orinoco-setup-summary-")))
    git(root, "init", "--quiet")
    print(f"Fetching commit details from {repository}...", file=sys.stderr, flush=True)
    git(root, "fetch", "--quiet", "--depth=1", "--no-tags", "--", repository, commit)
    return root


def shorten(text, width):
    text = " ".join(text.split())
    return text if len(text) <= width else text[:max(0, width - 3)] + "..."


def line(text, color=None):
    text = shorten(text, shutil.get_terminal_size(fallback=(120, 24)).columns)
    if color and sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb":
        text = f"\033[{color}m{text}\033[0m"
    print(text)


def show_commit(label, repository, commit, root, selection):
    message = git(root, "show", "-s", "--format=%cs %s", commit).stdout.strip()
    coordinates = commit[:7] + (f", {selection}" if selection != commit else "")
    prefix, suffix = f"• {label}: ", f" ({coordinates})"
    width = shutil.get_terminal_size(fallback=(120, 24)).columns
    repository = shorten(repository, max(16, width - len(prefix) - len(suffix)))
    line(prefix + repository + suffix, "36")
    line(f"  Commit: {message}", "2")


def changes(root):
    result = git(root, "status", "--porcelain=v1", "--untracked-files=normal",
                 "--ignore-submodules=none", check=False)
    return result.stdout.splitlines() if result.returncode == 0 else None


def show_changes(label, entries):
    if entries is None:
        line(f"Warning: {label}: Git status unavailable", "33")
        return
    tracked = [entry.strip() for entry in entries if not entry.startswith("??")]
    untracked = [entry[3:] for entry in entries if entry.startswith("??")]
    details = []
    if tracked:
        details.append(", ".join(tracked))
    if untracked:
        details.append(f"untracked: {', '.join(untracked)}")
    if details:
        line(f"Warning: {label}: {'; '.join(details)}", "33")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", nargs=3, metavar=("CHECKOUT", "REPOSITORY", "COMMIT"), required=True)
    parser.add_argument("--template", nargs=3, metavar=("CHECKOUT", "REPOSITORY", "COMMIT"), required=True)
    parser.add_argument("--template-selection", required=True)
    parser.add_argument("--package-selection", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--dump", default="")
    parser.add_argument("--site-specific", default="")
    parser.add_argument("--api", required=True)
    parser.add_argument("--site-layout", required=True)
    parser.add_argument("--build", choices=("true", "false"), required=True)
    parser.add_argument("--from-downstream", default="")
    parser.add_argument("--development", choices=("true", "false"), default="false")
    args = parser.parse_args()
    engineering, package_repository, package_commit = args.package
    template, template_repository, template_commit = args.template
    with ExitStack() as stack:
        package_root = commit_checkout(stack, engineering, package_repository, package_commit)
        template_root = commit_checkout(stack, template, template_repository, template_commit)
        upstream_path = "submodules/www-from-model"
        entry = git(package_root, "ls-tree", package_commit, "--", upstream_path).stdout.split()
        if len(entry) != 4 or entry[:2] != ["160000", "commit"]:
            raise ValueError(f"Selected package has no {upstream_path} gitlink")
        upstream_commit = entry[2]
        modules = git(package_root, "config", "--blob", f"{package_commit}:.gitmodules",
                      "--get-regexp", r"^submodule\..*\.path$").stdout.splitlines()
        key = next(line.split()[0][:-4] + "url" for line in modules
                   if line.split(maxsplit=1)[1] == upstream_path)
        upstream_repository = git(package_root, "config", "--blob", f"{package_commit}:.gitmodules",
                                  "--get", key).stdout.strip()
        if upstream_repository.startswith(("./", "../")):
            # Let Git resolve relative submodule URLs against the selected origin.
            scratch = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="orinoco-setup-url-")))
            git(scratch, "init", "--quiet")
            git(scratch, "fetch", "--quiet", "--depth=1", "--no-tags", "--",
                str(Path(package_root).resolve()), package_commit)
            git(scratch, "remote", "add", "origin", package_repository)
            git(scratch, "read-tree", package_commit)
            git(scratch, "checkout-index", "--", ".gitmodules")
            git(scratch, "submodule", "init", "--", upstream_path)
            upstream_repository = git(scratch, "config", "--get", key).stdout.strip()
        upstream_root = commit_checkout(stack, Path(engineering) / upstream_path,
                                        upstream_repository, upstream_commit)
        show_commit("Package", package_repository, package_commit, package_root, args.package_selection)
        show_commit("Template", template_repository, template_commit, template_root, args.template_selection)
        show_commit("www-from-model", upstream_repository, upstream_commit, upstream_root, "package gitlink")
        if args.from_downstream:
            source = Path(args.from_downstream).resolve()
            commit = git(source, "rev-parse", "HEAD").stdout.strip()
            line(f"• Inputs: {source} @ {commit[:7]} (retained; no acquisition or import)", "36")
        elif args.site_specific:
            line(f"• Inputs: {Path(args.site_specific).resolve()} (site-specific submodule)", "36")
        else:
            source = f"dump {Path(args.dump).resolve()}" if args.dump else args.api
            line(f"• Inputs: {source} (site layout: {args.site_layout})", "36")
        local_changes = [("Engineering", changes(engineering)), ("Template", changes(template))]
        if (Path(engineering) / upstream_path / ".git").exists():
            local_changes.append(("www-from-model", changes(Path(engineering) / upstream_path)))
        destination = args.destination.resolve()
        if (destination / ".git").exists():
            local_changes.append(("Destination", changes(destination)))
        action = "Forced overwrite" if destination.exists() else "Create"
        line(f"{action}: {destination}", "31" if destination.exists() else None)
        line("Build: site + publication bundle" if args.build == "true" else "Build: skipped")
        if args.development == "true":
            line("Development: tracked .orinoco-lite/orinoco-lite-dev, editable installation")
        for label, entries in local_changes:
            show_changes(label, entries)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, ValueError, StopIteration) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise SystemExit(f"Cannot prepare setup review: {detail or 'missing submodule declaration'}")
