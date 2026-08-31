# Milestone 3: publications and public preview

Status: implementation complete; draft human review open

**Historical milestone record.** Milestone 4 supersedes this document's branch, preview, and operating instructions.
Preserve it as derivation evidence; use [`milestone-4.md`](milestone-4.md) for current architecture and [`human-review-decisions.md`](human-review-decisions.md) for open questions.

Parent branch: `codex/milestone-3`

Site branch: `codex/milestone-3`

Accepted base: [`milestone-2-acceptance.md`](milestone-2-acceptance.md)

Decision register: [`milestone-3-decisions.md`](milestone-3-decisions.md)

Dependency review: [`milestone-3-dependencies.md`](milestone-3-dependencies.md)

Static editor workflow: [`milestone-3-editor.md`](milestone-3-editor.md)

## Outcome

Milestone 3 makes the populated CON site representative enough for broad human review.
It adds the maintained CON Zotero publication feed through a repeatable API ingestion boundary, publishes a GitHub Pages project preview, and provides a credential-free static editing handoff that produces reviewable local input for a pull request.

This milestone publishes a preview, not the production CON website.
It does not change DNS or the custom domain and does not add hosted authentication or a persistent metadata service.

## Workstreams

### Public Zotero API ingestion

Use public Zotero group `6197458` as the maintained publication intake source.
The ingestion implementation must:

- read through Zotero Web API v3 without credentials for the public library;
- follow API pagination and record the library version, item versions, collection membership, item keys, response metadata, and capture time;
- produce a deterministic, committed source snapshot and a separately generated candidate set;
- preserve source observations before duplicate resolution or semantic promotion;
- apply only reviewed exact creator mappings and fail unresolved identity closed;
- report excluded collections, duplicate DOI groups, unsupported item types, unresolved venues, missing identifiers, and unmodeled creators;
- promote reviewed publications and only semantically connected venue and reference records into the canonical site profile with provenance; and
- never write to Zotero as part of normal ingestion or CI.

An API refresh proposes a source and canonical change.
It never updates the site implicitly.

### GitHub Pages preview

Publish the parent repository at the GitHub Pages project path `https://con.github.io/orinoco-lite-dev/` using a pinned GitHub Actions workflow.
The workflow must:

- initialize every pinned submodule commit from a publicly readable GitHub remote;
- use the locked Pixi runtime and exact Node, Hugo, Python, and Git Annex dependencies;
- hydrate only the declared site asset manifest through read-only remotes;
- verify the committed projection and assembly digests;
- build and audit the project-path artifact;
- include the production SHACL Vue bundle and static editing inputs under `/orinoco-lite-dev/edit/`;
- upload one immutable Pages artifact and deploy it through the GitHub Pages environment; and
- avoid secrets, writable metadata services, custom domains, and production redirects.

### Static editing handoff

The preview editor may display and modify the public committed records in the browser.
It must operate without a service token and must not claim to submit a change directly.

The supported handoff is:

1. open a record through its preview edit link;
2. edit and validate it through SHACL Vue;
3. download an RDF review bundle;
4. apply that bundle in an authenticated local checkout through a checked-in validation helper; and
5. inspect the canonical YAML diff before committing or opening a pull request.

The browser receives no GitHub credential.
Direct pull-request creation, OAuth, GitHub Apps, hosted tokens, and branch-protection policy remain a later milestone.

Canonical CON content lives in the upstream-derived branch of `centerforopenneuroscience.org` and remains rebasable onto reviewed `www-from-model` changes.
The repository also preserves its unrelated legacy branches and tags without merging them into that ancestry.
`orinoco-lite-dev` coordinates this site and its other submodules through deliberate gitlink pins.

### SHACL Vue dependency refresh

Update the pinned pool UI and nested SHACL Vue dependencies, commit the exact lockfile, run the upstream unit/build suite and the parent Playwright suite, and record any advisory that cannot be removed without an unsupported behavior change.
Do not weaken browser security controls to make the update pass.

## History and publication policy

The accepted `codex/full-con-migration` parent and site branches do not move.
The Milestone 3 site branch drops and later regenerates the terminal projection commit around reviewed hand-authored batches.

Required submodule commits may be pushed to their existing account or CON GitHub mirrors so a clean parent checkout can resolve each gitlink.
They do not receive pull requests in this milestone.

After complete acceptance:

1. push the exact submodule branches;
2. update and verify the parent gitlinks;
3. push parent `codex/milestone-3` to `con/orinoco-lite-dev`;
4. open one draft PR against parent `main`;
5. configure the parent repository's Pages source as GitHub Actions; and
6. verify the public preview and downloadable editing handoff.

## Acceptance

Milestone 3 is complete when:

- a fresh public Zotero API capture is byte-reproducible after normalization and its source/library versions are recorded;
- every promoted publication passes source-schema validation, JSON-to-RDF-to-JSON round trips, reference closure, native relationship, and dangling-target checks;
- source observations, canonical decisions, exclusions, duplicates, and unresolved records have separate provenance;
- the terminal projection is regenerated twice byte-identically;
- root and project-path static builds are byte-identical on repetition and contain no German entity routes or graph nodes;
- the production SHACL Vue build has a committed lockfile and the dependency audit has no unreviewed high or critical finding;
- Playwright proves that a preview record can be edited without a token and downloaded as RDF without a network write;
- the local application helper rejects unrelated, unknown, invalid, and stale bundles and produces only the intended canonical YAML changes;
- a disposable public clone resolves every pushed gitlink and reproduces the Pages artifact;
- one draft parent PR exists, no submodule PR exists, and the Pages preview is publicly reachable; and
- all required human decisions are enumerated in the decision register and PR description.

## Deferred

Milestone 3 does not include:

- automatic or authenticated browser creation of GitHub branches or pull requests;
- OAuth, GitHub Apps, hosted write tokens, or production authorization;
- production-domain cutover, DNS, redirects, or replacement of the legacy site;
- automatic writes to Zotero;
- a persistent public Dump Things service;
- final resolution of every creator, venue, asset, or hidden-person ambiguity;
- grants, CVs, annual reports, or secondary projections; or
- a broad upstream template fork.

## Implementation checkpoint

The reviewed public capture is Zotero library version 451 with 197 top-level items in five collections.
The deterministic transform currently yields 126 publications, 20 venue candidates, four datasets, and three instruments.
The site promotes all 126 publications, one reviewed topic, and the required bibliographic reference closure.

The 20 venue candidates remain in the ingestion evidence rather than becoming disconnected site records.
The source relates them through a generic publishing placeholder rather than a canonical native activity.
Typed ISSNs remain on the publications, and the unresolved activity/venue decision remains visible in the decision register.

The candidate site projection contains 186 canonical records, 13 reference records, 186 graph nodes, 467 native edges, and 185 rendered record pages.

The implementation, publication evidence, and bounded debt are recorded in [`milestone-3-acceptance.md`](milestone-3-acceptance.md).
The draft pull request and public preview are review surfaces; this status does not imply final human content approval or a production cutover.
