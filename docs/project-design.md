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
It maintains the minimal integration layer over the German upstream and provides the workspace for validating upstream updates and preparing contributions back.
The template repository owns the website, defaults, and downstream update mechanism.
A downstream repository owns only its site-specific data, configuration, assets, and custom source adapter code.

Site-specific material should converge on one clear tree:

```text
site-specific/
  static/
  curation-records/
  metadata/
    overlays/
    records/
  sources/
    <adapter>/
extensions/
  source-adapters/
    <site-specific-adapter>/
```

Content and presentation supplied by the template should be driven by this data.
Downstreams may override the framework, but routine adoption should not require copying and maintaining template Markdown or application pages.
Configuration, captured source content, mapping policy, and curation decisions for both reusable and site-specific adapters belong under `site-specific/`.
Reusable adapter code belongs in the engine or template; site-specific adapter code belongs under `extensions/source-adapters/`.

## Workflow

External sources are captured without changing them, transformed into metadata proposals, reviewed, and then promoted into canonical site data.
These stages remain distinct so that automation is repeatable and editorial decisions are visible.

The normal development loop tests unreleased engine or template changes against a temporary downstream locally.
An agent may also use a user-owned `<github-user>/orinoco-lite-demo` for faster, less constrained experimentation with GitHub workflows without mandatory human review.
The `ORINOCO-Lite/test-orinoco-downstream-website` repository deliberately requires human review so developers experience the frequency and severity of updates imposed on downstream users.

## Design principles

- Maintain a minimal compatibility layer over the German upstream.
Keep broadly useful changes suitable for contribution upstream, and keep Orinoco-specific adaptations small and clearly separated so updates can be rebased with little friction.
- Prefer one source of truth.
Repository state, locks, Git, and GitHub should not be restated in additional manifests or ledgers.
- Aim to keep downstreams small.
The template should provide the website; a downstream should instantiate it for an organization by supplying site metadata, configuration, assets, and necessary extensions.
- Generate static output.
Validation, building, browsing, editing, and bundle download must not depend on a continuously running metadata service.
- Keep GitHub credentials out of the site.
Authentication and verified submission cross a narrow service boundary.
- Preserve human control where it matters.
Proposals are reviewable, direct submission is explicit, and a credential-free bundle remains available.
- Use Git for recovery.
Reverting a current commit and allowing the static website to redeploy is the normal rollback mechanism; additional session manifests or coordinate inventories are unnecessary.
- Use the engineering repository's Pixi task to test engine and template changes against a temporary downstream before publishing them.
Local iteration is the default; a user-owned `<github-user>/orinoco-lite-demo` may extend that testing into an autonomous GitHub workflow.
Propose the resulting downstream update to `ORINOCO-Lite/test-orinoco-downstream-website` for the deliberate human-review gate.

Normative engineering contracts live under `docs/agents/contract/`; active plans and open decisions live directly under `docs/agents/`.
They may evolve as the design is implemented.
Humans and agents should use this document as their concise shared interface for the project's core design, checking active work against it and discussing any proposed departure before that departure becomes implementation detail.
