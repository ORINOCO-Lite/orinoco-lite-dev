# Milestone 7: sustainable downstream ownership

Status: implementation complete; organization adoption awaiting human review

Current human-policy queue: [`open-decisions.md`](../open-decisions.md)

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

`site-specific/site.yaml` is the editable authority for site identity, contact data, navigation, presentation groups, and explicitly declared presentation or index routes.
`site-specific/projection.yaml` contains site-specific record selection, graph, PID-derived record routing, and editor-scope policy.
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

### Current acceptance record

1. The local candidate command exercised working-tree engine and template changes together against the retained downstream before either release.
The final full run passed four adapter canaries, 155 consumer tests, validation of 224 records and 202 annotation companions, deterministic static builds, and five Chromium plus five WebKit route and editor checks.
Unit coverage separately proves engine-only and template-only staging.
2. [Engineering pull request 73](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/73) delivered the unified source contract, structured rendering, local candidate loop, review discovery, bot copy, and engineering skill at `6d268efac4ad6283103e9ff38f93780cbff9eb24`.
Immutable engine/runtime release [`v0.2.0rc12`](https://github.com/ORINOCO-Lite/orinoco-lite-dev/releases/tag/v0.2.0rc12) was produced by [release run 33218446554](https://github.com/ORINOCO-Lite/orinoco-lite-dev/actions/runs/33218446554).
3. Immutable template release [`v0.2.0rc16`](https://github.com/ORINOCO-Lite/orinoco-lite-template/releases/tag/v0.2.0rc16) is based on `aa2428fd58fa1e0d2ffc2e57c0ada279f6c7e0d3`.
Its published `github-template` commit is `60cfbc1f37d580e21ade08200ca47758e9ab3e94`, with exact tree `a3679dbb94ebf3b343063208c4e5602bae7fe220`.
[Post-merge run 33222094866](https://github.com/ORINOCO-Lite/orinoco-lite-template/actions/runs/33222094866) passed on Linux and macOS.
4. Developer-downstream [pull request 33](https://github.com/leej3/orinoco-lite-demo/pull/33) installed the new ownership layout, and [pull request 34](https://github.com/leej3/orinoco-lite-demo/pull/34) adopted the final validation scope.
The current source is `f22c8f3dfa9c0942c523784868ecad84a8caaa49`; [Pages run 33222159712](https://github.com/leej3/orinoco-lite-demo/actions/runs/33222159712) deployed it at [`https://leej3.github.io/orinoco-lite-demo/`](https://leej3.github.io/orinoco-lite-demo/).
[Validation run 33222159713](https://github.com/leej3/orinoco-lite-demo/actions/runs/33222159713) passed on Linux and macOS.
The live `/edit/` and `/review/` routes are downstream-owned, and bare `/review/` links to the repository's filtered open curation pull requests.
5. Source-curation branches use their existing exact-head dispatch once.
Metadata changes receive full validation; decision-cache-only updates receive joined-graph validation; ordinary pull requests retain full validation.
The final source-curation message reports the decision commit as ready for merging without a human-draft disclaimer.
6. The organization reference is rebuilt from the same retained data and adapter baseline in [pull request 52](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/pull/52).
The pull request remains open at the required human gate after local adapter, consumer, validation, deterministic-build, and browser checks plus [hosted validation run 33222244960](https://github.com/ORINOCO-Lite/test-orinoco-downstream-website/actions/runs/33222244960) on Linux and macOS.
7. The engineering `develop-orinoco-lite` skill drove the local-to-developer exercise, and template release `v0.2.0rc16` distributes the `maintain-orinoco-site` skill for ordinary downstream updates.
8. The central backend-only service was deployed from the clean engineering commit `6d268efac4ad6283103e9ff38f93780cbff9eb24`, tree `8dc652dcc6832dada9eb3bd3890337f1b2320b31`, to Cloudflare Pages project `orinoco-curation-review` as immutable deployment `058c3cc9-8ebd-45ff-95a0-9acb903d57f6` at [`https://058c3cc9.orinoco-curation-review.pages.dev/`](https://058c3cc9.orinoco-curation-review.pages.dev/).
The canonical origin remains [`https://orinoco-curation-review.pages.dev/`](https://orinoco-curation-review.pages.dev/) with public client ID `Iv23limCfUnRPCFcXx3H`; its configuration contains only `PUBLIC_ORIGIN`, `GITHUB_CLIENT_ID`, and the encrypted `GITHUB_CLIENT_SECRET` and `SESSION_SEAL_KEY` values.
The deployment uploaded no static files: it contains only the checked Functions bundle and route file.
Anonymous probes confirmed the retired root and presentation routes return empty `404` responses, discovery tombstones return `410`, the anonymous session returns `authenticated: false`, and OAuth uses the exact callback plus PKCE without an OAuth scope.
A live browser exercise against `leej3/orinoco-lite-demo` loaded 224 records in the downstream editor, exposed credential-free **Download review bundle**, exercised the then-current shared-origin and public-data controls, completed GitHub authentication without a write, and confirmed the downstream's human-friendly filtered pull-request link.
The current shared-origin policy is warning-only.
Deployment `8d448e3d-97e2-4054-b29d-b9ed88321b8b` remains the previously successful production rollback coordinate.
