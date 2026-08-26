---
name: upstream-convergence
description: Deliberately update a fork, mirror, submodule stack, or thin integration layer to authoritative upstream heads while preserving linear upstream-plus-local history, advancing exact pins and locks, validating clean clones, and recording review or release evidence. Use for coordinated upstream repinning and fork convergence; do not use for an ordinary package-manager upgrade with no mirrored Git history.
---

# Upstream Convergence

Update the retained stack to reviewed current upstream coordinates without turning the integration repository into a second upstream or hiding local ownership in merge commits.

## Establish the boundary

- Read repository instructions and preservation rules before changing refs.
- Inventory only components used by a retained build, test, release, migration, or preservation path.
Do not revive unused dependencies merely because they are present.
- Distinguish the authoritative upstream remote from an account or organization mirror.
A mirror's default branch is not evidence of upstream currency.
- Record the current parent gitlink, direct pin, nested pin, lock, and local-layer tip before mutation.
Treat released or accepted checkpoints as immutable unless the user explicitly authorizes rewriting them.
- Confirm that the request authorizes external Git writes, pull requests, merges, releases, or force pushes before performing each class of mutation.

## Choose the history operation from the ownership shape

Classify each component after fetching its authoritative branch:

- **Already current:** keep the exact pin and record that no change was needed.
- **Pure mirror behind upstream:** fast-forward to the authoritative head.
- **Thin local layer:** rebase only the repository-owned commits onto the authoritative head.
- **Diverged or ambiguous ownership:** identify the branch point and local commit intent before rewriting.
Stop if authorship or durable-state ownership cannot be resolved safely.

Do not merge authoritative upstream into a thin layer.
The desired graph is the unaltered upstream history followed by the smallest necessary sequence of owned commits.
If an earlier integration branch contains a merge, preserve a local safety ref, rebuild the branch by rebasing the owned layer, validate it, and use `--force-with-lease` only when rewriting that branch is authorized.

For nested submodules, Annex-backed repositories, mirror default-branch updates, or GitHub review mechanics, read [references/git-and-evidence.md](references/git-and-evidence.md) before acting.

## Validate from the leaves upward

1. Test each rebased leaf component with its native locked build and focused tests.
2. Update nested gitlinks to the corresponding rebased commits, not to discarded merge tips.
3. Test each owning component, then advance its reviewed mirror ref.
4. Audit every independently interpreted pin surface: parent and nested gitlinks, direct VCS requirements, generated locks, build-time commit assertions, runtime source specifications, compatibility declarations, and CI or deploy pins.
Updating one surface does not update the others.
5. Reproduce at least one clean, non-recursive or otherwise cache-cold checkout.
A warm local object, package, or Annex cache is not evidence that a pin is complete.
6. Run the combined cross-layer checks appropriate to the changed paths.
Keep expected warnings separate from failures and record explicit fixture requirements for tests that cannot run locally.

When a clean clone fails, preserve fail-closed gates and find the missing coordinate or object.
Do not weaken completeness, integrity, or exact-version checks merely to match a warm worktree.

## Publish and record

- Prefer a review branch for each owned repository layer.
State the authoritative base, owned commits, validation, and whether history was rebased.
- A normal GitHub PR merge can recreate a merge topology when the mirror default still contains the old local commits.
After approval and checks, advance the reviewed default ref directly with an exact lease when that rewrite is authorized; verify how GitHub records the PR afterward.
- Update the parent only to commits reachable from the published reviewed refs.
- Record exact accepted gitlinks, nested heads, lock/runtime changes, PRs, CI runs, and release coordinates in the repository's existing acceptance surface.
Do not invent a mutable upstream-head inventory unless the user asks for one.
- If the update changes a released compatibility boundary, create a new immutable release source rather than editing an older release specification, then finish the aligned engine/runtime and consumer-template releases before declaring convergence complete.

Stop for clarification when a choice would change semantic behavior, provenance, review authority, protected history, repository custody, or production state.
