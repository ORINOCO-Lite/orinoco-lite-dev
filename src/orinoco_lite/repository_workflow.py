"""Process editor submissions in the repository that owns their metadata.

Credential jobs fetch and publish Git objects. Materialization runs in a
separate job without credentials or OIDC access. Git handles branch integration.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlencode

from .progress import progress
from .workflow_access import request_json, submission_credentials

INPUT_PATH = ".orinoco-lite/submission.json"
REF = re.compile(r"orinoco/submissions/([0-9a-f]{64})")


def git(root: Path, *arguments: str, token: str | None = None,
        environment: dict[str, str] | None = None) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0")
    if token:
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                   GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + encoded)
    env.update(environment or {})
    result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *arguments],
                            env=env, text=True, capture_output=True)
    if result.returncode:
        # Git error output can include credential-bearing configuration. Keep
        # errors operational; conflicts remain inspectable in the worktree.
        raise RuntimeError(f"Git {arguments[0]} failed; inspect the workflow and any merge conflicts")
    return result.stdout.strip()


def api(repository: str, path: str, token: str, body: dict | None = None,
        *, method: str | None = None):
    return request_json(f"https://api.github.com/repos/{repository}{path}", token, body, method=method)


def clone(repository: str, commit: str, destination: Path, token: str) -> None:
    if destination.is_symlink() or (destination.exists() and any(destination.iterdir())):
        raise RuntimeError("The checkout destination is not empty")
    destination.mkdir(parents=True, exist_ok=True)
    git(destination, "init", "--quiet")
    git(destination, "remote", "add", "origin", f"https://github.com/{repository}.git")
    git(destination, "fetch", "--quiet", "origin", commit, token=token)
    git(destination, "checkout", "--quiet", "--detach", commit)


def bundle(root: Path, destination: Path) -> None:
    git(root, "branch", "-f", "orinoco-result", "HEAD")
    git(root, "bundle", "create", str(destination.resolve()), "orinoco-result")


def restore_bundle(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    git(destination.parent, "clone", "--quiet", "--branch", "orinoco-result",
        str(source.resolve()), str(destination.resolve()))


def identity(authorization: dict, timestamp: str) -> dict[str, str]:
    user = authorization["submitter"]
    return {
        "GIT_AUTHOR_NAME": user["login"],
        "GIT_AUTHOR_EMAIL": f"{user['id']}+{user['login']}@users.noreply.github.com",
        "GIT_COMMITTER_NAME": "github-actions[bot]",
        "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
        "GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp,
    }


def result_branch(submission: str) -> str:
    match = REF.fullmatch(submission)
    if match is None:
        raise RuntimeError("Invalid submission branch")
    return "orinoco/proposals/" + match[1]


def require_input_owner(authorization: dict) -> None:
    if os.environ["GITHUB_REPOSITORY"] != authorization["input_repository"]:
        raise RuntimeError("Process this submission in its input repository to keep private input there")


def read_input(storage: Path, authorization: dict, submission: str, token: str) -> dict:
    remote = f"https://github.com/{authorization['input_repository']}.git"
    git(storage, "fetch", "--quiet", remote, authorization["input_commit"], token=token)
    value = git(storage, "show", authorization["input_commit"] + ":" + INPUT_PATH)
    if len(value.encode()) > 10 * 1024 * 1024 + 64 * 1024:
        raise RuntimeError("The submitted edit exceeds 10 MiB")
    fingerprint = hashlib.sha256((authorization["scope"]["source"]["repository"] + "\n" + value + "\n").encode()).hexdigest()
    if submission != "orinoco/submissions/" + fingerprint:
        raise RuntimeError("The submission branch does not identify its authorized input")
    submitted = json.loads(value)
    if not isinstance(submitted, dict) or submitted.get("operation") != "shacl":
        raise RuntimeError("This worker does not support the submitted operation")
    if submitted.get("bundle", {}).get("source_commit") != authorization["scope"]["source"]["commit"]:
        raise RuntimeError("The edit does not identify its authorized source snapshot")
    target = submitted.get("target", {"kind": "standalone"})
    if not isinstance(target, dict) or target.get("kind") not in {"standalone", "pull_request"}:
        raise RuntimeError("Invalid website proposal target")
    numbers = ([target.get("pull_request")] if target["kind"] == "pull_request" else [])
    if target.get("metadata_pull_request") is not None:
        numbers.append(target["metadata_pull_request"])
    if any(type(number) is not int or number < 1 for number in numbers):
        raise RuntimeError("Invalid proposal number")
    return submitted


def selected_pull(repository: str, number: int, token: str) -> dict:
    if type(number) is not int or number < 1:
        raise RuntimeError("Invalid proposal number")
    pull = api(repository, f"/pulls/{number}", token)
    if pull["head"]["repo"]["full_name"] != repository:
        raise RuntimeError("The selected proposal belongs to another repository")
    return pull


@progress("Fetching the submitted edit from GitHub")
def prepare(directory: Path, submission: str) -> None:
    directory.mkdir(parents=True)
    with submission_credentials(submission) as access:
        authorization = access["authorization"]
        require_input_owner(authorization)
        scope = authorization["scope"]
        credentials = access["credentials"]
        source = scope["source"]
        website = directory / "website"
        clone(source["repository"], source["commit"], website,
              credentials[source["repository"]]["token"])
        bundle(website, directory / "website.bundle")
        storage = website
        if scope["metadata"]:
            metadata = scope["metadata"]
            storage = directory / "metadata"
            clone(metadata["repository"], metadata["commit"], storage,
                  credentials[metadata["repository"]]["token"])
            bundle(storage, directory / "metadata.bundle")
        submitted = read_input(storage, authorization, submission,
                               credentials[authorization["input_repository"]]["token"])
        (directory / "input.json").write_text(json.dumps(submitted))
        (directory / "context.json").write_text(json.dumps({
            "authorization": authorization,
            "timestamp": git(storage, "show", "-s", "--format=%cI", authorization["input_commit"]),
        }))


@progress("Applying and validating the submitted metadata")
def materialize(directory: Path) -> None:
    if any(os.environ.get(key) for key in ("GH_TOKEN", "GITHUB_TOKEN",
           "METADATA_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL")):
        raise RuntimeError("Materialization must run in a job without credentials or OIDC access")
    from .config import load_workspace
    from .driver import invoke_driver
    from .editor import apply_bundle_report
    from .resources import resolve_resources
    from .shacl_handoff import inspect_materialized_changes

    context = json.loads((directory / "context.json").read_text())
    authorization = context["authorization"]
    source = authorization["scope"]["source"]
    metadata = authorization["scope"]["metadata"]
    website = directory / "materialized"
    restore_bundle(directory / "website.bundle", website)
    if metadata:
        # A clone leaves an empty directory at its gitlink path.
        restore_bundle(directory / "metadata.bundle", website / "site-specific")
    submitted = json.loads((directory / "input.json").read_text())
    bundle_path = directory / "editor-bundle.json"
    bundle_path.write_text(json.dumps(submitted["bundle"]))
    workspace = load_workspace(website)
    resources = resolve_resources()
    report = apply_bundle_report(workspace, resources.root, bundle_path, write=True)
    if not report["changed_paths"]:
        raise RuntimeError("Nothing changed in the submitted records")
    inspect_materialized_changes(website, source_commit=source["commit"])
    if invoke_driver("validate", workspace, resources):
        raise RuntimeError("The edited metadata did not pass validation")
    env = identity(authorization, context["timestamp"])
    target = website / "site-specific" if metadata else website
    git(target, "add", "--all")
    git(target, "commit", "-qm", "feat(metadata): apply submitted editor changes", environment=env)
    if metadata:
        bundle(target, directory / "metadata-result.bundle")
        git(website, "add", "site-specific")
        git(website, "commit", "-qm", "chore(metadata): propose the edited website metadata", environment=env)
    bundle(website, directory / "website-result.bundle")


def integrate(root: Path, repository: str, branch: str, token: str,
              environment: dict[str, str], metadata_repository: str | None = None) -> str:
    """Fast-forward or merge; never replace work already pushed by a person."""
    remote = f"https://github.com/{repository}.git"
    proposed = git(root, "rev-parse", "HEAD")
    for attempt in range(3):
        current = git(root, "ls-remote", "--heads", remote, "refs/heads/" + branch, token=token)
        git(root, "checkout", "--quiet", "--detach", proposed)
        if current:
            current_sha = current.split()[0]
            git(root, "fetch", "--quiet", remote, current_sha, token=token)
            git(root, "checkout", "--quiet", "--detach", current_sha)
            if metadata_repository:
                from .shacl_handoff import site_submodule
                selected = site_submodule(root, current_sha)
                if selected is None or selected["repository"] != metadata_repository:
                    raise RuntimeError("The website changed its metadata repository; resolve that conflict before continuing")
            try:
                git(root, "merge", "--no-edit", proposed, environment=environment)
            except RuntimeError:
                raise RuntimeError(f"The edit conflicts with {repository}@{branch}; resolve that Git conflict and rerun") from None
        try:
            git(root, "push", remote, f"HEAD:refs/heads/{branch}", token=token)
            return git(root, "rev-parse", "HEAD")
        except RuntimeError:
            if attempt == 2:
                raise RuntimeError(f"Could not update {repository}@{branch}; inspect GitHub's repository rules or rerun after concurrent pushes") from None
    raise AssertionError("Unreachable")


def find_pull(repository: str, branch: str, token: str) -> dict | None:
    query = urlencode({"head": repository.split("/")[0] + ":" + branch, "state": "all"})
    existing = api(repository, "/pulls?" + query, token)
    return existing[0] if existing else None


def ensure_pull(repository: dict, branch: str, token: str, body: str) -> dict:
    name = repository["name"]
    pull = find_pull(name, branch, token)
    if pull:
        if pull["state"] == "open":
            return pull
        if not pull.get("merged_at"):
            raise RuntimeError(f"The submission pull request is already closed: {pull['html_url']}")
        # If the website was merged first, propose the remaining gitlink update.
        from urllib.parse import quote
        comparison = api(name, f"/compare/{quote(repository['defaultBranch'], safe='')}...{quote(branch, safe='')}", token)
        if not comparison["files"]:
            return pull
    return api(name, "/pulls", token, {
        "head": branch, "base": repository["defaultBranch"], "draft": True,
        "title": "feat(metadata): apply website editor changes", "body": body,
    })


def advance_gitlink(website: Path, repository: str, branch: str, token: str,
                    metadata_repository: str, metadata_token: str, proposal: str,
                    merged: str, environment: dict[str, str]) -> str:
    """Replace the proposal's gitlink after any GitHub merge method.

The metadata commits may be rewritten by squash/rebase. Check the old pointer
against the original PR history, then commit the result on the current website
head so unrelated website edits survive.
"""
    from .shacl_handoff import site_submodule
    metadata = website / "site-specific"
    git(metadata, "fetch", "--quiet", "origin", proposal, merged, token=metadata_token)
    remote = f"https://github.com/{repository}.git"
    base = git(website, "rev-parse", "HEAD")
    for attempt in range(3):
        current = git(website, "ls-remote", "--heads", remote, "refs/heads/" + branch, token=token)
        head = current.split()[0] if current else base
        if current:
            git(website, "fetch", "--quiet", remote, head, token=token)
        git(website, "checkout", "--quiet", "--detach", head)
        selected = site_submodule(website, head)
        if selected is None or selected["repository"] != metadata_repository:
            raise RuntimeError("The website changed its metadata repository; resolve that conflict before continuing")
        old = selected["source_commit"]
        git(metadata, "fetch", "--quiet", "origin", old, token=metadata_token)
        try:
            git(metadata, "merge-base", "--is-ancestor", merged, old)
            return head  # Already updated, or deliberately advanced further.
        except RuntimeError:
            pass
        try:
            git(metadata, "merge-base", "--is-ancestor", old, proposal)
        except RuntimeError:
            raise RuntimeError("The website gitlink has a conflicting metadata change; resolve it and rerun") from None
        git(website, "update-index", "--cacheinfo", f"160000,{merged},site-specific")
        git(website, "commit", "-qm", "chore(metadata): use the merged metadata proposal", environment=environment)
        try:
            git(website, "push", remote, f"HEAD:refs/heads/{branch}", token=token)
            return git(website, "rev-parse", "HEAD")
        except RuntimeError:
            if attempt == 2:
                raise RuntimeError("The website changed during completion; rerun to finish the same proposal") from None
    raise AssertionError("Unreachable")


@progress("Publishing the metadata and website pull requests")
def publish(directory: Path, submission: str) -> None:
    from .shacl_handoff import verify_materialized_commit
    with submission_credentials(submission) as access:
        authorization = access["authorization"]
        require_input_owner(authorization)
        scope = authorization["scope"]
        credentials = access["credentials"]
        website = directory / "publish"
        restore_bundle(directory / "website-result.bundle", website)
        if scope["metadata"]:
            restore_bundle(directory / "metadata-result.bundle", website / "site-specific")
        # Treat validation artifacts as data. Recheck their Git paths/parents
        # using fresh signed authority, without executing the proposal's code.
        verify_materialized_commit(website, source_commit=scope["source"]["commit"],
                                   commit=git(website, "rev-parse", "HEAD"))
        branch = result_branch(submission)
        website_repo = scope["repositories"][0]
        storage = website / "site-specific" if scope["metadata"] else website
        submitted = read_input(storage, authorization, submission,
                               credentials[authorization["input_repository"]]["token"])
        env = identity(authorization, git(storage, "show", "-s", "--format=%cI", authorization["input_commit"]))
        for result in ([website, storage] if storage != website else [website]):
            author = git(result, "show", "-s", "--format=%an%x00%ae", "HEAD")
            if author != env["GIT_AUTHOR_NAME"] + "\0" + env["GIT_AUTHOR_EMAIL"]:
                raise RuntimeError("The materialized commit does not identify the authenticated submitter")
        target = submitted.get("target", {"kind": "standalone"})
        website_pull = find_pull(website_repo["name"], branch, credentials[website_repo["name"]]["token"])
        if target["kind"] == "pull_request":
            website_pull = selected_pull(website_repo["name"], target["pull_request"], credentials[website_repo["name"]]["token"])
        elif target["kind"] != "standalone":
            raise RuntimeError("Invalid website proposal target")
        if website_pull and website_pull["state"] != "open" and not website_pull.get("merged_at"):
            raise RuntimeError("The website proposal was closed without merging")
        run_url = f"https://github.com/{authorization['input_repository']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
        body = f"Submitted by @{authorization['submitter']['login']}. [Processing and validation]({run_url})."
        if scope["metadata"]:
            metadata_repo = next(repo for repo in scope["repositories"] if repo["name"] == scope["metadata"]["repository"])
            token = credentials[metadata_repo["name"]]["token"]
            metadata_pull = (selected_pull(metadata_repo["name"], target["metadata_pull_request"], token)
                             if target.get("metadata_pull_request") is not None else find_pull(metadata_repo["name"], branch, token))
            if metadata_pull and metadata_pull.get("merged_at"):
                complete(directory / "after-merge", submission, metadata_pull["number"])
                return
            if metadata_pull and metadata_pull["state"] != "open":
                raise RuntimeError("The metadata proposal is closed; use completion to finish its website update")
            metadata_branch = metadata_pull["head"]["ref"] if metadata_pull else branch
            integrate(website / "site-specific", metadata_repo["name"], metadata_branch, token, env)
            if git(website, "diff", "--name-only", "--", "site-specific"):
                git(website, "add", "site-specific")
                git(website, "commit", "-qm", "chore(metadata): include concurrent proposal edits", environment=env)
            metadata_pull = metadata_pull or ensure_pull(metadata_repo, branch, token, body)
            marker = f"<!-- orinoco-submission:{REF.fullmatch(submission)[1]} -->"
            comments = api(metadata_repo["name"], f"/issues/{metadata_pull['number']}/comments?per_page=100", token)
            if not any(marker in comment["body"] for comment in comments):
                api(metadata_repo["name"], f"/issues/{metadata_pull['number']}/comments", token,
                    {"body": f"This edit will update its website proposal after this metadata PR merges.\n\n{marker}"})
            body += f"\n\nMetadata: {metadata_pull['html_url']}. Its merge will update this website proposal automatically."
        token = credentials[website_repo["name"]]["token"]
        website_branch = website_pull["head"]["ref"] if website_pull else branch
        integrate(website, website_repo["name"], website_branch, token, env,
                  scope["metadata"]["repository"] if scope["metadata"] else None)
        pull = (website_pull if website_pull and website_pull["state"] == "open"
                else ensure_pull(website_repo, website_branch, token, body))
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(f"[Open the website proposal]({pull['html_url']})\n")


@progress("Updating the website proposal after metadata merge")
def complete(directory: Path, submission: str, pull_number: int = 0) -> None:
    with submission_credentials(submission) as access:
        authorization = access["authorization"]
        require_input_owner(authorization)
        scope = authorization["scope"]
        metadata = scope["metadata"]
        if metadata is None:
            return
        credentials = access["credentials"]
        branch = result_branch(submission)
        token = credentials[metadata["repository"]]["token"]
        directory.mkdir(parents=True)
        website = directory / "complete"
        source = scope["source"]
        clone(source["repository"], source["commit"], website,
              credentials[source["repository"]]["token"])
        clone(metadata["repository"], authorization["input_commit"], website / "site-specific", token)
        submitted = read_input(website / "site-specific", authorization, submission, token)
        target = submitted.get("target", {"kind": "standalone"})
        if target.get("metadata_pull_request") is not None:
            pull = selected_pull(metadata["repository"], target["metadata_pull_request"], token)
        else:
            query = urlencode({"head": metadata["repository"].split("/")[0] + ":" + branch, "state": "closed"})
            merged = [pull for pull in api(metadata["repository"], "/pulls?" + query, token) if pull.get("merged_at")]
            if len(merged) != 1:
                raise RuntimeError("The metadata proposal has not merged")
            pull = selected_pull(metadata["repository"], merged[0]["number"], token)
        if (not pull["merged"] or (pull_number and pull["number"] != pull_number)
                or not re.fullmatch(r"[0-9a-f]{40}", pull["merge_commit_sha"])):
            raise RuntimeError("GitHub has not returned this submission's metadata merge result")
        env = identity(authorization, pull["merged_at"])
        website_repo = scope["repositories"][0]
        website_token = credentials[website_repo["name"]]["token"]
        website_pull = (selected_pull(website_repo["name"], target["pull_request"], website_token)
                        if target["kind"] == "pull_request" else find_pull(website_repo["name"], branch, website_token))
        if website_pull and website_pull["state"] != "open" and not website_pull.get("merged_at"):
            raise RuntimeError("The website proposal was closed without merging")
        website_branch = website_pull["head"]["ref"] if website_pull else branch
        advance_gitlink(website, website_repo["name"], website_branch, website_token,
                        metadata["repository"], token, pull["head"]["sha"], pull["merge_commit_sha"], env)
        website_pull = (website_pull if website_pull and website_pull["state"] == "open" else
                        ensure_pull(website_repo, website_branch, website_token,
                        f"Finish @{authorization['submitter']['login']}'s submitted edit with merged metadata {pull['html_url']}."))
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(f"[Website proposal updated]({website_pull['html_url']})\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "materialize", "publish", "complete"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--submission")
    parser.add_argument("--pull-request", type=int, default=0)
    args = parser.parse_args(argv)
    if args.operation != "materialize" and not args.submission:
        parser.error("credential operations require --submission")
    try:
        directory = args.directory.resolve()
        if args.operation == "prepare":
            prepare(directory, args.submission)
        elif args.operation == "materialize":
            materialize(directory)
        elif args.operation == "publish":
            publish(directory, args.submission)
        else:
            complete(directory, args.submission, args.pull_request)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"Repository workflow: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
