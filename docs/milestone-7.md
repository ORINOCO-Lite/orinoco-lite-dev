# Milestone 7: sustainable downstream ownership

Status: planning

Current human-policy queue: [`human-review-decisions.md`](human-review-decisions.md)

## Objective

Milestone 7 establishes a fast local development loop, gives generic behavior one owner, and migrates downstream site data once.
A generic change is proved in the engineering workspace, released through the engine and template, and then proposed to the organization reference downstream.

## Execution order

1. Add the hermetic Pixi dry-run task and ownership classifier.
2. Implement generic ownership, structured rendering, the site-data contract, and migration as one vertical batch.
3. Release immutable engine and template coordinates and promptly migrate `ORINOCO-Lite/test-orinoco-downstream-website` through its normal human-gated path.
4. Exercise an optional developer-owned AI sandbox in parallel after the release or afterward.
5. Remove legacy paths and copied framework files after reference acceptance.

Failures found downstream return to the engine or template when the behavior is generic.

## Downstream contract

```text
site-specific/
  site.yaml
  content/
    pages/
  static/
    manifest.yaml
    files/
  curation-records/
    <adapter>.yaml
  sources/
    <adapter>/
      source.yaml
      content/
      policy/
      evidence/
  metadata/
    records/
    overlays/
      annotations/
extensions/
  source-adapters/
  site/
```

`site-specific/site.yaml` is the editable authority for site identity, navigation, contact data, routes, and presentation groups.
Copier metadata and generated configuration derive from it.

`curation-records/` contains compact current decision caches.
`sources/` contains source coordinates, adapter configuration, captured source content and evidence, and mapping policy.
Git remains the historical record.

`dump-research-info` is site-specific executable code under `extensions/source-adapters/dump-research-info/`.
Its configuration, source content, evidence, and policy belong under `site-specific/sources/dump-research-info/`; its decisions belong in `site-specific/curation-records/dump-research-info.yaml`.
Generic adapters such as the Zotero adapter belong to the engine or template but will still have their own site-specific configuration, source content, evidence, and policy.

`site-specific/static/` owns site assets, including CSS.
`extensions/site/` is available for site-specific templates or rendering code that cannot be expressed as data.
Framework assets move upstream with their licenses or clean replacements.

## Workstream 1: engineering dry run

Add one Pixi task that constructs an ordinary downstream in a fresh temporary directory from the candidate template and exact engine/runtime coordinates.
It exercises:

- template render and update;
- configuration and ownership validation;
- adapter ingestion, proposal planning, deterministic curation, and a no-op rerun;
- canonical and joined metadata validation, projection, and static build; and
- focused `/edit/` and `/review/` browser flows.

The Pixi task may select compact or full fixture input and materializes each run in a separate ephemeral downstream.
A persisted downstream repository maintains one canonical corpus only; it never carries parallel smoke and full corpora.

The task runs from a clean clone on macOS ARM64 and Linux x86-64, uses only declared inputs, and leaves no tracked or sibling-worktree state.

## Workstream 2: ownership, rendering, and migration

Classify copied downstream files as generic framework, structured site data, consumer extension, generated output, test fixture, legal material, or obsolete state.
Move generic projection, rendering, curation, workflow, and adapter behavior to the engine or template.
Thin downstream workflows call immutable reusable workflows with site data as input.

Generate configured home, record, index, and navigation surfaces from `site.yaml` and canonical records.
Optional structured content or Markdown supplies bespoke pages without becoming a required copy of the framework or record-derived lists.

Introduce configurable record, annotation, curation, source, and asset roots with one migration command.
The command verifies its source contract, moves site data, applies the generated framework, reports conflicts with edited content, updates configuration and workflows, validates the joined graph and route inventory, and is idempotent after success.

## Workstream 3: review and validation

The bare `/review/` route links to relevant open curation pull requests and may populate an in-page selector.
Exact proposal links remain the deterministic review entry point.

Curation pull requests identify the source adapter, link to the downstream review application, retain the merge and artifact notes, and put the source coordinate in a closed details block.
Finalization reports the decision commit and validation state concisely.
Workflow-authored bot text does not carry an agent-draft disclaimer.

A base-branch-owned classifier selects validation for:

- opened, reopened, or updated proposals whose head changes canonical metadata and therefore require full validation;
- authenticated decision-only finalization requiring trusted joined-graph validation at the exact head; and
- framework, content, default-branch, and manual events.

Trusted dispatch does not execute untrusted pull-request code, and concurrency does not replace the required exact-head result with an approval-gated duplicate.

## Workstream 4: agent workflows

Add `.apm/skills/exercise-orinoco-ai-sandbox/SKILL.md` to the engineering repository.
It accepts a repository selected by the developer in that developer's account and treats the broad repository-local grant as standing authority.
The agent may navigate, curate, merge, deploy, and recover without repeated approval; branches, pull requests, and checks remain useful practice rather than permission gates.
Submission provenance records the authenticated GitHub principal and agent-mediated execution, with a dedicated bot identity optional.

Add a template-owned `maintain-orinoco-site` skill for ordinary downstreams.
It guides an agent through immutable-coordinate inspection, template updates, preservation of site data, local validation, content or adapter adjustment, and the downstream's own review policy.
Copier distributes this skill with the template.

## Workstream 5: release and adoption

Release and pin each generic layer, migrate the organization reference downstream, and record the accepted engine, template, downstream, deployment, and rollback coordinates.
After acceptance, remove old data roots, copied generic code, duplicate Markdown lists, and stale configuration.
An ownership check prevents generic implementation from returning to site-owned paths.

The real CON site and external source systems remain read-only evidence during this milestone.
Static validation, editing, review, and builds continue to work without a persistent metadata service.

## Acceptance

Milestone 7 is complete when:

1. the Pixi dry run passes from clean clones on supported macOS and Linux platforms and catches generic failures before hosted promotion;
2. all site data follows the new contract, `dump-research-info` follows the code/data split above, and generic behavior has one engine or template owner;
3. a generated downstream builds a useful site from `site-specific/` data without required custom Markdown;
4. the migration is conflict-aware, idempotent, semantically stable, and adopted by a clean generated consumer and the organization reference downstream;
5. review discovery, curation copy, and validation dispatch satisfy the exact-head and untrusted-code contracts;
6. both skills pass focused tests, with an online developer sandbox exercise recorded when one is configured; and
7. release, deployment, rollback, and legacy-removal evidence is recorded at immutable coordinates.
