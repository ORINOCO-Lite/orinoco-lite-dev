# Milestone 5 decision register

Status: proposed; no Milestone 5 decisions accepted

Planning parent: `68b0ec1e0d70b9247d94091ae0754550074ae14e`

This file will become the authoritative source register for reviewed Milestone 5 engineering decisions.
It does not make a prototype path, representation, or command a supported contract merely by listing it as an evidence question.

Human policy choices remain in [`human-review-decisions.md`](human-review-decisions.md).
When Milestone 5 activates such a choice, its resolution and the corresponding source-register entry must land in the same reviewed change.
Objective runs, hashes, and pull-request evidence belong in [`milestone-5-acceptance.md`](milestone-5-acceptance.md).

## Inherited accepted constraints

| Source | Milestone 5 consequence |
| --- | --- |
| M4-D001 and M4-I014 | Reviewed Things remain in one `metadata/records/` tree; generated projection remains ignored. |
| M4-D004 | A supported downstream remains one ordinary Git repository without submodules or gitlinks. |
| M4-D008 | Static validation, build, preview, and review require no persistent service. |
| M4-D010 and M4-I004 | Human pull-request review is authoritative; automation does not approve or merge. |
| M4-I003 | Concrete adapters and site policy use the existing site-owned `source-adapters/` root; no new configured root is implied. |
| M4-I015 and HR-207 | Lite supplies fixed safety defaults while adapters configure bounded source-specific identity, fingerprint, defer, and re-review inputs. |
| M4-D011 | The real site remains read-only unless a later reviewed milestone explicitly changes that boundary. |

These constraints are not reopened by Milestone 5 without new evidence and an explicit reviewed decision.

## Open engineering decision gates

| ID | Question | Evidence required before acceptance |
| --- | --- | --- |
| M5-Q001 | What represents and transports a candidate inventory, and how long is it retained? | Deterministic Zotero and `dump-research-info` proposals, all-rejected review, stale-candidate detection, public-repository privacy and history review, and no second canonical metadata pool |
| M5-Q002 | What serializes adapter decisions, and where is their long-term authority? | Both adapters, version migration, cache independence, public-repository privacy/retention review, and framework-update preservation |
| M5-Q003 | What is the supported reconciliation and merge transaction? | Complete-decision checks, interrupted-run recovery, final-head review, and evidence preserved by the actual consumer merge mode |
| M5-Q004 | How are reviewer identity, rationale, and evidence recorded without deciding who may approve? | Explicit decision evidence from both adapters and escalation of any privacy, authorization, or governance choice to the human-review queue |
| M5-Q005 | Is additional PROV activity lineage useful beyond Git/DataLad and PAV? | A demonstrated query or audit need plus schema and round-trip evidence |
| M5-Q006 | For a genuine semantic-mapping case, which representation, if any, is authoritative and should SSSOM be retained? | One real mapping set, one tracked authority, deterministic derivation, and lossless round-trip for required semantics |
| M5-Q007 | Which behavior, if any, should become a shared CLI, schema, engine helper, template adapter, or upstream primitive? | Independent evidence from both adapters and clean-clone cross-layer acceptance |

Until a gate is accepted, implementations must remain replaceable prototypes and avoid compatibility promises.
M5-Q002 does not authorize a new public configuration root, and M5-Q003 does not claim that multi-record editor transactionality is already solved.

## Decisions not authorized by this register

Milestone 5 does not infer answers about identities, publication versions, venues, topics, eligibility, approvers, hosted editing, persistent service operation, automation credentials, deployed pull-request previews, production graduation, or real-site operation.
Those remain governed by the existing human-review queue and accepted milestone decisions.
