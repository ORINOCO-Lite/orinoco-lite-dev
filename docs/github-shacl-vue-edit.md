# GitHub SHACL Vue human-edit profile

Status: normative profile incorporated by [`source-adapters.md`](source-adapters.md)

This document defines a human-authored metadata-edit path that is separate from the [`GitHub source-adapter curation profile`](github-curation-review.md).
SHACL Vue remains a schema-driven RDF editor and retains its normal **Download bundle** behavior.
A thin Orinoco wrapper supplies GitHub authentication, coordinates, and proposal transport without adding GitHub, source-adapter, disposition, provenance, or decision-cache semantics to SHACL Vue.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## Editor boundary

The released editor MUST continue to produce the normal `orinoco-shacl-review-bundle` version 2 object and download.
After producing that exact object, SHACL Vue MAY expose it through the neutral `orinoco:review-bundle` browser event.
The event detail is the same object supplied to the download operation and adds no repository or curation semantics.

The Orinoco wrapper MAY offer **Propose via GitHub** when it receives that event.
It MUST bind the editor input and resulting bundle to an exact repository and Git commit and MUST NOT modify the bundle, choose metadata values, or retain a copy after the request completes.
The central service origin is configurable; a downstream may use the central deployment or host the same code.
The canonical authenticated wrapper route is `/edit/` on that origin.
A downstream site's own `/edit/` route MAY continue serving the credential-free editor and **Download bundle** fallback; identical path names on different origins do not make that static page the GitHub wrapper.
Signing in to GitHub does not add proposal controls to the downstream's static page: that page has no GitHub session.
A curator who enters the central wrapper without a session is shown **Continue with GitHub** before the exact-coordinate editor loads.

Milestone 6 will make the two destinations visible from the site before editing.
It will not add cross-origin storage or an OAuth recovery store to transfer an already completed static-editor session.
The choice of whether the site shows two explicit actions or makes the authenticated wrapper the primary edit action remains M6-Q001 in [`milestone-6.md`](milestone-6.md).

## Exact-head editor input

For every exact pull-request or default-branch commit that it materializes, a trusted workflow loaded only from the reviewed default branch MUST publish exactly one untracked, expiring, reproducible editor-input artifact named `orinoco-shacl-vue-input-<source_sha>`.
Its ZIP contains exactly these three ordinary files and no executable editor code:

- `edit/config.json`;
- `edit/records.ttl`; and
- `edit/data/record-sources.json`.

The workflow MUST produce those files deterministically from the canonical records and annotation companions at the exact source commit.
The record catalog's `source_commit` MUST equal that commit.
For an existing source-adapter pull request, **Edit in SHACL Vue** MUST select the pull request's exact current head.
For a standalone edit, it MUST select the repository's exact current default-branch head, which is also the commit from which a proposal branch may start.
A stale editor input or resulting bundle is rejected rather than rebased or retargeted.

The central stateless application MUST verify the selected repository, exact source commit, unexpired artifact, and successful trusted workflow run before exposing those files.
In the browser it combines the three data files only in memory with a generic SHACL Vue shell and Things schema taken from one immutable, digest-verified Orinoco Lite runtime release.
It MUST NOT use editor executable code, schema, or conversion behavior from the pull request or editor-input artifact, and it MUST NOT retain the assembled input.

The editor-input artifact is reproducible presentation input.
It is not canonical metadata, the generated version 2 bundle, a source-adapter candidate or decision artifact, provenance, or a durable curation record.
Its expiry cannot change metadata, a decision, or Git history.
It is distinct from the source-adapter decision profile's exactly one `orinoco-curation-review-<proposal_sha>` artifact and does not relax that one-artifact contract.
Neither profile parses pull-request Markdown as a machine protocol.

This presentation path reuses the existing central application and MUST NOT add a separate Worker, browser-side metadata converter, conversion service, database, object store, or artifact cache.

## Ephemeral Git handoff

The normal RDF bundle is not itself canonical metadata.
The authenticated service therefore writes it as one temporary Git handoff commit so trusted default-branch Python code can apply the pinned Orinoco editor conversion without a TypeScript replacement or an additional runtime service.

The handoff commit MUST:

- be created only after an explicit **Propose via GitHub** action by a collaborator with `write` or `admin` access;
- have exactly one parent, the exact displayed repository head;
- add exactly one regular file at `.orinoco-lite/shacl-vue-review-bundle.json`;
- contain exactly the unchanged, bounded version 2 bundle;
- be attributed by GitHub to the authenticated curator; and
- be the exact head of a same-repository draft pull-request branch.

For an existing pull request, its previous head is the handoff parent.
For a standalone edit, the service requires the bundle source commit to equal the repository's current default-branch head, creates a unique branch there, appends the handoff, and opens a draft pull request against that branch.
The service MUST NOT create a pull request against another repository, write to an external source, or use contents permission for any other operation.

The handoff is ephemeral transport, not a metadata proposal, review bundle, manifest, provenance record, or durable curation authority.
It MUST NOT be merged.
The pull request MUST remain draft while a handoff is present.
Before creating the handoff, the wrapper MUST require the curator to acknowledge explicitly that the bundle contains only data approved for public repository history and contains no secrets.
Because a public Git host can retain unreachable objects, the wrapper MUST also warn that the bundle is temporarily public and that its unreachable Git object may remain recoverable after replacement.

## Trusted replacement

A `pull_request_target` workflow loaded only from the reviewed default branch is the conversion and validation boundary.
It treats the pull-request tree and bundle only as data and never executes code from them.

Against the exact observed handoff head, the workflow MUST:

1. verify the same-repository draft pull request, curator authority, authenticated event actor, handoff authorship, one-parent history, fixed path, file mode, format, bounds, and bundle source commit;
2. run the pinned released Orinoco editor apply behavior with trusted code against an isolated checkout of the handoff parent;
3. require every input digest, PID, schema type, and source path to match and permit output only under `metadata/records/` and the mirrored `metadata/overlays/annotations/` tree;
4. validate every stored record and companion and the complete joined Things graph;
5. create one ordinary human metadata commit with the same parent as the handoff, the verified curator as author, and automation as committer; and
6. replace only the exact handoff head with that commit using a force-with-lease comparison against the observed head.

This single history replacement is the profile's transport cleanup.
It removes the temporary bundle from the branch while preserving every earlier source-adapter proposal and human-review commit unchanged.
It MUST NOT rewrite a canonical metadata commit, silently retry against a new head, or generalize into branch-history repair.
Failure leaves the draft pull request visibly blocked at the handoff commit and does not create or modify metadata.

The replacement is an ordinary attributed human commit, not a DataLad run: the Action deterministically materializes the curator's exact editor result and does not execute a source adapter or choose a semantic change.
The normal trusted workflow validates the resulting joined graph and adds the configurable curation-service link idempotently.

## Permissions and prohibitions

The shared GitHub App requests repository metadata read, Actions read, contents write, and pull requests write for selected repositories.
Contents write is used only for the explicit human handoff branch and commit operations in this profile.
The decision-review profile reads repository contents and never commits through the service.
Actions read retrieves the two profiles' distinct expiring artifacts; it does not authorize an artifact store.

The service and workflow MUST NOT:

- retain the generated bundle after request processing or after replacement;
- store metadata, candidates, decisions, provenance, or credentials;
- execute pull-request or external-source code;
- infer or choose a source-adapter disposition;
- add machine PAV or decision-cache entries to a human edit;
- approve, mark ready, merge, deploy, or write to an external source; or
- introduce another Worker, a browser or hosted metadata converter, a database, persistent metadata service, object store, artifact cache, recovery protocol, manifest, journal, or transaction graph.

OAuth state and short-lived authentication sessions remain operational state.
Git commits and pull-request history are the durable record of the resulting human proposal.
