# Source-adapter implementation gaps

Status: non-normative snapshot for the source-adapter specification

The following work remains before the current implementation conforms to [`docs/source-adapters.md`](../docs/source-adapters.md):

- implement upstream-compatible recursive mapping ordering, then normalize the existing metadata corpus in a separate pull request;
- implement the generic `metadata/provenance/` companion format, selector validation, and joined semantic view;
- move adapter-generated PAV out of record YAML and prove joined schema, RDF, and projection round trips;
- replace stable adapter URNs with versioned adapter Things for `pav:importedBy`;
- represent imported scalar facts through joined assertion-level PAV and extend Zotero beyond record-level provenance;
- preserve existing companions when an incoming assertion is semantically identical;
- support comment-applied edits, SHACL Vue bundle application, and deletion proposals in the GitHub workflow;
- run Pixi review-application tasks through DataLad; and
- permit merge commits and warn that rebase and squash merges invalidate adapter provenance.

This report tracks implementation, not alternative behavior allowed by the specification.
