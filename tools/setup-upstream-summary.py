"""Print the exact setup selections before the shell starts modifying a dataset."""

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
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
    git(root, "fetch", "--quiet", "--depth=1", "--no-tags", "--", repository, commit)
    return root


def show_commit(label, repository, commit, root, selection):
    message = git(root, "show", "-s", "--format=%cs %s", commit).stdout.strip()
    print(f"\nSelected {label}: {repository}\n  Source: {selection}\n  Commit: {commit}\n  {message}")


def show_changes(label, root):
    result = git(root, "status", "--porcelain=v1", "--untracked-files=normal",
                 "--ignore-submodules=none", check=False)
    if result.returncode:
        print(f"  {label}: Git status unavailable ({root})")
        return False
    lines = result.stdout.splitlines()
    untracked = sum(line.startswith("??") for line in lines)
    print(f"  {label}: {len(lines) - untracked} changed, {untracked} untracked entries ({root})")
    for line in lines[:12]:
        print(f"    {line}")
    if len(lines) > 12:
        print(f"    ... {len(lines) - 12} more; use git status in this checkout")
    return bool(lines)


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
        print("\nSetup review")
        show_commit("package", package_repository, package_commit, package_root, args.package_selection)
        show_commit("template", template_repository, template_commit, template_root, args.template_selection)
        show_commit("www-from-model", upstream_repository, upstream_commit, upstream_root,
                    "selected package gitlink; retained as sourcedata/www-from-model")
        print("\nLocal checkout changes (Git status codes; untracked directories grouped):")
        dirty = show_changes("Engineering", Path(engineering).resolve())
        show_changes("Template", Path(template).resolve())
        if (Path(engineering) / upstream_path / ".git").exists():
            show_changes("www-from-model", Path(engineering) / upstream_path)
        print("  Selected commits exclude local edits in these checkouts.")
        if dirty:
            print("  Warning: the engineering checkout has uncommitted changes.")
            print("  To test local edits, run `pixi run orinoco-lite dev enable PATH` in an existing downstream.")
        destination = args.destination.resolve()
        print(f"\nDestination: {destination}")
        if destination.exists():
            print("  REPLACE (--force): delete ALL existing contents, including local changes.")
            if (destination / ".git").exists():
                show_changes("Destination", destination)
        else:
            print("  Create a new downstream.")
        if args.site_specific:
            print(f"Inputs: existing site-specific dataset {Path(args.site_specific).resolve()}")
            print("  Install as a submodule; skip import; use template root site settings.")
        else:
            source = f"dump {Path(args.dump).resolve()}" if args.dump else f"fetch Pool dump from {args.api}"
            print(f"Inputs: {source}\n  Import upstream site files; site layout: {args.site_layout}.")
        print("Build: projection, validation, site and publication bundle; no deployment." if args.build == "true"
              else "Build: skipped; setup stops after preparation.")
        print("Setup records DataLad commits; selected commits must remain available from their remotes.")


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, ValueError, StopIteration) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        raise SystemExit(f"Cannot prepare setup review: {detail or 'missing submodule declaration'}")
