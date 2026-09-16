# GitHub SHACL Vue editing

This profile lets a curator propose the bundle already produced by a downstream SHACL Vue editor.
The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## Static editor

The downstream `/edit/` route is the only editor.
Its build combines the downstream-selected editor shell and schema with records from the exact site source used for that deployment.
Generated editor inputs are static output, not canonical metadata or durable curation state.

The editor exposes:

- **Download bundle**, which remains credential-free; and
- **Upload bundle**, which restores an exact downloaded bundle after the curator returns to the same deployed editor; and
- **Propose via GitHub**, which uses the configured curation service.

Repository identity comes from the trusted build.
`site.curation_service` is an optional service override; the central Orinoco Lite service is the default.

## Browser handoff

The downstream owns file selection, warnings, changed-path summary, and final confirmation.
The service popup owns GitHub authentication and transport.

The channel binds the downstream origin, service origin, opener and popup windows, repository, operation, and a one-time nonce.
The unchanged bounded bundle crosses only that verified channel after the popup signals readiness.
Tokens and session cookies remain at the service origin.

If browser policy or GitHub App setup interrupts the proposal, the curator may download the bundle, upload it on the same downstream `/edit/` route, and start a new session.
A framed editor refuses direct GitHub submission while retaining bundle download.

Shared `github.io` deployments display a clear origin-wide security warning and custom-domain guidance.
Unique and custom origins use the normal flow.

## Git handoff

After explicit confirmation, the service creates or updates a same-repository draft pull request with one temporary fixed-path bundle commit.
It MUST verify:

- installed repository and curator write permission;
- trusted downstream and service origins;
- source commit and current exact head;
- allowed bundle format, size, record coordinates, and changed paths; and
- the one-time session grant.

A standalone proposal MUST originate at the configured canonical editor origin.
A Netlify deploy preview MAY update only its own open same-repository draft pull request.
For that exception, the service MUST verify GitHub's successful Netlify deploy-preview status for the exact pull-request head, preview origin, and pull-request number.

The service MUST NOT retarget a stale bundle, create a pull request with a head from another repository, convert metadata, or retain the bundle after processing.

When `site-specific` is a Git submodule, the service MUST resolve its GitHub URL and exact gitlink from the deployed website commit.
This bounded profile requires an absolute GitHub HTTPS or SSH URL and a gitlink at the metadata repository's current default-branch head.
The App MUST be installed on both repositories and the curator MUST have write permission in both.
The service first creates a metadata draft pull request containing the unchanged bundle, then hands off the website proposal with the metadata draft's exact coordinates.
Each draft has its head and base in its own repository.
The fixed temporary website handoff may wrap the unchanged bundle and metadata proposal coordinates; these are operational state removed by replacement.

## Trusted replacement

A trusted workflow runs the downstream-selected package against an isolated checkout of the handoff parent.
It verifies the bundle and allowed paths, applies the edits, validates all records and the joined graph, and replaces the temporary handoff with one ordinary metadata commit.

For a submodule proposal, the trusted website workflow MUST verify both exact heads, the pinned metadata base, the identical bundles, and curator authority in both repositories.
It checks out metadata as data and validates the complete website and metadata composition without write credentials.
Only then may it replace the metadata handoff with a metadata-only commit and replace the website handoff with a commit changing only the gitlink to that metadata commit.
The workflow requires a repository-scoped GitHub App installation token for metadata access, supplied by the downstream's trusted configuration.
Both branch updates MUST use exact-head leases.
The metadata update precedes the website update so the website never points at an unpublished commit.
GitHub does not provide an atomic transaction across repositories: a partial failure MUST identify the retained draft and commit and require inspection before another submission.
Automation MUST NOT merge either proposal.

The verified curator is the author and automation is the committer.
The temporary bundle is removed from branch history.
Earlier source-adapter proposal and review commits remain unchanged.

Failure leaves the draft pull request visibly blocked and does not modify either reviewed default branch.
A stale or ambiguous input fails rather than being rebased, retargeted, or guessed.

## Boundaries

The backend MUST NOT:

- host `/edit/`, another editor, a landing page, upload page, or confirmation UI;
- store bundles, metadata, decisions, provenance, or credentials;
- add source-adapter dispositions or decision-cache semantics to SHACL Vue;
- weaken OAuth state, PKCE, origin, nonce, exact-head, or path checks; or
- use contents permission for any operation outside the bounded handoff.

The source-adapter review artifact remains separate.
This profile adds no editor input Actions artifact and no persistent service.
