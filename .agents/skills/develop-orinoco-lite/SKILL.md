---
name: develop-orinoco-lite
description: Develop and exercise Orinoco Lite package or template changes against a selected downstream. Use for local package-only, template-only, or combined candidate testing and for autonomous end-to-end GitHub workflow experiments in a user-owned demo. Use maintain-orinoco-site instead for ordinary downstream maintenance.
---

# Develop Orinoco Lite

Exercise package and template changes through a disposable downstream before adoption.
When more than one repository changes, use a downstream deploy preview with exact candidate package and template commits before adopting either component.
An exact-SHA Netlify preview may write only to its own open same-repository draft pull request after the service verifies GitHub's successful Netlify status for that exact head and origin.
Do not cut a release merely to discover whether a package or template commit composes with a downstream.
Reuse the submodule-selected `www-from-model` Hugo and projection source and resolve its dependencies through that revision's normal dependency mechanism.
Keep generic source resolution, metadata, projection, and composition in the package; keep the Orinoco adaptation, bounded materialized Hugo asset overlay, and downstream scaffold in the template; keep declarative site inputs under `site-specific/`; and keep site-specific executable metadata adapters under `extensions/`.

## Establish the live scope

1. Read the instructions, dependency state, active milestone, and relevant tests in every selected working tree.
   Git Annex is permitted for engineering repinning and explicit upstream-site media retrieval.
   Site-specific media go into downstream site inputs, not the generic template.
   Downstream source-adapter tasks use DataLad for commit provenance without requiring Git Annex.
2. Identify the package and template candidates and any downstream inputs to inject.
   Local candidate testing is the default.
   When useful, extend it into less constrained GitHub-workflow experimentation in a user-owned `<github-user>/orinoco-lite-demo`, where mandatory human review does not slow the exercise.
   Use `ORINOCO-Lite/test-orinoco-downstream-website` as the human-gated reference downstream that exposes developers to the frequency and severity of updates experienced by downstream users.
   A deploy preview builds the downstream pull request head plus the explicit full-SHA package and, when relevant, template candidates.
   A branch name is not an adequate candidate coordinate.
   A downstream may select an official release, a release from its own fork, or an exact commit from any suitable fork.
   Prefer a full Git commit while iterating.
   Before adopting a candidate, pin the merged commit reachable from the source repository's maintained default branch, or a commit retained by a release tag.
   A fetchable pull-request-only commit is suitable for temporary tests, but its SHA alone does not guarantee continued availability after branch deletion.
   Do not require a central release or a separate release lock.
   Use the real browser proposal action and inspect its pull-request result; a successful build alone is not evidence that the authenticated path works.
3. Confirm `gh auth status`, the repository remotes, and the SSH push credential before a long end-to-end run.
   Resolve missing access early.
4. Treat publishing a release and merging a reference-downstream change as separate optional gates.
   Permission to test a working tree locally does not itself authorize either one.

## Exercise a local downstream

Use the engineering `setup-upstream` task to test candidates in a fresh downstream.
Ordinary setup keeps the selected template's package declaration and lock; coordinated changes merge the package first, then update and test the template's package pin before merging the template.
Consult its `--help` and the installed CLI help for input selection and individual stages.
Do not push a candidate as a side effect of setup or overwrite a developer's downstream.

For software comparisons, retain the input data while changing the package selection.
For historical replay, restore the desired package, input, and subdataset states before starting Pixi: DataLad does not replace a running environment or restore subdataset worktrees through `rerun --onto`.

Use ordinary `orinoco-lite validate`, `build`, and `serve` commands when requested.
The package owns projection and validation sequencing.
Use `pixi run pytest` and pytest selection flags for automated tests, rather than separate quick/full task wrappers.
When setup-only validation is requested, do not run projection or a website build.
When testing package, template, or upstream integration, fix generic behavior in the package, Orinoco adaptation in the template, and site inputs only for actual site data or policy changes.

## Complete the user-owned demo

For an explicitly requested end-to-end exercise in a user-owned `<github-user>/orinoco-lite-demo`, project policy grants standing authority for the normal repository-local cycle:

- run the existing curation and finalization workflows;
- create and push exercise branches, open or update the pull request, and mark the agent's pull request ready for review;
- use the local full-run evidence to decide whether another pull-request CI run is useful, merge with a merge commit, and monitor the resulting default-branch validation and Pages deployment; and
- diagnose and recover CI or deployment failures without requesting separate approval for each of those steps.

Standing authority covers the mechanics of the exercise, not invented metadata or curation decisions.
Use supplied fixture decisions or retained reviewed state.
Follow `docs/agents/contract/github-curation-review.md` and `docs/agents/contract/source-adapters.md` for the current curation contract rather than restating it in this skill.

When package, template, browser, or service behavior affects the GitHub proposal path:

- build the demo pull-request head with explicit full-SHA package and template candidates and its exact pull-request number;
- use the successful Netlify deploy preview GitHub recorded for that exact head;
- when the backend changed, deploy the matching backend candidate and retain the previous deployment coordinate for rollback;
- navigate the editor in a real browser, make a harmless fixture edit, and click the actual **Propose via GitHub** action;
- verify the browser result, updated draft pull request, bundle-materialization commit, and downstream checks; and
- restore or close the exercise pull request after the test.

Record the exact deployment refs before changing them and use lease-protected updates when restoring a deployment branch.
Standalone proposal creation remains restricted to the configured canonical editor origin.

## Recover quickly

Use GitHub's current state rather than polling by guesswork:

- watch pull-request checks with `gh pr checks --watch` and runs with `gh run watch <run-id> --exit-status`;
- inspect a failure with `gh run view <run-id> --log-failed` before choosing a recovery;
- rerun failed jobs only when the evidence indicates a transient runner, browser, or service failure; and
- for a deterministic failure, repair the owning working tree, pass the local candidate again, push the repair, and watch the replacement checks.

The full local candidate run may replace duplicate pull-request CI when speed is more valuable than a second copy of the same evidence.
Exercise editor and popup protocol details against a local transport that structured-clones the proposal and simulates the ready, started, and result messages.
Create routine scratch exercise pull requests with `gh`.
When the popup-to-pull-request behavior itself is under test, use the real browser action from the exact verified preview and inspect the pull request it updates.
Merge a curation pull request according to the repository's current policy.
After merge, verify the exact default-branch validation and Pages runs and the relevant deployed routes.
If a merged demo change breaks validation or deployment, recover through a checked repair or revert pull request and verify the replacement deployment before reporting completion.

## Keep the reference downstream human-gated

`ORINOCO-Lite/test-orinoco-downstream-website` is the organization-owned reference downstream.
When adoption is in scope, an agent may generate the update, test it locally, push its branch, open or update the pull request, and report the exact candidate and check evidence.
Leave approval and merge to the human gate; the developer-demo standing authority does not cross into this repository.
