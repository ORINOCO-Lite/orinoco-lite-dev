# Orinoco Lite project design

Orinoco Lite helps an organization maintain structured metadata and publish it as a useful static website.
A downstream should primarily supply its content and configuration; it should not have to design or maintain a separate website.

## Product

The project provides:

- a reusable engine for validating, joining, and projecting schema-backed metadata;
- a reusable website template with accessible presentation, metadata editing, curation review, and deployment defaults;
- a pattern for automated metadata augmentation from arbitrary sources, with each implementation termed a source adapter and a possible future path to a formal plugin architecture;
- a static downstream site that remains useful without a running application server; and
- secure paths for turning metadata changes into proposals.

Users can inspect and edit metadata within the deployed site.
They can download a change bundle and apply it locally, create a pull request using GitHub authentication mediated by the central service, or use a self-hosted instance of that authentication-mediation service.
The editing interface remains part of the deployed site in every case.

## Division of responsibility

The engineering repository owns the engine, shared tests, release assembly, and local integration tooling.
The pinned German metadata-driven site in `submodules/www-from-model`, together with its pinned supporting submodules, is the website baseline.
Its layouts, navigation, record and index pages, static components, and `page_templates/` projection templates should be reused directly where practical.
Only behavior that must vary between sites should be generalized in `orinoco-lite-template`.

The template provides a complete generic website: layouts, projection templates, navigation behavior, record and index pages, workflows, UI components, and useful defaults.
The engine supplies metadata validation, projection, composition, and other generic operations without carrying a competing website implementation.
A downstream supplies site-specific inputs and optional explicit overrides to the template.

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
The template must build a useful website without overrides, and ordinary downstreams should not need copied framework code, duplicated framework configuration, or site-specific copies of workflows and tests.
The composition order is the generic template followed by declared `site-specific/` inputs and overrides.

The separate `extensions/` surface is reserved exclusively for site-specific executable metadata acquisition and curation adapters.
These programs may capture external evidence, transform it into metadata proposals, and support the review or application of curation decisions through declared metadata interfaces.
They are not website extensions: `extensions/` must contain no website assets, layouts, presentation overrides, navigation, UI components, client-side code, workflows, or other website functionality.
Extension code and runtime products are never copied into the generated website.
Reusable metadata-adapter code belongs in the engine or template.
Keeping all declarative website inputs and overrides in `site-specific/` gives website composition deterministic path and precedence rules instead of relying on subjective judgments about individual files.

The engineering dependency state records one exact German upstream website pin.
Local tooling builds the unmodified reference site and the generalized template from that same pin, checks reused surfaces for unintended drift, and exposes changes that require a deliberate template adaptation.
The generic website is available as a versioned template dependency selected by each downstream.
A downstream controls when to upgrade, may retain supported overrides, and may use a fork or alternative compatible template; it does not need a direct dependency on the German repository or Orinoco Lite's engineering checkout.
The template contains no German metadata or editorial content, and an instantiated downstream includes only its supplied records and content.

## Workflow

External sources are captured without changing them, transformed into metadata proposals, reviewed, and then promoted into canonical site data.
These stages remain distinct so that automation is repeatable and editorial decisions are visible.

Most development happens in `orinoco-lite-dev` and tests unreleased engine and template working trees locally by injecting compact mock site-specific data into a fresh template instantiation.
A developer may additionally use a user-owned `<github-user>/orinoco-lite-demo` as a less constrained environment for end-to-end GitHub workflow experiments, reducing human-review blocking while iterating.
The demo is optional; local engine and template development must not depend on one existing.
The `ORINOCO-Lite/test-orinoco-downstream-website` repository deliberately requires human review so developers experience the frequency and severity of updates imposed on downstream users.

## Design principles

- Start from the pinned German upstream website and its projection templates.
Reuse upstream behavior directly, generalize only demonstrated downstream variability, and keep Orinoco-specific adaptations small and clearly separated.
- Track upstream with executable checks.
Use one exact engineering pin and compare the reference and generalized sites from that pin without creating a second provenance ledger.
- Prefer one source of truth.
Repository state, locks, Git, and GitHub should not be restated in additional manifests or ledgers.
- Enforce a compositional boundary.
The template provides the complete default website, and a downstream supplies declared `site-specific/` inputs and overrides.
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
