# Milestone 3 implementation acceptance

Status: implementation complete; draft human review open

**Historical acceptance record.** Its counts and review evidence remain authoritative for Milestone 3, but its preview branch is not the current distribution interface.
See [`milestone-4-acceptance.md`](milestone-4-acceptance.md) and the current [`open decisions`](../open-decisions.md).

This report accepts the Milestone 3 implementation as the review candidate.
It does not accept the site's content on behalf of its maintainers, merge the draft pull request, or authorize a production-domain cutover.

## Published review surfaces

- Preview: <https://con.github.io/orinoco-lite-dev/>
- Static editor: <https://con.github.io/orinoco-lite-dev/edit/>
- Draft parent pull request: <https://github.com/con/orinoco-lite-dev/pull/4>
- Representative person: <https://con.github.io/orinoco-lite-dev/persons/yaroslav-halchenko/>
- Representative project: <https://con.github.io/orinoco-lite-dev/projects/datalad/>
- Representative publication: <https://con.github.io/orinoco-lite-dev/publications/datalad-joss-2021/>

No component pull request was opened.
The component branches exist only so a public recursive checkout can resolve the exact parent gitlinks.

## Accepted implementation pins

| Component | Branch | Accepted commit |
| --- | --- | --- |
| Parent coordinator | `codex/milestone-3` | recorded by the draft PR head |
| CON site | `codex/milestone-3` | `26907c487efaa2c31bba9d02398aa201ab6f774b` |
| Zotero ingestion | `codex/milestone-3-zotero` | `062da59cb5a00ca128b3df895426a54088bfc625` |
| Pool UI wrapper | `codex/milestone-3-dependency-refresh` | `93961ace8d4ceaea088ccc04526a9bc5428139a6` |
| SHACL Vue | `codex/milestone-3-dependency-refresh` | `3be33196f0eb7a65817df78b88ea40ecbb5eca11` |

The immutable clean-migration checkpoints remain named and exact:

- parent `codex/clean-migration` at `f54cf5fdb2b5ae4bf03fe6939246316fd9ec818d`; and
- site `codex/clean-migration` at `a122e506de9e4a13473edbe8d74a950d74032a16`.

The workflow fetches only those named checkpoint refs and rejects a missing or moved checkpoint before building the successor.

## Publication migration result

The reviewed source is public Zotero group `6197458`, library version 451.
The capture contains five collections and 197 top-level items.
The deterministic selection uses 134 items, excludes 55 items in `External`, and leaves eight unfiled items out of the public promotion.

The ingestion yields 126 publications, 20 publication-venue candidates, four datasets, and three instruments.
The site promotes all 126 publications, one reviewed Neuroimaging topic, and the required bibliographic reference closure.
Venue candidates remain ingestion evidence because the source's generic publishing placeholder is not a canonical native activity.

The final projection contains:

- 186 canonical and 13 reference records;
- 186 graph nodes and 467 native edges; and
- 185 rendered record pages.

The evidence preserves six DOI duplicate groups, 1,817 unresolved creator observations covering 1,221 names, 42 venue observations, and 49 topic observations covering 36 tags.
These are review queues, not silently invented records.

## Static preview and editor result

The Pages deployment is backend-free.
It contains no Dump Things service, browser credential, service token, GitHub token, `CNAME`, or production-domain redirect.
Generated edit links open the static SHACL Vue bundle under the Pages project path.

SHACL Vue loads digest-bound public records and shapes, saves changes only to an in-memory review queue, and downloads an RDF review bundle.
The checked-in local helper verifies the site commit, source digest, PID, class, path, schema, native relationship closure, and clean checkout before showing or applying canonical YAML changes.
It does not create a branch or pull request.

Canonical YAML and downloaded patches belong to the upstream-derived site branch in `centerforopenneuroscience.org`.
That branch remains rebasable onto reviewed `www-from-model` changes, while the repository's unrelated legacy CON branches and tags remain permanently reachable without being merged into the active ancestry.
The parent gitlink is the normal version pin for this site component within the larger coordinating repository.
Publishing the same public YAML in the editor catalog is accepted as an intentional convenience for bulk access and reuse.

Playwright covers the project-path navigation, record load, edit, save, download, and local dry-run validation.
It also proves that the browser sends no write request and ignores or removes service-token state in static mode.

## Dependency result

The dependency refresh reduces 23 original package findings to zero production findings.
Four findings remain in the development-only stable VitePress documentation chain: three moderate and one high.
There is no supported stable upgrade or automatic fix; forcing VitePress 2 alpha or an out-of-range Vite is not accepted.
Question M3-Q017 records the human exception.

The production build, lockfile, unit tests, documentation build, Markdown sanitization regression, external-URL guard, and parent browser tests pass.
The wrapper independently builds the editor twice and rejects byte differences.

## Reproducibility and hosted evidence

The final gate uses a public recursive clone with an empty home directory, no system or global Git configuration, no credentials, no ambient Git identity, and no interactive authentication.
It verifies every one of the 28 recursive gitlinks and all public component origins, then builds and exercises the Pages artifact.

Two editor builds and two complete Pages builds are byte-identical.
The branch checkout and detached recursive checkout produce the same editor and Pages trees.
Profile-local presentation overrides use the reviewed source images directly rather than invoking Hugo's platform-dependent responsive-image encoder, so Linux and macOS do not generate competing derived pixels.
The Engage page loads lightweight poster previews and leaves the preserved print-resolution artwork behind explicit links.
Quicklink prefetching is disabled for the CON profile and rejected by the artifact audit, so those large originals remain click-driven.

The final local gate produced two identical 144-file editor bundles and two identical 444-file Pages artifacts.
The backend-free site subset has digest `2c88cd971b5ba90c47d1a6a49bfc45636baac7336c3de1116f7de3128f5b3442`; the complete pre-publication payload has digest `18abe466822a8a2d95d47f2a4b60eeac81e2e9630e4aaa05e2a9da73b17c631e`.
Hugo processed zero images, while the 186-node graph and 185 edit routes remain unchanged.

The uploaded archive includes the audited root dotfiles so its file counts and hashes match `publication.json`.
Pull-request runs build and upload an artifact but cannot enter the deploy job.
Pushes to the temporary review branch deploy through the protected `github-pages` environment.

## Bounded technical debt

The following issues are intentionally visible for the broader human review:

- the editor still requests the Roboto font from Google, so the preview is backend-free but not fully offline or independently archived;
- four development-only VitePress audit findings await a supported stable dependency line;
- sixteen annex-backed assets depend on exact read-only remote objects, and the unavailable Chris Markiewicz portrait uses the declared neutral fallback;
- creator, venue, topic, hidden-person, and duplicate-publication reconciliation remains bounded by the source evidence described above;
- applying a multi-record editor bundle is safe per file but not a transactional all-or-nothing filesystem operation; and
- the single Pages environment is a shared branch preview, not a distinct URL for every pull request.

These items do not require a persistent service and do not block content review.
They must not be misrepresented as resolved production policy.

## Human decisions still required

The complete decision register is [`milestone-3-decisions.md`](milestone-3-decisions.md).
In particular, maintainers must decide:

- which unresolved creators, venues, tags, duplicates, and supporting people to promote;
- whether named Pages deployment reviewers are required;
- whether to remove the temporary milestone-branch deployment after merge;
- whether the external font and development-only advisory exceptions are acceptable; and
- whether, after separate content approval, this preview should move toward the production custom domain.

The safe defaults remain fail-closed.
None of these questions authorizes hosted authentication, automatic pull-request submission, Zotero writes, DNS changes, or production cutover.

## Completion statement

Milestone 3 is implementation-complete and ready for comprehensive human review.
The draft pull request remains deliberately unmerged and the preview remains a review deployment.
Human content acceptance and production policy are the next phase, not implicit consequences of this technical acceptance.
