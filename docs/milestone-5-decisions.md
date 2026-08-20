# Milestone 5 decision register

Status: architecture accepted; implementation evidence pending

Original planning parent: `68b0ec1e0d70b9247d94091ae0754550074ae14e`

Normative contract: [`source-adapters.md`](source-adapters.md)

Human policy choices remain in [`human-review-decisions.md`](human-review-decisions.md).
Commands, hashes, releases, and pull-request evidence belong in [`milestone-5-acceptance.md`](milestone-5-acceptance.md).
This register summarizes reviewed engineering outcomes without duplicating the normative specification.

## Accepted decisions

| ID | Outcome | Consequence |
| --- | --- | --- |
| M5-D001 | The Git metadata diff is the proposal and the candidate plan is ephemeral. | No tracked candidate inventory, duplicate review document, or retained source snapshot is required. |
| M5-D002 | Each adapter owns one compact current-state decision cache under `source-adapters/<adapter>/policy/curation-decisions.yaml`; Git stores its history. | The cache records accepted, rejected, and deferred claims without baseline/proposed records or an event graph. |
| M5-D003 | Git commits are the review transaction. DataLad records the proposal and programmatic metadata changes; a merge commit preserves the reviewed lineage. | Custom journals, transaction-recovery machinery, sidecars, reports, and attestations are prohibited. Linear-history-only downstreams are not supported. This supersedes M4-I008 for a conforming source-adapter consumer. |
| M5-D004 | The authenticated reviewer confirms the complete decision state. The hosted GitHub App posts on the user's behalf, the Action derives identity from the comment event, and the most recent triggering human is the Git author of a bot-applied change; automation is the committer. | The compact cache and Git/host history retain reviewer, time, source coordinate, and review URL without trusting browser-supplied identity or deciding who may approve production content. |
| M5-D005 | Git and DataLad record execution and review history; PAV records machine assertion provenance. | Additional W3C PROV is not activated without a demonstrated unanswered lineage query. |
| M5-D006 | No ontology-mapping representation is activated by Milestone 5. | SSSOM is used only if a genuine mapping set later requires it; rejection, identity linkage, and deduplication are not mappings. |
| M5-D007 | The host-neutral contract, shared canonicalizer, annotation-overlay join, and GitHub profile are common Orinoco Lite behavior. Concrete adapters and policy remain site-owned. | No generic Python ABI, plugin framework, persistent adapter service, or second host implementation is required. |
| M5-D008 | Canonical semantic metadata is stored in `metadata/records/` plus `metadata/overlays/annotations/` and joined before validation or RDF export. | Human-facing record diffs remain readable while the resulting graph preserves upstream PAV semantics. Another overlay requires a focused specification change. |
| M5-D009 | The supported GitHub decision interface is a deployed web application backed by a minimal stateless GitHub App user-authorization service; trusted workflow output and pull-request Markdown provide the actual diff, accessible summary, and fallback. | The service reads only GitHub proposal objects and posts the complete proposal- and head-bound decision payload as the user; it runs no adapter or source logic, stores no metadata or curation state, and never commits, approves, merges, deploys, or writes to a source. GitHub Actions regenerates candidate facts and remains the trusted commit boundary. |
| M5-D010 | Annotation joining follows the pinned upstream distinction between object, data, and class-range assertions. Class-range URI assertions become annotated `Statement` objects; non-string topical data retains its native type and uses a schema-typed lexical value only in the derived `AttributeSpecification`. | The overlay preserves assertion-level PAV without turning URI relationships into literals or coercing stored metadata to strings. Focused upstream-parity and locked RDF round-trip tests are required. |

## Refined inherited defaults

M5-D001 through M5-D010 refine M4-I003, M4-I008, M4-I014, and M4-I015 and implement HR-201, HR-207, and HR-208 for source-adapter operation.
All other accepted Milestone 4 boundaries remain in force, including the ordinary-repository topology, no-persistent-service requirement, human review authority, site-owned adapter policy, and read-only real-site boundary.

## Superseded exploration

The following are not dormant requirements and must not be restored without a focused specification change:

- tracked candidate inventories or full-record review bundles;
- append-only decision events or transaction graphs;
- `link`, `supersede`, permanent-exclusion, or conditional-deferral dispositions;
- custom reconciliation journals, locks, crash recovery, reports, or artifact attestations;
- squash- or rebase-compatible substitutes for preserving the original DataLad commit; and
- speculative template distribution, plugin APIs, or additional semantic overlays.

Implementation ambiguity is handled by stopping for clarification, not by adding another authority, artifact, or threat model.
