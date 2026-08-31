# Agent instructions

## Current direction

- Keep reusable website behavior in the engine or template.
Keep site content, configuration, and custom source-adapter code in downstream repositories.
- Test unreleased engine or template work locally with `pixi run test-downstream-candidate` when practical.
A user-owned `<github-user>/orinoco-lite-demo` may extend this into autonomous GitHub-workflow experimentation.
Propose the downstream update to `ORINOCO-Lite/test-orinoco-downstream-website` for deliberate human review of its impact on downstream users.
- Prefer one source of truth.
Do not create manifests, ledgers, or decision registers that restate repository configuration, locks, Git, or GitHub.
- Use commit identifiers where software requires them, such as dependency locks, release inputs, and concurrency checks.
Do not require per-file origins or before-and-after coordinate inventories for ordinary work.

## Documentation

- Keep `AGENTS.md`, `README.md`, and `docs/project-design.md` concise.
- Follow the project `organize-project-docs` skill when placing or reorganizing documentation.
- Detailed specifications, plans, decisions, and reports belong under `docs/agents/` only while active.
Retire them at milestone boundaries.
- Archived documents are historical context, not instructions or current policy.
Do not link to them from active instructions or indexes.

## Boundaries

- Keep credentials, caches, downloads, browser output, and generated builds out of tracked state.
- Do not invent metadata semantics, identities, rights, or curation decisions.
- Use Conventional Commits, keep commit text near 80 columns, and run the relevant formatting and tests for changed files.
