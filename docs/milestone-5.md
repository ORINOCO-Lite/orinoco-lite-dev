# Milestone 5: durable static source-adapter curation

Status: proposed; planning only

Planning parent: `68b0ec1e0d70b9247d94091ae0754550074ae14e`

Predecessor: [`milestone-4.md`](milestone-4.md)

Decision register: [`milestone-5-decisions.md`](milestone-5-decisions.md)

Acceptance record: [`milestone-5-acceptance.md`](milestone-5-acceptance.md)

Detailed architecture: [`source-adapters.md`](source-adapters.md)

## Outcome

Milestone 5 is proposed to demonstrate that two materially different static source adapters can remember explicit human dispositions across runs, preserve execution and assertion provenance, reopen materially changed candidates safely, and complete review in one ordinary-repository pull request without a persistent service.

Zotero is the reusable-looking case.
`dump-research-info` is the deliberately CON-specific case.
Shared storage, serialization, CLI, engine, template, or upstream behavior is extracted only when both demonstrations justify it.

Milestone 4 remains the accepted distribution while this plan is reviewed.
Activating Milestone 5, naming its implementation branches, or changing the current-work instructions requires a separate reviewed change.

## Exact planning baseline

| Surface | Coordinate | Authority for Milestone 5 |
| --- | --- | --- |
| Planning parent | `68b0ec1e0d70b9247d94091ae0754550074ae14e` | Accepted exploration policy at plan time; not a released adapter interface |
| Engineering `main`, observed 2026-08-18 | `fe01e297d3d22d1690bf891b40eaab36595cea9e` | Public-main ancestor of the planning parent |
| Orinoco Lite | [`v0.1.12`](https://github.com/con/orinoco-lite-dev/releases/tag/v0.1.12); tag object `b28987ba1dc8085344529ea8d4d0742848b646c0`; source `dd19a61489ba14c8f47a8baf33ab3c65bde0db47` | Supported public runtime and configuration contract 2 |
| Orinoco Lite release artifacts | wheel `7bcba4c4124873d5a985233c4fef84aa3cd3902dfa401bbdfefb951785c36173`; runtime `0d43cf6b3db4c324777a373c7d2178ab8dcdaf224795f19b4ce2c16e8f114a5a`; manifest `4751bab7bfe5fa65bdc95499aff05a77b48de2f7f194270293865d6f25ab200f` | Immutable released-interface digests |
| Things Schema | `cb6c791aec4c5309775437df4bd58e94e1bfcc3c`; profile `demo-research-information/unreleased` | Supported schema pin |
| Dump Things service | `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf`; release `6.3.6` | Supported package dependency; the running service remains optional |
| Dump Things service advisory tag, observed 2026-08-18 | `6.3.7`; tag object `31e00603dba18345fdbff7d64a46150dc53bc4ca`; source `d65d9b09a4d70fb127e0858a7cfae57be0a08d91` | Unadopted changelog-only drift; not a supported pin |
| Dump Things Python client | `1e79391195ad4412286344189dc5f81a06accb90` | Engineering and parity evidence only |
| Query Things | `ef1141430a471455d4a5f4e07d7989ec717f56f4` | Engineering query and parity baseline |
| Things enrichment tools | reviewed pin `2e6a5ddc92928a6165b81fdae24a52c447967c7d` | Engineering comparison/parity pin and optional reuse candidate; not a runtime or downstream dependency |
| Things enrichment tools upstream, observed 2026-08-18 | `6023b026576f6ffb0d7677146c1b729bb8d7fb8c` | Advisory drift candidate, not an accepted pin |
| Zotero fixture | public group `6197458`; library version `451`; 197 top-level items | Reviewed source evidence |
| `dump-research-info` | `062da59cb5a00ca128b3df895426a54088bfc625` | Reviewed CON-specific adapter evidence |
| Test consumer, observed 2026-08-18 | `1d7962720eaa3021ffe0a6cd52ac0694be47cffd`; template `v0.1.14`; engine/runtime `0.1.12`; workflow `fe01e297d3d22d1690bf891b40eaab36595cea9e` | Complete downstream baseline |
| Template source release, observed 2026-08-18 | `v0.1.15`; tag object `ca8c78070e7a9fed291db662c43026d2cac65ac4`; source `bea66d916da3791fe3820498aca676c8b64a585d`; checked-in generated tree `e48b02823f6d257fcbfb8a2687186d766496121e` | Current Copier-source release; not yet adopted by the observed consumer |
| Published `github-template` branch, observed 2026-08-18 | `92ce600d2a0428169d94d9ad71bd438230d48558`; generated for `v0.1.14` | Current published template branch; distinct from the `v0.1.15` source release |
| Source-adapter defaults | M4-I015 and HR-207 at the planning parent | Accepted project policy, not yet a released adapter interface |

There is no baseline SSSOM implementation, decision serialization, candidate-inventory format, reconciliation protocol, or common adapter ABI.
Those remain evidence questions.
The immutable `v0.1.12` release and observed consumer lock support the runtime classification above; Milestone 5 activation must copy their exact release and lock evidence into the acceptance record before relying on it.
Development and operations skills are navigation guidance only: installing or invoking one is not a runtime requirement or acceptance evidence, and no interface exists merely because a skill describes it.

## Inherited boundaries

Milestone 5 preserves the accepted Milestone 4 architecture:

- reviewed YAML under `metadata/records/` remains the sole canonical metadata pool;
- concrete adapters and their site policy remain site-owned under `source-adapters/`;
- a downstream remains one ordinary Git repository with no submodules or gitlinks;
- validation, build, review, and deployment require no persistent metadata service;
- caches, stores, credentials, generated output, and browser artifacts remain ignored;
- human review is authoritative, and automation never infers a disposition, approves, merges, or deploys pull-request code;
- the real `centerforopenneuroscience.org` repository remains read-only; and
- open identity, publication, venue, topic, eligibility, governance, and production decisions remain open.

HR-207 and M4-I015 additionally require unchanged rejection suppression, re-review after relevant material or policy change, an explicit return condition for deferral, and explicit human scope for permanent exclusion.
Adapters may configure source-specific identity and fingerprint inputs without weakening those safety properties.

## Implementation sequence and gates

### 1. Freeze executable baselines

- Create isolated worktrees in the engineering, template, consumer, and adapter repositories that are actually changed.
- Record the exact Zotero source fixture, `dump-research-info` revision, current consumer and template releases, upstream pins, commands, and expected corpus counts.
- Reproduce the existing adapter tests and the complete Milestone 4 consumer contract before changing behavior.
- Separate live-source or authoritative-head drift from changes to reviewed pins.

Gate: clean checkouts reproduce the baseline without a live-source, credential, git-annex, or persistent-service dependency.

### 2. Define implementation-neutral behavior vectors

- Define fixtures for stable source identity, claim kind, material fingerprints, relevant policy versions, explicit dispositions, deferral return, permanent scope, linking, supersession, and stale decisions.
- Define how reviewer identity, rationale, and evidence are recorded for an auditable decision without choosing who is authorized to approve.
- Treat storage under `source-adapters/<name>/policy/`, serialization, command names, and candidate-inventory transport as prototypes rather than contracts.
- Escalate public-repository privacy or retention choices to the human-review queue if concrete source data makes them policy decisions.

Gate: both adapters can express the same safety outcomes while retaining source-specific identity and material-field rules.

### 3. Build the Zotero vertical slice

- Consume an exact source snapshot, current metadata, adapter policy, and prior decisions.
- Produce deterministic candidates and proposed Things with appropriate PAV assertion provenance.
- Record explicit accept, reject, link, defer, supersede, and permanent-scope cases without writing to Zotero or inventing identities.
- Reconcile the decisions into final metadata and prove an idempotent rerun.
- Produce an all-rejected branch-local result whose durable state is decision-only.

Gate: a deterministic branch-local proposal, decision, and reconciliation slice works without a bot or service; the real review and merge transaction remains step 5.

### 4. Prove the same invariants with `dump-research-info`

- Run the CON-specific adapter from a literal relative checkout path and exact revision.
- Demonstrate the same candidate and disposition behavior without copying Zotero-specific identity rules or storage assumptions.
- Exercise source changes, policy changes, deferral return, stale decisions, and overlap with another adapter.
- Preserve unresolved content-policy cases as unresolved rather than minting or linking automatically.

Gate: both adapters satisfy the shared behavior vectors independently.

### 5. Prove the static review transaction and provenance split

- Exercise proposal, explicit human disposition, recorded reconciliation, final-head review, and one reviewed default-branch transition.
- Fail closed on missing, stale, malformed, contradictory, or unexpected transaction-local decisions.
- Retain dormant historical dispositions according to the reviewed retention rule when a source record legitimately disappears; never discard them merely because they are unused by one run.
- Test interrupted reconciliation, safe recovery, and the repository's actual merge mode so sufficient run evidence survives squash or rebase behavior.
- Keep Git and DataLad as execution evidence, PAV on imported assertions, and tracked decisions as human-disposition state.
- Add W3C PROV only if a demonstrated lineage question is not answered by those layers.

Gate: every candidate has one valid outcome, failure cannot silently publish a partial result, and the merged state is deterministic and reproducible.

### 6. Test semantic mapping only where real evidence exists

- Keep entity resolution and record linkage separate from ontology mapping.
- For a genuine semantic-mapping case, compare Things mapping slots with A Simple Standard for Sharing Ontological Mappings (SSSOM).
- Choose one tracked authority and derive any alternate representation.
- Do not encode rejection as a negated mapping or use SSSOM as a record-deduplication key.

Gate: any retained mapping representation round-trips without duplicate hand-maintained authority.

### 7. Compare and decide extraction or distribution

- Compare both vertical slices and decide whether evidence justifies shared semantics only, a shared test suite, a serialization, a CLI, an engine helper, a template-managed adapter, an upstream contribution, or no common contract yet.
- Review the observed enrichment-tools drift through the normal pinned-upstream and parity process before advancing any gitlink.
- Make engineering, template, and consumer changes in their owning repositories and review them separately.
- Run cross-platform and clean-clone acceptance through the released interfaces before claiming support.

Gate: every extracted contract has two-adapter evidence; otherwise the accepted result remains adapter-specific.

## Required acceptance evidence

The detailed matrix lives in [`milestone-5-acceptance.md`](milestone-5-acceptance.md).
At minimum it must prove:

- unchanged rejected claims are not proposed again;
- already accepted unchanged records are not proposed again, and accepted changes reconcile idempotently;
- non-material source changes, unrelated policy changes, and run identifiers do not reopen or re-key a decision;
- material source or relevant policy changes reopen review;
- deferral returns only on its declared condition;
- permanent exclusion requires explicit broad scope;
- absence or pull-request closure is never interpreted as a decision;
- linking to an existing record prevents duplicate creation and ambiguity fails closed;
- all-rejected runs leave reviewed decision state on the integration consumer's default branch with no metadata addition;
- proposal, explicit decision, reconciliation, and final-head review occur on one pull request without a required follow-up pull request or bot;
- caches and diagnostics can be deleted without changing decisions;
- an adapter rerun cannot overwrite an explicit human disposition;
- candidate inventories and decisions are not ingested or projected as Things unless M5-Q002 explicitly accepts the required schema, privacy, and publication model;
- a normal framework update preserves site-owned decisions and crosswalks;
- identical inputs and decisions yield an identical inventory and no further metadata diff;
- PAV survives reconciliation, schema JSON/RDF round-trip, and the machine record projection without requiring public page or graph exposure;
- overlap between adapters remains visible and reviewable;
- the actual merge strategy and recovery path preserve sufficient execution evidence; and
- the complete consumer regression remains unchanged unless a separately accepted content decision authorizes a change.

## Repository ownership

| Repository or surface | Milestone 5 role |
| --- | --- |
| `con/orinoco-lite-dev` | Plan, exact pins, integration fixtures, parity tests, optional engine/runtime work, reusable CI, and cross-layer acceptance |
| `con/test-orinoco-downstream-website` | Initial site-owned `source-adapters/zotero/` implementation; the `dump-research-info` adapter wrapper; source snapshots; configuration, policy, and decisions; and actual review transactions |
| `con/dump-research-info` | External source records, acquisition and source-specific transforms, and focused source tests; consumer-owned adapter and curation state do not move here |
| `con/orinoco-lite-template` | No speculative changes; receive only behavior demonstrated by both adapters and accepted for distribution |
| Evaluated upstream Things projects | Candidate schema, query, serialization, and PAV-aware update primitives; adopt only an exact pin with parity evidence, and contribute later generally useful behavior when justified |
| `centerforopenneuroscience.org` | Read-only evidence only |

## Non-goals

Milestone 5 does not:

- modify or graduate the production site;
- write to Zotero;
- require a persistent Dump Things service, authenticated editor, new bot credential, automatic approval, automatic merge, or routine follow-up pull request;
- resolve identity, DOI/version, venue, topic, eligibility, approver, hosting, or production policy;
- establish a universal deletion or field-ownership rule;
- make human decisions public Things without an explicit M5-Q002 schema, privacy, and publication decision;
- freeze a storage root, serialization, fingerprint algorithm, CLI, Python ABI, or host protocol before both adapters demonstrate it;
- use SSSOM as a rejection ledger or generic entity-resolution standard;
- create a generic projection registry or plugin system; or
- promote `dump-research-info` into a generic adapter.

## Exit gate

Milestone 5 is complete when both adapters provide reviewed evidence for identity, disposition, transaction, provenance, failure recovery, and idempotence; M5-Q001 through M5-Q004 and M5-Q007 have reviewed outcomes; M5-Q005 and M5-Q006 have either reviewed outcomes or an explicit not-activated result; any genuine mapping case has one authoritative representation; all activated human choices are recorded in both the human queue and this milestone's source register; and cross-repository acceptance passes from clean clones.

A new common adapter contract or release is optional.
If the two examples do not justify one, an evidence-backed decision to keep them adapter-specific is a valid Milestone 5 outcome.
