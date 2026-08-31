---
name: develop-orinoco-lite
description: Develop and exercise unreleased Orinoco Lite engine or template changes against a selected downstream. Use for local engine-only, template-only, or combined candidate testing and for end-to-end curation, pull-request, CI, merge, deployment, and recovery work in the developer-owned demo. Use maintain-orinoco-site instead for ordinary maintenance of a released downstream.
---

# Develop Orinoco Lite

Exercise cross-repository changes through an ordinary downstream before release.
Keep generic fixes in the engine or template that owns them and keep site data and extensions in the downstream.

## Establish the live scope

1. Read the instructions, configuration, and relevant tests in every selected working tree.
2. Identify the downstream plus an engine candidate, a template candidate, or both.
Use `leej3/orinoco-lite-demo` as the Milestone 7 metadata, curation, source-evidence, and source-adapter baseline.
Inspect the organization fixture only for useful unique material rather than treating it as a second baseline.
3. Confirm `gh auth status`, the repository remotes, and the SSH push credential before a long end-to-end run.
Resolve missing access early.
4. Treat a release and organization-fixture merge as separate user-visible actions.

## Exercise the temporary downstream

Run the engineering task from the `orinoco-lite-dev` working tree:

```console
pixi run test-downstream-candidate \
  --downstream /path/to/orinoco-lite-demo \
  --engine /path/to/orinoco-lite-dev \
  --template /path/to/orinoco-lite-template \
  --mode quick
```

Select at least one of `--engine` and `--template`; omit the other for an engine-only or template-only candidate.
The task leaves the source downstream unchanged.
It stages a disposable candidate, renders the template working-tree bytes when selected, overlays the downstream's declared site-owned data and extensions, and exposes the selected engine working tree to downstream tasks.

Use quick mode while iterating.
Use `--mode full` before release or adoption.
Use repeated `--task` arguments only for focused diagnosis, and use `--output` or `--keep` when the staged tree needs inspection.
A failed candidate is retained for diagnosis; a successful automatic candidate is removed unless requested.

When a downstream failure exposes generic behavior, fix the owning engine or template working tree and repeat the candidate run.
Change the downstream only for its declared site data, policy, presentation, or executable extensions.

## Complete the developer-owned demo

For an explicitly requested end-to-end exercise in `leej3/orinoco-lite-demo`, project policy grants standing authority for the normal repository-local cycle:

- run the existing curation and finalization workflows;
- create and push exercise branches, open or update the pull request, and mark the agent's pull request ready for review;
- use the local full-run evidence to decide whether another pull-request CI run is useful, merge with a merge commit, and monitor the resulting default-branch validation and Pages deployment; and
- diagnose and recover CI or deployment failures without requesting separate approval for each of those steps.

Standing authority covers the mechanics of the exercise, not invented metadata or curation decisions.
Use supplied fixture decisions or retained reviewed state.
For curation behavior, follow `docs/github-curation-review.md` and `docs/source-adapters.md`.

## Recover quickly

Use GitHub's current state rather than polling by guesswork:

- watch pull-request checks with `gh pr checks --watch` and runs with `gh run watch <run-id> --exit-status`;
- inspect a failure with `gh run view <run-id> --log-failed` before choosing a recovery;
- rerun failed jobs only for a likely transient runner, browser, or service failure; and
- for a deterministic failure, repair the owning working tree, pass the local candidate again, push the repair, and watch the replacement checks.

The full local candidate run may replace duplicate pull-request CI when speed is more valuable than running the same checks twice.
After merge, verify default-branch validation, Pages, and the relevant routes.
If a merged demo change breaks validation or deployment, recover through a checked repair or revert pull request and verify the replacement deployment before reporting completion.

## Keep the organization fixture human-gated

`ORINOCO-Lite/test-orinoco-downstream-website` remains the organization-owned acceptance fixture.
When adoption is in scope, an agent may generate the update, test it locally, push its branch, open or update the pull request, and report the checks.
Leave approval and merge to the external human gate; the developer-demo standing authority does not cross into this repository.
