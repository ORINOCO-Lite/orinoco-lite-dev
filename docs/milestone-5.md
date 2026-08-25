# Milestone 5: complete source-adapter support

Status: active implementation milestone

Original planning parent: `68b0ec1e0d70b9247d94091ae0754550074ae14e`

Predecessor: [`milestone-4.md`](milestone-4.md)

Normative contract: [`source-adapters.md`](source-adapters.md)

GitHub review profile: [`github-curation-review.md`](github-curation-review.md)

GitHub human-edit profile: [`github-shacl-vue-edit.md`](github-shacl-vue-edit.md)

Decision register: [`milestone-5-decisions.md`](milestone-5-decisions.md)

Acceptance record: [`milestone-5-acceptance.md`](milestone-5-acceptance.md)

## Outcome

Milestone 5 completes the Orinoco Lite source-adapter system defined by the normative source-adapter specification.
It delivers two materially different adapters, durable human decisions, upstream-compatible assertion provenance, and a complete GitHub review workflow without a persistent metadata service or required local checkout.
The hosted decision path uses a small stateless GitHub authentication application plus one expiring GitHub Actions decision-review artifact; GitHub commits and the authenticated comment remain the durable authorities.
The separate SHACL Vue path reuses that application and adds one expiring exact-head editor-input artifact without making either artifact durable state.

Zotero is the reusable-looking case.
`dump-research-info` is the deliberately CON-specific case.
Their shared behavior is the source-adapter contract; their source acquisition, transformation, identity policy, and site policy remain adapter-owned.

The specification is the design authority.
This document sequences implementation and acceptance without redefining that behavior.
If implementation exposes a material ambiguity, work stops for clarification and any resulting contract change is made in the specification first.

## Accepted foundation

Milestone 5 preserves the accepted Milestone 4 distribution unless this milestone explicitly supersedes it:

- a downstream is one ordinary Git repository without submodules or gitlinks;
- concrete adapters and their policy are site-owned under `source-adapters/`;
- static validation, build, and deployment require no persistent metadata service, while hosted source-adapter review and human editing use only the normative stateless GitHub authentication application plus their distinct untracked, expiring presentation artifacts;
- human review is authoritative, and automation never chooses a disposition, approves, merges, deploys, or writes to an external source;
- the real `centerforopenneuroscience.org` repository remains read-only; and
- open identity, publication, venue, topic, eligibility, governance, and production decisions remain open.

Milestone 5 adds two explicit distribution requirements:

- canonical semantic metadata comprises the human-facing records under `metadata/records/` and the machine-managed annotation overlay under `metadata/overlays/annotations/`; and
- a conforming downstream permits merge commits because the reviewed DataLad and human-edit commits must survive unchanged on the curated branch.

The original planning coordinates remain historical evidence.
Exact implementation bases, releases, source versions, and reviewed heads are recorded in the acceptance record when exercised rather than frozen into this plan.

## Implementation sequence

### 1. Implement the shared metadata foundation

- Implement one shared canonicalizer matching the pinned Dump Things mapping-order and YAML behavior.
- Prove parity and idempotence with focused tests.
- After that implementation is reviewed, normalize the existing metadata corpus once in a separate pull request.
- Implement the annotation-overlay format, selector validation, deterministic join, schema validation, JSON/RDF round trip, and projection behavior.
- Match pinned enrichment behavior for imported objects and qualified data and class-range assertions.
- Implement M5-D012: canonical records store the real `AttributeSpecification` and `Statement` objects, companions retain only their PAV, and the join attaches annotations rather than deriving semantic objects from scalar selectors.
- Follow the pinned helper when an equivalent assertion exists but its topical slot is missing: propose the topical convenience copy without claiming ownership or adding PAV.
- Preserve non-string topical types with schema-derived typed attribute values, and use a reversible ephemeral compact-PAV view rather than forking the pinned ownership helper.

Gate: the canonical corpus produces stable review diffs, joined records preserve the complete upstream Things semantics without exposing machine annotations in human-facing record YAML, and the reviewed HR-212 outcome has focused helper-parity, RDF, and projection evidence.

### 2. Conform both adapters

- Derive an ephemeral candidate plan from stable source identifiers, normalized metadata-affecting source facts, current canonical metadata, adapter policy, and the compact decision cache.
- Produce deterministic additions, modifications, and deletions in the record and annotation-overlay trees.
- Implement only `accept`, `reject`, and `defer` with the behavior defined by the specification.
- Store PID-keyed current decisions and only their referenced authenticated-comment review blocks in the adapter-owned compact v1 cache; rely on Git for history.
- Coalesce same-adapter source rows per PID, keep candidate PID/path fixed during review, and use correction-safe three-way reversal for rejection and deferral.
- Preserve semantically unchanged qualified assertions and their existing PAV; do not produce provenance-only changes or infer ownership from a topical scalar.
- Reuse pinned upstream validation, serialization, PAV, and ownership-aware update primitives where compatible, with focused parity tests for local replacements.
- For a source split across declared roots, select authoritative dependency records by PID, bind every root to an immutable coordinate, and reject unequal duplicates rather than choosing by input order.
- Preserve an external `Identifier.creator` Thing PID string without network resolution, following pinned qri unresolved-reference behavior; continue to require local targets for declared site-graph relationships and locally dereferenced controlled roles.

Gate: Zotero and `dump-research-info` independently satisfy the same observable contract without sharing source-specific policy.

### 3. Complete the GitHub profile

Implement the separately reviewed normative [`GitHub source-adapter curation profile`](github-curation-review.md):

- Start from a default-branch workflow dispatch and open one draft pull request containing the actual metadata proposal.
- Create the proposal with one inline `datalad run --explicit` commit and render a friendly accessible fallback and review-application link in the pull-request body.
- Provide responsive before-and-after record diffs, mutually exclusive per-record controls, a non-destructive bulk default for unresolved records, filtering, keyboard navigation, changed-only views, and complete-submission validation in the stateless hosted review application.
- Have the trusted workflow generate the actual diff and exactly one untracked, expiring, reproducible Actions presentation bundle containing source and proposal coordinates plus per-record UI facts.
- Have the application use GitHub Actions read access to load that bundle, derive candidate membership and operations from the proposal commit's metadata diff, and run no adapter or source logic.
- Keep that proposal-review artifact distinct from the SHACL Vue editor-input artifact; the latter never changes this exactly-one proposal artifact contract or enters decision finalization.
- Keep pull-request Markdown as an accessible fallback rather than a machine protocol or native-diff-size conformance boundary.
- Provide a central application origin by default while keeping the origin configurable so a downstream can self-host the same stateless implementation.
- Bind the authenticated comment submission to the repository, pull request, proposal commit, exact head, source coordinate, and complete candidate set without retaining a second proposal or decision copy in the service.
- Support attributed comment suggestions and direct human metadata commits through ordinary GitHub collaboration.
- Keep SHACL Vue proposal editing in the distinct [`GitHub SHACL Vue human-edit profile`](github-shacl-vue-edit.md) rather than making its bundle an input to this decision workflow.
- Require a complete `/curation submit` decision state, mechanically apply it, update the compact cache, and validate the resulting graph.
- Keep trusted workflow code separate from pull-request data, use exact-head compare-and-swap for automated commits, and require no local checkout from reviewers.
- Preserve every proposal and human-review commit through a merge commit; never squash or rebase the reviewed lineage.

Gate: an authorized reviewer can complete the entire workflow in one pull request, and automation neither decides nor publishes on the reviewer's behalf.

### 3a. Complete the SHACL Vue human-edit profile

- Preserve the normal **Download bundle** workflow and expose the exact generated object through a neutral browser event.
- Add **Propose via GitHub** only in the thin Orinoco wrapper.
- Have a trusted default-branch workflow publish exactly one expiring, reproducible `orinoco-shacl-vue-input-<source_sha>` artifact for each exact pull-request or current default-branch commit exposed for editing.
- Limit that artifact to `edit/config.json`, `edit/records.ttl`, and `edit/data/record-sources.json`; it is presentation input, not metadata, a generated bundle, provenance, or durable curation state.
- Have the stateless application verify the trusted workflow and exact source commit, then combine those data files only in browser memory with the generic editor shell and schema from an immutable, digest-verified runtime release.
- For an existing curation pull request, bind **Edit in SHACL Vue** to its exact head; for a standalone edit, bind to the exact current default-branch commit.
- Use the authenticated curator's GitHub identity to append one temporary bundle-only handoff commit to a same-repository draft pull-request branch.
- Have trusted default-branch Python code replace only that exact handoff commit with the equivalent canonical record and annotation-overlay commit, preserving every earlier commit.
- Validate the joined graph and add the configurable curation-service link without retaining the bundle or choosing any metadata or decision.
- Require explicit acknowledgment that the handoff contains only public-approved data and no secrets.
- Confine contents write to this explicit human proposal operation, retain no service-side copy, and add no separate Worker, conversion service, database, object store, or artifact cache.

Gate: the final branch contains the attributed human metadata commit and no handoff bundle, stale heads fail, and neither SHACL Vue nor the service gains source-adapter semantics or durable curation state.

### 4. Exercise interaction and recovery

- Prove unchanged accept and reject behavior, material-change re-review, next-run deferral, deletion, all-rejected review, human correction, and idempotent rerun.
- Exercise both adapters against overlapping and non-overlapping metadata.
- Merge clean non-overlapping proposals without regeneration.
- When Git reports a conflict, recreate the affected proposal from the new curated base and discard the obsolete proposal lineage.
- Demonstrate ordinary Git retry, correction, and revert behavior without custom transaction or attestation machinery.

Gate: failures cannot become accepted decisions, adapter runs cannot silently revert human corrections, and the final graph validates after either merge order allowed by Git.

### 5. Release and cross-layer acceptance

- Release engine/runtime changes if the canonicalizer or annotation join changes the supported runtime.
- Update the template only for behavior proven generic across both adapters; concrete adapter code and policy remain site-owned.
- Exercise clean clones on macOS ARM64 and Linux x86-64 through released interfaces.
- Record exact pull-request, release, source, merge, rollback, and regression coordinates in the acceptance record.

Gate: the complete consumer contract passes from clean clones and every distributed interface has two-adapter evidence.

## Repository ownership

| Repository or surface | Milestone 5 role |
| --- | --- |
| `con/orinoco-lite-dev` | Normative contract, shared engine/runtime support, upstream parity, releases, and cross-layer acceptance |
| `con/test-orinoco-downstream-website` | Concrete adapters, site policy, compact decisions, metadata overlays, GitHub profile, and consumer acceptance |
| `con/dump-research-info` | External source records and source-specific transforms; consumer curation state does not move here |
| `con/orinoco-lite-template` | Generic downstream support demonstrated by both adapters; no concrete adapter or site policy |
| Evaluated upstream Things projects | Preferred validation, serialization, PAV, ownership, query, and mapping primitives |
| `centerforopenneuroscience.org` | Read-only evidence only |

## Non-goals

Milestone 5 does not:

- modify or graduate the production site;
- write to Zotero or another external source;
- resolve identity, publication, venue, topic, eligibility, approver, hosting, or production policy;
- require a persistent metadata or credential service, durable hosted curation state, automatic approval, automatic merge, or pull-request deployment;
- add another semantic overlay, generic plugin ABI, persistent adapter service, or second hosted implementation;
- use SSSOM without a genuine ontology-mapping set or add W3C PROV without a demonstrated lineage question;
- retain candidate inventories, review documents, exhaustive manifests, DataLad sidecars, reconciliation reports, custom attestation graphs, or either expiring presentation artifact as durable state; or
- promote `dump-research-info` into a generic adapter.

## Exit gate

Milestone 5 is complete when both adapters satisfy the normative contract; the GitHub profile completes reviewed one-pull-request transitions; the annotation overlay survives joined schema, RDF, and projection round trips; required proposal, human-edit, and merge commits survive on the curated branch; the compact decision cache and material-change behavior pass for both adapters; and cross-repository clean-clone acceptance passes on both supported platforms.

The exact evidence required to make that claim is maintained in [`milestone-5-acceptance.md`](milestone-5-acceptance.md).
