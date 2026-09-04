---
name: develop-orinoco-lite
description: Develop and exercise unreleased Orinoco Lite package or template changes against a selected downstream. Use for local package-only, template-only, or combined candidate testing and for autonomous end-to-end GitHub workflow experiments in a user-owned demo. Use maintain-orinoco-site instead for ordinary maintenance of a released downstream.
---

# Develop Orinoco Lite

Exercise package and template changes through a disposable content-only downstream before release.
Reuse the submodule-selected `www-from-model` presentation and projection source and resolve its dependencies through that revision's normal dependency mechanism.
Keep generic source resolution, metadata, projection, and composition in the package; keep the Orinoco adaptation, bounded materialized presentation overlay, and downstream scaffold in the template; keep declarative site inputs under `site-specific/`; and keep site-specific executable metadata adapters under `extensions/`.

## Establish the live scope

1. Read the instructions, dependency state, active milestone, and relevant tests in every selected working tree.
   Git Annex is permitted only in the engineering repinning path.
   Downstream source-adapter tasks use DataLad for commit provenance without requiring Git Annex.
2. Identify the package and template candidates and any downstream inputs to inject.
   Local candidate testing is the default.
   When useful, extend it into less constrained GitHub-workflow experimentation in a user-owned `<github-user>/orinoco-lite-demo`, where mandatory human review does not slow the exercise.
   Use `ORINOCO-Lite/test-orinoco-downstream-website` as the human-gated reference downstream that exposes developers to the frequency and severity of updates experienced by downstream users.
3. Confirm `gh auth status`, the repository remotes, and the SSH push credential before a long end-to-end run.
   Resolve missing access early.
4. Treat a release and reference-downstream merge as separate gates.
   Permission to test a working tree locally does not itself authorize either one.

## Exercise the temporary downstream

Run the engineering task from the `orinoco-lite-dev` working tree.
It must materialize the selected template afresh and apply only the selected downstream's declared `site-specific/` inputs and `extensions/` metadata adapters:

```console
pixi run test-downstream-candidate \
  --downstream /path/to/orinoco-lite-demo \
  --package /path/to/orinoco-lite-dev \
  --template /path/to/orinoco-lite-template \
  --mode quick
```

Select at least one of `--package` and `--template`; omit the other for a package-only or template-only candidate.
The task leaves the source downstream unchanged and must not copy its framework files, workflows, framework tests, or duplicated template configuration.

Use quick mode while iterating.
Use `--mode full` before release or adoption.
Use repeated `--task` arguments only for focused diagnosis, and use `--output` or `--keep` when the staged tree needs inspection.
A failed candidate is retained for diagnosis; a successful automatic candidate is removed unless requested.

When a candidate failure exposes generic source resolution, metadata, projection, or composition behavior, fix the package.
When it exposes an Orinoco adaptation or scaffold, fix the template.
When required Annex-backed upstream content is missing, repair the maintainer dependency-closure hydration and materialization path; do not remove upstream functionality or add Git Annex to the downstream.
Change downstream inputs only for site data, policy, supported presentation choices or overrides, or executable metadata adapters.

## Complete the user-owned demo

For an explicitly requested end-to-end exercise in a user-owned `<github-user>/orinoco-lite-demo`, project policy grants standing authority for the normal repository-local cycle:

- run the existing curation and finalization workflows;
- create and push exercise branches, open or update the pull request, and mark the agent's pull request ready for review;
- use the local full-run evidence to decide whether another pull-request CI run is useful, merge with a merge commit, and monitor the resulting default-branch validation and Pages deployment; and
- diagnose and recover CI or deployment failures without requesting separate approval for each of those steps.

Standing authority covers the mechanics of the exercise, not invented metadata or curation decisions.
Use supplied fixture decisions or retained reviewed state.
Follow `docs/agents/contract/github-curation-review.md` and `docs/agents/contract/source-adapters.md` for the current curation contract rather than restating it in this skill.

## Recover quickly

Use GitHub's current state rather than polling by guesswork:

- watch pull-request checks with `gh pr checks --watch` and runs with `gh run watch <run-id> --exit-status`;
- inspect a failure with `gh run view <run-id> --log-failed` before choosing a recovery;
- rerun failed jobs only when the evidence indicates a transient runner, browser, or service failure; and
- for a deterministic failure, repair the owning working tree, pass the local candidate again, push the repair, and watch the replacement checks.

The full local candidate run may replace duplicate pull-request CI when speed is more valuable than a second copy of the same evidence.
Exercise editor and popup behavior in the browser against a local transport that structured-clones the proposal and simulates the ready, started, and result messages.
Create scratch exercise pull requests with `gh`, not through the browser.
A live authenticated popup-to-pull-request run is a separate manual acceptance check and must not block the normal autonomous development loop.
Merge a curation pull request according to the repository's current policy.
After merge, verify the exact default-branch validation and Pages runs and the relevant deployed routes.
If a merged demo change breaks validation or deployment, recover through a checked repair or revert pull request and verify the replacement deployment before reporting completion.

## Keep the reference downstream human-gated

`ORINOCO-Lite/test-orinoco-downstream-website` is the organization-owned reference downstream.
When adoption is in scope, an agent may generate the update, test it locally, push its branch, open or update the pull request, and report the exact candidate and check evidence.
Leave approval and merge to the human gate; the developer-demo standing authority does not cross into this repository.
