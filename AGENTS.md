# Agent instructions

- Read `docs/orinoco-lite-plan.md` before working and follow its current
  milestone and scope.
- Do not begin work listed as deferred or excluded from the current milestone.
- Implement the CON site in `submodules/centerforopenneuroscience.org` on the
  `orinoco-lite` branch, which descends from the existing CON `master` branch.
  Preserve the legacy branch and tag.
- Keep `submodules/www-from-model` `main` available to mirror `upstream/main`.
- Adopt upstream code selectively; do not merge or graft the complete
  `www-from-model` history into the CON branch.
- Treat `submodules/dump-research-info` as a migration input, not a production
  runtime dependency.
- Do not require a continuously running metadata service for builds or deployed
  sites.
- Update parent submodule pins deliberately and keep credentials outside every
  repository.

## User preferences

- Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)
  for every commit subject and body.
- Keep commit messages, logs, and documentation prose wrapped to approximately
  80 columns; avoid long unwrapped lines.

## Commit co-authorship

Every commit authored by Codex must include:

```text
Co-Authored-By: <tool name> <tool version> / <model name> <model version> <codex@openai.com>
```

Discover both versions from the active tool and session. Do not guess.
