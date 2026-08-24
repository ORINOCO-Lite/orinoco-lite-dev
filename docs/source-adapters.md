# Orinoco Lite source-adapter specification

Status: normative specification

This document defines a host-neutral source-adapter contract.
The initial hosted implementation is the separately specified normative [`GitHub source-adapter curation profile`](github-curation-review.md), which this contract incorporates by reference.
Its small stateless authentication and comment service and its expiring GitHub Actions presentation artifact are not a metadata service or durable curation store.
This document does not define a Python ABI, plugin protocol, or persistent metadata service.
Superseded but potentially useful implementation observations are retained in the non-normative [source-adapter design notes](../reports/source-adapter-design-notes.md).

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## Scope and vocabulary

A source adapter turns an identified external metadata source into a reviewable change to an Orinoco Lite site's canonical Things.

`source adapter` is an Orinoco Lite umbrella term.
Implementations SHOULD use the more specific upstream role when applicable:

- a **scraper** acquires source data;
- an **importer** translates source records into Things; and
- an **enricher** adds or updates assertions using another source.

A projection derives a presentation from canonical metadata and is not a source adapter.
A report-only diagnostic is useful adapter tooling but does not, by itself, implement this contract.

The supported workflow has one proposal commit, zero or more human-review modification commits, and a final complete decision state on one review branch.
The proposal is a DataLad run commit.
Pixi tasks that programmatically apply metadata changes also use DataLad.
Direct human changes are ordinary Git commits.

The reviewed default branch is the curated state.
A proposal branch is the service-free equivalent of an upstream inbox.

## Authorities and state

| Concern | Authority | Rule |
| --- | --- | --- |
| Metadata records | `metadata/records/` | Store every reviewable semantic assertion object, including qualified `AttributeSpecification` and `Statement` objects, without inline machine-source annotations. |
| Machine assertion provenance | `metadata/overlays/annotations/` | Store only PAV annotation companions for assertion objects already present in records; joining the two trees reattaches PAV without supplying assertion content. |
| Metadata change | Git diff | The proposal diff is the review payload; it MUST NOT be duplicated in a tracked inventory. |
| Human decision | Adapter-owned compact decision cache | Preserve accepted, rejected, and deferred current decisions. |
| Human modification | Attributed Git commit, host comment, or review bundle | Preserve the human actor and resulting metadata diff. |
| Execution provenance | DataLad run commit | Record each Pixi task that programmatically changes metadata. |
| Review history | Git commits and host review history | Preserve prior record and decision-cache states. |
| Hosted authentication | GitHub and short-lived service sessions | OAuth state and authentication sessions are operational state, never durable curation state. |
| Hosted review presentation | One expiring GitHub Actions artifact | Reproducibly present source and proposal coordinates plus per-record UI facts without becoming metadata, candidate, decision, or provenance authority. |
| Scratch state | Ignored `build/` content | Never determine or replace a human decision. |

The record and annotation-overlay trees are canonical site-owned state.
Generated projections, candidate plans, caches, diagnostics, hosted form renderings, and the expiring presentation artifact are not canonical metadata.
For hosted review, the proposal commit and its metadata diff remain authoritative for candidate membership and operations.

## Core adapter contract

### Inputs and boundaries

An adapter run MUST identify:

- the adapter and implementation version;
- a source coordinate or version;
- the exact canonical-metadata base;
- the adapter policy relevant to the proposed change; and
- its declared read and write roots.

Operative values MUST be literal and reproducible.
Developer-specific absolute paths, credentials, run IDs, timestamps, and scratch locations MUST NOT affect candidate identity or output.

Source acquisition MUST be read-only.
Credentials, non-redistributable source payloads, and caches MUST remain outside tracked repository state.
The adapter MUST apply every validation rule exposed by its declared source model before transformation.
Before the proposal commit, every stored record and every Thing produced by joining its annotation companion MUST pass the complete automated validation supported by the locked Things Schema and runtime.
Validation failures are diagnostics to correct, not review dispositions or durable candidate state.
Each source claim MUST bind a stable source-record identifier to a content hash of all and only the normalized source facts that can affect its proposed metadata.
Transport metadata and unused source fields MUST NOT affect that hash or reopen review.
A source-level version such as a Git commit or Zotero library version SHOULD also be recorded when available.
Historical source payloads MAY be retained, but the specification never requires a full source snapshot.
Historical reacquisition is not a conformance requirement: the identifier, source version, content hash, proposal diff, and review history are sufficient evidence of what was reviewed.

### Canonical ordering

One shared canonicalizer MUST order and serialize every record and annotation companion written by an adapter.
Adapters MUST NOT implement private YAML-ordering rules.
The canonicalizer MUST match the upstream Dump Things `order_dict()` and `json2yaml()` behavior: recursively sort mapping keys lexically and preserve list order.
It MUST be an idempotent shared library operation with focused upstream-parity tests, not a service or plugin framework.
Every record in the canonical corpus MUST already conform to that serialization.
An adapter run serializes only records it writes and does not reserialize untouched records.

Record comparison operates on canonical metadata without machine-source annotations, claim hashing on its canonical source-mapped semantic proposal fragment, and the Git diff on deterministic record and annotation-companion serialization.
That claim fragment contains every adapter-owned unannotated semantic assertion produced by source mapping and policy, including qualified predicates, values, objects, ranges, and policy-created output.
It excludes PAV, baseline and human-owned content, formatting, unused source facts, and the adapter version by itself.
An implementation or policy change that changes semantic output therefore changes the claim digest, while a compatible version change with identical output does not reopen review.
This makes formatting and unused source changes invisible while retaining meaningful source and metadata changes for review.

### Candidate plan

The adapter MUST deterministically derive an ephemeral candidate plan before writing metadata.
Each candidate contains at least:

- a stable source namespace and source-native record identifier;
- the target canonical PID and record path;
- a human-readable label;
- the baseline and proposed Thing, or an explicit deletion;
- the corresponding annotation-overlay changes; and
- the claim content hash defined above.

The plan drives proposal generation, hosted review rendering, and submission validation.
It MUST be reproducible and MUST NOT be tracked.
Full records, opaque candidate IDs, transaction IDs, or copies of Git diffs MUST NOT be stored as review provenance.
Internal digests MUST NOT be the primary human identifier.

A host MAY materialize reproducible presentation output from the plan and identified proposal for the duration of review.
Such output MUST remain untracked and non-authoritative, and its expiry or absence MUST NOT alter metadata, a decision, or review history.

### Proposal

Given identical source, base, policy, and active decisions, proposal output MUST be deterministic and idempotent.
It MUST change only proposed Things under `metadata/records/` and their matching PAV annotation companions under `metadata/overlays/annotations/`.

The proposal MUST be created by one project-locked `datalad run --explicit` invocation.
The run record MUST remain inline in a distinct commit; a DataLad sidecar is not used.
The recorded command MUST name the adapter, exact source coordinate, relevant inputs, base, and both metadata outputs.

The proposal's DataLad commit and every later review commit MUST survive unchanged as distinct commits in default-branch history.
A merge commit preserves those commits.
Rebasing or squashing the final reviewed lineage is not conformant because it rewrites the execution record.
An obsolete proposal replaced during conflict regeneration is not part of the final reviewed lineage and need not be retained.

### Decisions and cache

The system supports three dispositions for any proposed addition, modification, or deletion:

- `accept`: apply the reviewed change, including any attributed human edits;
- `reject`: restore the baseline and suppress the same unchanged claim;
- `defer`: restore the baseline and ask again on the next proposal.

Absence, an unchecked form, pull-request closure, workflow failure, or a missing cache entry is never a decision.

The cache is current state, not an append-only event log.
It MUST be owned by the adapter under `source-adapters/<adapter>/policy/curation-decisions.yaml`.
Git history is the history of prior cache states.

The compact representation MUST store:

- once per review: the exact source coordinate, reviewer, review time, and review URL; and
- once per current record decision: canonical PID, source-native record ID, claim digest, disposition, and review reference.

The cache is canonical YAML with exactly these top-level fields:

- `format`, whose value is `orinoco-lite-curation-decisions-v1`;
- `adapter`, whose value is the literal adapter name;
- `reviews`, a mapping whose keys are `github-comment:<decimal comment id>` references; and
- `decisions`, a mapping whose keys are canonical PIDs.

Each review contains exactly `source_coordinate`, `reviewer`, `reviewed_at`, and `review_url`.
The reviewer and canonical UTC-second review time come from the authenticated GitHub comment event, and `review_url` is the exact comment URL.
Each decision contains exactly `source_record_id`, `claim_sha256`, `disposition`, and `review`.
The claim digest uses the normative `sha256:` form and `review` names one extant review mapping.
Every source record identity and PID occurs at most once, and every retained review is referenced by a current decision.
Re-review replaces current decisions for the same source identities and prunes review mappings that are no longer referenced.

It MUST NOT contain baseline or proposed records, rendered diffs, candidate or decision event graphs, run manifests, or duplicated batch metadata.
Re-review replaces the current entry; the prior entry remains available through Git.

An unchanged rejection remains suppressed.
A change to the canonical source-mapped claim MUST reopen review.
An unused source change does not reopen review because it cannot alter the proposal.
An accepted claim whose source-mapped proposal is unchanged is not proposed again, even when the reviewed metadata contains a human correction.
Deferral always returns on the next proposal.
There is no separate permanent-exclusion disposition: rejection persists until the canonical source-mapped claim changes.
Identity linkage is adapter policy or a reviewed crosswalk, not a disposition.

### Human modification and finalization

Review may revise proposed metadata before finalization.
Supported inputs include:

- attributed suggestions in review comments that automation applies;
- one or more metadata commits pushed by authorized humans.

SHACL Vue proposal editing is a distinct human-edit profile, not an input to this decision-review and finalization profile.
Its existing generated bundle may be handed to a separately reviewed GitHub wrapper, but SHACL Vue itself does not acquire source-adapter, disposition, provenance, or decision-cache semantics.

Human review MAY add, modify, or delete metadata beyond the original candidate plan on the same pull request.
That scope is governed by ordinary pull-request review, attribution, and final validation rather than an adapter restriction.
Unrelated human edits do not acquire a machine-annotation entry or a source-candidate cache entry merely because they share the branch.
The PID and record path identifying an initial candidate remain fixed for that review.
A human identity retarget is expressed as rejection or deferral of the source candidate plus a separately attributed human deletion or addition; the cache never silently moves a source decision to another Thing.

A direct human commit is already its own execution and attribution record.
When automation applies a comment or patch, the project Pixi task MUST support recording that operation with `datalad run --explicit`.
The Pixi task MUST run through that DataLad recording path.
The command SHOULD record an input identifier and content hash when available, but the input payload need not remain in the final tree or Git history.
DataLad is not useful for a decision-cache-only commit.

Finalizing review MUST:

1. require exactly one valid disposition for every current candidate;
2. verify the form's stable source identifiers and content hashes against the initial proposal commit;
3. retain all attributed human metadata edits on the review branch;
4. apply the reviewed record and provenance changes for accepted candidates;
5. restore rejected and deferred record and provenance changes;
6. update no durable review artifact other than the compact decision cache; and
7. validate the record tree, annotation-overlay tree, and complete joined Things graph.

For each rejected or deferred candidate, finalization MUST reverse that candidate's metadata-base-to-proposal patch against the submitted head using Git three-way semantics.
A clean non-overlapping human edit survives.
An overlapping hunk is a focused conflict: finalization stops without committing and requires correction and resubmission rather than choosing which metadata to retain.

For an accepted candidate, attributed human record bytes remain authoritative.
If such a correction makes an untouched proposal-added annotation selector stale, finalization removes only that stale proposal-added entry.
It MUST fail rather than overwrite a human-edited companion or resolve an ambiguous selector.
After reconciliation, a companion with no assertions is deleted rather than retained with an empty assertion list.

If finalization changes metadata programmatically, its Pixi task MUST run through DataLad.
For each bot commit, the most recent authenticated human whose action triggered the operation is the Git author and automation is the committer.

Accepted record or provenance bytes may exist only in the earlier proposal commit.
Their Git history, the PID-keyed cache entry, and the review commit together form the per-record human audit.
A record MUST NOT be rewritten solely to make it appear in the review commit.

Automation MUST NOT choose a disposition, mark a review ready, approve, merge, deploy, or write to the external source.

Before merge, corrections remain on the same review branch and add attributable commits; finalization is rerun against the new head.
After merge, a correction starts a new adapter run and pull request from the reviewed default branch.

### Update and adapter interaction

Adapters MUST apply the upstream machine-ownership rules: a machine update does not silently overwrite a human- or differently owned assertion.
When a whole-record proposal would replace such content, the complete loss or change MUST remain visible in the Git diff and require explicit acceptance.
Candidate derivation MUST compare assertion content independently of its annotation companion.
When an incoming assertion is semantically identical to an existing assertion, the adapter MUST preserve both and MUST NOT produce a provenance-only diff.
When an incoming assertion differs substantively, the proposal MAY replace it; an accepted replacement records the proposing adapter and source in the companion.
This rule applies assertion by assertion, so an unrelated change elsewhere in a record does not change the provenance of unchanged assertions.
The scalar compatibility gate below is more specific: this general replacement permission does not authorize an adapter to replace an already populated topical data or class-range slot when the pinned enrichment helper would preserve it and represent the source value as a qualified assertion.

An adapter MAY propose deletion for any record.
The Git diff and form MUST make the deletion explicit, and acceptance or rejection is a human decision like any other proposed change.
Deleting a record also deletes its annotation companion.
The record tree, annotation-overlay tree, and joined graph MUST still pass schema and relationship validation; the adapter does not need a separate lifecycle-ownership or source-completeness protocol.

Two adapters may target the same Thing.
Each maintains its own source identities and decision cache, so one adapter's decision never suppresses another adapter's claim.
Each proposal MUST start from the current reviewed base.
Proposal branches that Git can merge cleanly may be merged in either order without rebasing or rerunning either adapter, provided the resulting tree validates.
If Git reports a conflict, the proposal branch MUST be recreated on the new default branch and the adapter rerun; the obsolete proposal commit is replaced rather than retained.
Assertions from different adapters may coexist in one Thing and retain their own assertion-level PAV in the joined graph.
Conflicting proposals remain ordinary visible diffs for a human to accept, reject, defer, or edit.
No global field-ownership registry is implied.

Within one adapter, multiple source rows that intentionally target the same PID MUST be coalesced into one candidate and one adapter-defined stable composite source identity before the shared plan is built.
The compact PID-keyed cache does not represent multiple independent same-adapter decisions for one Thing.

## Semantic annotation overlay

Upstream stores PAV annotations inline in a Thing and therefore in the same RDF graph.
Orinoco Lite stores the assertion content in the user-facing record and its machine assertion provenance separately to keep record diffs readable, then joins them into the same semantic Thing before validation or RDF export.
The intended difference is only the location of PAV: the unannotated assertion content in `metadata/records/` plus its companion entry MUST produce the same joined assertion that the pinned enrichment helper produces inline.

Adapter-generated PAV MUST be stored under `metadata/overlays/annotations/`, in a YAML companion that mirrors the record's relative path under `metadata/records/`.
One companion covers one record and contains its PID plus only its current machine assertion provenance.
It MUST NOT copy the record, retain prior states, or contain review decisions.
The top-level mapping contains exactly `record` and `assertions`.
`record` is the canonical PID and MUST match the mirrored record.

Only the `annotations` overlay is defined by this specification.
A new `metadata/overlays/<name>/` directory requires a focused specification change, a deterministic join rule, and validation of the resulting Thing.

Each item in `assertions` contains exactly:

- `path`, identifying a mapping assertion or collection of mapping assertions;
- `assertion_sha256`, identifying the canonical assertion with annotations excluded;
- `pav:importedBy`, identifying the adapter; and
- `pav:importedFrom`, identifying the logical source record.

`path` uses an RFC 6901 JSON Pointer.
It MUST terminate at an inlined mapping assertion or a collection of mapping assertions and MUST NOT traverse a collection by array index; collection membership is selected only by the assertion fingerprint.
`assertion_sha256` is `sha256:` followed by the lowercase SHA-256 digest of the UTF-8, whitespace-free JSON serialization produced with lexically sorted mapping keys, preserved list order, and recursively omitted `annotations` keys.
For a direct mapping, the fingerprint MUST match that mapping; for a collection, it MUST match exactly one mapping item.
Zero or multiple matches are invalid.
This is the complete selector model: adapters MUST NOT add private identifiers or matching rules.
Entries MUST be ordered lexically by `path` and then `assertion_sha256`.

The join operation is a shared engine function.
It attaches annotations directly to the selected stored object, including imported objects such as `attributed_to` and `identifiers`, qualified data assertions under `attributes`, and qualified class-range assertions under `characterized_by`.
It MUST NOT manufacture an `AttributeSpecification`, `Statement`, or other semantic assertion from a scalar companion selector.
The joined representation uses the expanded `annotation_tag` and `annotation_value` objects required by the pinned runtime and MUST pass JSON-to-RDF-to-JSON and projection round trips with the locked Things Schema.

### Upstream-compatible qualified assertions

Status: accepted.

The pinned `update_data_property()` behavior separates a topical slot from its qualified source assertion.
It fills the topical slot only when that slot is absent.
Whether the topical slot was absent or already populated, it manages the machine-owned qualified assertion in `attributes`, or in `characterized_by` when configured for a class-range relation.
If the source later differs from an existing topical value, upstream leaves that topical value untouched, removes obsolete qualified assertions owned by the same updater, preserves human- and differently owned assertions, and appends the new qualified source assertion.

A scalar companion selector cannot preserve that behavior.
It contains no assertion value of its own, so a join can only derive a qualified assertion from the current topical value.
When the source and topical values differ, deriving from the topical value loses the source claim, while replacing the topical value creates a local ownership behavior that the pinned helper does not have.
Putting the differing source value in the companion would turn the provenance companion into a second metadata store, contrary to its exact schema and authority boundary.

The upstream-compatible resolution stores the qualified assertion content as canonical metadata and separates only its PAV:

- a data value is a schema-valid `dlthings:AttributeSpecification` under `attributes`, with the schema-induced predicate and source value;
- a class-range URI is the pinned `Statement` under `characterized_by`, with the schema-induced predicate and source URI object and no `schema_type`;
- a missing topical slot is populated exactly as upstream does, while an existing topical slot is preserved;
- non-string topical data retains its native type, while its stored `AttributeSpecification` uses the canonical JSON lexical value and locked LinkML datatype in `range`, as required by the locked schema;
- the companion selects that stored qualified object and contains only its PAV; and
- the join reattaches expanded PAV to the selected object without creating another semantic assertion.

Under this resolution, adding a missing qualified assertion is a substantive metadata proposal even when the topical value already matches.
It records the source's qualified claim in the canonical graph; it is not a provenance-only rewrite.
If an equivalent qualified assertion already exists, the upstream subset match preserves the richer existing object and its current ownership and produces no PAV-only diff.
Same-owner obsolete qualified assertions are removed, human- or differently owned assertions survive, existing order is preserved, and missing desired assertions are appended in deterministic source order.
The claim digest remains over the normalized source-mapped semantic fragment with native source value types and the qualified assertion content produced by policy, not over PAV or the storage bridge.
A changed source value therefore reopens review and updates only the adapter-owned qualified assertion, while the populated topical slot remains unchanged.
If a reviewer later edits or removes the qualified assertion, the accepted unchanged claim stays suppressed under the ordinary human-correction rule.

The alternatives and their compatibility costs are:

| Option | Benefit | Cost |
| --- | --- | --- |
| Store the upstream qualified assertion and split only PAV | Preserves the upstream semantic graph, topical-slot behavior, ownership rules, and existing companion authority without another artifact. | Canonical records and public projections contain the real qualified assertions; the first source run may therefore have a material metadata diff even where topical values already match. A small wrapper must split inline upstream PAV and normalize the already approved typed-value edge case. |
| Derive a qualified assertion from a scalar companion selector | Keeps stored records shorter and is simple when source and topical values are equal. | Cannot represent a differing source value without replacing or losing the topical value, so it permanently forks update semantics and requires local ownership rules and parity maintenance. |
| Replace only a topical value inferred to have the same owner | Propagates source changes while attempting to preserve human and foreign values. | Upstream does not record ownership on the topical scalar, so qualifier ownership cannot prove who owns that scalar. The inference needs new state or a local rule and is not sustainable under the accepted authority boundary. |
| Store the source value in the companion | Keeps the qualified assertion out of the record. | Makes the companion a second metadata and candidate store, changes its schema and authority, duplicates source facts, and requires a new migration and hashing contract. |
| Preserve the topical value and emit no qualified source assertion | Avoids overwriting curated data. | Drops a material source claim from the canonical graph and Git diff, so it cannot be reviewed or reproduced as upstream represents it. |
| Restore inline PAV | Uses upstream storage bytes directly. | Reintroduces machine-only provenance noise into human-facing records and abandons the accepted companion boundary even though storing the unannotated qualified assertion is sufficient. |

If the topical slot is absent but an equivalent human- or unowned qualified assertion already exists, the pinned helper fills the topical slot and does not add machine PAV because its subset match ignores ownership.
The adapter MUST follow that upstream behavior: it proposes the topical convenience copy as a normal metadata change without claiming ownership of the existing qualified assertion and without adding new PAV.
Human review may accept, reject, or defer that proposal.
The proposal commit and review history attribute the copied topical value; the pre-existing qualified assertion remains human- or unowned.

Adapters MUST NOT emit a scalar-path companion, omit a source-qualified object, classify a source field as unused merely because a topical value is populated, use the general visible-replacement rule to overwrite a populated topical scalar, or extend the companion schema.
Implementation evidence MUST compare the local split/join result with the pinned enrichment helper for missing, equal, differing, same-owner, human-owned, and differently owned values; cover string, typed non-string, class-range, and multivalued cases; and prove locked-schema RDF and projection round trips.
Any accepted qualified-assertion additions to the existing corpus are source-adapter metadata changes reviewed through the normal proposal workflow, not part of the separate canonical-serialization normalization pull request.

Every machine-provided assertion object MUST have a companion entry.
Assertions created by a human or downstream policy do not.
Structural `pid` and `schema_type` slots are not imported assertions.
The stored record tree MUST NOT contain either CURIE or expanded-URI `pav:importedBy` or `pav:importedFrom` annotations; those machine annotations belong only in companions and the derived joined graph.
A provenance entry changes only when the metadata assertion it describes changes: an unchanged adapter result produces no diff, while a human replacement removes the old machine-source entry in the same change.
Git retains the earlier assertion and provenance.
The accepted source claim remains cached, so the unchanged source MUST NOT later propose reverting the human replacement.

`pav:importedBy` MUST reference a versioned Thing/PID describing the adapter or enricher, matching upstream practice. Changing the adapter incompatibly requires a new versioned agent Thing. The exact source revision belongs in Git/DataLad review provenance; `pav:importedFrom` may remain the stable logical record URI.

W3C PROV is added only when a specific lineage query cannot be answered by Git, DataLad, and PAV.
SSSOM is used only for a genuine ontology mapping set and never as a decision cache or generic identity ledger.

## Host profile

A conforming host MUST provide:

- a visible metadata diff and friendly per-record decision controls;
- authenticated reviewer identity and authorization;
- complete-decision validation;
- proposal-time validation bound to the source version, record identifiers, content hashes, and metadata base;
- attributable human modification inputs and commit history;
- exact-head compare-and-swap for each automated commit;
- normal metadata validation on the reviewed head; and
- a merge method that preserves the exact proposal, review, and finalization commit objects.

A conforming downstream MUST permit merge commits on its curated branch.
A linear-history-only branch policy is not supported.

The adapter core is host-neutral.
No second host implementation is required until the GitHub profile is complete, but another host may implement the same contract without adopting GitHub-specific files or APIs.

### GitHub profile

The initial supported host implementation MUST conform to the normative [`GitHub source-adapter curation profile`](github-curation-review.md).
That profile owns GitHub-specific workflow, authentication, interface, comment, and hosting behavior without changing this document's metadata, provenance, decision, or history contract.

The trusted proposal workflow MUST publish exactly one untracked, expiring, reproducible GitHub Actions presentation bundle for the hosted application.
The bundle contains the identified source and proposal coordinates and the per-record facts required to render the review interface.
The application MUST derive candidate membership and add, modify, or delete operations from the proposal commit's metadata diff and use the bundle only for presentation.
It therefore requests GitHub Actions read access in addition to the permissions needed to read the proposal and post the authenticated comment.

Pull-request Markdown remains an accessible summary and link, not a machine protocol, candidate authority, or reason to impose GitHub's native diff-display limits as conformance limits.
The presentation bundle expires under ordinary GitHub artifact retention and MAY be reproduced from the same identified inputs; it is not a persistent store, attestation, journal, or recovery artifact.
Git commits, the authenticated submission comment, and the compact decision cache remain the durable review state.

The project MAY publish one central application origin by default.
That origin MUST remain configurable, and a downstream MAY self-host the same stateless application without creating another host profile or durable authority.

## Security and complexity guardrails

The supported threat model trusts collaborators who already have repository `write` or `admin` permission as authorized curators.
Branch protection, review, and GitHub's audit history govern misuse of that authority.
The workflow does not construct a cryptographic protocol against a malicious authorized collaborator.

An implementation MUST stop and request human clarification when an ambiguity would change metadata semantics, provenance, review behavior, repository history, authority, or durable state.
It MUST NOT resolve that ambiguity by broadening the threat model, inventing another authority or artifact, or generalizing the architecture.
A new requirement at one of those boundaries requires a focused specification change before implementation continues.

The implementation MUST protect write credentials from untrusted source data and pull-request executable code.
Beyond that boundary:

- Git commits are the transaction and recovery mechanism.
- A failed operation is retried, corrected, or reverted.
- No custom distributed transaction, journal, lock service, or crash-recovery protocol is introduced.
- No tracked inventory, review document, exhaustive manifest, DataLad sidecar, reconciliation report, or custom attestation graph is introduced.
- No artifact is added merely to authenticate another artifact produced by the same trusted workflow.
- The GitHub Actions presentation bundle is transient UI output, not a candidate inventory, attestation, journal, or recovery mechanism.
- No semantic overlay beyond `annotations` is introduced without a focused specification change and a source or human state that Git, PAV, and the compact decision cache cannot represent.
- A stronger attacker or availability model requires a separate reviewed design rather than incremental workflow machinery.

## Repository and dependency boundaries

Concrete adapters and their policy are site-owned under `source-adapters/<adapter>/`.
Scratch state belongs under ignored `build/`.
The record and annotation-overlay trees are site-owned semantic metadata.
The annotation-companion format and join operation are an engine contract; framework updates MUST NOT overwrite companion content.
Adapters MUST NOT store decisions beneath `metadata/` or write source-adapter state beneath `.orinoco-lite/`.

An adapter MAY have its own locked environment when its acquisition or transformation dependencies differ from the site.
A supported downstream remains one ordinary Git repository without submodules or gitlinks and does not require a persistent Dump Things or metadata service for validation, review, build, or publication.
The stateless GitHub authentication and comment service is the hosted decision transport, not a metadata runtime dependency.

Prefer released upstream acquisition, matching, serialization, and update helpers.
In particular, reuse `things-enrichment-tools` ownership-aware update helpers when their data model and pinned runtime are compatible.
A local replacement MUST have focused parity tests and a documented reason it remains local.
The pinned source Things Schema and exact `dlthings:*` CURIE spellings remain authoritative.

The accepted qualified-assertion resolution keeps the ownership algorithm upstream rather than forking it.
An adapter would build an ephemeral enrichment view in which companion PAV is attached to its selected assertion objects in the compact string form understood by the pinned helper, run that helper unchanged, and then split machine PAV back into companions while retaining every semantic assertion object in the record.
The RDF-validation join's expanded annotation objects MUST NOT be passed directly to the current helper because its owner matching does not recognize that representation.
The split and join MUST be inverse for supported machine PAV.
The only local semantic normalization is the locked-schema shape already required by HR-208: explicit `AttributeSpecification` type, string lexical value, datatype `range` for native non-string data, and no `schema_type` on `Statement`.
Typed normalization must also be reversible in the ephemeral helper view so an unchanged typed assertion remains idempotent.

The pinned upstream reference points map directly onto this contract:

- Dump Things [validation and curated storage](../submodules/dump-things-service/dump_things_service/curated.py) supply the schema-gated curated-state model;
- Dump Things [`order_dict()` and `json2yaml()`](../submodules/dump-things-service/dump_things_service/utils.py) define canonical mapping and list ordering;
- the [inbox/curation model](../submodules/dump-things-service/WHAT_IS_IT.md) supplies the proposal-versus-curated-state separation;
- the [GitAudit backend](../submodules/dump-things-service/dump_things_service/audit/gitaudit.py) supplies record diff plus author/curator/time audit semantics; and
- enrichment-tools [machine annotation rules](../submodules/things-enrichment-tools/docs/machine_annotations.md) and [ownership-aware updates](../submodules/things-enrichment-tools/things_enrichment_tools/__init__.py) supply PAV, idempotence, human priority, and multi-enricher behavior.

The local runtime remains pinned to the exact [Things Schema contract](explaining-schema-issues.md).

## Required deviations from German upstream

| Upstream pattern | Orinoco Lite deviation | Reason and status |
| --- | --- | --- |
| Dump Things inbox and curated collection | Pull-request branch and reviewed default branch | Required for a static ordinary-repository deployment. |
| Persistent schema-validating service | Locked local/CI validation of Git-backed YAML | Intentional; static operation must not require a service. |
| Scraper/importer/enricher are distinct roles | `source adapter` is a local umbrella | Naming convenience only; specific upstream terms remain preferred. |
| Positive proposals move through an inbox | Git diff contains proposed Things directly | Required for native pull-request metadata review. |
| PAV annotations are stored inline in each Thing | Records retain every semantic assertion object, while only PAV is stored in a parallel annotation companion and reattached before validation or RDF export | Keeps provenance out of record diffs while preserving the same semantic graph and avoiding a second metadata store. |
| Rejected inbox proposals do not enter curated GitAudit history | The proposal DataLad commit remains in default-branch history after rejection | Required to preserve the single-PR execution and decision record; public retention is disclosed. |
| No durable negative-decision state | Compact reject/defer cache | Required Orinoco feature to avoid repeated human review. |
| Separate per-record GitAudit log | Record Git history plus PID-keyed cache and review commit | Avoids a duplicate audit store while retaining human attribution. |
| Service records curator and author IDs | Reviewer is Git author; bot is committer | Host-specific equivalent of the upstream distinction. |
| Enrichment tools do not use DataLad as semantic provenance | DataLad records proposal and Pixi-applied metadata changes | Orinoco execution provenance only; not claimed as upstream alignment. |
| Ownership-aware helpers preserve populated topical data and allow differently owned qualified values to coexist | Store qualified assertions as canonical record content, split only PAV into companions, and limit visible replacement to behavior performed by the pinned helper | Avoids inferring ownership for a direct scalar or making pull-request acceptance a permanent scalar-update fork. |
| Enrichment deletion is limited by assertion ownership; generic deletion remains unresolved | An adapter may propose whole-record deletion | The visible Git deletion and human decision replace service-side ownership gating. |
| `pav:importedFrom` may include source-version information | PAV uses the stable logical source record and DataLad records the exact revision | Separates semantic source identity from execution coordinates without losing reproducibility. |
| Compact scalar PAV annotations | The ephemeral update view uses compact PAV, while the joined validation/RDF view uses expanded annotation objects | The pinned helper recognizes compact ownership and the pinned converter requires expanded annotations for lossless round trips. The conversion is transient and parity-tested. |
| Service curation API and authorization model | Hosted stateless review application and mechanical GitHub Action application | Required GitHub profile; GitHub remains authoritative and the human remains the decision authority. |

Implementation status is recorded separately in the non-normative [source-adapter implementation report](../reports/source-adapter-implementation-gaps.md).

Implementations MUST preserve commit history, attribute each bot commit to its triggering human, and avoid inventing semantic overlays beyond the defined annotation overlay.
