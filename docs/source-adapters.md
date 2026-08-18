# Source adapters

Status: evolving architecture; two downstream examples under review

## Purpose and vocabulary

A source adapter turns an external metadata source into a reviewable change in an Orinoco Lite site.
The name describes the boundary without prescribing one implementation or one kind of change.

Orinoco Lite adopts the vocabulary already used by the upstream Things tools:

- a **scraper** acquires data from a remote source;
- an **importer** translates source records into Things records;
- an **enricher** adds or revises fields using another source;
- an **extractor** or **reporter** emits information for review; and
- a **projection** derives a website or another presentation from site metadata and is not a source adapter.

Source adapter is the umbrella term for the first four roles.
It replaces the earlier use of *plugin*, which upstream uses for unrelated CLI modularity.

## Review and provenance model

The site repository is the staging and review surface.
An adapter writes its declared outputs, and the resulting Git diff shows every addition, removal, and modification proposed for the site.
One adapter run per pull request is the clearest default, although the reviewer may deliberately combine or revise changes.

Run a metadata-changing adapter through the downstream project's locked DataLad environment:

```console
pixi run datalad run \
  -m "Apply Zotero source adapter (basic)" \
  "source-adapters/zotero/update \
    --source source-adapters/zotero/source/items.json \
    --source-version {literal-source-version} \
    --mode basic \
    --config source-adapters/zotero/config.toml \
    --records metadata/records"
```

The braces mark documentation placeholders only.
The command actually passed to `datalad run` must contain resolved literal values.
In particular, a source checkout is passed as a path relative to the downstream project root, such as `../dump-research-info`, together with its exact revision.
Do not record a developer-specific absolute path or hide the operative value in an environment variable.
A `.env` file may help prepare an invocation, but the expanded value belongs in the recorded command so the commit says exactly what ran.

The adapter executable does not commit, merge, or deploy.
`datalad run` records the command and resulting ordinary-Git changes; a pull request supplies human review.
The diff is already the precise content-change record, so adapters must not add a second SHA inventory or a custom copy of the same diff.
Detailed digests are retained only when they establish an external fact, such as the identity of a fetched payload.
API snapshots and other redistributable source evidence are ordinary Git files.
Downstream source-adapter operation does not use git-annex.

## Modes and adapter-specific policy

Adapters may expose three consistent mode names when those distinctions are useful:

- `report` inspects the source and site without changing site metadata;
- `basic` applies narrow, high-confidence changes; and
- `aggressive` permits broader inference or a wider class of changes.

These names describe review risk, not universal semantics.
Each adapter documents its inputs, matching rules, exact read and write roots, and what additions, replacements, field removals, or record deletions each mode may perform.
Whether a source record's absence should remove a record from the site metadata depends on that adapter, mode, source completeness, and review context.
There is no cross-adapter ownership map or default deletion rule.

Likewise, two adapters may propose changes to the same record.
Each writes its own change; the reviewer sees the overlap in Git and can adjust the invocation, order, or result before merging.
An adapter should be deterministic and idempotent so rerunning it from the same base with the same declared inputs produces no further diff.

Every Thing that participates in validation or projection lives under `metadata/records/`.
There is no separate reference-record class or lookup-only metadata root.
Files used solely for source matching belong to the adapter that interprets them, not under `metadata/`.
Apart from the root `metadata/records/.dumpthings.yaml` source-control marker, every file below `metadata/` must be a Thing and is a real projection input.
This keeps adapter-specific evidence out of the site model.

## Repository layout and environments

Concrete, site-owned adapters are visible at the downstream root:

```text
metadata/records/
source-adapters/<name>/        # site-owned adapter
.orinoco-lite/source-adapters/ # selected generic adapters and support
.orinoco-lite/provenance/
build/source-adapters/         # ignored diagnostic output
```

The public configuration names these roots `paths.records`, `paths.source_adapters`, and `paths.provenance` respectively.
Configuration contract 2 exposes only this single-record-pool interface; there are no compatibility aliases.

An adapter may keep its own Pixi manifest and lock when its source client or transformation dependencies differ from the root project.
That independent dependency boundary is intentional.
The root Pixi environment supplies DataLad and the site-level orchestration; the recorded command still identifies the adapter, inputs, configuration, mode, and outputs explicitly.

Shared implementations may eventually live in template-managed `.orinoco-lite/source-adapters/` or in separately versioned packages.
If a packaged adapter needs matching tables, captured source data, or other private working inputs, it keeps them with its implementation under `.orinoco-lite/`; it does not create a second metadata class.
That distribution choice remains evidence-driven.
The engineering workspace may pin upstream source implementations as submodules while evaluating them, but a generated downstream remains one ordinary Git repository with no submodules or gitlinks.

## Alignment and reuse

Prefer released upstream acquisition, import, enrichment, matching, and update helpers over local equivalents.
Where field-level provenance is appropriate, use upstream PAV semantics such as `pav:importedBy` and `pav:importedFrom` rather than inventing an Orinoco Lite ownership inventory.
New source-adapter work should pay down local technical debt by contributing a generally useful primitive upstream when possible.
The engineering workspace follows the reviewed `things-enrichment-tools` source through its gitlink; that commit is the version authority, without a second downstream checksum inventory.

The current examples have different roles:

- Zotero is the only present candidate for a reusable adapter selected by a downstream or generated by the template.
Its source mapping and publication policy remain site-owned.
- The `dump-research-info` adapter is a deliberately messy, CON-specific exploration.
It helps test modes and review behavior, but it is not a candidate generic adapter for an arbitrary Git checkout containing Things JSON.

Do not freeze a common Python ABI, manifest schema, or host protocol from these two examples alone.
Extract only behavior demonstrated by multiple adapters and continue to track upstream's organization and vocabulary.

## Work plan

1. **Completed: align names and dependencies.** Establish the `source-adapters/` interface, advance reviewed upstream pins, and verify both static and service-backed engineering stacks.
2. **Normalize the exploratory adapter.** Record a literal project-relative source path and exact revision in the DataLad command; document its precise read/write roots and defensible modes; prove deterministic, idempotent direct metadata diffs.
3. **Develop Zotero as the reusable case.** Keep API snapshots in ordinary Git, separate reusable mechanics from site policy, and exercise report, basic, and aggressive behavior only where each mode has a clear meaning.
4. **Extract demonstrated common behavior.** Standardize the smallest useful CLI surface after the examples agree; keep adapter-specific Pixi environments and avoid a speculative host API.
5. **Converge with upstream.** Reuse or improve upstream helpers first, keep engineering pins reviewable, and decide between template-managed files and separately versioned packages only after more adapters establish the maintenance boundary.

An adapter is ready for reuse when its recorded command has no absolute paths or hidden operative configuration, its pull request contains a focused source diff, its source evidence is ordinary Git, reruns are idempotent, and its local code exists only where no suitable upstream implementation is available.
