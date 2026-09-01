# Orinoco Lite project design

Orinoco Lite helps an organization maintain structured metadata and publish it as a useful static website.
A downstream should primarily supply its content and configuration, while the project reuses an existing website rather than maintaining a duplicate.

## Product

The project provides:

- a reusable engine for validating, joining, and projecting schema-backed metadata;
- verified resolution and composition of a pinned upstream static website;
- a thin template for Orinoco adaptations, bounded materialized presentation assets, downstream scaffolding, workflows, and dependency locks;
- a pattern for automated metadata augmentation from arbitrary sources, with each implementation termed a source adapter and a possible future path to a formal plugin architecture;
- a static downstream site that remains useful without a running application server; and
- secure paths for turning metadata changes into proposals.

Users can inspect and edit metadata within the deployed site.
They can download a change bundle and apply it locally, create a pull request using GitHub authentication mediated by the central service, or use a self-hosted instance of that authentication-mediation service.
The editing interface remains part of the deployed site in every case.

## Division of responsibility

The exact German `www-from-model` revision selected by the controlled engineering submodule gitlink is the authoritative presentation and projection source.
Its layouts, navigation, record and index pages, static components, and `page_templates/` are reused directly.
That revision selects Congo through its normal nested dependency mechanism.
Orinoco Lite resolves that dependency closure and does not redeclare its coordinates in the runtime manifest, template, or downstream.

The engine owns source resolution, integrity checks, metadata validation, projection, composition, and shared tests.
It resolves the pinned website and theme into an ignored cache, then combines those sources with the selected template adaptation and declared downstream inputs.

The template is deliberately small.
It owns the Orinoco-specific adaptation, Copier scaffold, workflows, locks, and a bounded overlay of presentation assets that maintainers have materialized from upstream.
It does not own or copy a complete website.
A downstream selects a template release and supplies its site-specific data.

Site-specific material should converge on one clear tree:

```text
site-specific/
  assets/
  curation-records/
  editorial/
  metadata/
    overlays/
    records/
  overrides/
    layouts/
  sources/
    <adapter>/
extensions/
  source-adapters/
```

The `site-specific/` tree contains semantic metadata and curation records, editorial content, assets, site identity and limited presentation choices, source-adapter configuration and evidence, and declarative overrides such as custom layouts.
Ordinary downstreams should not need copied framework code, duplicated framework configuration, or site-specific copies of workflows and tests.
Composition applies the resolved upstream website, the template adaptation and materialized overlay, and then declared `site-specific/` inputs and overrides.

The separate `extensions/` surface is reserved exclusively for site-specific executable metadata acquisition and curation adapters.
These programs may capture external evidence, transform it into metadata proposals, and support the review or application of curation decisions through declared metadata interfaces.
They are not website extensions: `extensions/` must contain no website assets, layouts, presentation overrides, navigation, UI components, client-side code, workflows, or other website functionality.
Extension code and runtime products are never copied into the generated website.
Reusable metadata-adapter code belongs in the engine or template.
Keeping all declarative website inputs and overrides in `site-specific/` gives website composition deterministic path and precedence rules instead of relying on subjective judgments about individual files.

Git Annex is confined to maintainer repinning.
Required assets are part of the selected upstream functionality rather than a feature-specific allowlist.
The repinning workflow hydrates and verifies required Annex-backed content against the selected Git state and copies only the redistributable payloads needed by downstream runtime into the template overlay as ordinary files.
The selected repositories and their Git and Git Annex state are the provenance; runtime and template configuration do not duplicate information that tooling can derive from them.

Downstream source-adapter tasks use DataLad to capture run-commit provenance.
Their repositories are configured to record the relevant content directly in Git, so source-adapter execution and website builds do not require Git Annex.
The template contains no German metadata or editorial content, and an instantiated downstream includes only its supplied records and content.

## Workflow

External sources are captured without changing them, transformed into metadata proposals, reviewed, and then promoted into canonical site data.
These stages remain distinct so that automation is repeatable and editorial decisions are visible.

Most development happens in `orinoco-lite-dev` and tests unreleased engine and template working trees locally by injecting compact mock site-specific data into a fresh template instantiation.
A developer may additionally use a user-owned `<github-user>/orinoco-lite-demo` as a less constrained environment for end-to-end GitHub workflow experiments, reducing human-review blocking while iterating.
The demo is optional; local engine and template development must not depend on one existing.
The `ORINOCO-Lite/test-orinoco-downstream-website` repository deliberately requires human review so developers experience the frequency and severity of updates imposed on downstream users.

## Design principles

- Reuse upstream directly.
Start from the submodule-selected German website and its declared dependency closure, and preserve its behavior unless a deliberate Orinoco adaptation requires a change.
- Track upstream with executable checks.
Use Git and Git Annex tooling to inspect and materialize the selected state without creating a second provenance ledger.
- Prefer one source of truth.
Repository state, locks, Git, and GitHub should not be restated in additional manifests or ledgers.
- Enforce a compositional boundary.
The upstream source provides the website, the template provides a thin adaptation and bounded materialized overlay, and a downstream supplies declared `site-specific/` inputs and overrides.
Optional `extensions/` executables may prepare metadata through separate curation workflows but never extend or ship with the website.
- Generate static output.
Validation, building, browsing, editing, and bundle download must not depend on a continuously running metadata service.
- Keep GitHub credentials out of the site.
Authentication and verified submission cross a narrow service boundary.
- Preserve human control where it matters.
Proposals are reviewable, direct submission is explicit, and a credential-free bundle remains available.
- Use Git for recovery.
Reverting a current commit and allowing the static website to redeploy is the normal rollback mechanism; additional session manifests or coordinate inventories are unnecessary.
- Use the engineering repository's Pixi task to test engine and template changes by injecting mock data into a fresh disposable template instantiation before publishing them.
Local quick and full runs are the default; a developer-owned `<github-user>/orinoco-lite-demo` may extend them with autonomous GitHub-workflow acceptance.
Propose the resulting downstream update to `ORINOCO-Lite/test-orinoco-downstream-website` for the deliberate human-review gate.

Normative engineering contracts live under `docs/agents/contract/`; active plans and open decisions live directly under `docs/agents/`.
They may evolve as the design is implemented.
Humans and agents should use this document as their concise shared interface for the project's core design, checking active work against it and discussing any proposed departure before that departure becomes implementation detail.
