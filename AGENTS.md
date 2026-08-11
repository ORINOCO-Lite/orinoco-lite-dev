# Agent instructions

- Read `docs/orinoco-lite-plan.md`, `docs/clean-migration.md`, and `docs/full-con-migration.md` before working and follow the active milestone.
- Do not begin work listed as deferred or excluded from the current milestone.
- The active effort is the local-only full CON migration on the parent `codex/full-con-migration` branch.
- Implement the site in `submodules/centerforopenneuroscience.org` on its `codex/full-con-migration` branch, rebased onto reviewed upstream website commit `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8`.
- Preserve the accepted parent and site `codex/clean-migration` branches as immutable checkpoints.
Do not amend, rebase, or move them.
- Direct upstream ancestry is an intentional exception only for the accepted clean-migration site branch and its full-migration successor.
Do not apply it to `master`, `legacy-site`, `orinoco-lite`, or another CON branch.
- Preserve the legacy CON history, preservation refs, and completed `orinoco-lite` effort unchanged.
- Keep `submodules/www-from-model` `main` available to mirror `upstream/main`.
- On the successor site branch, use ordinary focused commits for reviewed hand-authored profile and content batches.
Keep one terminal, regenerable projection commit containing generated outputs only; replace or amend it after changes instead of committing generated churn into content batches.
- Keep the CON profile, collections, canonical homepage root, references, and projection isolated from the upstream snapshot.
- Make reviewed YAML in the clean site tree the sole canonical content source.
Treat legacy website history and `submodules/dump-research-info` only as migration evidence, never as normal build-time dependencies.
- Use the pinned source Things Schema and the `dlthings:*` CURIE contract in `docs/explaining-schema-issues.md`.
Do not use the vendored resolved schema, LinkML trial, or later Things Schemas candidates.
- Do not require a continuously running metadata service for builds or deployed sites.
- Keep this effort local-only.
Do not push, publish Pages, change DNS, alter production, or update any remote configuration.
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
