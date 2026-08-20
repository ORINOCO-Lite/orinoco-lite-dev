# Milestone capability map

This map answers a narrow maintenance question: which Milestone 1–3 results are part of the supported Milestone 4 stack, which remain engineering checks, and which were intentionally superseded?
It is an audit of carried behavior, not a replacement for the historical evidence.

## Result

Most Milestone 1–3 achievements are present in Milestone 4 at the correct abstraction layer.
The complete accepted content and supported static-site behavior moved into an ordinary downstream repository, while the reusable implementation moved into the engine, runtime, template, and locked consumer facade.

The audit did find one active gap: the service-backed upstream stack is a required engineering integration capability, but its 19 direct contract assertions were no longer exercised from `main`.
The scoped upstream tasks restore those 14 service tests and five integration-contract successors in an isolated environment.
This closes the engineering execution gap without making a metadata service a downstream runtime dependency.

## Carried into the supported product

| Earlier result | Milestone 4 successor |
| --- | --- |
| Repository-owned Things metadata and relationship closure | One `metadata/records/` inventory containing all 199 Things; declarative policy selects 186 editor records and 185 pages |
| Schema validation and native relationship closure | Locked engine validation against the pinned source Things Schema and exact `dlthings:*` contract |
| Deterministic qri/Hugo projection | Generic declarative projection: 199 records, 185 record pages, 186 graph nodes, and 467 native edges |
| Static output after ephemeral validation | Root-relative local builds and absolute project-path Pages builds, with no persistent service |
| Full CON content rather than a sample | All accepted metadata, editorial sources, assets, provenance, and publication integration evidence |
| Static credential-free editing | Public catalog, browser review-bundle export, commit/path/digest-bound application, validation, projection, and rollback |
| Project-path browser behavior | Chromium and WebKit graph, route, editor, download, and credential-scrub contracts |
| Read-only Zotero integration | Captured source evidence, 23 active consumer successors, and exact publication-transform parity |
| Reviewable generated output | Ignored projection regeneration, stale-output rejection, deterministic double builds, and source-only metadata diffs |
| Local/offline operation | Digest-addressed asset hydration followed by OS-level denied-network validation, projection, build, and editor checks |

The M4 traceability baseline maps 106 parent Python methods, five Playwright definitions with nine browser executions, 42 Zotero methods, and eight editor methods with no unmapped source assertion.
The complete details and immutable coordinates remain in [`milestone-4-acceptance.md`](milestone-4-acceptance.md).
Counts in that historical evidence use the former 186-canonical/13-reference filesystem vocabulary; configuration contract 2 supersedes it with one 199-record input tree without changing the accepted content.

## Retained as engineering capability

These capabilities remain useful for component development, compatibility checks, and upstream work, but are not required to build or host a downstream site:

- the exact static Psychoinformatics reference deployment, including Congo and annex hydration;
- the pool UI, SHACL Vue, Things Schema, Dump Things service, and local annex transport;
- public/protected collection seeding and editor write-confinement checks;
- component gitlinks, preservation history, release assembly, and cross-repository acceptance evidence; and
- the schema and LinkML investigations that explain the pinned type-designator and recursion workarounds.

The recorded upstream tasks restore the parent gitlinks automatically and fail closed on modified component worktrees.
The parallel worktree tasks preserve candidate commits and dirty edits so a cross-repository update can be tested before its gitlinks become the next recorded stack.
The ordinary pull-request matrix checks both platforms without depending on mutable live pool data; a manual workflow dispatch performs the live recorded full-stack deployment on a selected parent ref.
`diff-upstream-pool` compares the prepared cache with the current public pool without replacing either, so maintainers can distinguish data drift from a component regression before recording a new stack.

## Intentionally superseded

The following were milestone mechanisms rather than durable product interfaces:

- a submodule-based CON website checkout as the supported downstream topology;
- unqualified root `build` and `serve` tasks whose meaning mixed CON migration and upstream service work;
- the engineering repository's temporary Pages preview branch;
- a browser token or persistent metadata service for ordinary static review;
- production content sourced from an ephemeral service store rather than reviewed Git inputs; and
- generated churn mixed into hand-authored content commits.

Their evidence and rollback refs remain preserved.
They should not be reintroduced into the consumer facade.

## Known limits

The static recorded reference deployment is reproducible from Git and annex pins.
The full service-backed stack pins its software repositories and locked tool environment, but its ignored public-pool snapshot is fetched live on a fresh checkout and reused by digest afterward.
Milestone 3 measured 4,978 public records; the 2026-08-14 check measured 4,979.

Consequently `check-upstream` is a known-software-stack compatibility test, not yet a bit-for-bit reconstruction of a permanent public-pool dataset.
Making that stronger would require an explicitly licensed, immutable snapshot artifact plus its URL and digest; silently committing or republishing the live pool is not part of this change.

The historical modeling deferrals also remain real: native qualified roles, typed DOI/ISSN records, and a durable upstream repair for recursive Pydantic range generation were investigated but not invented downstream.
Milestone 4 preserves their constraints and uses narrow compatibility boundaries rather than claiming those upstream issues are solved.

## Removal rule for historical machinery

Historical scripts may leave the active task surface only when all of the following hold:

1. their supported product behavior has a traceable engine, template, or consumer successor;
2. any still-useful engineering behavior has a scoped isolated task and active contract;
3. accepted commits, refs, provenance, and decision records remain reachable; and
4. the replacement is exercised from a clean recorded checkout.

Under that rule the old CON-coupled root environment can remain historical, while the static and full upstream modes stay supported engineering tools.

## Next engineering goal

The draft [`source-adapter specification`](source-adapters.md) generalizes the cache-versus-live semantic comparison without moving source-specific policy into the engine or template prematurely.
Its first reusable candidate is Zotero; the CON-specific `dump-research-info` experiment supplies design evidence but does not define a common host or a generic adapter.
