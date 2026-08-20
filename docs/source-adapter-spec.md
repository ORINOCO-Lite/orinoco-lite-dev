# Orinoco Lite source-adapter specification

Status: draft reference for review; intended to supersede [`source-adapters.md`](source-adapters.md) after acceptance

This document defines a host-neutral source-adapter contract and the GitHub profile that Orinoco Lite will implement first.
It is intentionally narrower than the exploration in [`source-adapters.md`](source-adapters.md).
It does not define a Python ABI, plugin protocol, or persistent service.

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
Later programmatic metadata changes MAY also use DataLad through the project's Pixi tasks.
Direct human changes are ordinary Git commits.

The reviewed default branch is the curated state.
A proposal branch is the service-free equivalent of an upstream inbox.

## Authorities and state

| Concern | Authority | Rule |
| --- | --- | --- |
| Canonical metadata | `metadata/records/` | Every file except the source-control marker is a schema-valid Thing. |
| Metadata change | Git diff | The proposal diff is the review payload; it MUST NOT be duplicated in a tracked inventory. |
| Machine assertion provenance | PAV annotations in the Thing | Identify the importing adapter and source record. |
| Human decision | Adapter-owned compact decision cache | Preserve accepted, rejected, and deferred current decisions. |
| Human modification | Attributed Git commit, host comment, or review bundle | Preserve the human actor and resulting metadata diff. |
| Execution provenance | Git commit, optionally recorded by DataLad | Record a programmatic metadata-changing command when requested. |
| Review history | Git commits and host review history | Preserve prior record and decision-cache states. |
| Scratch state | Ignored `build/` content | Never determine or replace a human decision. |

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
Each source claim MUST bind a stable source-record identifier to a content hash of the material source facts.
A source-level version such as a Git commit or Zotero library version SHOULD also be recorded when available.
Historical source payloads MAY be retained, but the specification never requires a full source snapshot.
Historical reacquisition is not a conformance requirement: the identifier, source version, content hash, proposal diff, and review history are sufficient evidence of what was reviewed.

### Candidate plan

The adapter MUST deterministically derive an ephemeral candidate plan before writing metadata.
Each candidate contains at least:

- a stable source namespace and source-native record identifier;
- the target canonical PID and record path;
- a human-readable label;
- the baseline and proposed Thing, or an explicit deletion;
- a versioned digest of material source facts and relevant adapter policy; and
- any condition that blocks acceptance.

The plan drives proposal generation, form rendering, and submission validation.
It MUST be reproducible and MUST NOT be tracked.
Full records, opaque candidate IDs, transaction IDs, or copies of Git diffs MUST NOT be stored as review provenance.
Internal digests MUST NOT be the primary human identifier.

### Proposal

Given identical source, base, policy, and active decisions, proposal output MUST be deterministic and idempotent.
It MUST change only proposed Things under `metadata/records/`.

The proposal MUST be created by one project-locked `datalad run --explicit` invocation.
The run record MUST remain inline in a distinct commit; a DataLad sidecar is not used.
The recorded command MUST name the adapter, exact source coordinate, relevant inputs, base, and `metadata/records/` output.

The proposal's DataLad commit and every later review commit MUST survive as distinct commits in default-branch history.
A rebase may rewrite its commit ID while preserving its message and diff.
Squashing it into another commit is not conformant.

### Decisions and cache

The system supports three dispositions for any proposed addition, modification, or deletion:

- `accept`: apply the reviewed change, including any attributed human edits;
- `reject`: restore the baseline and suppress the same unchanged claim;
- `defer`: restore the baseline and ask again on the next proposal.

Absence, an unchecked form, pull-request closure, workflow failure, or a missing cache entry is never a decision.
A blocked candidate MUST NOT be accepted.

The cache is current state, not an append-only event log.
It MUST be owned by the adapter under `source-adapters/<adapter>/policy/curation-decisions.yaml`.
Git history is the history of prior cache states.

The compact representation MUST store:

- once per review: the exact source coordinate, reviewer, review time, and review URL; and
- once per current record decision: canonical PID, source-native record ID, claim digest, disposition, and review reference.

It MUST NOT contain baseline or proposed records, rendered diffs, candidate or decision event graphs, run manifests, or duplicated batch metadata.
Re-review replaces the current entry; the prior entry remains available through Git.

An unchanged rejection remains suppressed.
A material source change or change to relevant policy MUST reopen review.
An accepted record with no resulting metadata change is not proposed again.
Deferral always returns on the next proposal.
There is no separate permanent-exclusion disposition: rejection persists until the material claim or relevant policy changes.
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
Unrelated human edits do not acquire source PAV or a source-candidate cache entry merely because they share the branch.

A direct human commit is already its own execution and attribution record.
When automation applies a comment, patch, or bundle, the project Pixi task MUST support recording that operation with `datalad run --explicit`.
The user MAY select ordinary Git instead.
The command SHOULD record an input identifier and content hash when available, but the input payload need not remain in the final tree or Git history.
DataLad is not useful for a decision-cache-only commit.

Finalizing review MUST:

1. require exactly one valid disposition for every current candidate;
2. verify the form's stable source identifiers and content hashes against the initial proposal commit;
3. retain all attributed human metadata edits on the review branch;
4. apply the reviewed change for accepted candidates;
5. restore rejected and deferred candidates;
6. update no durable review artifact other than the compact decision cache; and
7. validate the complete resulting metadata tree.

If finalization changes metadata, the same Pixi task MUST support optional DataLad recording.
For each bot commit, the most recent authenticated human whose action triggered the operation is the Git author and automation is the committer.
Compact commit trailers MUST identify the adapter, exact source coordinate, review URL, and review time.

Accepted record bytes may exist only in the earlier proposal commit.
The record's Git history, its PID-keyed cache entry, and the review commit together form the per-record human audit.
A record MUST NOT be rewritten solely to make it appear in the review commit.

Automation MUST NOT choose a disposition, mark a review ready, approve, merge, deploy, or write to the external source.

Before merge, corrections remain on the same review branch and add attributable commits; finalization is rerun against the new head.
After merge, a correction starts a new adapter run and pull request from the reviewed default branch.

### Update and ownership behavior

Adapters MUST apply the upstream machine-ownership rules: a machine update does not silently overwrite a human- or differently owned assertion.
When a whole-record proposal would replace such content, the complete loss or change MUST remain visible in the Git diff and require explicit acceptance.

An adapter MAY propose deletion for any record.
The Git diff and form MUST make the deletion explicit, and acceptance or rejection is a human decision like any other proposed change.
The final metadata tree MUST still pass schema and relationship validation; the adapter does not need a separate lifecycle-ownership or source-completeness protocol.
Two adapters may target the same Thing, but each works from the current reviewed base and maintains its own source identity and decisions.
No global field-ownership registry is implied.

## Semantic provenance

Accepted imported records MUST use upstream PAV terms:

- `pav:importedBy` identifies the adapter; and
- `pav:importedFrom` identifies the logical source record.

The pinned runtime requires expanded annotation objects containing `annotation_tag` and `annotation_value`.
Adapters MUST use that representation and prove JSON-to-RDF-to-JSON and projection round trips with the locked Things Schema.

Semantic machine provenance belongs in the canonical Thing because the upstream Things model includes this PAV annotation pattern.
It is not moved into an Orinoco-specific provenance file.

Every machine-provided assertion MUST carry assertion-level PAV.
Imported objects such as `attributed_to`, `identifiers`, and `generated_by` carry annotations directly.
Imported scalar data is represented by annotated `AttributeSpecification` objects in `attributes`, using the upstream enrichment pattern; a topical scalar slot MAY remain when required by the schema or presentation.
A record-level annotation MAY supplement but MUST NOT replace assertion-level provenance.

An assertion created by a human or downstream policy rather than present in the external source is not imported source data and MUST NOT receive the adapter's PAV annotation.
Examples include a manually resolved identity, an eligibility decision, or a locally chosen relationship.
When a human changes a machine-provided assertion, the resulting human assertion MUST lose the adapter's PAV annotation unless it still states exactly the imported source fact.
The adapter may report a later upstream conflict but MUST NOT silently reclaim ownership.

`pav:importedBy` MUST reference a versioned Thing/PID describing the adapter or enricher, matching upstream practice.
Changing the adapter incompatibly requires a new versioned agent Thing.

The exact source revision belongs in Git/DataLad review provenance.
The PAV source may remain the stable logical record URI.
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
- a merge method that preserves every proposal, review, and finalization commit.

The adapter core is host-neutral.
No second host implementation is required until the GitHub profile is complete, but another host may implement the same contract without adopting GitHub-specific files or APIs.

### GitHub profile

The initial supported profile MUST:

- start from a default-branch `workflow_dispatch` and open one draft pull request;
- show proposed Things in **Files changed**;
- render one task-list group per record in the pull-request body, headed by a friendly label, canonical PID, and useful source-native identifier;
- support attributed comment suggestions, direct metadata commits, and SHACL Vue bundle application on the same branch;
- accept a complete form through an exact `/curation submit` comment;
- treat the authenticated submitter as the reviewer attesting the whole form;
- accept submissions only from collaborators with `write` or `admin` access;
- load executable workflow and adapter code from the trusted default branch;
- treat the pull-request branch and source checkout only as data while a write token is available;
- verify the form against the initial proposal, preserve later attributed human metadata changes, and validate the resulting tree before applying decisions;
- restrict changes to declared metadata and decision-cache paths;
- push against the exact observed head with a lease; and
- dispatch normal validation without approving, merging, or deploying.

In a public repository, proposed metadata remains visible in Git history even when review later rejects it.
The workflow MUST disclose that retention and require an explicit acknowledgment before proposing public data.
Secrets and data that are not approved for repository history MUST be excluded before the proposal commit.

Reviewers MUST NOT need a local checkout.
Local execution MAY expose the same deterministic operations for development and reproduction.

Adapter review pull requests MUST use a commit-preserving merge method.
Under a linear-history policy, use rebase merge; do not squash.
When the host supports merge-method controls, it MUST disable or forbid squash merging for adapter pull requests.

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
- A new durable artifact requires a source or human state that Git, PAV, and the compact decision cache cannot represent.
- A stronger attacker or availability model requires a separate reviewed design rather than incremental workflow machinery.

## Repository and dependency boundaries

Concrete adapters and their policy are site-owned under `source-adapters/<adapter>/`.
Scratch state belongs under ignored `build/`.
Adapters MUST NOT store decisions beneath `metadata/` or write source-adapter state to `.orinoco-lite/provenance/`.

An adapter MAY have its own locked environment when its acquisition or transformation dependencies differ from the site.
A supported downstream remains one ordinary Git repository without submodules or gitlinks and does not require a persistent Dump Things service for validation, review, build, or publication.

Prefer released upstream acquisition, matching, serialization, and update helpers.
In particular, reuse `things-enrichment-tools` ownership-aware update helpers when their data model and pinned runtime are compatible.
A local replacement MUST have focused parity tests and a documented reason it remains local.
The pinned source Things Schema and exact `dlthings:*` CURIE spellings remain authoritative.

The concrete upstream reference points are the Dump Things [inbox/curation model](../submodules/dump-things-service/WHAT_IS_IT.md), its [GitAudit backend](../submodules/dump-things-service/dump_things_service/audit/gitaudit.py), the enrichment-tools [machine annotation rules](../submodules/things-enrichment-tools/docs/machine_annotations.md), and the pinned [schema contract](explaining-schema-issues.md).

## Required deviations from German upstream

| Upstream pattern | Orinoco Lite deviation | Reason and status |
| --- | --- | --- |
| Dump Things inbox and curated collection | Pull-request branch and reviewed default branch | Required for a static ordinary-repository deployment. |
| Persistent schema-validating service | Locked local/CI validation of Git-backed YAML | Intentional; static operation must not require a service. |
| Scraper/importer/enricher are distinct roles | `source adapter` is a local umbrella | Naming convenience only; specific upstream terms remain preferred. |
| Positive proposals move through an inbox | Git diff contains proposed Things directly | Required for native pull-request metadata review. |
| No durable negative-decision state | Compact reject/defer cache | Required Orinoco feature to avoid repeated human review. |
| Separate per-record GitAudit log | Record Git history plus PID-keyed cache and review commit | Avoids a duplicate audit store while retaining human attribution. |
| Service records curator and author IDs | Reviewer is Git author; bot is committer | Host-specific equivalent of the upstream distinction. |
| Enrichment tools do not use DataLad as semantic provenance | DataLad records the proposal and optionally later programmatic edits | Orinoco execution provenance only; not claimed as upstream alignment. |
| Compact scalar PAV annotations | Expanded annotation objects | Required by the pinned converter for lossless round trips. |
| Service curation API and authorization model | Hosted task-list review and mechanical bot application | Required GitHub profile; the human remains the decision authority. |

## Current implementation gaps

These are gaps to close, not permitted variants of the specification:

- current adapters use stable URNs rather than versioned adapter Things for `pav:importedBy`;
- direct scalar imports rely on record-level PAV instead of upstream-style annotated attributes;
- Zotero has record-level rather than assertion-level PAV;
- the GitHub workflow does not yet support comment-applied edits, direct SHACL Vue bundle application, or deletion proposals; and
- Pixi review-application tasks do not yet expose optional DataLad recording; and
- the hosted merge path does not yet enforce preservation of every DataLad and human-review commit.

## Remaining review questions

The following details are deliberately not settled by this draft:

1. Should optional DataLad recording of review edits be enabled by default in the hosted GitHub workflow, or only exposed as an explicit reviewer choice?
2. Should squash merging be disabled repository-wide, or enforced only for adapter pull requests through the strongest host rule available?
3. When a human changes a machine-imported assertion, is removing its PAV annotation sufficient, or should the schema also record explicit human authorship on that assertion?

Until these questions are resolved, implementations MUST preserve commit history, attribute each bot commit to its triggering human, and avoid inventing additional provenance stores.
