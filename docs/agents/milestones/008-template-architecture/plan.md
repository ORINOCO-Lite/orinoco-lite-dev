# Milestone 8: upstream composition and thin template

## Outcome

Establish and prove one maintainable composition:

```text
controlled www-from-model gitlink
        |
        v
exact www-from-model checkout
        + upstream-declared dependency closure
        + thin Orinoco template adaptation
        + bounded materialized presentation overlay
        + downstream site-specific inputs
        |
        v
disposable static-site build
```

The German `www-from-model` repository and its `page_templates/` are the authoritative presentation and projection source.
The engine resolves the exact revision and performs generic metadata, projection, and composition operations.
The template is a lightweight Copier scaffold with the Orinoco adaptation, required materialized presentation assets, workflows, and locks.

This is a replacement implementation, not a migration.
Do not retain old framework copies, checked rendered trees, legacy paths, updater machinery, or backward compatibility as requirements.

## Boundary

- The controlled engineering gitlink selects the exact `www-from-model` revision.
That revision's normal dependency mechanism selects Congo and other upstream dependencies; the runtime manifest, template, and downstream do not repeat those pins.
- Git and Git Annex state are the provenance for an upstream Annex payload.
Do not add per-asset coordinates, digests, or origin inventories to runtime, template, or downstream configuration.
- Git Annex is used only by maintainer repinning tooling.
The released engine, template tasks, and downstream validation, projection, build, test, and deployment paths do not invoke or depend on it.
- DataLad remains in downstream source-adapter workflows to record run provenance in Git.
Correct repository configuration keeps adapter inputs and outputs out of Annex, so these workflows do not require Git Annex.
- The engine owns source resolution, integrity verification, metadata validation, projection, composition, and shared behavioral tests.
- `orinoco-lite-template` owns the small Orinoco adaptation, bounded materialized presentation overlay, Copier scaffold, workflows, and dependency locks.
It does not own a complete website.
- `site-specific/` contains declarative downstream metadata, curation records, editorial content, assets, identity, limited presentation choices, source-adapter configuration and evidence, and supported small overrides.
- `extensions/` contains only site-specific executable metadata acquisition and curation adapters.
Extension code and runtime products are neither loaded during website composition nor copied into the generated site.
- Generated projections, static sites, caches, and Copier renderings remain untracked build products.
The template publication branch may contain its exact rendered distribution tree because that branch is itself a distribution product.

Do not copy it wholesale.
Keep required materialized artifacts in a bounded template overlay that carries a license and applicable notices.

## Implementation

### Resolve and verify upstream

Use the controlled gitlink as the direct `www-from-model` coordinate and resolve its dependency closure through the selected revision's normal dependency declarations, nested gitlinks, and locks.
Resolve the resulting exact state into an ignored cache and reject a checkout or dependency that does not match it.

The first resolution may require network access.
After declared dependencies are present, ordinary validation, projection, building, and browser use must work offline.
Candidate development may use an explicit local exact checkout without changing the downstream contract or duplicating the pin.

### Carry required upstream assets

Required assets are part of retained upstream functionality automatically; do not maintain a feature-specific allowlist.
Maintainer repinning derives the required Annex-backed content from the selected upstream state, hydrates and verifies it, and copies payloads needed by downstream runtime into the licensed template overlay as ordinary files.
A Pixi task may report precise Git and Git Annex information when useful, but its output is derived evidence rather than another tracked source of truth.

Failure to hydrate, verify, or match any asset required by retained upstream functionality blocks the repin.
Do not remove or replace upstream behavior, import upstream site data, or introduce Git Annex into a downstream to make the build pass.

### Keep the template thin

Remove copied upstream layouts, projection templates, configuration, and other website framework files from the Copier source.
Retain only files that intentionally adapt upstream behavior, materialize a required presentation asset, or create an ordinary downstream repository.

Do not keep a rendered Copier result on the source branch.
Render into temporary or ignored storage for local inspection and tests, then publish that validated ephemeral result directly to the template distribution branch.

### Compose downstream inputs

Build in this order:

1. resolve and verify the controlled upstream revision and its declared dependency closure;
2. compose the ordinary upstream presentation and projection surfaces;
3. apply the template adaptation and materialized asset overlay;
4. project and add declared `site-specific/` metadata, editorial content, assets, identity, and presentation choices; and
5. apply supported `site-specific/overrides/` with explicit precedence.

Run executable metadata adapters under `extensions/` only through separate metadata acquisition and curation tasks before validation and projection.
Those tasks use DataLad for run provenance but do not annex their inputs or outputs.
Website composition must not import extension code or copy extension files, caches, captured evidence, proposals, or dependencies into its output.

### Prove the composition

Use the smallest relevant check for each important boundary rather than creating a persistent proof framework.
The engineering candidate task creates a fresh disposable Copier instance, injects compact mock downstream inputs, and tests selected engine and template working trees together.
Focused checks cover observable behavior and major failure boundaries rather than comparison with a checked-in rendered website or exhaustive restatement of this plan.

## Acceptance criteria

Milestone 8 is complete when:

- a fresh downstream reuses the exact upstream presentation and projection behavior without copying the website framework;
- the template source is a small reviewable adaptation and scaffold containing only required materialized assets rather than a complete website;
- retained upstream functionality works with its required assets without a feature-specific allowlist;
- Git and Git Annex tooling can reconstruct materialization provenance without a redundant coordinate inventory;
- DataLad records source-adapter run provenance while downstream website and adapter tasks require no Git Annex;
- a missing required asset blocks repinning rather than removing upstream behavior or publishing an Annex pointer;
- downstream metadata builds the expected static website without German records, identifiers, editorial content, or site-specific assets leaking into it;
- a fresh candidate run passes against the engine and template working trees using a disposable render and focused behavioral assertions;
- a verified cached dependency supports an offline repeat build;
- the template publication branch is produced directly from the validated ephemeral render; and
- after reviewed engine and template releases, the reference downstream update is proposed through its normal human-review gate.

Do not delay acceptance for migration, historical reconstruction, updater compatibility, or preservation of prior downstream framework structure.
