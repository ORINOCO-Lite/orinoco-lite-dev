# Orinoco Lite engine

`orinoco-lite` is the stable, location-independent command-line and integrity boundary for a single-repository Orinoco Lite website.
It discovers the site through `orinoco.yaml`, enforces the exact release coordinates in `orinoco.lock`, verifies a checksummed runtime, and invokes only drivers declared by that runtime.

This package is one layer of the larger system:

- the [engineering repository](https://github.com/ORINOCO-Lite/orinoco-lite-dev) integrates components and publishes the wheel, runtime, and reusable CI;
- the [template repository](https://github.com/ORINOCO-Lite/orinoco-lite-template) pins those releases and owns the downstream framework/update surface; and
- each downstream repository owns its metadata, editorial content, assets, policy, and extensions; projection output is ignored and regenerated.

The engineering workspace's submodules, upstream-rebase history, release fixtures, and preservation refs are not part of the package interface.

## Responsibilities

The engine owns:

- structural validation of the single-repository workspace;
- exact engine, runtime, manifest, and resource integrity checks;
- verified asset hydration and fetch-free verification;
- semantic validation and deterministic projection through released drivers;
- canonical source-adapter serialization, annotation joining, candidate planning, compact decisions, and Git-based finalization primitives;
- deterministic static builds for root-relative local preview or an explicit public project-path base;
- serving an already built artifact without rewriting it;
- validation and optional application of static-editor review bundles; and
- deterministic runtime assembly and release verification for engineering.

It does not own site content, presentation policy, GitHub branch protection, template migrations, framework-update pull requests, or production cutover.
Those belong respectively to the consumer, template, or repository operator.

## Public command surface

Run `orinoco --help` for the exact argument contract.
The stable commands are:

| Command | Purpose |
| --- | --- |
| `orinoco validate` | Validate structure and run the verified runtime's semantic contract. |
| `orinoco assets hydrate` | Retrieve only manifest-declared payloads and verify their sizes and digests. |
| `orinoco assets verify` | Verify declared local payloads without silently fetching them. |
| `orinoco projection update` | Regenerate and atomically install projection output. |
| `orinoco projection verify` | Prove existing projection output is current and deterministic. |
| `orinoco build` | Validate and build a static site below the configured build root. |
| `orinoco serve` | Serve existing static bytes; it never changes the artifact's URL base. |
| `orinoco editor apply` | Validate a review bundle; add `--write` only after review. |
| `orinoco runtime install` | Resolve and install the exact locked runtime archive. |
| `orinoco runtime verify` | Verify the runtime manifest, resource inventory, and tree digest. |
| `orinoco release assemble` | Engineering-only deterministic runtime assembly. |
| `orinoco release verify` | Verify a release archive or extracted runtime. |

Normal users should invoke the corresponding `pixi run ...` facade from their downstream repository.
The template can compose prerequisites and platform compatibility checks that a raw engine command intentionally does not own.

## Configuration and release locks

`orinoco.yaml` names the site, public base URL, normalized site-owned roots, and optional released-driver aliases.
The current configuration contract is version 2; version 1 is intentionally rejected rather than translated implicitly.
To expose the optional static-editor GitHub proposal action, a site configures `site.repository` as its exact GitHub `owner/repository` coordinate and `site.curation_service` as the credential-free HTTPS origin of the receiver.
Those two values are accepted only as a pair; omitting both preserves the credential-free **Download bundle** action without a GitHub handoff.
The semantic metadata interface comprises reviewed Things under `metadata/records/` and their machine-managed PAV companions under `metadata/overlays/annotations/`.
`paths.records` defaults to `metadata/records`; the companion tree mirrors that fixed record path below its overlay namespace, and the deterministic join is the validation and RDF boundary.
Every Thing below the configured record root participates in validation and projection.
Declarative site policy controls page generation and editor-catalog exposure without creating another record class.
Projection preserves well-formed unresolved references by default without network access.
It also defaults an omitted `graph.missing_external_targets` policy to `drop`, so only graph-view edges whose selected target cannot materialize are omitted; deterministic projection reports count preserved references and dropped edges by field.
Malformed or schema-invalid values still fail.
Editor RDF includes all records by default, while an explicit `editable` scope can limit the static editor payload to page-eligible records without excluding any record from structural, semantic, RDF, or projection validation.
Site-owned source adapters use `paths.source_adapters` (default `source-adapters`), while framework provenance defaults to `.orinoco-lite/provenance`.
There are no legacy `canonical`, `reference`, or `integrations` path aliases.
`orinoco.lock` binds:

- the exact `orinoco-lite` distribution version, immutable wheel URL, and SHA-256 digest;
- the exact runtime version, immutable archive URL, archive digest, and embedded-manifest digest; and
- the template and reusable-workflow coordinates recorded by the surrounding downstream contract.

The immutable wheel digest must also match the consumer's frozen `pixi.lock`.
Placeholder digests, mismatched installed versions, mutable runtime contents, path escapes, and undeclared drivers fail closed.

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

The current runtime is content-neutral within the selected Things Schema profile; it does not claim arbitrary-schema compatibility.
The pinned schema has an intentional recursive relationship range and an acyclic inheritance graph.
LinkML's current generated Pydantic representation expands the wide recursive descendant union deeply enough to exceed Python's default recursion limit during model rebuilding.

Until LinkML emits a named recursive alias, the engine serializes converter construction, raises the limit to the already-proven value only inside that boundary, and restores the caller's exact value on success or failure.
It does not change the schema, hide semantic errors, or leave a process-wide setting behind.
The diagnosis and removal condition are recorded in [`docs/milestone-4-decisions.md`](../../docs/milestone-4-decisions.md).

## Release and license boundary

Releases contain a deterministic wheel and source archive, a checksummed runtime archive, a machine-readable source inventory, component license texts, and build provenance.
The runtime contains the localized schema closure, reviewed renderer, graph support, and static editor required by consumers; it does not expose component checkouts.

The engine and original Orinoco Lite software are licensed under the [MIT License](LICENSE).
Bundled component licenses and notices remain authoritative for their own files; the runtime inventory preserves them rather than replacing them with the Orinoco Lite license.
Documentation, factual metadata, media, and branding use the repository-wide matrix in [`LICENSES.md`](../../LICENSES.md).

## Development

From the engineering repository root:

```console
pixi install --locked
PYTHONPATH=packages/orinoco-lite/src \
  python -m unittest discover -s packages/orinoco-lite/tests -v
```

The release workflow additionally proves independent package, editor, and runtime builds and verifies the installed wheel.
Package discovery stays content-neutral; pinned schema and editor checks activate when their recorded sources are available.
Ordinary engineering and release CI initialize those sources and reject every skipped package test.
Engineering CI separately projects one exact consumer revision from tracked inputs, while complete site-content and browser acceptance remain consumer-owned.
