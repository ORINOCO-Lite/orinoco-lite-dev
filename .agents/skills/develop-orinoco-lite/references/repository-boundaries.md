# Repository boundaries

Confirm the active repositories' own instructions because names, release
coordinates, and ownership details change. Apply these role boundaries unless a
reviewed local contract supersedes them.

## Engineering workspace

Own engine implementation, runtime assembly, component integration, reusable
validation and CI, immutable release evidence, and cross-layer acceptance.
Keep upstream-rebase and component coordination history here. Do not turn an
engineering checkout into downstream canonical content.

## Template repository

Own Copier source, rendered template output, framework ownership classes,
upgrade mechanics, and framework-supplied downstream skills. Edit the canonical
template source, run its renderer, and test source/render parity. Do not hand-edit
the staged render as an independent authority.

Treat a template release and a consumer update as separate human-reviewed
changes. A framework agent may prepare a branch and pull request; it must not
approve, merge, or deploy pull-request code.

## Downstream consumer

Own accepted metadata, site policy, presentation overrides, site assets,
site-owned source adapters, curation decisions, and consumer acceptance. Follow
the local ownership manifest when a path's apparent role is ambiguous.

Use consumer locks and release coordinates for ordinary operation. Remote
latest is advisory until a reviewed framework update advances those coordinates.

## Real or production site

Treat a real site and its remotes as read-only evidence unless the user and its
local policy explicitly authorize a scoped production change. Never reuse it as
a worktree, test target, or convenient place to stage engineering changes.

Preserve immutable acceptance and migration branches. Do not rebase, amend, or
move them while doing unrelated work.

## Cross-repository changes

1. Use an isolated branch and worktree in each repository being changed.
2. Identify which repository owns every source file and generated counterpart.
3. Keep release, template-update, and consumer-content review coordinates
   distinct.
4. Preserve site-owned content across template updates and test ownership
   conflicts explicitly.
5. Record exact immutable coordinates when compatibility spans repositories.

Do not install a project skill directly into a downstream path that the template
owns. Change the template source and use its normal release and update path.

## Human decisions

Read the current human-review queue and the source-specific decision register
before materializing ambiguous metadata. Do not silently resolve an open item.
When a human resolves one, update both authorities in the same reviewed change
when the local contract requires it.

Distinguish:

- evidence gathered by the agent;
- a recommendation with tradeoffs;
- the human's explicit choice;
- the machine application of that recorded choice.

Successful execution or schema validation proves none of the human choices.
