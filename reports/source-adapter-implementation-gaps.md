# Source-adapter implementation gaps

Status: non-normative snapshot for the source-adapter specification

The following work remains before the current implementation conforms to [`docs/source-adapter-spec.md`](../docs/source-adapter-spec.md):

- implement upstream-compatible recursive mapping ordering, then normalize the existing metadata corpus in a separate pull request;
- replace stable adapter URNs with versioned adapter Things for `pav:importedBy`;
- represent imported scalar facts with assertion-level PAV and extend Zotero beyond record-level PAV;
- support comment-applied edits, SHACL Vue bundle application, and deletion proposals in the GitHub workflow;
- run Pixi review-application tasks through DataLad; and
- permit merge commits and warn that rebase and squash merges invalidate adapter provenance.

This report tracks implementation, not alternative behavior allowed by the specification.
