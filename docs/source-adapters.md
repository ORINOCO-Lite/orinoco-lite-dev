# Source adapters

Status: evolving architecture; two downstream examples under review

## Purpose and vocabulary

A source adapter turns an external metadata source into a reviewable change in an Orinoco Lite site.
The name describes the boundary without prescribing one implementation or one kind of change.

Orinoco Lite aligns with the concrete vocabulary used by the upstream Things tools:

- a **scraper** acquires data from a remote source;
- an **importer** translates source records into Things records;
- an **enricher** adds or revises fields using another source;
- a **projection** derives a website or another presentation from site metadata and is not a source adapter.

Source adapter is Orinoco Lite's local umbrella term for tools that acquire or propose changes to site records, including report-only modes.
It is not an upstream-defined interface or role name.
It replaces the earlier use of *plugin*, which upstream uses for unrelated CLI modularity.

## Review and provenance model

The site repository is the staging and review surface.
The current exploration distinguishes four kinds of state rather than treating all of them as provenance:

| State | Tracked authority | Purpose |
| --- | --- | --- |
| Execution provenance | Git and preserved DataLad run evidence | Records the literal command, declared inputs, source version, and resulting changes. |
| Assertion provenance | The proposed or accepted Thing in `metadata/records/` | Uses Provenance, Authoring and Versioning (PAV) annotations to identify the tool and source responsible for an imported field, object, or statement. |
| Human disposition | Site-owned adapter policy | Records an explicit candidate disposition, such as accept, reject, link, defer, or supersede, that later adapter runs can consume. |
| Cache and diagnostics | Ignored adapter/build state | Improves acquisition or reporting but never determines what a human already decided. |

An adapter can write only provenance known when it runs.
Human-review provenance and disposition arise later and must be recorded by the review action, not inferred by the generator.
The target static workflow is therefore one pull request with a proposal phase and a reconciliation phase, rather than one command that both proposes and decides.

Run the proposal phase through the downstream project's locked DataLad environment:

```console
pixi run datalad run \
  -m "Propose Zotero source adapter changes (basic)" \
  "source-adapters/zotero/update \
    --source source-adapters/zotero/source/items.json \
    --source-version {literal-source-version} \
    --mode basic \
    --config source-adapters/zotero/config.toml \
    --records metadata/records"
```

The proposal command may write intermediate proposed Things directly to `metadata/records/` on the pull-request branch.
They are not accepted metadata until the final reviewed state is merged.
Reconciliation retains or revises accepted proposals and removes rejected or linked-away proposed Things.
The proposal phase must also expose, or deterministically reproduce, a machine-readable candidate inventory bound to the source snapshot and claim fingerprints.
Choosing its representation, transport, and retention is part of the current exploration; it must not become a second canonical metadata pool.

The braces mark documentation placeholders only.
The command actually passed to `datalad run` must contain resolved literal values.
In particular, a source checkout is passed as a path relative to the downstream project root, such as `../dump-research-info`, together with its exact revision.
Do not record a developer-specific absolute path or hide the operative value in an environment variable.
A `.env` file may help prepare an invocation, but the expanded value belongs in the recorded command so the commit says exactly what ran.

The adapter executable does not commit, merge, or deploy.
`datalad run` records the command and resulting ordinary-Git changes; a pull request supplies human review.
The diff precisely records the materialized content delta—additions, modifications, and removals—so adapters must not add a second SHA inventory or a custom copy of the same diff.
Absence from a diff cannot distinguish rejection, deferral, abandonment, or a failed run, so a durable disposition is not a duplicate diff inventory.
Detailed digests are retained only when they establish an external fact, such as the identity of a fetched payload.
API snapshots and other redistributable source evidence are ordinary Git files.
Downstream source-adapter operation does not use git-annex.

The workflow under exploration is:

1. Propose changes and a candidate inventory from an exact source snapshot, current metadata, adapter policy, and previously merged decisions.
2. Have a human explicitly record a candidate disposition, such as accept, reject, link, defer, or supersede, on the same branch.
3. Run a recorded reconciliation command that consumes the exact proposal and decisions and produces the final metadata state.
4. Verify in CI that every proposal has an explicit valid disposition, every decision still matches its source claim, and the reconciled result is deterministic and idempotent.
5. Review the final pull-request head and merge the metadata and decisions as one reviewed default-branch transition.

If every proposal is rejected, the final metadata diff may be empty.
The decision-only pull request must still be merged; closing the proposal does not create state that a future adapter can consume.
A bot is not required.
Automation may help materialize an explicit human decision on the same branch, but it must not infer a disposition, approve, merge, or make a follow-up pull request the normal path.
The exploration must also prove that the repository's actual merge mode preserves enough run evidence to reproduce the final state; a proposal-branch commit is not assumed to remain authoritative after a squash or rebase.

## Modes and adapter-specific policy

Adapters may expose three consistent mode names when those distinctions are useful:

- `report` inspects the source and site without changing site metadata;
- `basic` proposes narrow, high-confidence changes; and
- `aggressive` permits broader inference or a wider class of proposed changes.

These names describe review risk, not universal semantics.
Each adapter documents its inputs, matching rules, exact read and write roots, and what additions, replacements, field removals, or record deletions each mode may perform.
Whether a source record's absence should remove a record from the site metadata depends on that adapter, mode, source completeness, and review context.
There is no cross-adapter ownership map or default deletion rule.

Likewise, two adapters may propose changes to the same record.
Each writes its own change; the reviewer sees the overlap in Git and can adjust the invocation, order, or result before merging.
An adapter should be deterministic and idempotent so rerunning it from the same base with the same declared inputs and decisions produces no further diff.

A decision key must survive individual run identifiers.
The exploration must define a stable source namespace and record identifier, the kind of claim under review, a versioned semantic fingerprint, and the relevant matching-policy version.
Orinoco Lite's default is that rejection suppresses the same materially unchanged claim.
A material source change or a change to relevant matching policy reopens review, and permanent exclusion requires explicit human scope.
A deferral is not a rejection: it must declare when the candidate returns, such as a date, a material source change, or resolution of a named policy question.

An adapter may configure the stable source-identity components, normalized material fields included in the versioned fingerprint, deferral conditions, and additional re-review triggers needed for that source.
It may not make decisions implicit, use run-local identity, treat deferral as permanent rejection, or suppress materially changed claims without an explicit broader human decision.
These semantics are accepted defaults; the serialized disposition schema and common adapter interface remain exploratory.

Every Thing that participates in validation or projection lives under `metadata/records/`.
There is no separate reference-record class or lookup-only metadata root.
Implementation-private caches, indexes, and heuristics used only by one adapter belong with that adapter, not under `metadata/`.
Reviewed entity crosswalks, ontology mappings, and human dispositions are durable site knowledge rather than disposable matching internals and must have one declared tracked authority.
Apart from the root `metadata/records/.dumpthings.yaml` source-control marker, every file below `metadata/` must be a Thing and is a real projection input.
Putting a disposition there would make it a canonical, potentially public Thing; do that only when publication is intentional and supported by the schema.

For the current exploration, adapter-scoped decisions and reviewed crosswalks may be prototyped under `source-adapters/<name>/policy/`.
This uses the existing site-owned adapter root and does not establish a new public configuration path or freeze a common decision schema.
Evidence from multiple adapters is required before choosing a shared curation or mapping authority.

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
The exploratory decision state stays within the site-owned source-adapter root; `.orinoco-lite/provenance/` remains reserved for framework provenance that is not already expressed by the Git/DataLad commit.

An adapter may keep its own Pixi manifest and lock when its source client or transformation dependencies differ from the root project.
That independent dependency boundary is intentional.
The root Pixi environment supplies DataLad and the site-level orchestration; the recorded command still identifies the adapter, inputs, configuration, mode, and outputs explicitly.

Shared implementations may eventually live in template-managed `.orinoco-lite/source-adapters/` or in separately versioned packages.
If a packaged adapter needs generic, implementation-private matching aids, it keeps them with its implementation under `.orinoco-lite/`.
During the prototype, site-specific source captures and candidate decision state remain under the site-owned adapter root and must not be overwritten by a framework update.
The long-term authority for reviewed crosswalks and decisions remains an exploration outcome.
That distribution choice remains evidence-driven.
The engineering workspace may pin upstream source implementations as submodules while evaluating them, but a generated downstream remains one ordinary Git repository with no submodules or gitlinks.

## Alignment and reuse

Prefer released upstream acquisition, import, enrichment, matching, query, serialization, and update helpers over local equivalents.
When a local service-free implementation is still required, retain executable parity tests against the upstream primitive or fixture it replaces.
Where field-level provenance is appropriate, use upstream PAV semantics such as `pav:importedBy` and `pav:importedFrom` rather than inventing an Orinoco Lite ownership inventory.
During the prototype phase those annotations inform adapter behavior without imposing a universal field-ownership gate: `report`, `basic`, and `aggressive` modes may deliberately propose wider diffs, and pull-request review remains authoritative.
Use W3C PROV for run or review-activity lineage only when that additional semantic model is useful beyond the Git/DataLad record.
A Simple Standard for Sharing Ontological Mappings (SSSOM) is a candidate interchange format for reviewed ontology or concept mappings, not a generic record-deduplication key or rejection ledger.
Record linkage remains a separate identity problem whose evidence, confidence, and invalidation policy this exploration must define.
When Things mappings and an SSSOM mapping set both exist, choose one tracked authority and derive the other representation instead of maintaining two independent assertions.
At the reviewed upstream pins, the enrichment helpers provide positive-state deduplication and PAV-aware updates but no durable record of a rejected inbox proposal.
The adapter-policy prototype addresses that missing curation state without presenting it as an existing upstream interface.
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
2. **Encode the accepted decision defaults.** Define a prototype versioned representation for stable source identity, claim kinds, material fingerprints, explicit dispositions, adapter-configurable defer and re-review rules, and minimum reviewer/rationale evidence without weakening the fixed safety boundaries or silently resolving content policy.
3. **Select prototype authorities.** Define how the proposal inventory is represented and transported and how adapter-scoped decisions are tracked under the existing site-owned adapter root, including retention and public-repository privacy, while leaving a shared root and common schema unfrozen.
4. **Prove the two-phase transaction.** Exercise propose, explicit human decision, recorded reconciliation, and final-head review with Zotero and `dump-research-info`; include an all-rejected decision-only pull request, stale decisions, overlapping adapters, and the repository's actual merge mode.
5. **Prove the invariants.** Verify complete decision coverage, suppression of unchanged rejections, re-review after material changes, deterministic and idempotent reconciliation, schema-valid metadata, preserved PAV annotations, and recoverable failure behavior.
6. **Resolve mapping representation and extraction.** Where a genuine semantic-mapping case exists, test Things and SSSOM with one tracked authority; then decide whether evidence from both adapters justifies any common CLI or decision contract.
7. **Converge with upstream.** Reuse or improve upstream helpers first, maintain parity tests for local qri-like behavior, keep engineering pins reviewable, and contribute a generally useful decision or mapping primitive when its semantics are established.

The current exploration is complete when both adapters provide reviewed evidence for the identity, disposition, transaction, and invariant questions; mapping choices additionally require a genuine mapping case.
Any human policy resolutions activated by that evidence must update `human-review-decisions.md` and the corresponding originating decision register in the same reviewed change; objective engineering outcomes belong in the acceptance evidence.
An adapter is ready for reuse when its recorded commands have no absolute paths or hidden operative configuration, its pull request contains focused policy and metadata diffs, its source evidence is ordinary Git, reruns are idempotent, and its local code exists only where no suitable upstream implementation is available.
