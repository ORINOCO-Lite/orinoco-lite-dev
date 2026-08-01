# Milestone 1 progress

Status: complete — revised metadata-navigation prototype

Completed: 2026-07-31

The revised CON vertical slice is implemented at
`2621231d27b70fb425107a132159f7a9e0d99cda` on `orinoco-lite`.

- Preview: <https://leej3.github.io/centerforopenneuroscience.org/>
- Successful Pages run: <https://github.com/leej3/centerforopenneuroscience.org/actions/runs/30676418204>
- Candidate fork branch: <https://github.com/leej3/centerforopenneuroscience.org/tree/orinoco-lite>
- Original review PR 84: <https://github.com/con/centerforopenneuroscience.org/pull/84>
  (closed by its author; it was not reopened by this revision)

## What changed after the design review

The first candidate proved that an ephemeral Dump Things service, qri, Hugo,
and GitHub Pages could work together, but it did not preserve enough of
`www-from-model`'s metadata-navigation layer. The revised prototype restores
that layer selectively rather than merging upstream history:

- Hugo taxonomy and term layouts generate class lists and record pages;
- metadata relationships generate forward terms and Hugo-derived reverse
  backlinks;
- collection pages retain the upstream filter/list behavior;
- qri cache, list, inline, and render stages remain in the build;
- the pinned Things graph renderer produces a compact side graph from the same
  nodes and edges; and
- CON branding, editorial introductions, compatibility routes, and deployment
  policy remain downstream concerns.

Checked-in collection `_index.md` files now contain only editorial text and
display settings. Entity membership, labels, paths, links, backlinks, and
graph data are generated from the canonical YAML. The build rejects nested
hand-authored entity Markdown and the publication checker rejects any extra
entity route, so committed content cannot silently override metadata.

## Exit criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| A canonical change deterministically changes the preview | Met | Two baseline builds produce byte-identical manifests. A metadata-only sixth record adds one page, node, and edge without changing code, templates, routes, or indexes. |
| Selected records validate through upstream Orinoco | Met | Exact canonical record streams are posted with pinned upstream `dtc` to an ephemeral Dump Things service, then exported into qri. |
| Invalid records stop publication | Met | Nested schema-invalid input fails with the upstream `extra_forbidden` diagnostic; dangling DOI targets, route collisions, and unauthorized entity Markdown also fail closed. |
| Navigation is metadata-derived | Met | Generated class membership, forward links, reverse `.Data.Pages` backlinks, publication author/project filters, and related-record groups all derive from the validated stream. |
| The graph is part of the data and navigation contract | Met | `graph.json`, textual edge links, and the compact Sigma panel use the same generated node/edge set; the checker enforces bidirectional navigation and symmetric-edge semantics. |
| No persistent metadata service is required | Met | The service is localhost-only during a build and is always stopped; the deployed result is static. |
| Candidate files plus pinned dependencies are sufficient | Met | Pixi is the sole locked environment for Python, Hugo Extended, Node, and Orinoco tools; npm uses its checked-in renderer lock. |
| Existing large-file storage is respected | Met | Yaroslav's portrait remains its legacy git-annex MD5E object. Clean-clone CI retrieves and checks it from `datasets.datalad.org`; existing small logos remain ordinary Git objects. |
| CON-specific and reusable work remain distinguishable | Met | `UPSTREAM.md` and the provenance manifests classify exact copies, adaptations, local policy, schema compatibility, and assets. |
| Production remains unchanged | Met | The legacy `master`, production `CNAME`, DNS, and domain deployment were not changed. Only the fork's `orinoco-lite` Pages workflow publishes. |

## Acceptance evidence

The locked local contract completed successfully after the final source
changes:

- baseline: 5 metadata pages, 6 graph edges, 21 Hugo pages, 52 files, and 594
  checked internal links;
- identical repeat build with the same manifest;
- extension fixture: 6 metadata pages, 7 graph edges, 22 Hugo pages, 53 files,
  and 630 checked internal links;
- upstream schema-invalid fixture rejected;
- dangling URL/DOI target rejected by the generic relationship boundary;
- duplicate route and hand-authored entity-route fixtures rejected; and
- the pinned LinkML discriminator reproducer fails in the documented way.

The local browser check also confirmed that the graph initializes without
console errors, occupies a small 4:3 side panel on desktop, exposes an
accessible relationship-link alternative, and follows record links. The
publication list filters by Yaroslav's generated author metadata, and the
DataLad page shows its forward person relationship and reverse instrument,
organization, and publication backlinks.

## Build and source boundaries

The ordinary publication build now has six scripts with distinct roles:

1. `build.sh` orchestrates the ephemeral service, direct `dtc` post, qri,
   renderer, Hugo, and final site check.
2. `prepare_build.py` creates the immutable snapshot and disposable workspace.
3. `project_records.py` supplies the one generic temporary schema boundary and
   emits routes, relations, taxonomies, and graph data.
4. `check_site.py` verifies rendered output rather than revalidating source
   metadata.
5. `test-milestone.sh` owns repeat, extension, and negative acceptance tests;
   it is not rerun inside the Pages deployment build.
6. `reproduce_schema_discriminator.py` isolates the upstream LinkML defect.

The former record validator, fixed five-record enrichment table, individual
gate scripts, Hugo downloader, uv project, and uv lock were removed. Pixi
0.73.0 installs the checked-in cross-platform lock; Linux CI also receives the
pinned git-annex package.

The clean `www-from-model` mirror remains at
`6945272e5f3fcf353627b8e1c3e68bcaf76cc2ce`. The CON branch selectively adapts
the taxonomy, term, relationship, filter, qri, and graph patterns; it does not
merge or graft upstream history. `dump-research-info` remains migration
evidence only and is not a build dependency.

## Accepted schema exception

The pinned Pydantic and Python LinkML model families do not round-trip a common
type discriminator for native `Association`, `Attribution`, `Generation`,
`DOI`, and `ISSN` subclasses. The exact failure, minimal reproducer, attempted
solutions, trade-offs, tested pin-update strategy, and removal condition are
documented in the site repository at
`docs/upstream-schema-discriminator-issue.md` and in
`provenance/schema-compatibility.yaml`.

Milestone 1 therefore retains one bounded generic projection. It contains no
CON PID, label, route, image, or per-record table; checks every configured
relationship target independent of PID syntax; and keeps the original
source/predicate/target assertions on projected edges. Native qualified roles
and typed identifiers remain explicitly deferred until an upstream-compatible
schema/service/client/qri tuple passes the recorded fixtures. Updating a pin
should then regenerate the model and remove normalization, not add another
version-specific hack.

## Deferred scope

The full CON metadata migration, native qualified roles after the upstream
fix, production cutover and DNS, detailed visual/theming work, broader
information organization, reusable action/template extraction, graphical
editing, published RDF/JSONL contracts, and secondary projections remain later
milestones.
