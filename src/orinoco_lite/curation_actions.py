"""Transport for the trusted downstream source-adapter Actions workflow."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from . import curation
from .finalization import _diff_paths, _site_gitlink
from .workflow_access import obtain, request_json, revoke

SCRATCH = Path("build/curation")
CONTEXT = SCRATCH / "context.json"
NOTICE = "**AI-generated draft — not reviewed by John**\n\n"


def git(root: Path, *args: str, token: str | None = None) -> str:
    env = dict(os.environ)
    if token:
        encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                   GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {encoded}")
    return subprocess.check_output(["git", "-C", str(root), *args], env=env, text=True).strip()


def api(path: str, body: dict | None = None, *, metadata: bool = False) -> dict:
    return request_json("https://api.github.com" + path,
                        os.environ["METADATA_TOKEN" if metadata else "GH_TOKEN"], body)


def output(**values: object) -> None:
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
        for key, value in values.items():
            text = str(value)
            if any(c in text for c in "\r\n\0"):
                raise RuntimeError("Workflow output must be one line")
            stream.write(f"{key}={text}\n")


def prepare() -> None:
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    repository = os.environ["GITHUB_REPOSITORY"]
    base = git(Path.cwd(), "rev-parse", "HEAD")
    context = {"repository": repository, "base": base, "head": base,
               "comment_id": None, "number": 0, "adapter": event.get("inputs", {}).get("adapter", ""),
               "branch": f"automation/curation/{os.environ['GITHUB_RUN_ID']}"}
    if os.environ["GITHUB_EVENT_NAME"] == "issue_comment":
        comment = api(f"/repos/{repository}/issues/comments/{event['comment']['id']}")
        if comment != event["comment"]:
            # Compare durable review facts; API responses may add unrelated fields.
            for key in ("body", "id", "created_at", "updated_at", "html_url"):
                if comment.get(key) != event["comment"].get(key):
                    raise RuntimeError("The authenticated comment changed")
        if any(comment["user"].get(key) != event["comment"]["user"].get(key)
               for key in ("id", "login", "type")):
            raise RuntimeError("The authenticated comment author changed")
        if comment["created_at"] != comment["updated_at"]:
            raise RuntimeError("Edited decision comments require a new submission")
        matches = re.findall(r"```json\n([\s\S]*?)\n```", comment["body"])
        if len(matches) != 1 or "/curation submit" not in comment["body"]:
            raise RuntimeError("Missing complete decision submission")
        submission = json.loads(matches[0])
        number = event["issue"]["number"]
        pull = api(f"/repos/{repository}/pulls/{number}")
        if (submission["repository"] != repository or submission["pull_request"] != number
                or pull["state"] != "open" or not pull["draft"]
                or pull["head"]["repo"]["full_name"] != repository
                or pull["head"]["sha"] != submission["head_sha"] or pull["base"]["sha"] != base):
            raise RuntimeError("The decision submission is stale")
        context.update(head=submission["head_sha"], number=number,
                       comment_id=comment["id"], adapter=submission["adapter"],
                       branch=pull["head"]["ref"], proposal=submission["proposal_sha"],
                       metadata=submission.get("metadata"))
        SCRATCH.mkdir(parents=True, exist_ok=True)
        (SCRATCH / "comment.json").write_text(json.dumps(comment))
    if re.fullmatch(r"[a-z][a-z0-9-]*", context["adapter"]) is None:
        raise RuntimeError("Invalid adapter name")
    if _site_gitlink(Path.cwd(), base) is None:
        raise RuntimeError("This coordinated workflow requires site-specific as a submodule")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    CONTEXT.write_text(json.dumps(context))


def checkout(context: dict) -> None:
    repository = os.environ["METADATA_REPOSITORY"]
    metadata_head = os.environ["METADATA_HEAD"]
    context.update(metadata_repository=repository, metadata_head=metadata_head)
    for name, ref in (("base", context["base"]), ("review", context["head"])):
        root = SCRATCH / name
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", ".", str(root)], check=True)
        # Proposal objects may not exist in the trusted default-branch checkout.
        git(root, "fetch", f"https://github.com/{context['repository']}.git", ref, token=os.environ["GH_TOKEN"])
        git(root, "checkout", "--quiet", "--detach", ref)
        sha = _site_gitlink(root, ref)
        git(root, "clone", "--quiet", f"https://github.com/{repository}.git", "site-specific", token=os.environ["METADATA_TOKEN"])
        git(root / "site-specific", "checkout", "--quiet", "--detach", str(sha))
        for repo in (root, root / "site-specific"):
            git(repo, "config", "user.name", "github-actions[bot]")
            git(repo, "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    if git(SCRATCH / "review/site-specific", "rev-parse", "HEAD") != metadata_head:
        raise RuntimeError("Metadata checkout no longer matches the authorized head")
    CONTEXT.write_text(json.dumps(context))


def record(context: dict) -> None:
    root = (SCRATCH / "review").resolve()
    base_root = (SCRATCH / "base").resolve()
    plan = curation.build_plan(base_root, Path.cwd(), context["adapter"], context["base"])
    if not plan.candidates:
        if context["comment_id"]:
            raise RuntimeError("The regenerated proposal has no candidates")
        context["has_changes"] = False
        CONTEXT.write_text(json.dumps(context))
        print("No new source claims require review.")
        return
    if context["comment_id"]:
        # Review code, configuration, and captured source remain trusted-base data.
        if set(_diff_paths(root, context["base"], context["head"])) != {"site-specific"}:
            raise RuntimeError("The website review must change only the metadata gitlink")
        meta_base = _site_gitlink(root, context["base"])
        paths = _diff_paths(root / "site-specific", meta_base, context["metadata_head"])
        roots = tuple(str(path.relative_to("site-specific")) + "/" for path in plan.metadata_roots)
        if any(not path.startswith(roots) or not path.endswith((".yaml", ".yml")) for path in paths):
            raise RuntimeError("The metadata review changes non-metadata inputs")
    command = ["python", "-m", "orinoco_lite.curation",
               "finalize" if context["comment_id"] else "stage", "--root", ".",
               "--base-root", "../base", "--trusted-root", "../../..",
               "--adapter", plan.adapter, "--base", plan.metadata_base]
    if context["comment_id"]:
        command += ["--comment", "../comment.json", "--repository", context["repository"],
                    "--pull-request", str(context["number"])]
        message = f"chore(curation): record {plan.adapter} decisions"
    else:
        source = json.dumps(dict(plan.source_coordinate), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        message = (f"chore(curation): propose {plan.adapter} metadata\n\n"
                   f"Curation-Adapter: {plan.adapter}\nCuration-Adapter-Agent: {plan.adapter_agent_pid}\n"
                   f"Curation-Metadata-Base: {plan.metadata_base}\nCuration-Source: {source}")
    env = {key: value for key, value in os.environ.items()
           if key not in {"GH_TOKEN", "GITHUB_TOKEN", "METADATA_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL"}}
    subprocess.run([str(Path(sys.executable).with_name("datalad")), "run", "--explicit", "-m", message,
                    "-o", str(plan.metadata_roots[0]), "-o", str(plan.metadata_roots[1]),
                    "-o", f"site-specific/curation-records/{plan.adapter}.yaml", "--", *command],
                   cwd=root, env=env, check=True)
    if git(root, "show", "-s", "--format=%P", "HEAD") != context["head"]:
        raise RuntimeError("DataLad did not produce exactly one website commit")
    if git(root / "site-specific", "show", "-s", "--format=%P", "HEAD") != context["metadata_head"]:
        raise RuntimeError("DataLad did not produce exactly one metadata commit")
    if _diff_paths(root, context["head"], git(root, "rev-parse", "HEAD")) != ("site-specific",):
        raise RuntimeError("DataLad changed more than the website gitlink; initialize the datasets before proposing")
    if git(root, "status", "--porcelain", "--untracked-files=all") or git(root / "site-specific", "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("Adapter recording left uncommitted changes outside its declared outputs")
    context.update(result=git(root, "rev-parse", "HEAD"), metadata_result=git(root / "site-specific", "rev-parse", "HEAD"),
                   source_coordinate=dict(plan.source_coordinate), has_changes=True)
    CONTEXT.write_text(json.dumps(context))


def publish(context: dict) -> None:
    website = context["repository"]
    metadata = context["metadata_repository"]
    branch = context["branch"]
    source_details = ""
    if not context["comment_id"]:
        from .config import load_workspace
        from html import escape
        review_url = load_workspace(SCRATCH / "base").base_url.rstrip("/") + "/review/"
        coordinate = escape(json.dumps(context["source_coordinate"], ensure_ascii=False, indent=2))
        source_details = (f"\n\n[Downstream review]({review_url})\n\n<details>\n"
                          f"<summary>Source coordinate</summary>\n\n<pre>{coordinate}</pre>\n\n</details>")
    root = SCRATCH / "review"
    if context["comment_id"]:
        current = api(f"/repos/{website}/pulls/{context['number']}")
        if current["head"]["sha"] != context["head"] or current["state"] != "open" or not current["draft"]:
            raise RuntimeError("Website head changed before publishing")
        meta_pull = api(f"/repos/{metadata}/pulls/{context['metadata']['pull_request']}", metadata=True)
        if meta_pull["head"]["sha"] != context["metadata_head"] or meta_pull["state"] != "open" or not meta_pull["draft"]:
            raise RuntimeError("Metadata head changed before publishing")
        meta_branch = meta_pull["head"]["ref"]
        expected = context["metadata_head"]
    else:
        meta_branch = branch
        expected = ""
    git(root / "site-specific", "push", f"--force-with-lease=refs/heads/{meta_branch}:{expected}",
        f"https://github.com/{metadata}.git", f"HEAD:refs/heads/{meta_branch}", token=os.environ["METADATA_TOKEN"])
    try:
        if not context["comment_id"]:
            meta_pull = api(f"/repos/{metadata}/pulls", {
                "title": f"chore(curation): propose {context['adapter']} metadata", "head": branch,
                "base": api(f"/repos/{metadata}", metadata=True)["default_branch"], "draft": True,
                "body": NOTICE + f"Source-adapter proposal coordinated by {website}. Explicit decisions are submitted on the website review page." + source_details,
            }, metadata=True)
            context["metadata_number"] = meta_pull["number"]
        git(root, "push", f"--force-with-lease=refs/heads/{branch}:{context['head'] if context['comment_id'] else ''}",
            f"https://github.com/{website}.git", f"HEAD:refs/heads/{branch}", token=os.environ["GH_TOKEN"])
        if not context["comment_id"]:
            pull = api(f"/repos/{website}/pulls", {
                "title": f"chore(curation): propose {context['adapter']} metadata", "head": branch,
                "base": os.environ["DEFAULT_BRANCH"], "draft": True,
                "body": NOTICE + f"Review the source-adapter proposal with metadata draft https://github.com/{metadata}/pull/{context['metadata_number']}. The exact proposal review link follows when its presentation artifact is ready." + source_details,
            })
            context["number"] = pull["number"]
        CONTEXT.write_text(json.dumps(context))
    except Exception:
        print(f"Partial write: metadata {metadata}@{context['metadata_result']} was pushed. Inspect both drafts before retrying; no rollback or merge was attempted.", file=sys.stderr)
        raise


def bundle(context: dict) -> None:
    plan = curation.build_plan((SCRATCH / "base").resolve(), Path.cwd(), context["adapter"], context["base"])
    value = curation.review_bundle(plan, context["repository"], context["number"], int(os.environ["GITHUB_RUN_ID"]), context["result"])
    (SCRATCH / "artifact").mkdir(exist_ok=True)
    (SCRATCH / "artifact/review-bundle.json").write_text(json.dumps(value))


def announce(context: dict) -> None:
    if context["comment_id"]:
        body = NOTICE + f"Recorded human acceptance decisions in {context['result']}. Ready for merging.\n\nMetadata commit: {context['metadata_result']}."
    else:
        from .config import load_workspace
        from urllib.parse import urlencode
        query = urlencode({"repository": context["repository"], "pull_request": context["number"], "artifact_id": os.environ["ARTIFACT_ID"]})
        url = load_workspace(SCRATCH / "base").base_url.rstrip("/") + "/review/?" + query
        body = NOTICE + f"[Review the complete {context['adapter']} proposal]({url}).\n\nMetadata draft: https://github.com/{context['metadata_repository']}/pull/{context['metadata_number']}"
    api(f"/repos/{context['repository']}/issues/{context['number']}/comments", {"body": body})


@contextmanager
def environment(**values: str):
    """Limit credentials to the transport that needs them; never save them on disk."""
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def access(context: dict, *, write: bool = False) -> dict:
    return obtain({"repository": context["repository"], "head": context["head"],
                   "comment_id": context["comment_id"], "write": write}, curation=True)


def validate_run() -> None:
    print("Resolve the trusted event and check out both repository heads.", flush=True)
    prepare()
    context = json.loads(CONTEXT.read_text())
    credentials = access(context)
    try:
        with environment(METADATA_TOKEN=credentials["token"],
                         METADATA_REPOSITORY=credentials["repository"],
                         METADATA_HEAD=credentials["head"]):
            checkout(context)
    finally:
        revoke(credentials["token"])
    print("Validate and record the composed adapter result without installation credentials.", flush=True)
    record(context)


def publish_run() -> None:
    context = json.loads(CONTEXT.read_text())
    if not context["has_changes"]:
        print("No new source claims require publication.")
        return
    print("Recheck authorization and publish both drafts at their exact heads.", flush=True)
    credentials = access(context, write=True)
    # Only a successful proposal publication needs a token in the final step,
    # after GitHub's official action has uploaded the review artifact.
    retain_website_token = False
    try:
        with environment(GH_TOKEN=credentials["website_token"], METADATA_TOKEN=credentials["token"],
                         DEFAULT_BRANCH=json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["repository"]["default_branch"]):
            publish(context)
            if context["comment_id"]:
                announce(context)
            else:
                bundle(context)
                output(review_artifact=f"orinoco-curation-review-{context['result']}",
                       review_token=credentials["website_token"])
                retain_website_token = True
    finally:
        # ExitStack attempts both revocations even if the first one fails.
        with ExitStack() as cleanup:
            if not retain_website_token:
                cleanup.callback(revoke, credentials["website_token"])
            cleanup.callback(revoke, credentials["token"])


def complete_run(artifact_id: str) -> None:
    token = os.environ.get("CURATION_REVIEW_TOKEN", "")
    if not token:
        return
    try:
        if artifact_id:
            if not artifact_id.isdigit():
                raise RuntimeError("Invalid review artifact identifier")
            with environment(GH_TOKEN=token, ARTIFACT_ID=artifact_id):
                announce(json.loads(CONTEXT.read_text()))
        else:
            print("Review presentation was not uploaded; inspect the published drafts before retrying.")
    finally:
        revoke(token)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run trusted source-adapter curation in GitHub Actions.")
    commands = result.add_subparsers(dest="curation_command", required=True)
    commands.add_parser("validate", help="prepare, validate, and record the event's metadata changes locally")
    commands.add_parser("publish", help="authorize and publish the validated changes as paired drafts")
    complete = commands.add_parser("complete", help="link the uploaded review and release its temporary access")
    complete.add_argument("--artifact-id", default="", help="identifier returned by GitHub's artifact upload action")
    return result


def execute(args: argparse.Namespace) -> int:
    if args.curation_command == "validate":
        validate_run()
    elif args.curation_command == "publish":
        publish_run()
    else:
        complete_run(args.artifact_id)
    return 0


if __name__ == "__main__":
    execute(parser().parse_args())
