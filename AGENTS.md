# Agent instructions

## Current work

- The active effort is Milestone 4 on `codex/milestone-4`.
- Read `README.md`, `docs/milestone-4.md`, `docs/milestone-4-decisions.md`, and `docs/human-review-decisions.md` before changing current architecture or acceptance documentation.
- Read Milestone 1–3 plans and acceptance records only when their derivation or preserved evidence is relevant.
Their old operating commands and branch descriptions are not the downstream interface.
- Do not silently infer an answer to an open human decision.
Record resolutions in `docs/human-review-decisions.md` and the corresponding source decision register in the same reviewed change.
- Do not begin work explicitly deferred from Milestone 4 unless the user expands scope.

## Repository boundaries

- This repository owns engineering integration, the `orinoco-lite` engine, runtime assembly, immutable release evidence, reusable CI, and cross-layer acceptance.
- `con/orinoco-lite-template` owns Copier source, generated template output, framework ownership, and update mechanics.
- `con/test-orinoco-downstream-website` owns the complete accepted content, site policy, presentation overrides, provenance, and consumer acceptance.
- A supported downstream is one ordinary Git repository with no submodules or gitlinks.
Keep component coordination and upstream-rebase history inside the engineering workspace.
- The test consumer contains all accepted Milestone 3 content and the complete test contract.
Representative records are smoke checks, never a selection mechanism.

## Real-site and preservation boundary

- Treat `centerforopenneuroscience.org` and its remotes as read-only evidence.
Do not modify its files, index, refs, branches, remotes, settings, workflows, Pages configuration, deployment, DNS, custom domain, or production site.
- Preserve the accepted parent and site `codex/clean-migration` branches as immutable checkpoints.
Do not amend, rebase, or move them.
- Preserve the accepted parent and site `codex/full-con-migration` branches as immutable Milestone 2 checkpoints.
Do not amend, rebase, or move them.
- Preserve legacy CON history, preservation refs, and the completed historical `orinoco-lite` effort.
- Direct upstream ancestry was a reviewed exception for the accepted migration branches.
Do not apply it to unrelated branches.
- Keep `submodules/www-from-model` `main` available to mirror `upstream/main`.

## Content and runtime contracts

- Reviewed YAML is the sole canonical metadata source.
Zotero ingestion remains repeatable, read-only source evidence and never a normal production runtime dependency.
- Keep source capture, transformation, human review, and site promotion distinct.
Do not write to Zotero or invent identities, publication semantics, venues, topics, licensing, asset custody, or cutover policy.
- Use the pinned source Things Schema and exact `dlthings:*` CURIE contract in `docs/explaining-schema-issues.md`.
Do not substitute the vendored resolved schema, an unreviewed LinkML trial, or a later schema candidate.
- Do not require a continuously running metadata service for static validation, builds, preview, Pages, or review-bundle editing.
- Keep credentials, tokens, caches, stores, downloaded assets, browser output, and generated build artifacts outside tracked repository state.

## Change and publication rules

- Work in isolated engineering, template, and consumer worktrees appropriate to the repository being changed.
Do not use the real site as a worktree target.
- Framework updates may create a branch and pull request but never approve or merge themselves or deploy pull-request code to the shared Pages environment.
- Preserve exact immutable release coordinates, ownership classifications, site-owned before/after hashes, and rollback evidence.
- Update the engineering acceptance record and pull-request summary when hosted state changes materially; do not leave superseded review coordinates as the current entry point.

## User preferences

- Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for every commit subject and body.
- Keep commit subjects and body lines wrapped to approximately 80 columns.
- Use the Snapper pre-commit hook to format prose and minimize documentation diffs.

## Commit co-authorship

Every Codex-authored commit must include:

```text
Co-Authored-By: <tool name> <tool version> / <model name> <model version> <codex@openai.com>
```

Discover both versions from the active tool and session immediately before the commit.
Do not guess.
