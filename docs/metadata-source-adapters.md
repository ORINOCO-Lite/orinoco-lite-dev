# Metadata source-adapter goal

Status: accepted engineering goal; experimental downstream proof in progress

## Goal

Orinoco Lite should support independently maintained metadata sources through a small plugin protocol.
Each adapter owns the source-specific acquisition, identity, normalization, and candidate rules needed to turn a live source into review evidence.
The common host owns semantic comparison, report validation, safe staging, and the boundary between source evidence and canonical site metadata.

The first proof is the public Center for Open Neuroscience Zotero library in `con/test-orinoco-downstream-website`.
It starts downstream-owned because its source mapping and review policy are CON content policy, not a generic template concern.

## Review pipeline

```text
reviewed source snapshot ─┐
                          ├─ source diff ─┐
live source ──────────────┘               │
                                          ├─ review report
live transformed candidates ──────────────┤
                                          │
canonical repository metadata ─ candidate diff
```

A source refresh and a canonical metadata update are different changes:

1. Fetch the complete source at one verified source version.
2. Validate and normalize records by the adapter's stable source identity.
3. Compare the live source with the reviewed source snapshot without replacing either during the comparison.
4. Transform the live snapshot into deterministic candidates.
5. Compare candidates with both the prior candidates and canonical YAML by canonical PID.
6. Record additions, removals, field changes, exclusions, collisions, unresolved mappings, source versions, input digests, and policy digests.
7. Optionally update only the source evidence and candidates on a review branch.
8. Promote selected candidates to canonical YAML only through a separate, explicit human-reviewed content change.

An adapter or workflow must never interpret “the source changed” as “the site approved this metadata change.”

## Experimental plugin contract

The downstream proof uses a versioned manifest that names site-owned adapter modules.
The host loads each module in isolation and requires one adapter API version and one entry point.
An adapter receives only the repository root, an ignored staging directory, its manifest configuration, and the requested `review` or `refresh-evidence` mode.
It returns a JSON-compatible result containing:

- source identity, version, and normalized content digest;
- a source-record map keyed by stable source identity;
- deterministic candidate records keyed by canonical PID;
- comparisons with the reviewed snapshot, reviewed candidates, and canonical metadata;
- ambiguity and policy-use reports;
- proposed evidence-file replacements; and
- an explicit statement that canonical promotion was not performed.

The host validates the result, writes a common aggregate JSON and Markdown report, and applies proposed replacements only in `refresh-evidence` mode.
Replacement destinations must be declared, site-owned, ordinary files below the integration or generated-manifest roots.
All adapters must stage completely before any tracked evidence is replaced.

Source retention is adapter policy.
A small, redistributable source such as the public Zotero response may be committed with its source version and digest.
A large, mutable, private, or rights-constrained source may retain only an immutable external coordinate or a local digest-checked cache.

## Pull-request boundary

The first proof uses a separate metadata-review process, not the Orinoco framework updater.
Framework updates must preserve site-owned metadata, while metadata review intentionally examines possible site-owned changes.

An automated metadata review may fetch public read-only sources, update source evidence and deterministic candidates, validate the complete site, and open a pull request.
It may not write to the source, change canonical YAML, approve or merge the pull request, or deploy pull-request code.
The durable report belongs in the review branch; transient full payloads and credentials remain ignored local state.

## Graduation to the template

Do not copy the experimental Zotero implementation into the template merely because one adapter works.
Move a common host and workflow facade into `con/orinoco-lite-template` only after all of these gates pass:

1. At least two independent source adapters exercise the same versioned host contract.
2. At least one complete metadata-review pull request demonstrates useful, bounded source and canonical-impact reports.
3. Source-specific policy and dependencies remain entirely site-owned.
4. A content-neutral site with no adapters gets a clear no-op result.
5. Adapter failure, ambiguous identity, stale policy, and partial fetches are fail-closed.
6. Evidence refresh, canonical promotion, framework update, and deployment remain distinct review boundaries.
7. Template updates preserve all adapter configuration and site-owned evidence.

Only after those gates should the root consumer facade expose stable generic tasks such as `metadata-review`, `metadata-refresh-evidence`, and `metadata-check`.
If multiple adapters then need the same semantic diff implementation, that implementation may graduate into the engine without moving source policy there.

## First proofs

The Zotero proof exercises a maintained public API, stable source item keys, library-version consistency, deterministic transformation, collision policy, and canonical publication comparison.
Its first implementation is downstream [`con/test-orinoco-downstream-website#7`](https://github.com/con/test-orinoco-downstream-website/pull/7).
The live review detects the `CON Articles` to `CON Articles & Posters` collection rename, reports the resulting apparent loss of 146 candidates, and blocks evidence refresh before changing tracked state.

A separate one-off DataLad run will compare `con/dump-research-info:data/con_site` with current downstream canonical YAML.
That exploratory run records exact inputs, commands, and outputs and produces review candidates only.
It may inform a second adapter, but one provenance run does not by itself define or stabilize the plugin contract.
The resulting inactive review evidence is the stacked downstream [`#8`](https://github.com/con/test-orinoco-downstream-website/pull/8): 19 source-only candidates, field-level enrichment evidence for 60 matched records, and an exact DataLad rerun with an identical output tree.
