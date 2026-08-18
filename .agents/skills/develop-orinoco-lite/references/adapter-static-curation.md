# Adapter, provenance, mapping, and static curation

Use this model to reason about adapter work, then verify which pieces the active
repository has implemented. Do not invent a universal decision-file schema from
this guidance.

## Separate the state classes

| State | Authority | Evictable? |
| --- | --- | --- |
| HTTP responses, pool indexes, diagnostics, match acceleration | Ignored cache or build state | Yes |
| Captured source snapshot used as review evidence | Declared source input with repository-defined retention | Only by its retention policy |
| Execution and content history | Git or DataLad record | No |
| Accepted semantic assertions and their origin | Supported Things records under canonical metadata | No |
| Human accept, reject, link, defer, or supersede decisions | Tracked, site-owned curation policy | No |
| Published semantic mappings | One declared canonical mapping authority | No |

The phrase "files used solely for source matching belong to the adapter" applies
to operational lookup material. It does not make durable human dispositions or
published ontology mappings disposable adapter cache.

Keep adapter-specific policy beside the site-owned adapter while it is truly
adapter-specific, for example under a locally defined
`source-adapters/<name>/policy/`. Propose a shared, site-owned curation root only
after multiple adapters demonstrate the need. Never put site decisions in a
template-owned support path merely because the framework reads them.

## Use a two-phase static review transaction

Model the flow as:

```text
proposal = propose(source snapshot, base metadata, policy, prior decisions)
final tree = apply(source snapshot, base metadata, policy, explicit decisions)
```

1. Capture or select an immutable-enough source snapshot.
2. Generate candidates and a focused review report without deciding for the
   human.
3. Have the human explicitly accept, reject, link, defer, or supersede each
   in-scope candidate.
4. Record those decisions in tracked site-owned state.
5. Apply the decisions to canonical metadata and attach supported provenance to
   accepted assertions.
6. Validate the latest reviewed branch head and prove idempotence.

Prefer one review pull request containing the proposal review, explicit decision
state, and final application when local permissions allow. Separate commits for
machine proposal, human decisions, and application can make authorship and
reproduction clearer.

If every proposal is rejected, prepare and preserve a decision-only pull request
for human review and merge. Closing the proposal or producing no metadata diff
does not preserve the decision. A bot may transport an explicit human decision
to the branch or open a fallback decision pull request; it must not infer the
choice, approve, merge, or deploy.

## Key decision memory semantically

Default a decision's scope to an unchanged semantic proposal, not merely a run
identifier or raw byte hash. A useful adapter-specific design normally includes:

- readable source namespace and stable source entity identifier;
- candidate or claim kind;
- versioned semantic fingerprint over fields material to the decision;
- adapter matching or policy version;
- disposition and link target, when applicable;
- reviewer, date, rationale, and supporting evidence;
- invalidation or re-review rule;
- superseded decision reference, when applicable.

Specify normalization and fingerprint fields. Exclude volatile retrieval times,
ordering noise, and irrelevant display changes. A material source change should
normally mark the old decision stale and return the candidate to review. A
permanent entity-level suppression needs a separate explicit scope and rationale.

Treat absence of a decision as pending, never as rejection. Fail visibly on
ambiguous duplicate decision keys, stale link targets, contradictory decisions,
and policy entries that were expected to be consumed but were unused.

## Distinguish provenance from disposition

Use the exact vocabulary and shapes supported by the selected Things schema.

- Git or DataLad records the command, inputs, base, and resulting content change.
- PAV describes origin and responsible import or derivation of accepted values,
  objects, attribute specifications, or reified statements. Apply it at the
  narrowest supported assertion level when fields have different origins.
- PROV can express richer activity, entity, and agent lineage when that extra
  model is justified. Do not duplicate Git history without a consumer need.
- A human disposition describes what to do with a proposal. It is not PAV or
  PROV provenance attached to a record that does not exist.

Use `retrievedFrom`, `importedFrom`, and `derivedFrom` according to their actual
semantics. Do not call a transformation mere retrieval. Verify current upstream
helper behavior and schema support before selecting properties or shapes.

## Distinguish matching from semantic mapping

Keep four concepts separate:

1. operational matching from a source record to a possible canonical record;
2. a reviewed identity or link decision used by an adapter;
3. an ontological mapping asserted as site knowledge;
4. provenance of an accepted assertion.

SSSOM is an interchange model for mappings between semantic entities. It can
carry mapping predicates, justification, authorship, confidence, tooling, and
source versions. It is not a proposal-disposition ledger. Do not use
`NoTermFound`, a negated mapping, or a false semantic relation to mean "a human
rejected adding this source record."

Use SKOS mapping predicates only for their semantic meaning. If Things mapping
slots and an SSSOM mapping set both exist, declare one canonical and generate or
validate the other. Do not hand-maintain equivalent mappings in two authorities.

## Require behavioral tests

Test at least:

- identical base, inputs, policy, and decisions produce no second diff;
- an unchanged rejected proposal is suppressed;
- a material proposal change becomes stale and returns to review;
- a matching or policy version change follows an explicit invalidation rule;
- no decision remains distinguishable from rejection;
- an accepted link resolves to exactly one valid target;
- ambiguous identity evidence never creates or links an entity automatically;
- stale, contradictory, and expected-but-unused policy fails visibly;
- deleting every ignored cache cannot erase decisions or alter semantics;
- the all-rejected case produces durable decision state with no metadata record;
- accepted assertion provenance survives serialization and projection;
- generated SSSOM and Things mappings agree when both are emitted.

Also compare behavior with the exact pinned upstream helpers. If current upstream
adds a relevant feature, characterize and test it before proposing pin adoption.
