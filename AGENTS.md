# Agent instructions

- Read `docs/orinoco-lite-plan.md` before working and follow its current
  milestone and scope.
- Do not begin work listed as deferred or excluded from the current milestone.
- In `submodules/www-from-model`, keep `main` available to mirror
  `upstream/main`; make downstream changes on the branch named by the plan.
- Treat `submodules/dump-research-info` and
  `submodules/centerforopenneuroscience.org` as migration inputs, not production
  runtime dependencies.
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
