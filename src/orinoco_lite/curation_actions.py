"""Transport for the trusted downstream source-adapter Actions workflow."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from . import curation
from .finalization import _diff_paths, _site_gitlink
from .workflow_access import request_json

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
               "comment_id": None, "number": 0, "adapter": os.environ.get("ADAPTER", ""),
               "branch": f"automation/curation/{os.environ['GITHUB_RUN_ID']}"}
    if os.environ["GITHUB_EVENT_NAME"] == "issue_comment":
        comment = api(f"/repos/{repository}/issues/comments/{event['comment']['id']}")
        if comment != event["comment"]:
            # Compare durable review facts; API responses may add unrelated fields.
            for key in ("body", "id", "user", "created_at", "updated_at", "html_url"):
                if comment.get(key) != event["comment"].get(key):
                    raise RuntimeError("The authenticated comment changed")
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
    output(head=context["head"], number=context["number"], comment_id=context["comment_id"] or "")


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
        output(has_changes="false")
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
    context.update(result=git(root, "rev-parse", "HEAD"), metadata_result=git(root / "site-specific", "rev-parse", "HEAD"))
    CONTEXT.write_text(json.dumps(context))
    output(has_changes="true")


def publish(context: dict) -> None:
    website = context["repository"]
    metadata = context["metadata_repository"]
    branch = context["branch"]
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
                "body": NOTICE + f"Source-adapter proposal coordinated by {website}. Explicit decisions are submitted on the website review page.",
            }, metadata=True)
            context["metadata_number"] = meta_pull["number"]
        git(root, "push", f"--force-with-lease=refs/heads/{branch}:{context['head'] if context['comment_id'] else ''}",
            f"https://github.com/{website}.git", f"HEAD:refs/heads/{branch}", token=os.environ["GH_TOKEN"])
        if not context["comment_id"]:
            pull = api(f"/repos/{website}/pulls", {
                "title": f"chore(curation): propose {context['adapter']} metadata", "head": branch,
                "base": os.environ["DEFAULT_BRANCH"], "draft": True,
                "body": NOTICE + f"Review the source-adapter proposal with metadata draft https://github.com/{metadata}/pull/{context['metadata_number']}. The review link follows when its presentation artifact is ready.",
            })
            context["number"] = pull["number"]
        CONTEXT.write_text(json.dumps(context))
    except Exception:
        print(f"Partial write: metadata {metadata}@{context['metadata_result']} was pushed. Inspect both drafts before retrying; no rollback or merge was attempted.", file=sys.stderr)
        raise
    output(number=context["number"], proposal=context["result"])


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "checkout", "record", "publish", "bundle", "announce"))
    args = parser.parse_args()
    if args.operation == "prepare":
        prepare()
    else:
        globals()[args.operation](json.loads(CONTEXT.read_text()))


if __name__ == "__main__":
    main()
