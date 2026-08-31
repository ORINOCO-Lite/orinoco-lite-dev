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
- Read the relevant active contract under `docs/agents/contract/` before changing metadata, source adapters, review, editing, or authentication behavior.
- Detailed plans, decisions, and reports belong under `docs/agents/` only while active.
Retire them at milestone boundaries.
- Delete retired documents from the active tree after promoting any lasting guidance.
Use Git when historical context is specifically needed.

## Boundaries

- Keep credentials, caches, downloads, browser output, and generated builds out of tracked state.
- Do not invent metadata semantics, identities, rights, or curation decisions.
- Stop for clarification when ambiguity would change metadata semantics, review authority, or durable state.
- Keep the real CON site read-only unless the user explicitly includes it, and do not resolve the production choices in `docs/agents/open-decisions.md` by inference.
- Keep the engine on the pinned upstream Things Schema and exact `dlthings:*` CURIE contract; do not silently substitute a generated, vendored, or newer schema.
- Treat `.agents/skills/` as the single canonical source for project-owned skills and edit those files directly.
Do not add skill dependency infrastructure until this project consumes an independently maintained promoted skill.
- Use Conventional Commits, keep commit text near 80 columns, and run the relevant formatting and tests for changed files.
