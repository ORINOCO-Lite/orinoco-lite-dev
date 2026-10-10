# Agent instructions

## Current direction

- Use one selected `www-from-model` source for Hugo, projection, and assets.
  Distributions bundle only the required rendering subset from the package gitlink and its exact nested dependencies; editable installs use the actual nested working checkout, including edits.
  Resolve Congo and other upstream dependencies through the dependency declarations and exact pins owned by that selected revision rather than repeating them in package or downstream configuration.
  The package owns generic source resolution, metadata, projection, and composition operations.
  Keep the template thin: it contains the Orinoco adaptation, Copier scaffold, workflows, and dependency locks, not a copied website.
- Git Annex is used for maintainer repinning and explicit upstream-site preparation.
  Package builds hydrate and verify required upstream Hugo assets.
  Fixed site builds use ordinary bundled files without an upstream Git/Annex checkout; editable builds hydrate required assets from their working source.
  `dev upstream import-from-www` may retrieve upstream site media with Annex and copy ordinary files into `site-specific/`; those media do not belong in the generic template.
  Upstream asset preparation uses Git Annex independently of the downstream media opt-in.
  Opted-in `site-specific` submodules may use Annex only for `assets/` and `static/`; builds copy verified content into ordinary output files.
  DataLad remains a downstream dependency for recording source-adapter run provenance; records and other structured inputs always remain in Git.
  DataLad operations in opted-in Annex submodules require the Annex executable even when saving ordinary Git records.
- Upstream website reproduction always uses downstream development mode with `.orinoco-lite/orinoco-lite-dev` tracked as a Git submodule.
  Import authored inputs and Annex media from its nested `www-from-model` checkout; ordinary downstream builds use bundled rendering resources without cloning upstream.
- Test unreleased package and template work together by applying a selected downstream's declared inputs to a fresh disposable template instance with `pixi run setup-upstream` when practical.
  Setup stops before projection and building; run those explicitly only when they are part of the requested validation.
  When multi-repository rendering remains uncertain, test the downstream pull-request head in a deploy preview with explicit full-SHA package and template candidates before releasing.
  An exact-SHA Netlify deploy preview may exercise an authenticated GitHub write only into its own open same-repository draft pull request after the service verifies GitHub's successful Netlify status for that exact head and origin.
  Use the real browser action and verify the resulting pull-request commit and trusted workflow.
  A downstream may select an official release, a release from its own fork, or an exact package commit from any suitable fork.
  An immutable Git commit is a sufficient reproducibility coordinate; do not require a central release or a separate release lock.
  For adopted dependency pins, use commits reachable from the source repository's maintained default branch or a retained release tag.
  Pull-request-only commits are temporary test candidates; replace them with retained commits before adoption because deleting a branch can remove their only durable reference.
  A user-owned `<github-user>/orinoco-lite-demo` may extend this into autonomous GitHub-workflow experimentation.
  Propose the downstream update to `ORINOCO-Lite/test-orinoco-downstream-website` for deliberate human review of its impact on downstream users.
- Keep the template's minimum package requirement separate from its exact package pin.
  Raise the minimum only when its adaptation or workflows require new functionality.
  Recreate downstream scaffolding around retained site inputs when that avoids compatibility or migration code.
- Prefer one source of truth.
  Do not create manifests, ledgers, or decision registers that restate repository configuration, locks, Git, or GitHub.
- Use commit identifiers where software requires them, such as dependency selections and concurrency checks.
  Do not require per-file origins or before-and-after coordinate inventories for ordinary work.
- Track each upstream mirror in Orinoco Lite with the branch selected by its parent's `.gitmodules` (or the authoritative default when none is declared) as the accepted upstream base, `latest-upstream` as the most recently observed upstream commit, and `orinoco-lite-diff` as the retained local commits on that base.
  An updater advances `latest-upstream` only.
  A reviewed repin rebases the local layer onto it, advances the accepted base, and pins the parent to the rebased layer or to that base when the layer is empty.
  Keep non-empty `latest-upstream` and `orinoco-lite-diff` comparisons into the accepted base branch as draft pull requests; do not merge them.
  Stage the corresponding [divergence report](docs/agents/submodule-divergence.md) when changing a selected dependency; existing local commit subjects are descriptive, not a validation gate.
  Delete superseded mirror branches after preserving active-purpose branches, including Git Annex branches.

## Data provenance

- Use `.agents/skills/datalad-provenance/SKILL.md` when designing or reviewing capture, ingestion, transformation, or rerun workflows.
  Distinguish recording a command from making its inputs and environment recoverable.

## Minimum machinery

- Across the package and template, CI installs the latest Pixi without a version pin; manifests require `>=0.76` without an upper bound.
  Keep the package development `pixi.lock` local and untracked; allow Pixi to resolve dependencies in development and engineering CI.
  Unset inherited `PIXI_LOCKED` in development shells.
  Generate and test release consumer locks with locked installation; do not restore Pixi pins to work around lock serialization changes.
- Use `.agents/skills/review-terminology/SKILL.md` before establishing or changing shared component or interface terminology, or when a term denotes different things across code, configuration, and guidance.
  Delegate its exploratory review to a sub-agent and use the returned recommendations to resolve naming before implementation depends on it.
- Inspect the selected upstream dependency's API or CLI before implementing functionality it may already provide, and use that functionality where applicable.
  Add only project-specific behavior around it.
  A parallel implementation requires a demonstrated gap, an explanation of why composition cannot address it, and explicit user agreement before implementation.
  Convenience or assumptions about upstream limitations are insufficient.
- Do not create manifests, registries, ledgers, inventories, compatibility layers, validation frameworks, or other durable machinery merely to prove, document, or test facts already established by Git, gitlinks, dependency declarations, locks, licenses, or generated outputs.
- New durable machinery is justified only when an operation requires it or when an existing authoritative source cannot represent the required state.
  Ease of testing, auditing, explanation, or agent completion is not sufficient justification.
- Use the smallest evidence appropriate to the risk.
  Prefer exercising an existing workflow and observing its output over introducing a new proof artifact or framework.
- Test externally observable behavior and important failure boundaries.
  Do not encode incidental repository structure, implementation details, or exhaustive acceptance-criterion restatements as compatibility contracts.
- Before adding durable machinery, identify what user-facing operation cannot work without it.
  If no such operation exists, do not add it.

## CLI feedback

- Use the APM-managed `unix-cli-design` skill when designing or reviewing CLI behavior.
  Restore it with `pixi run -e skills setup-skills` before starting an agent task; verify it with `pixi run -e skills audit-skills`.
  Edit external skills in their canonical source repositories, not their generated deployments.

- Keep help and argument parsing fast; defer expensive imports until execution.

- Use `orinoco_lite.progress.progress` around potentially slow, silent operations.
  It emits one flushed stderr note after one second; quick operations stay quiet and stdout remains available for results, JSON, and pipes.

- Name the current operation, including an upstream program when it owns the work.
  Report distinct stages at their owning boundary; avoid duplicate outer timers when inner stages already report progress.
  Flush immediate setup and server-ready messages to stderr.

## Documentation

- Place new documentation under `docs/agents/` unless another location is explicitly requested or approved by the user.

- Treat `docs/project-design.md` as the durable project design charter.
  Use it for intended design; keep implementation status and sequencing in active plans.

- Keep human-facing docs as concise orientation and CLIs unsurprising.
  Put option details and necessary caveats in CLI help; omit narration of obvious interactions.
  Revise existing guidance instead of appending notes for each change; Git and PRs carry change history.

- Keep `AGENTS.md`, `README.md`, and `docs/project-design.md` concise.

- In `docs/project-design.md`, name concrete actors, artifacts, and Git operations.
  Prefer terms such as commit, comment, pull request, and merge over abstract workflow language when they describe the actual action, and omit conclusions already evident from the flow.

- Follow the project `organize-project-docs` skill when placing or reorganizing documentation.

- Read the relevant active contract under `docs/agents/contract/` before changing metadata, source adapters, review, editing, authentication, or automated GitHub writes.

- Detailed plans, decisions, and reports belong under `docs/agents/` only while active.
  Retire them at milestone boundaries.

- Delete retired documents from the active tree after promoting any lasting guidance.
  Use Git when historical context is specifically needed.

## Boundaries

- Keep credentials, caches, downloads, browser output, and generated builds out of tracked state.
- Do not copy the German website or its dependency trees into an Orinoco Lite release.
  Required upstream functionality includes its required assets automatically.
  Materialize required assets as ordinary files in the build assembly and preserve their licenses and applicable notices.
- Use Git and Git Annex state as the provenance for materialized assets.
  Do not add redundant per-asset coordinates or provenance inventories when tooling can derive precise information from the selected repositories.
- Do not invent metadata semantics, identities, rights, or curation decisions.
- Do not resolve the production choices in `docs/agents/open-decisions.md` by inference.
- Do not preserve copied framework files, workflows, tests, configuration, or updater machinery in downstreams as compatibility requirements.
- Keep the package on the pinned upstream Things Schema and exact `dlthings:*` CURIE contract; do not silently substitute a generated, vendored, or newer schema.
- Treat `.agents/skills/` as the single canonical source for project-owned skills and edit those files directly.
  Do not add skill dependency infrastructure until this project consumes an independently maintained promoted skill.
- Use Conventional Commits, keep commit text near 80 columns, and run the relevant formatting and tests for changed files.
