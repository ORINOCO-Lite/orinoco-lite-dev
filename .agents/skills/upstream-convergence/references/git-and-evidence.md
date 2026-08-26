# Git, nested dependency, and evidence details

Read this reference when the update includes mirrored Git history, nested submodules, Git Annex, GitHub PR/ref writes, or coordinated acceptance evidence.

## Inspect before rewriting

For each repository, capture:

```bash
git status --short --branch
git remote -v
git rev-parse HEAD
git merge-base <accepted-tip> <authoritative-remote>/<branch>
git log --oneline --reverse <branch-point>..<accepted-tip>
```

Fetch the authoritative remote immediately before deciding what is current.
Inspect both fetch and push URLs; use the repository's required authenticated transport for writes.

The commit list after the branch point is the candidate owned layer, not proof of ownership by itself.
Check its diffs, repository history, and acceptance records.

## Rebase a thin layer

Keep a local safety ref to the discarded integration tip, then rebase a branch that starts at the accepted local tip:

```bash
git branch safety/pre-rebase-<date> <old-tip>
git switch -c <rebase-branch> <accepted-tip>
git rebase --onto <authoritative-remote>/<branch> <branch-point>
```

Resolve conflicts according to commit intent.
Do not select a whole side merely because it is labelled "ours" or "theirs" during a rebase.

Verify the topology explicitly:

```bash
git merge-base --is-ancestor <authoritative-remote>/<branch> HEAD
git log --oneline --graph --max-count=<bounded-count>
```

Rewriting a published branch requires explicit authorization.
Fetch its current remote value, then protect the update with an exact lease:

```bash
git push --force-with-lease=refs/heads/<branch>:<observed-old-oid> \
  <mirror-remote> HEAD:refs/heads/<branch>
```

Use a plain fast-forward push when the old ref is already an ancestor.
Never use an unqualified force push.

## Map nested rebased commits

A parent may have several historical gitlink updates into a child layer.
Build an old-to-new mapping from rebased commit order and intent.
During the parent rebase, resolve each gitlink conflict to the corresponding new child commit, then stage the gitlink and continue.
The final parent must point to a published child commit.

Test the child first, the parent second, and the top-level integration last.
Generated build directories should remain ignored; verify the source worktrees are clean after each build.

## Keep review topology linear

When the mirror default contains old local commits, a normal PR merge combines the old and rebased histories.
If the reviewed outcome is a replacement linear history and the user authorized rewriting it:

1. validate the rebased PR head;
2. observe the exact mirror-default OID;
3. update the default with a fast-forward or force-with-lease as appropriate;
4. verify the remote graph and PR state; and
5. update the parent gitlink only afterward.

Do not use a platform "rebase and merge" button if it would rewrite authoritative upstream commits.
Preserve upstream commit identities and replay only owned commits.

## Git Annex and cache-cold validation

Git content and Annex metadata are separate coordinates.
Advancing a repository gitlink can introduce new Annex keys even when the previously pinned Annex branch still hydrates every older path.

After updating an Annex-backed source:

- resolve and pin the authoritative `git-annex` ref independently;
- hydrate from the intended remote in a fresh clone;
- require `git annex find --not --in=here` to produce no paths;
- keep the build's Annex pin and any deployment-workflow pin synchronized; and
- add a focused invariant test when two current execution paths must share the same coordinate.

Git Annex can misinterpret a relative `core.worktree` when a submodule `.git` is a symlink.
Prefer verified absolute worktree context for Annex commands and restore the caller's local configuration carefully.
Treat a warm Annex cache as a diagnostic convenience, never acceptance evidence.

## Audit release pin surfaces

Do not assume a parent gitlink is the release coordinate.
Search source files, generated metadata, locks, workflows, and release inputs for every retired OID or version.
Common independent surfaces include:

- a submodule gitlink used for development;
- a direct VCS dependency in package metadata;
- one or more generated environment locks;
- hard-coded source assertions in deterministic assembly code;
- runtime compatibility ranges and source inventories;
- CI, deployment, and Annex refs; and
- consumer-template checksums or release coordinates.

Classify matches before changing them.
Historical acceptance evidence and prior immutable release specifications should keep their original coordinates.
Active build inputs and the new immutable release specification should converge on the new reviewed set.

Treat each repository's release sequence as independent.
An engine `rc5` may be consumed by a template `rc8`; choose the next unused version in the repository being released rather than copying another component's suffix.
Likewise, a reusable-workflow ref can intentionally remain at the last reviewed commit that changed that workflow.
Verify the file history and policy before moving it solely to make release numbers or commit dates look aligned.

Exercise the release workflow's deterministic path twice when practical.
Compare the package artifacts, editor shell and license inventory, schema closure, and runtime archive byte-for-byte.
Local determinism is useful evidence, but the hosted workflow remains authoritative when it fixes exact runner toolchains or produces attestations.

## Acceptance checklist

Record the smallest useful evidence in the project's existing authority:

- authoritative upstream head and branch for every changed component;
- old and accepted parent/nested gitlinks;
- owned commits replayed above upstream;
- mirror PRs and final default-branch OIDs;
- exact package, tool, runtime, assembly assertion, consumer-template, and Annex pins plus regenerated locks;
- focused leaf tests, parent builds, clean-clone builds, and cross-layer tests;
- hosted CI run and immutable release coordinates when applicable; and
- explicit unchanged components that were verified current.

Keep dated diagnostics in PRs or acceptance records.
Do not create a continuously maintained upstream inventory unless that artifact is itself requested and owned.
