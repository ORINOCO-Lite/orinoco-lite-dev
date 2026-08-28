# Milestone 7: sustainable downstream ownership

Status: planning

Current human-policy queue: [`human-review-decisions.md`](human-review-decisions.md)

## Objective

Milestone 7 makes engine and template changes easy to try against a real downstream locally before anything is released or pushed.
It then reorganizes generic ownership and site data and rebuilds the development downstreams from the improved template.
The result is one understandable metadata and source baseline for faster fixes and collaboration.

## Execution order

1. Add the local downstream development command.
2. Implement generic ownership, structured rendering, and the new site-data layout.
3. Generate fresh downstreams from the candidate template using the retained `leej3/orinoco-lite-demo` data and source adapters, and test them locally.
4. Release the engine and template only after the local downstream succeeds.
5. Push the developer-owned downstream, then update `ORINOCO-Lite/test-orinoco-downstream-website` through its normal human-gated path.

Failures found downstream return to the engine or template when the behavior is generic.

## Downstream contract

```text
site-specific/
  site.yaml
  projection.yaml
  content/
    pages/
  static/
    manifest.yaml
    files/
  curation-records/
    <source-id>.yaml
  sources/
    <source-id>/
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
`site-specific/projection.yaml` contains site-specific record selection, graph, routing, and editor-scope policy.
Copier metadata and generated configuration derive from these files.

`curation-records/` contains compact current decision caches.
`sources/` contains source coordinates, adapter configuration, captured source content and evidence, and mapping policy.
Git remains the historical record.

`dump-research-info` is site-specific executable code under `extensions/source-adapters/dump-research-info/`.
Its configuration, source content, evidence, and policy belong under `site-specific/sources/dump-research-info/`; its decisions belong in `site-specific/curation-records/dump-research-info.yaml`.
Generic adapters such as the Zotero adapter belong to the engine or template but will still have their own site-specific configuration, source content, evidence, and policy.
Engine-owned and site-owned adapters use the same source contract, so captured provenance and curation decisions stay in predictable site-owned locations.

`site-specific/static/` owns site assets, including CSS.
`extensions/site/` is available for site-specific templates or rendering code that cannot be expressed as data.
Framework assets move upstream with their licenses or clean replacements.

## Workstream 1: local downstream development

Add one Pixi task that runs a temporary downstream using unreleased engine or template working-tree changes, independently or together.
It runs without a GitHub push or release.

Quick mode runs the relevant adapter, validation, static build, and focused `/edit/` and `/review/` browser checks.
Full mode runs the complete downstream suite before release.
The task may select compact or full fixture input for an ephemeral run; each persisted downstream still maintains one canonical corpus.

The temporary downstream may be rebuilt freely while the source downstream and local engine and template working trees remain available for another iteration.

## Workstream 2: ownership, rendering, and downstream rebuild

Classify copied downstream files as generic framework, structured site data, consumer extension, generated output, test fixture, legal material, or obsolete state.
Executable validation, projection, curation, and generic adapter behavior belong to the engine.
Repository scaffolding, workflows, layouts, and generated configuration belong to the template.
Thin downstream workflows call immutable reusable workflows with site data as input.

Generate configured home, record, index, and navigation surfaces from `site.yaml` and canonical records.
Optional structured content or Markdown supplies bespoke pages without becoming a required copy of the framework or record-derived lists.

Generate a fresh downstream from the candidate template, place the retained site data under `site-specific/`, and copy retained executable extensions under `extensions/`.
`leej3/orinoco-lite-demo` is the canonical migration input for metadata, curation decisions, source coordinates and captures, adapter configuration, and the Zotero and `dump-research-info` adapter results.
Inspect the organization reference downstream once and fold any useful unique material into that baseline deliberately.
Validate the joined graph, route inventory, static build, and edit and review flows before replacing the old generated tree.
Use the resulting data and generated structure for the organization reference downstream through its normal review path, while retaining destination-specific site identity and deployment settings.

## Workstream 3: review and validation

The bare `/review/` route links to relevant open curation pull requests and may populate an in-page selector.
Exact proposal links remain the deterministic review entry point.

Curation pull requests identify the source adapter, link to the downstream review application, retain the merge and artifact notes, and put the source coordinate in a closed details block.
Finalization reports the decision commit and validation state concisely.
Workflow-authored bot text does not carry an agent-draft disclaimer.

Opening a pull request or pushing a change to canonical metadata records runs full validation.
When the bot records curation decisions without changing those records, a smaller joined-graph check validates the latest commit using released code.
Other code and content changes continue to run their relevant checks.
If one update creates multiple GitHub events, one event must not cancel the useful validation started by another.

## Workstream 4: agent workflows

Add an engineering-repository skill for exercising a downstream selected by the developer in that developer's account.
It treats repository-local curation, merging, deployment, and recovery as standing authority so an agent can complete an end-to-end exercise without repeated approval.

Add a template-owned `maintain-orinoco-site` skill for ordinary downstreams.
It guides an agent through immutable-coordinate inspection, template updates, preservation of site data, local validation, content or adapter adjustment, and the downstream's own review policy.
Copier distributes this skill with the template.

## Workstream 5: release and adoption

After the local candidate succeeds, release and pin the engine and template, deploy the developer-owned downstream, and then propose the same generated structure to the organization reference downstream.
The downstream update may replace the generated tree wholesale.
Both builds start from the retained `leej3/orinoco-lite-demo` metadata, source evidence, decisions, and adapter setup rather than preserving two downstream datasets.
Record the accepted release and deployment coordinates.

The real CON site and external source systems remain read-only evidence during this milestone.
Static validation, editing, review, and builds continue to work without a persistent metadata service.

## Acceptance

Milestone 7 is complete when:

1. the Pixi task can apply an engine-only candidate, a template-only candidate, or both to a temporary downstream and run quick checks without a GitHub push or release;
2. a full local run exercises the retained `leej3/orinoco-lite-demo` data, its Zotero and `dump-research-info` sources, validation, build, and edit and review flows;
3. all site data follows the new contract, `dump-research-info` follows the code/data split above, and generic behavior has one engine or template owner;
4. `leej3/orinoco-lite-demo` and the organization reference downstream are generated afresh from the template, build and deploy from the retained `leej3/orinoco-lite-demo` data and adapter baseline, and the organization update remains human-gated;
5. the bare review route, curation messages, and validation triggers behave as described above;
6. the engineering skill completes one end-to-end exercise in the developer-owned downstream, and the template distributes its downstream-maintenance skill; and
7. the accepted release and deployment coordinates are recorded.
