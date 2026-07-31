# Agent instructions

- Read `docs/orinoco-lite-plan.md` before working and follow its current
  milestone and scope.
- Do not begin work listed as deferred or excluded from the current milestone.
- Implement the CON site in `submodules/centerforopenneuroscience.org` on the
  `orinoco-lite` branch. Preserve its legacy branch and tag.
- Keep `submodules/www-from-model` `main` available to mirror `upstream/main`.
- Treat `submodules/dump-research-info` as a migration input, not a production
  runtime dependency.
- Do not require a continuously running metadata service for builds or deployed
  sites.
- Update parent submodule pins deliberately and keep credentials outside every
  repository.

## Commit co-authorship

Every commit authored by Codex must include:

```text
Co-Authored-By: <tool name> <tool version> / <model name> <model version> <codex@openai.com>
```

Discover both versions from the active tool and session. Do not guess.
