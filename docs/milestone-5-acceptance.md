# Milestone 5 acceptance record

Status: proposed milestone; execution not started

Planning parent: `68b0ec1e0d70b9247d94091ae0754550074ae14e`

Plan: [`milestone-5.md`](milestone-5.md)

Decision register: [`milestone-5-decisions.md`](milestone-5-decisions.md)

This record will accumulate immutable commands, source coordinates, fixture digests, pull-request heads, platform results, and cross-repository release evidence after Milestone 5 is activated.
Planning statements and local discovery do not satisfy an acceptance gate.

## Baseline evidence to record at activation

| Surface | Required evidence | Status |
| --- | --- | --- |
| Engineering | exact implementation base, parent branch, clean worktree, and test command | pending |
| Released interface | immutable `v0.1.12` release assets, checksums, consumer lock, and any later reviewed update | pending |
| Zotero | public group, library version, normalized snapshot digest, adapter revision, and current behavior | pending |
| `dump-research-info` | exact source revision, literal relative path, adapter revision, and current behavior | pending |
| Consumer | exact commit, lock, template release, complete corpus counts, and current CI | pending |
| Template | exact source release and generated-template commit | pending |
| Upstream | reviewed gitlinks, observed authoritative heads, and classified drift | pending |
| Platforms | macOS 14 ARM64 and Linux x86-64 clean-checkout results | pending |

## Required behavior matrix

For each case, record the adapter, exact inputs and policy version, proposal command and digest, explicit human disposition, reconciliation command, final tree or commit, rerun result, platform, and review coordinate.

| Case | Required result | Zotero | `dump-research-info` |
| --- | --- | --- | --- |
| No prior decision | Candidate remains visible for explicit review. | pending | pending |
| Accepted unchanged record | Positive-state deduplication prevents a redundant proposal. | pending | pending |
| Accept disposition | Intended metadata is reconciled and the next identical run is idempotent. | pending | pending |
| Unchanged rejection | The same materially unchanged claim is not proposed again. | pending | pending |
| Non-material source change | Rejection remains effective and the candidate is not reopened. | pending | pending |
| Material source change | The changed claim returns for review with the prior decision identified as stale. | pending | pending |
| Unrelated policy change | Rejection remains effective and the candidate is not reopened. | pending | pending |
| Relevant policy change | The affected claim returns for review. | pending | pending |
| Run-identifier change | Stable candidate identity and the prior decision remain unchanged. | pending | pending |
| Deferral | The candidate returns only when its declared condition is met. | pending | pending |
| Permanent exclusion | Suppression occurs only within explicit human scope. | pending | pending |
| Link to existing | The valid target is used and duplicate creation is prevented. | pending | pending |
| Ambiguous link | Reconciliation fails closed without minting or guessing. | pending | pending |
| Supersede disposition | Only the intended active decision and record relationship remains. | pending | pending |
| All rejected | A reviewed decision-only transition reaches the integration consumer's default branch with no metadata addition. | pending | pending |
| Missing disposition | Reconciliation fails closed; absence is not interpreted as rejection. | pending | pending |
| Pull-request closure or abandoned proposal | A later run treats the candidate as undecided unless an explicit disposition was merged. | pending | pending |
| Malformed decision | Validation fails with a focused diagnostic. | pending | pending |
| Contradictory decisions | Validation fails with a focused diagnostic. | pending | pending |
| Stale transaction-bound decision | Validation fails or explicitly reopens review without applying the stale result. | pending | pending |
| Source disappearance | Historical dispositions follow the reviewed retention rule and are not silently discarded as unused. | pending | pending |
| Unexpected transaction-local decision | Validation fails while legitimate dormant historical dispositions remain valid. | pending | pending |
| Identical rerun | Candidate inventory is identical and reconciliation produces no further diff. | pending | pending |
| Deleted cache | Decisions and reconciled metadata remain unchanged. | pending | pending |
| Adapter rerun | Explicit human dispositions cannot be overwritten by generation. | pending | pending |
| Metadata boundary | Candidate inventories and decisions are not ingested or projected as canonical Things unless an accepted M5-Q002 decision supplies the schema, privacy, and publication contract. | pending | pending |
| Framework update | Site-owned decisions and crosswalks survive a normal Copier update unchanged. | pending | pending |
| Adapter overlap | Both proposals and the resolved order or outcome remain reviewable. | pending | pending |
| One-PR transaction | Proposal, explicit human decision, reconciliation, and final-head review occur on one pull request without a required follow-up pull request or bot. | pending | pending |
| Interrupted reconciliation | The partial run cannot be mistaken for an accepted final state and recovery is repeatable. | pending | pending |
| Actual merge mode | The default-branch result preserves enough execution evidence to reproduce the final state. | pending | pending |
| PAV round-trip | Imported assertion provenance survives reconciliation, schema JSON/RDF round-trip, and the machine `records.jsonl` projection; public page and graph exposure remains projection policy. | pending | pending |
| Decision audit fields | Required reviewer identity, rationale, and evidence survive reconciliation and merge; missing or invalid required fields fail with a focused diagnostic. | pending | pending |

If M5-Q002 proposes a versioned durable serialization and declares any predecessor supported, add migration and backward-compatibility evidence for every such predecessor before accepting M5-Q002, whether or not a release follows.

## Conditional mapping evidence

No SSSOM implementation or profile is accepted at the planning baseline.
If a genuine ontology or concept mapping case is selected, record its canonical authority, derived representation, predicates, justification, provenance, round-trip result, and proof that rejection or entity resolution was not encoded as a mapping.

Status: not selected.

## Cross-layer release evidence

Before Milestone 5 can claim a supported shared contract, record:

- the accepted M5 decision IDs that authorize it;
- engineering, template, and consumer pull requests with immutable reviewed heads;
- released engine and runtime coordinates if those artifacts change;
- template source and generated-tree coordinates if the downstream facade changes;
- clean-clone macOS ARM64 and Linux x86-64 results through released interfaces;
- complete consumer regression counts and any separately authorized content changes; and
- rollback coordinates.

No common interface, release, template change, upstream contribution, or production operation is accepted yet.

## Unconditional milestone-exit evidence

Whether the implementations remain adapter-specific or produce a shared contract, record:

- reviewed proposal and reconciliation pull-request heads and final trees for both adapters;
- the complete behavior matrix above;
- M5-Q001 through M5-Q004 and M5-Q007 outcomes, plus an outcome or explicit not-activated result for M5-Q005 and M5-Q006;
- clean-clone results on macOS 14 ARM64 and Linux x86-64;
- complete consumer regression results and any separately authorized content changes;
- all activated human-policy resolutions in both required registers; and
- rollback coordinates for every changed repository.

Status: pending.
