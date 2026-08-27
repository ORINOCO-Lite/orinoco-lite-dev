# Upstream snapshot workflows

The engineering workspace can now materialize one public-pool capture as exact JSONL and YAML records, exercise those YAML records through the full upstream service stack, and compose the same capture into an ordinary Orinoco Lite Git repository.
All generated state stays below ignored `build/`; the real CON site is not read or changed.

## What upstream already provides

Dump Things already has the essential record-level machinery.
Its record-dir backend serializes JSON objects with `json2yaml()`, and its schema-type layer removes top-level `schema_type` on write and reconstructs it from the class directory on read.
Its public data `Format` enum, however, exposes JSON and Turtle rather than YAML, and it has no single command that turns an envelope JSONL corpus into a Git-friendly YAML tree and proves an exact YAML-to-JSONL round trip.

The local snapshot bridge deliberately reuses upstream `order_dict()` and `json2yaml()` instead of introducing another YAML dialect.
Its additional job is corpus auditing: strict envelope checks, collision-resistant paths, duplicate rejection, exact type-and-value comparison, manifests, and reverse verification.

## Capture or reuse a snapshot

Fetch a new public-pool capture explicitly:

```console
pixi run refresh-upstream-records
```

For a reproducible rerun, reuse the existing digest-checked cache, fetching only when none exists:

```console
pixi run snapshot-upstream-records
```

The task writes three related representations:

| Representation | Location | Authority and purpose |
| --- | --- | --- |
| Source envelope JSONL | `build/upstream-stack/pool/public-thing.jsonl` | Untouched API capture and exact source-byte digest. |
| Exact canonical YAML | `build/upstream-stack/snapshot/metadata/records/` | One complete record per PID, including top-level `schema_type`. |
| Canonical envelope JSONL | `build/upstream-stack/snapshot/records.jsonl` | Deterministically ordered JSONL exported back from the YAML tree. |

`build/upstream-stack/snapshot/manifest.json` records source, semantic, and YAML-tree digests plus class counts and the locked Dump Things serializer version.

The exact comparison preserves list order and duplicate list members and distinguishes JSON number spellings such as `1` and `1.0`.
It rejects duplicate PIDs, duplicate YAML keys, non-finite numbers, malformed class/type pairs, symlinks, unexpected files, and noncanonical YAML. It does not invoke RDF, deduplicate assertions, close a graph, or normalize identifiers. This keeps a failure attributable to JSON/YAML conversion rather than to a second semantic layer.

## Use the records three ways

### Full upstream stack

```console
pixi run check-upstream
```

This retains the recorded upstream application, Hugo presentation, theme, Dump Things service, and SHACL Vue editor.
It seeds the `public` collection from the source JSONL and the isolated `protected` collection from the YAML-derived JSONL.
It then reloads both physical Dump Things stores, restores the schema type that upstream intentionally omits on disk, and requires both to equal the source snapshot exactly before running the existing service, UI, write-isolation, and static-site checks.

Use `pixi run serve-upstream` to leave the checked full stack running locally.
This is the strongest route for testing upstream itself and its presentation.

### Ordinary Orinoco Lite repository

```console
pixi run instantiate-upstream-orinoco
pixi run check-upstream-orinoco
```

The first command renders the pinned Copier template and composes `build/upstream-orinoco-site/`.
The result is an initialized, uncommitted Git repository with all captured records, annotation companions, source JSONL, canonical JSONL, upstream page templates, presentation framework, graph producer, editorial snapshot, and portable provenance.
Submodules, gitlinks, git-annex links, nested repositories, and developer-specific provenance paths are absent.
It can be moved elsewhere and committed after review.

Copier only scaffolds and updates the repository.
It is not involved in validation, projection, building, serving, or deployment after generation.
Those operations use Orinoco Lite directly.

`check-upstream-orinoco` first probes the engine locked by the generated repository, then exercises the current development engine against that lock's verified released runtime in fresh processes.
This distinction matters during engine development: template `v0.2.0rc7` locks engine/runtime `v0.2.0rc4`, which predates the explicit general open-reference and graph policies required by this corpus.
The generated repository's own normal `pixi run validate`, `pixi run build`, and `pixi run serve` commands become the direct standalone interface once a release containing these policies is adopted.
No ad hoc runtime archive is produced to bridge that release boundary.

After the check, preview the generated site with:

```console
pixi run serve-upstream-orinoco
```

### Compare deployment strategies

`check-upstream-orinoco` compares the Orinoco static tree with the upstream static tree and writes `build/upstream-orinoco-comparison.json`.
The report includes route sets, common-file digests, graph size, released-engine probe, verified runtime coordinates, projection diagnostics, deterministic verification, editor scope, and timings.
This makes switching formats or deployment paths a repeatable test rather than a manual migration.

## Exact source versus deployable Orinoco storage

The exact YAML tree above is always the source-format proof.
A second tree at `build/upstream-stack/snapshot/orinoco-storage/` represents the same records in Orinoco's canonical storage contract:

- semantic assertion objects remain in `metadata/records/`;
- machine `pav:importedBy` and `pav:importedFrom` move into reversible companions under `metadata/overlays/annotations/`;
- compact and expanded annotation values acquire one stable semantic form; and
- full-URI PAV aliases normalize to their canonical CURIE spelling.

The storage manifest records all such normalization counts and proves that joining records and companions recreates the annotation-normalized source.
The original JSONL and exact YAML are retained beside it, so this storage projection can never masquerade as a lossless lexical conversion.

One source value needs an explicit schema-compatibility adjustment before RDF validation: publication `xyzrins:publications/fec91e0d-f22a-42c8-8170-a0dd87da53f7` contains `-` at `/generated_by/0/at_time`.
That is not a W3C datetime.
The deployable view omits only this optional sentinel and records the PID, pointer, source value, and action; the exact source representations retain it.

## Findings from the 2026-08-25 capture

The generated manifests are authoritative when the live pool changes.
The capture exercised for this implementation had 5,011 records across 29 classes.
Its source JSONL SHA-256 is `f2a67237033601fd8b39dfbb90ed6cf28b7302de76f1a9b4f26f6a27d272e7a2`, and the exact, line-order-independent record digest is `63ef01ad90bb11ede61746bfd4f3ea3da8ea510b0f60d98985e0bc1325e72a70`.
JSONL to YAML to JSONL passed exactly.

The Orinoco storage projection created 786 companions containing 6,292 PAV assertions.
It normalized 126 PAV URI aliases, two already-expanded machine PAV values, and 18,489 compact annotation values.
Apart from the one invalid datetime sentinel above, its joined semantic records match its normalized source.

The corpus is intentionally not a closed local graph.
The explicit `references.missing_targets: preserve` policy retained 1,572 reference occurrences to 175 distinct nonlocal targets:

| Field | Occurrences |
| --- | ---: |
| `about` | 3 |
| `associated_with` | 12 |
| `attributed_to` | 1,208 |
| `delegated_by` | 7 |
| `identifiers.creator` | 273 |
| `influenced_by` | 68 |
| `influenced_by.roles` | 1 |

The graph view materialized 1,059 nodes and 2,092 edges.
Its explicit `graph.missing_external_targets: drop` policy omitted 2,033 source/target edge pairs that cannot appear as local graph nodes: 11 `associated_with`, 1,201 `attributed_to`, seven `delegated_by`, 706 `generated_by`, and 108 `influenced_by` pairs.
These include both genuinely external references and targets whose class is not selected as a graph node; they are retained in the canonical records.

Additional diagnostics found one schema-valid `attributed_to` relationship context with a role but no optional object target, and one top-level PID whose RDF round trip uses an equivalent URI/CURIE lexical spelling.
Both are now handled explicitly and counted rather than silently discarded.

The static comparison produced 986 upstream routes and 1,746 Orinoco routes, with 981 shared.
The five upstream-only routes are annotation-selected friendly slugs for records that Orinoco currently renders at their PID-derived routes; Orinoco's 765 additional routes are primarily record pages plus the editor.
Person records also span both `xyzrins` and `orcid` namespaces.
Generic multi-namespace routing remains tracked in [`ORINOCO-Lite/orinoco-lite-dev#34`](https://github.com/ORINOCO-Lite/orinoco-lite-dev/issues/34), and annotation-selected route aliases remain a separate projection parity gap.

## Engine issues exposed and covered

Running the complete snapshot revealed several bugs that small fixtures did not make obvious.
The implementation now has focused regressions for:

- compact, expanded, CURIE, and full-URI annotation spellings;
- RDF multivalue reordering and equivalent identifier spellings without weakening exact JSON/YAML comparison;
- schema-valid qualified relationship context without an object;
- preserving ordinary content nested below a route named `provenance`;
- deterministic per-record RDF blank-node scoping instead of an impractical whole-corpus canonicalization;
- limiting editor RDF generation to explicitly editable records while still validating all source records;
- editor builds from an initialized repository whose first commit has not yet been created; and
- direct script imports in locked environments that already contain an unrelated `tools` namespace.

Strict closed-reference, closed-graph, and all-record editor behavior remains the default for existing downstreams.
The broader policies are explicit opt-ins in this generated corpus, so future snapshots reveal drift without silently weakening ordinary consumer validation.
