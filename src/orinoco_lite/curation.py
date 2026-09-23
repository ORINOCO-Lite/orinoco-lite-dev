"""Trusted source-adapter execution and GitHub review bundles.

Executable adapters come from the trusted website checkout. Candidate plans
are regenerated from the immutable base and captured source, never loaded
from a pull request artifact.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

from .candidates import CandidatePlan
from .config import load_workspace
from .decisions import load_decision_cache, serialize_decision_cache, update_decision_cache
from .errors import ConfigurationError
from .finalization import (
    _exact_commit, _require_clean_submitted_head,
    _require_safe_worktree_path, finalize_candidate_plan,
)
from .cli import main as orinoco_main


def build_plan(root: Path, trusted: Path, adapter: str, base: str) -> CandidatePlan:
    if re.fullmatch(r"[a-z][a-z0-9-]*", adapter) is None:
        raise ConfigurationError("Adapter must be a safe extension name")
    _exact_commit(root, base, "Candidate metadata base")
    _require_clean_submitted_head(root, base)
    provider = _require_safe_worktree_path(trusted, f"extensions/source-adapters/{adapter}/review.py")
    spec = importlib.util.spec_from_file_location("orinoco_curation_provider", provider)
    if spec is None or spec.loader is None:
        raise ConfigurationError("The trusted adapter has no review entry point")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    plan = module.build_candidate_plan(root, trusted_root=trusted, metadata_base=base)
    if not isinstance(plan, CandidatePlan) or plan.adapter != adapter or plan.metadata_base != base:
        raise ConfigurationError("The trusted adapter returned inconsistent candidate coordinates")
    if len(plan.candidates) > 225:
        raise ConfigurationError("Review supports at most 225 candidates")
    workspace = load_workspace(root)
    expected = workspace.path("records").relative_to(root).as_posix()
    if plan.candidates and str(plan.metadata_roots[0]) != expected:
        raise ConfigurationError("Candidate record root does not match the website configuration")
    return plan


def validate(root: Path) -> None:
    if orinoco_main(["--root", str(root), "validate", "--no-cache"]) != 0:
        raise ConfigurationError("Composed metadata validation failed")


def stage(root: Path, plan: CandidatePlan) -> None:
    _require_clean_submitted_head(root, plan.metadata_base)
    destinations = [(change, _require_safe_worktree_path(root, change.path)) for change in plan.file_changes()]
    for change, path in destinations:
        if change.proposed is None:
            path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(change.proposed)
    validate(root)


def review_bundle(plan: CandidatePlan, repository: str, number: int, run: int, proposal: str) -> dict:
    return {
        "format": "orinoco-lite-curation-review-bundle-v1",
        "repository": repository, "pull_request": number, "workflow_run_id": run,
        "adapter": plan.adapter, "metadata_base_sha": plan.metadata_base,
        "proposal_sha": proposal, "source_coordinate": dict(plan.source_coordinate),
        "candidates": [{
            "pid": item.pid, "friendly_id": f"C{index + 1:03d}", "label": item.label,
            "source_namespace": item.source_namespace, "source_record_id": item.source_record_id,
            "record_path": item.record_repository_path,
            "paths": [change.path for change in item.file_changes()],
            "operation": item.operation.value, "blockers": list(item.blockers),
            "claim_sha256": item.claim_sha256,
        } for index, item in enumerate(plan.candidates)],
    }


def finalize(root: Path, plan: CandidatePlan, comment: dict, repository: str, number: int) -> None:
    matches = re.findall(r"```json\n([\s\S]*?)\n```", comment["body"])
    if len(matches) != 1 or "/curation submit" not in comment["body"]:
        raise ConfigurationError("The authenticated comment has no unique decision submission")
    submission = json.loads(matches[0])
    if (submission["repository"] != repository or submission["pull_request"] != number
            or submission["adapter"] != plan.adapter or submission["source_coordinate"] != dict(plan.source_coordinate)
            or submission["format"] != "orinoco-lite-curation-submission-v1"):
        raise ConfigurationError("The submission does not match the regenerated proposal")
    decisions = submission["decisions"]
    if len(decisions) != len(plan.candidates):
        raise ConfigurationError("Every candidate requires an explicit disposition")
    by_path = {item["record_path"]: item for item in decisions}
    if len(by_path) != len(decisions):
        raise ConfigurationError("Submission repeats a candidate")
    dispositions = {}
    for item in plan.candidates:
        decision = by_path.get(item.record_repository_path)
        if decision is None or decision["pid"] != item.pid or decision["operation"] != item.operation.value:
            raise ConfigurationError("Submission candidates differ from the regenerated plan")
        dispositions[item.pid] = decision["disposition"]
    cache_path = _require_safe_worktree_path(root, f"site-specific/curation-records/{plan.adapter}.yaml")
    cache = load_decision_cache(cache_path, adapter=plan.adapter)
    updated = update_decision_cache(
        cache, plan, dispositions, review_ref=f"github-comment:{comment['id']}",
        source_coordinate=plan.source_coordinate, reviewer=f"https://github.com/{comment['user']['login']}",
        reviewed_at=comment["created_at"], review_url=comment["html_url"],
    )
    finalize_candidate_plan(root, plan=plan, proposal_commit=submission["proposal_sha"],
                            submitted_head=submission["head_sha"], dispositions=dispositions)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(serialize_decision_cache(updated))
    validate(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("stage", "finalize"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--trusted-root", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--repository")
    parser.add_argument("--pull-request", type=int)
    parser.add_argument("--comment", type=Path)
    args = parser.parse_args()
    plan = build_plan(args.base_root.resolve(), args.trusted_root.resolve(), args.adapter, args.base)
    if args.operation == "stage":
        stage(args.root.resolve(), plan)
    elif args.operation == "finalize":
        finalize(args.root.resolve(), plan, json.loads(args.comment.read_text()), args.repository, args.pull_request)



if __name__ == "__main__":
    main()
