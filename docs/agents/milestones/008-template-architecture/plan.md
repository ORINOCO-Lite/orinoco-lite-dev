# Milestone 8: template architecture

## Outcome

Establish and prove one compositional architecture:

```text
optional metadata acquisition and curation executables
                |
                v
      site-specific metadata

generic template website
+ site-specific declarative inputs and overrides
= deployed downstream website
```

The pinned German `www-from-model` site and its `page_templates/` are the behavioral and structural baseline.
The template turns that baseline into a complete generic website that accepts downstream metadata and other site-specific inputs.
The engine performs generic metadata and composition operations.

This is a replacement implementation, not a migration.
Do not preserve downstream framework files, copied tests, layouts in legacy locations, updater machinery, configuration structure, or repository history as compatibility requirements.

## Boundary

The boundary follows artifact type:

- `orinoco-lite-template` contains the complete default website, including Hugo configuration, layouts, navigation, record and index pages, projection templates, workflows, UI components, tests, and useful defaults.
- `site-specific/` contains all declarative downstream inputs: semantic metadata, curation records, editorial content, assets, site identity, limited presentation choices, source-adapter configuration and evidence, and supported overrides.
- Custom layouts are declarative website overrides and therefore belong under `site-specific/overrides/layouts/`.
- `extensions/` contains only site-specific executable metadata acquisition and curation adapters.
It contains no website assets, layouts, presentation overrides, navigation, UI components, client-side code, workflows, build hooks, or other website functionality.
- Extension executables may capture evidence, create metadata proposals, and support curation review or application through declared metadata interfaces.
They run separately from website composition, and neither their code nor their runtime products are copied into the deployed website.
- The engine validates, projects, and composes these inputs but does not provide a second website implementation.

The template must produce a useful deployed website with no downstream overrides.
Overrides are an escape hatch with explicit tests, not the ordinary way to construct a site.

## Upstream tracking

Use one exact `www-from-model` commit in the engineering repository's existing dependency state.
Do not introduce a second provenance manifest or a downstream upstream pin.

The engineering workspace must:

1. build the unmodified German reference website from the exact pin;
2. build the generalized template website from the same pin;
3. compare surfaces intended for direct reuse and fail on unintended drift;
4. test deliberate generalizations with injected mock downstream data; and
5. make the generic website available as a versioned template dependency without requiring downstreams to clone the German upstream or the engineering workspace.

When the upstream pin advances, failures should identify the small template adaptation that needs review.
Do not preserve a permanent file-by-file origin ledger; Git, the dependency pin, and executable comparison are the evidence.
Each downstream chooses when to upgrade its template dependency and may use supported overrides, a fork, or another compatible template implementation.

## Part 1: agree on the architecture

Complete and merge the Milestone 8 design pull request before changing agent guidance or implementation:

1. Update `docs/project-design.md` with the German upstream baseline and the compositional boundary.
2. Record this Milestone 8 plan as the active implementation guide.
3. Review the architecture, downstream independence, upstream tracking, test strategy, and acceptance criteria.

Part 1 must not change agent instructions, skills, engine, template, downstream, workflow, or deployment behavior.

## Part 2: align agent guidance

After Part 1 merges, review and update `AGENTS.md`, the `develop-orinoco-lite` skill, and any other active instructions in a separate documentation-only pull request.
The guidance must direct agents to the agreed composition boundary and local test strategy without embedding transient milestone sequencing in universal instructions.

Review and merge the guidance before implementation, then begin Part 3 in a clean agent task that reads the merged documentation and instructions.

## Part 3: implement the architecture

### Build the generic template from upstream

Use the pinned `submodules/www-from-model` website surfaces and projection templates directly where practical.
Generalize only inputs demonstrated to vary between downstreams, including metadata, editorial content, assets, site identity, base URL, navigation choices, and limited theme choices.

The template must provide the website implementation as one coherent versioned dependency selected by the downstream.
The downstream controls its version and upgrade timing and retains the ability to use supported overrides, a fork, or a compatible alternative.
The implementation must not require downstream copies of framework internals, and the engine runtime must not carry a competing framework.

### Reduce the downstream contract

Create compact mock data and inject it into a fresh disposable template instantiation.
Prefer representative metadata shapes from `ORINOCO-Lite/test-orinoco-downstream-website`; a subset of a developer-owned demo may be used when useful.

Test the ordinary `site-specific/` contract without overrides, then test supported overrides separately.
Reject accidental framework duplication, workflows, copied framework tests, and configuration that restates template defaults.

### Make the engine compose the site

Change the engine build path to combine the selected template website with declared `site-specific/` inputs in a documented order:

1. materialize the generic template website;
2. project downstream metadata using template-owned projection templates;
3. add editorial content, assets, identity, and presentation choices;
4. apply declared `site-specific/overrides/`, including custom layouts.

Metadata acquisition and curation executables under `extensions/` run only through separate explicit metadata workflows before validation and projection.
The website build must not load extension code or copy extension files or runtime products into its output.

During development, select engine and template working trees explicitly.
Choose the simplest distribution mechanism that preserves downstream control of the template version and does not require the German upstream or engineering checkout at build time.
Do not begin with updater or backward-compatibility work.

### Make local proof comprehensive and routine

Confirm that Part 2 guidance describes the implemented command and test contract; update it in the implementation pull request if concrete interfaces change.

Add named Pixi tasks in `orinoco-lite-dev` that create a fresh template instantiation and inject the mock fixture:

- a quick candidate run for metadata validation, projection, build, and a Chromium route smoke test;
- a full candidate run for clean-room setup, engine and template tests, projection repeatability, deterministic builds, link and asset validation, Chromium and WebKit behavior, editor and curation-review behavior, project base paths, supported layout overrides, separate metadata-adapter execution, extension-isolation checks, and an offline build; and
- an optional end-to-end developer-demo run for GitHub validation, curation proposal, default-branch build, and Pages deployment.

CI must construct a minimal content-only downstream for boundary enforcement and test the engine and template working trees together.
A developer-owned `<github-user>/orinoco-lite-demo` may provide real-data and GitHub-workflow proof without becoming a prerequisite or canonical fixture.
The organization-owned reference downstream remains the human-gated adoption check.

## Acceptance criteria

Milestone 8 is complete when:

- a fresh template instantiation with only permitted mock `site-specific/` inputs builds a useful website retaining the German upstream's information architecture and record presentation;
- the instantiated site, projection, graph, search data, editor catalog, and generated routes contain no German records, identifiers, editorial content, or assets unless a downstream explicitly supplies them;
- the template builds a complete website without custom layouts or other downstream overrides;
- a custom layout under `site-specific/overrides/layouts/` is applied and tested without copying or modifying the template framework;
- `extensions/` accepts only metadata acquisition and curation executables through explicit stable metadata hooks;
- validation rejects website assets, layouts, presentation overrides, navigation, UI components, client-side code, workflows, build hooks, and other website functionality under `extensions/`;
- the website build does not execute extension code or contain extension source, dependencies, caches, captured evidence, proposals, or other extension runtime products;
- quick, full, and CI tasks pass against the engine and template working trees;
- local builds are deterministic, work offline after declared dependencies are present, and pass browser, editor, curation-review, link, asset, and project-path checks;
- the downstream selects its template version and can upgrade deliberately, retain supported overrides, or select a fork without depending on the German upstream or the Orinoco Lite engineering checkout;
- a developer-owned `<github-user>/orinoco-lite-demo` is deployed successfully as a working website through its normal GitHub and Pages workflows; and
- the organization-owned reference downstream can be proposed for adoption through its normal human-review gate.

Do not delay acceptance for migration, historical reconstruction, updater compatibility, or preservation of prior downstream framework structure.
