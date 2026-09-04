# Orinoco Lite package

`orinoco-lite` is the stable, location-independent command-line and integrity boundary for a single-repository Orinoco Lite website.
It discovers the site through `orinoco.yaml`, enforces the exact released-wheel coordinate in `orinoco.lock`, and runs with the code and resources bundled in that wheel.

This package is one layer of the larger system:

- the [engineering repository](https://github.com/ORINOCO-Lite/orinoco-lite-dev) integrates components and publishes the package and reusable CI;
- the submodule-selected `www-from-model` revision and its declared dependency closure provide the presentation and projection source;
- the [template repository](https://github.com/ORINOCO-Lite/orinoco-lite-template) provides the thin Orinoco adaptation, materialized presentation overlay, and downstream scaffold; and
- each downstream repository owns its declarative site inputs and site-specific executable metadata adapters; projection output is ignored and regenerated.

The engineering workspace's submodules, upstream-rebase history, release fixtures, and preservation refs are not part of the package interface.

## Responsibilities

The package owns:

- structural validation of the single-repository workspace;
- exact released-package integrity checks;
- semantic validation and deterministic projection through bundled drivers;
- canonical source-adapter serialization, annotation joining, candidate planning, compact decisions, and Git-based finalization primitives;
- deterministic static builds for root-relative local preview or an explicit public project-path base;
- serving an already built artifact without rewriting it;
- validation and optional application of static-editor review bundles; and
- deterministic package-resource assembly and release verification for engineering.

The package supplies the source-review runner and GitHub curation operations.
The current runner and workflow integrate `dump-research-info` and `zotero` explicitly; their implementation is not yet a general adapter-author interface.
Zotero acquisition and mapping remain downstream-owned under `extensions/source-adapters/zotero/`.
Future packaged adapters must meet the [source-adapter admission and interface requirements](../../docs/agents/contract/source-adapters.md#admitting-an-adapter-to-the-package).

It does not own site content, upstream website behavior, site-specific presentation policy, GitHub branch protection, or production cutover.
Those belong respectively to the downstream, selected upstream source, template and downstream overrides, or repository operator.

## Public command surface

Run `orinoco --help` for the exact argument contract.
The stable commands are:

| Command | Purpose |
| --- | --- |
| `orinoco validate` | Validate structure and run the package's semantic contract. |
| `orinoco projection update` | Regenerate and atomically install projection output. |
| `orinoco projection verify` | Prove existing projection output is current and deterministic. |
| `orinoco build` | Validate and build a static site below the configured build root. |
| `orinoco serve` | Serve existing static bytes; it never changes the artifact's URL base. |
| `orinoco editor apply` | Validate a review bundle; add `--write` only after review. |

Normal users should invoke the corresponding `pixi run ...` facade from their downstream repository.
The template can compose prerequisites and platform compatibility checks that a raw package command intentionally does not own.

## Configuration and release locks

`orinoco.yaml` selects normalized site-owned roots and optional curation-service settings.
The configured `paths.site/site.yaml` owns the public site identity, including `identity.base_url`.
The current configuration contract is version 2; version 1 is intentionally rejected rather than translated implicitly.
Hosted builds obtain the exact GitHub `owner/repository` coordinate from the trusted build invocation; `orinoco build --github-repository` defaults to GitHub Actions' `GITHUB_REPOSITORY` value.
The released central curation service is the default.
A site may replace only that backend with an optional credential-free HTTPS `site.curation_service` origin.
Nonstandard builds may supply `site.repository`; normal downstreams obtain their repository coordinate from the trusted build invocation.
The **Download bundle** action remains credential-free even when no repository coordinate or reachable service is available.
The semantic metadata interface comprises reviewed Things below configured `paths.records` and their machine-managed PAV companions below the package-derived annotation root.
Templates set `paths.records` to `site-specific/metadata/records/`, which derives `site-specific/metadata/overlays/annotations/`.
The companion tree mirrors the configured record path below the derived overlay namespace, and the deterministic join is the validation and RDF boundary.
Every Thing below the configured record root participates in validation and projection.
Declarative site policy controls page generation and editor-catalog exposure without creating another record class.
Projection preserves well-formed unresolved references by default without network access.
It also defaults an omitted `graph.missing_external_targets` policy to `drop`, so only graph-view edges whose selected target cannot materialize are omitted; deterministic projection reports count preserved references and dropped edges by field.
Malformed or schema-invalid values still fail.
Editor RDF includes all records by default, while an explicit `editable` scope can limit the static editor payload to page-eligible records without excluding any record from structural, semantic, RDF, or projection validation.
Site-specific executable metadata adapters live under `extensions/source-adapters/`; their configuration and evidence live under `site-specific/sources/`, and compact decisions under `site-specific/curation-records/`.
The `package` mapping in `orinoco.lock` binds the exact `orinoco-lite` distribution `version`, immutable wheel `url`, and `sha256` digest.
Copier records the corresponding `package_version`, `package_url`, and `package_sha256` answers.
The surrounding Copier and workflow contracts record their own coordinates.

The immutable wheel digest must also match the consumer's frozen `pixi.lock`.
Placeholder digests and mismatched installed versions fail closed.

### Open-reference policy migration

Sites adopting the Milestone 6 open-reference behavior do not need to add a graph policy: omitting `graph.missing_external_targets` selects `drop`.
An existing site that intentionally requires every selected graph target to materialize locally must retain that stricter policy explicitly:

```yaml
graph:
  missing_external_targets: reject
```

That setting fails validation when a selected relationship target is not a selected local graph node.
It does not alter canonical metadata or invent a local Thing.
For full local-reference closure, a site must separately set `references.missing_targets: reject`; omitting the `references` section preserves well-formed unresolved references.

## Schema conversion boundary

The package is content-neutral within the selected Things Schema profile; it does not claim arbitrary-schema compatibility.
The pinned schema has an intentional recursive relationship range and an acyclic inheritance graph.
LinkML's current generated Pydantic representation expands the wide recursive descendant union deeply enough to exceed Python's default recursion limit during model rebuilding.

Until LinkML emits a named recursive alias, the package serializes converter construction, raises the limit to the already-proven value only inside that boundary, and restores the caller's exact value on success or failure.
It does not change the schema, hide semantic errors, or leave a process-wide setting behind.

## Release and license boundary

One `orinoco-lite` release provides a deterministic wheel and source archive containing the static `/edit/` and `/review/` shells, localized schema closure, reviewed renderer, graph support, component license texts, notices, and release provenance.
Package code and bundled resources share one version and integrity boundary.
The package does not expose component checkouts as downstream dependencies.

The package and original Orinoco Lite software are licensed under the [MIT License](LICENSE).
Bundled component licenses and notices remain authoritative for their own files.
Documentation, factual metadata, media, and branding use the repository-wide matrix in [`LICENSES.md`](../../LICENSES.md).

## Development

From the engineering repository root:

```console
pixi install --locked
PYTHONPATH=packages/orinoco-lite/src \
  python -m unittest discover -s packages/orinoco-lite/tests -v
```

The release workflow additionally proves independent package and static-interface builds and verifies the installed wheel and its bundled resources.
Package discovery stays content-neutral; pinned schema and editor checks activate when their recorded sources are available.
Ordinary engineering and release CI initialize those sources and reject every skipped package test.
Engineering CI separately projects one exact consumer revision from tracked inputs, while complete site-content and browser acceptance remain consumer-owned.
