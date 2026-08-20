# Orinoco Lite source-adapter specification

Status: draft reference for review

This document defines a host-neutral source-adapter contract and the GitHub profile that Orinoco Lite will implement first.
It does not define a Python ABI, plugin protocol, or persistent service.
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
| Metadata records | `metadata/records/` | Store reviewable, user-facing Things without inline machine-source annotations. |
| Machine assertion provenance | `metadata/provenance/` | Store PAV companions; joining both metadata trees produces the complete semantic Things graph. |
| Metadata change | Git diff | The proposal diff is the review payload; it MUST NOT be duplicated in a tracked inventory. |
| Human decision | Adapter-owned compact decision cache | Preserve accepted, rejected, and deferred current decisions. |
| Human modification | Attributed Git commit, host comment, or review bundle | Preserve the human actor and resulting metadata diff. |
| Execution provenance | DataLad run commit | Record each Pixi task that programmatically changes metadata. |
| Review history | Git commits and host review history | Preserve prior record and decision-cache states. |
| Scratch state | Ignored `build/` content | Never determine or replace a human decision. |

The two metadata trees are canonical site-owned state.
Generated projections, candidate plans, caches, diagnostics, and hosted form renderings are not canonical metadata.

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
Before the proposal commit, every stored record and every Thing produced by joining its provenance companion MUST pass the complete automated validation supported by the locked Things Schema and runtime.
Validation failures are diagnostics to correct, not review dispositions or durable candidate state.
Each source claim MUST bind a stable source-record identifier to a content hash of all and only the normalized source facts that can affect its proposed metadata.
Transport metadata and unused source fields MUST NOT affect that hash or reopen review.
A source-level version such as a Git commit or Zotero library version SHOULD also be recorded when available.
Historical source payloads MAY be retained, but the specification never requires a full source snapshot.
Historical reacquisition is not a conformance requirement: the identifier, source version, content hash, proposal diff, and review history are sufficient evidence of what was reviewed.

### Canonical ordering

One shared canonicalizer MUST order and serialize every record and provenance companion written by an adapter.
Adapters MUST NOT implement private YAML-ordering rules.
The canonicalizer MUST match the upstream Dump Things `order_dict()` and `json2yaml()` behavior: recursively sort mapping keys lexically and preserve list order.
It MUST be an idempotent shared library operation with focused upstream-parity tests, not a service or plugin framework.
Every record in the canonical corpus MUST already conform to that serialization.
An adapter run serializes only records it writes and does not reserialize untouched records.

Record comparison operates on canonical metadata without machine-source annotations, claim hashing on its canonical source-mapped proposal fragment, and the Git diff on deterministic record and companion serialization.
This makes formatting and unused source changes invisible while retaining meaningful source and metadata changes for review.

### Candidate plan

The adapter MUST deterministically derive an ephemeral candidate plan before writing metadata.
Each candidate contains at least:

- a stable source namespace and source-native record identifier;
- the target canonical PID and record path;
- a human-readable label;
- the baseline and proposed Thing, or an explicit deletion;
- the corresponding assertion-provenance changes; and
- the claim content hash defined above.

The plan drives proposal generation, form rendering, and submission validation.
It MUST be reproducible and MUST NOT be tracked.
Full records, opaque candidate IDs, transaction IDs, or copies of Git diffs MUST NOT be stored as review provenance.
Internal digests MUST NOT be the primary human identifier.

### Proposal

Given identical source, base, policy, and active decisions, proposal output MUST be deterministic and idempotent.
It MUST change only proposed Things under `metadata/records/` and their matching PAV companions under `metadata/provenance/`.

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
- one or more metadata commits pushed by authorized humans;
- a SHACL Vue review bundle applied by an authenticated workflow; and
- the same bundle operation invoked directly by a future SHACL Vue integration.

Human review MAY add, modify, or delete metadata beyond the original candidate plan on the same pull request.
That scope is governed by ordinary pull-request review, attribution, and final validation rather than an adapter restriction.
Unrelated human edits do not acquire a PAV companion entry or a source-candidate cache entry merely because they share the branch.

A direct human commit is already its own execution and attribution record.
When automation applies a comment, patch, or bundle, the project Pixi task MUST support recording that operation with `datalad run --explicit`.
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
7. validate both metadata trees and the complete joined Things graph.

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
Candidate derivation MUST compare assertion content independently of its provenance companion.
When an incoming assertion is semantically identical to an existing assertion, the adapter MUST preserve both and MUST NOT produce a provenance-only diff.
When an incoming assertion differs substantively, the proposal MAY replace it; an accepted replacement records the proposing adapter and source in the companion.
This rule applies assertion by assertion, so an unrelated change elsewhere in a record does not change the provenance of unchanged assertions.

An adapter MAY propose deletion for any record.
The Git diff and form MUST make the deletion explicit, and acceptance or rejection is a human decision like any other proposed change.
Deleting a record also deletes its provenance companion.
Both metadata trees and the joined graph MUST still pass schema and relationship validation; the adapter does not need a separate lifecycle-ownership or source-completeness protocol.

Two adapters may target the same Thing.
Each maintains its own source identities and decision cache, so one adapter's decision never suppresses another adapter's claim.
Each proposal MUST start from the current reviewed base.
Proposal branches that Git can merge cleanly may be merged in either order without rebasing or rerunning either adapter, provided the resulting tree validates.
If Git reports a conflict, the proposal branch MUST be recreated on the new default branch and the adapter rerun; the obsolete proposal commit is replaced rather than retained.
Assertions from different adapters may coexist in one Thing and retain their own assertion-level PAV in the joined graph.
Conflicting proposals remain ordinary visible diffs for a human to accept, reject, defer, or edit.
No global field-ownership registry is implied.

## Semantic provenance companions

Upstream stores PAV annotations inline in a Thing and therefore in the same RDF graph.
Orinoco Lite stores the user-facing record and its machine assertion provenance separately to keep record diffs readable, then joins them into the same semantic Thing before validation or RDF export.
This is a storage-layout deviation, not a different provenance model.

Adapter-generated PAV MUST be stored under `metadata/provenance/`, in a YAML companion that mirrors the record's relative path under `metadata/records/`.
One companion covers one record and contains its PID plus only its current machine assertion provenance.
It MUST NOT copy the record, retain prior states, or contain review decisions.
The top-level mapping contains exactly `record` and `assertions`.
`record` is the canonical PID and MUST match the mirrored record.

Each item in `assertions` contains exactly:

- `path`, identifying a scalar slot or collection;
- `assertion_sha256`, identifying the canonical assertion with annotations excluded;
- `pav:importedBy`, identifying the adapter; and
- `pav:importedFrom`, identifying the logical source record.

`path` uses an RFC 6901 JSON Pointer.
`assertion_sha256` is `sha256:` followed by the lowercase SHA-256 digest of the UTF-8, whitespace-free JSON serialization produced with lexically sorted mapping keys, preserved list order, and recursively omitted `annotations` keys.
For a scalar slot, the fingerprint MUST match its value; for a collection, it MUST match exactly one item.
Zero or multiple matches are invalid.
This is the complete selector model: adapters MUST NOT add private identifiers or matching rules.
Entries MUST be ordered lexically by `path` and then `assertion_sha256`.

The join operation is a shared engine function.
It attaches annotations directly to imported objects such as `attributed_to`, `identifiers`, and `generated_by`.
For imported scalar data, it produces the annotated `AttributeSpecification` required by the upstream enrichment pattern while leaving the topical scalar in the stored record.
The joined representation uses the expanded `annotation_tag` and `annotation_value` objects required by the pinned runtime and MUST pass JSON-to-RDF-to-JSON and projection round trips with the locked Things Schema.

Every machine-provided assertion MUST have a companion entry.
Assertions created by a human or downstream policy do not.
Structural `pid` and `schema_type` slots are not imported assertions.
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

The initial supported profile MUST:

- start from a default-branch `workflow_dispatch` and open one draft pull request;
- show user-facing record changes under `metadata/records/` in **Files changed**, with machine provenance confined to the mirrored companion tree;
- render one task-list group per record in the pull-request body, headed by a friendly label, canonical PID, and useful source-native identifier;
- support attributed comment suggestions, direct metadata commits, and SHACL Vue bundle application on the same branch;
- accept a complete form through an exact `/curation submit` comment;
- treat the authenticated submitter as the reviewer attesting the whole form;
- accept submissions only from collaborators with `write` or `admin` access;
- load executable workflow and adapter code from the trusted default branch;
- treat the pull-request branch and source checkout only as data while a write token is available;
- verify the form against the initial proposal, preserve later attributed human metadata changes, and validate the resulting tree before applying decisions;
- restrict changes to both declared metadata trees and the decision-cache path;
- push against the exact observed head with a lease; and
- dispatch normal validation without approving, merging, or deploying.

In a public repository, proposed metadata remains visible in Git history even when review later rejects it.
The workflow MUST disclose that retention and require an explicit acknowledgment before proposing public data.
Secrets and data that are not approved for repository history MUST be excluded before the proposal commit.

Reviewers MUST NOT need a local checkout.
Local execution MAY expose the same deterministic operations for development and reproduction.

Adapter review pull requests MUST use a merge commit.
Rebase merge and squash merge both rewrite required DataLad or human-review commits and MUST NOT be used.
The pull-request opening text MUST prominently state that requirement, and the host MUST permit an exact-commit-preserving merge method.

## Security and complexity guardrails

The supported threat model trusts collaborators who already have repository `write` or `admin` permission as authorized curators.
Branch protection, review, and GitHub's audit history govern misuse of that authority.
The workflow does not construct a cryptographic protocol against a malicious authorized collaborator.

The implementation MUST protect write credentials from untrusted source data and pull-request executable code.
Beyond that boundary:

- Git commits are the transaction and recovery mechanism.
- A failed operation is retried, corrected, or reverted.
- No custom distributed transaction, journal, lock service, or crash-recovery protocol is introduced.
- No tracked inventory, review document, exhaustive manifest, DataLad sidecar, reconciliation report, or custom attestation graph is introduced.
- No artifact is added merely to authenticate another artifact produced by the same trusted workflow.
- No provenance store beyond the single companion tree is introduced without a source or human state that Git, PAV, and the compact decision cache cannot represent.
- A stronger attacker or availability model requires a separate reviewed design rather than incremental workflow machinery.

## Repository and dependency boundaries

Concrete adapters and their policy are site-owned under `source-adapters/<adapter>/`.
Scratch state belongs under ignored `build/`.
The record and provenance trees are site-owned semantic metadata.
The companion format and join operation are an engine contract; framework updates MUST NOT overwrite companion content.
Adapters MUST NOT store decisions beneath `metadata/` or write source-adapter state beneath `.orinoco-lite/`.

An adapter MAY have its own locked environment when its acquisition or transformation dependencies differ from the site.
A supported downstream remains one ordinary Git repository without submodules or gitlinks and does not require a persistent Dump Things service for validation, review, build, or publication.

Prefer released upstream acquisition, matching, serialization, and update helpers.
In particular, reuse `things-enrichment-tools` ownership-aware update helpers when their data model and pinned runtime are compatible.
A local replacement MUST have focused parity tests and a documented reason it remains local.
The pinned source Things Schema and exact `dlthings:*` CURIE spellings remain authoritative.

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
| PAV annotations are stored inline in each Thing | Records and PAV companions are stored in parallel trees and joined before validation or RDF export | Keeps record diffs focused on user-facing metadata while preserving the same semantic graph. |
| Rejected inbox proposals do not enter curated GitAudit history | The proposal DataLad commit remains in default-branch history after rejection | Required to preserve the single-PR execution and decision record; public retention is disclosed. |
| No durable negative-decision state | Compact reject/defer cache | Required Orinoco feature to avoid repeated human review. |
| Separate per-record GitAudit log | Record Git history plus PID-keyed cache and review commit | Avoids a duplicate audit store while retaining human attribution. |
| Service records curator and author IDs | Reviewer is Git author; bot is committer | Host-specific equivalent of the upstream distinction. |
| Enrichment tools do not use DataLad as semantic provenance | DataLad records proposal and Pixi-applied metadata changes | Orinoco execution provenance only; not claimed as upstream alignment. |
| Ownership-aware helpers do not overwrite another owner | A conflicting value may be proposed but only a human can accept the replacement | Pull-request curation is the explicit ownership-migration boundary. |
| Enrichment deletion is limited by assertion ownership; generic deletion remains unresolved | An adapter may propose whole-record deletion | The visible Git deletion and human decision replace service-side ownership gating. |
| `pav:importedFrom` may include source-version information | PAV uses the stable logical source record and DataLad records the exact revision | Separates semantic source identity from execution coordinates without losing reproducibility. |
| Compact scalar PAV annotations | The joined Thing uses expanded annotation objects | Required by the pinned converter for lossless round trips. |
| Service curation API and authorization model | Hosted task-list review and mechanical bot application | Required GitHub profile; the human remains the decision authority. |

Implementation status is recorded separately in the non-normative [source-adapter implementation report](../reports/source-adapter-implementation-gaps.md).

Implementations MUST preserve commit history, attribute each bot commit to its triggering human, and avoid inventing provenance stores beyond the companion tree.
