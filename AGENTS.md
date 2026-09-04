# Agent instructions

## Current direction

- Reuse the exact German `www-from-model` revision selected by the controlled submodule gitlink as the presentation and projection source.
  Resolve Congo and other upstream dependencies through the dependency declarations and exact pins owned by that selected revision rather than repeating them in package or downstream configuration.
  The package owns generic source resolution, metadata, projection, and composition operations.
  Keep the template thin: it contains the Orinoco adaptation, bounded materialized presentation assets, Copier scaffold, workflows, and dependency locks, not a copied website.
- Git Annex is maintainer-only repinning tooling.
  It may hydrate and verify Annex-backed content required by the selected upstream functionality before ordinary files are copied into the licensed template overlay.
  Released package and template tasks and downstream website builds must not invoke or depend on Git Annex.
  DataLad remains a downstream dependency for recording source-adapter run provenance; correctly configured downstream repositories keep those records in Git without requiring Git Annex.
- Test unreleased package and template work together by applying a selected downstream's declared inputs to a fresh disposable template instance with `pixi run test-downstream-candidate` when practical.
  A user-owned `<github-user>/orinoco-lite-demo` may extend this into autonomous GitHub-workflow experimentation.
  Propose the downstream update to `ORINOCO-Lite/test-orinoco-downstream-website` for deliberate human review of its impact on downstream users.
- Prefer one source of truth.
  Do not create manifests, ledgers, or decision registers that restate repository configuration, locks, Git, or GitHub.
- Use commit identifiers where software requires them, such as dependency locks, release inputs, and concurrency checks.
  Do not require per-file origins or before-and-after coordinate inventories for ordinary work.

## Minimum machinery

- Do not create manifests, registries, ledgers, inventories, compatibility layers, validation frameworks, or other durable machinery merely to prove, document, or test facts already established by Git, gitlinks, dependency declarations, locks, licenses, or generated outputs.
- New durable machinery is justified only when an operation requires it or when an existing authoritative source cannot represent the required state.
  Ease of testing, auditing, explanation, or agent completion is not sufficient justification.
- Use the smallest evidence appropriate to the risk.
  Prefer exercising an existing workflow and observing its output over introducing a new proof artifact or framework.
- Test externally observable behavior and important failure boundaries.
  Do not encode incidental repository structure, implementation details, or exhaustive acceptance-criterion restatements as compatibility contracts.
- Before adding durable machinery, identify what user-facing operation cannot work without it.
  If no such operation exists, do not add it.

## Documentation

- Treat `docs/project-design.md` as the durable project design charter.
  Use it for intended design; keep implementation status and sequencing in active plans.
- Keep `AGENTS.md`, `README.md`, and `docs/project-design.md` concise.
- In `docs/project-design.md`, name concrete actors, artifacts, and Git operations.
  Prefer terms such as commit, comment, pull request, and merge over abstract workflow language when they describe the actual action, and omit conclusions already evident from the flow.
- Follow the project `organize-project-docs` skill when placing or reorganizing documentation.
- Read the relevant active contract under `docs/agents/contract/` before changing metadata, source adapters, review, editing, or authentication behavior.
- Detailed plans, decisions, and reports belong under `docs/agents/` only while active.
  Retire them at milestone boundaries.
- Delete retired documents from the active tree after promoting any lasting guidance.
  Use Git when historical context is specifically needed.

## Boundaries

- Keep credentials, caches, downloads, browser output, and generated builds out of tracked state.
- Do not copy the German website or its dependency trees into an Orinoco Lite release.
  Required upstream functionality includes its required assets automatically.
  Materialize those assets as ordinary files only in a bounded template overlay that carries a license and applicable notices.
- Use Git and Git Annex state as the provenance for materialized assets.
  Do not add redundant per-asset coordinates or provenance inventories when tooling can derive precise information from the selected repositories.
- Do not invent metadata semantics, identities, rights, or curation decisions.
- Do not resolve the production choices in `docs/agents/open-decisions.md` by inference.
- Do not preserve copied framework files, workflows, tests, configuration, or updater machinery in downstreams as compatibility requirements.
- Keep the package on the pinned upstream Things Schema and exact `dlthings:*` CURIE contract; do not silently substitute a generated, vendored, or newer schema.
- Treat `.agents/skills/` as the single canonical source for project-owned skills and edit those files directly.
  Do not add skill dependency infrastructure until this project consumes an independently maintained promoted skill.
- Use Conventional Commits, keep commit text near 80 columns, and run the relevant formatting and tests for changed files.
