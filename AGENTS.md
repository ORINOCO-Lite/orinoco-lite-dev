# Agent instructions

- Read `docs/orinoco-lite-plan.md`, `docs/clean-migration.md`, `docs/full-con-migration.md`, `docs/milestone-2-acceptance.md`, `docs/milestone-3.md`, and `docs/milestone-4.md` before working and follow the active milestone.
- Do not begin work listed as deferred or excluded from the current milestone.
- The active effort is Milestone 4 on the parent `codex/milestone-4` branch.
- Implement Milestone 4 only in isolated engineering, release, template, and test-consumer worktrees.
Treat `centerforopenneuroscience.org` and its remotes as read-only extraction evidence: do not modify files, branches, refs, settings, workflows, deployments, or remote state in that repository.
- The Milestone 4 test consumer must contain the complete accepted Milestone 3 CON profile and test contract.
Representative records remain smoke assertions and must never become a content-selection mechanism.
- The downstream contract is one ordinary Git repository with no submodules or gitlinks.
Keep upstream rebases, component coordination, comparison fixtures, and preservation history internal to the engineering workspace.
- Milestone 4 may create and publish an Orinoco Lite package/release, a template repository, and `test-orinoco-downstream-website`; configure their GitHub Actions permissions and project Pages; and exercise reviewed automated update pull requests.
It must not change the real CON repository, its deployment, default branch, Pages configuration, DNS, custom domain, or production site.
- Implement site metadata on the successor worktree's `codex/milestone-3` branch, retaining reviewed upstream website commit `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8` until a later reviewed rebase.
- Preserve the accepted parent and site `codex/clean-migration` branches as immutable checkpoints.
Do not amend, rebase, or move them.
- Preserve the accepted parent and site `codex/full-con-migration` branches as immutable Milestone 2 checkpoints.
Do not amend, rebase, or move them.
- Direct upstream ancestry is an intentional exception only for the accepted clean-migration site branch and its full-migration successor.
Do not apply it to `master`, `legacy-site`, `orinoco-lite`, or another CON branch.
- Preserve the legacy CON history, preservation refs, and completed `orinoco-lite` effort unchanged.
- Keep `submodules/www-from-model` `main` available to mirror `upstream/main`.
- On the successor site branch, use ordinary focused commits for reviewed hand-authored profile and content batches.
Keep one terminal, regenerable projection commit containing generated outputs only; replace or amend it after changes instead of committing generated churn into content batches.
- Keep the CON profile, collections, canonical homepage root, references, and projection isolated from the upstream snapshot.
- Make reviewed YAML in the clean site tree the sole canonical content source.
Milestone 3 explicitly permits repeatable, read-only ingestion from the public CON Zotero API through `submodules/dump-research-info`.
Keep source capture, transformation, review, and site promotion separate, and do not turn that submodule into a production runtime dependency.
- Use the pinned source Things Schema and the `dlthings:*` CURIE contract in `docs/explaining-schema-issues.md`.
Do not use the vendored resolved schema, LinkML trial, or later Things Schemas candidates.
- Do not require a continuously running metadata service for builds or deployed sites.
- Milestone 3 may push exact successor commits to the existing GitHub mirrors, publish one parent `codex/milestone-3` branch, open one draft parent PR against `con/orinoco-lite-dev:main`, and configure that repository's GitHub Pages project preview.
Do not open submodule PRs, change DNS or a custom domain, replace production, publish credentials, or write to Zotero or a public metadata service.
- Hosted editing in this milestone is static and credential-free: it may load public committed metadata and download a review bundle or patch, but it must not create a GitHub token flow, write directly to GitHub, or require a persistent metadata service.
- Record every unresolved human decision in `docs/milestone-3-decisions.md`; do not silently infer publication identity, collection policy, authorship, venue, licensing, or production-cutover semantics.
- Update the parent site gitlink only after the complete local acceptance and rebase checks pass.
Keep credentials outside every repository.

## User preferences

- Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for every commit subject and body.
- Keep commit subjects and body lines wrapped to approximately 80 columns; avoid long unwrapped commit-message lines.
- Use the Snapper pre-commit hook to auto-format documentation and minimize diffs when editing prose.

## Commit co-authorship

Every commit authored by Codex must include:

```text
Co-Authored-By: <tool name> <tool version> / <model name> <model version> <codex@openai.com>
```

Discover both versions from the active tool and session.
Do not guess.
