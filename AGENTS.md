# Agent instructions

- Read `docs/orinoco-lite-plan.md` and `docs/clean-migration.md` before working and follow their active scope.
- Do not begin work listed as deferred or excluded from the current milestone.
- The active effort is the local-only clean migration on the parent `codex/clean-migration` branch.
- Implement the site in `submodules/centerforopenneuroscience.org` on its `codex/clean-migration` branch, based directly on upstream website commit `5b401e0c478a4409442b3a8a285bd3efd5d30e05`.
- Direct upstream ancestry is an intentional exception only for that site branch.
Do not apply it to `master`, `legacy-site`, `orinoco-lite`, or any other CON branch.
- Preserve the legacy CON history, preservation refs, and completed `orinoco-lite` effort unchanged.
- Keep `submodules/www-from-model` `main` available to mirror `upstream/main`.
- Keep exactly two CON site commits above the reviewed upstream base: one build-profile contract commit and one content-and-projection snapshot commit.
Amend those commits rather than accumulating cleanup commits.
- Keep the clean-migration profile, collections, canonical homepage root, references, and projection isolated from the upstream snapshot.
- Use the pinned source Things Schema and the `dlthings:*` CURIE contract in `docs/explaining-schema-issues.md`.
Do not use the vendored resolved schema, LinkML trial, or later Things Schemas candidates.
- Treat `submodules/dump-research-info` as a migration input, not a production runtime dependency.
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
