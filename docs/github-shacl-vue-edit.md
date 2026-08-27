# GitHub SHACL Vue human-edit profile

Status: normative profile incorporated by [`source-adapters.md`](source-adapters.md)

This document defines a human-authored metadata-edit path that is separate from the [`GitHub source-adapter curation profile`](github-curation-review.md).
SHACL Vue remains a schema-driven RDF editor and retains its normal **Download bundle** behavior.
The downstream static site is the only SHACL Vue editing surface for that downstream.
A thin Orinoco site integration and stateless service supply GitHub authentication, coordinates, and proposal transport without adding GitHub, source-adapter, disposition, provenance, or decision-cache semantics to SHACL Vue.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## Static editor boundary

The released editor MUST continue to produce the normal `orinoco-shacl-review-bundle` version 2 object and download.
After producing that exact object, SHACL Vue MAY expose it through the neutral `orinoco:review-bundle` browser event.
The event detail is the same object supplied to the download operation and adds no repository or curation semantics.

The Orinoco static-site integration MUST expose two explicit actions from that same editor session:

- **Download bundle**, which remains credential-free; and
- **Propose via GitHub**, which hands the same unchanged bundle to a configured stateless GitHub service.

The static site MUST NOT receive or retain a GitHub token.
The proposal action MUST bind the editor input and resulting bundle to an exact repository and Git commit and MUST NOT modify the bundle, choose metadata values, or retain another copy after the handoff completes.
The downstream declares the exact GitHub `owner/repository` coordinate and the credential-free HTTPS origin of the receiver in `site.repository` and `site.curation_service`.
Both values are required to enable **Propose via GitHub**; a downstream may use the central deployment or host the same service code.

The service MAY expose `/edit/` as a lightweight sign-in, confirmation, and bundle-receiver route.
That route MUST NOT assemble, embed, or host SHACL Vue, its schema, its record data, or another editing session.
A curator who is not signed in MAY complete GitHub authorization there and return to the same lightweight receiver.
After authorization, the receiver MAY accept either the unchanged bundle transferred from the static editor or a curator-selected copy previously produced by **Download bundle**.
It MUST keep the bundle only in browser memory until the explicit proposal request completes or the page is closed.

## Exact-source static input

The downstream build MUST produce the editor's ordinary static inputs deterministically from canonical records and annotation companions at one exact source commit:

- `edit/config.json`;
- `edit/records.ttl`; and
- `edit/data/record-sources.json`.

The record catalog's `source_commit` MUST equal that commit.
The static site MUST combine those inputs with the editor shell and Things schema from one immutable, digest-verified Orinoco Lite runtime release.
For a standalone edit, the source commit is the exact default-branch commit used to build the deployed site and from which a proposal branch may start.
If a site exposes an editor for an existing pull request, that editor MUST itself be built from the pull request's exact current head; the central service MUST NOT materialize that editor or retarget a default-branch bundle.
A stale input or resulting bundle is rejected rather than rebased or retargeted.

The static editor inputs are generated site output, not canonical metadata, a source-adapter candidate or decision artifact, provenance, or durable curation state.
No separate editor-input Actions artifact is required by this profile.
The source-adapter decision profile's exactly one `orinoco-curation-review-<proposal_sha>` artifact remains unchanged.

## Browser handoff

The static site MAY open the configured service receiver in a popup or separate page with only the repository, the static site's exact origin, and a cryptographically random one-time handoff nonce.
An existing pull-request link MAY additionally carry its exact pull-request and head coordinates.
The editor's exact source commit remains inside the unchanged bundle.
It MUST NOT place the bundle or a credential in the URL.
When a live browser handoff is used, the editor MUST send the exact bundle only after its receiver window at the configured service origin signals readiness with the same repository and nonce.
The editor MUST require that exact receiver origin and window, while the receiver MUST require that exact static-site origin, opener window, repository, and nonce.
OAuth state and the short-lived authentication session MAY preserve those non-secret channel coordinates across the sign-in redirect; the bundle MUST NOT be stored as OAuth recovery state or in cross-origin browser storage.

If authorization or browser policy severs the opener relationship, the curator MAY use **Download bundle** and select that unchanged file on the receiver page.
The service MUST apply the same coordinate, format, size, authorization, acknowledgment, and exact-head checks regardless of which browser transport supplied the bundle.
The receiver MUST require an explicit confirmation before it submits the proposal request.

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
Before creating the handoff, the receiver MUST require the curator to acknowledge explicitly that the bundle contains only data approved for public repository history and contains no secrets.
Because a public Git host can retain unreachable objects, the receiver MUST also warn that the bundle is temporarily public and that its unreachable Git object may remain recoverable after replacement.

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

For this profile, the shared GitHub App uses repository metadata read, contents write, and pull requests write for selected repositories.
Contents write is used only for the explicit human handoff branch and commit operations in this profile.
The shared registration additionally requests Actions read and contents read for the decision-review profile, which never commits through the service.
This profile does not use Actions read to retrieve or assemble an editor.

The service and workflow MUST NOT:

- retain the generated bundle after request processing or after replacement;
- store metadata, candidates, decisions, provenance, or credentials;
- assemble, embed, or host a second editor;
- execute pull-request or external-source code;
- infer or choose a source-adapter disposition;
- add machine PAV or decision-cache entries to a human edit;
- approve, mark ready, merge, deploy, or write to an external source; or
- introduce another Worker, a browser or hosted metadata converter, a database, persistent metadata service, object store, artifact cache, recovery protocol, manifest, journal, or transaction graph.

OAuth state and short-lived authentication sessions remain operational state.
Git commits and pull-request history are the durable record of the resulting human proposal.
