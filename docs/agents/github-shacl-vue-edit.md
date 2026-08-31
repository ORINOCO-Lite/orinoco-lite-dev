# GitHub SHACL Vue editing

This profile lets a curator propose the bundle already produced by a downstream SHACL Vue editor.
The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## Static editor

The downstream `/edit/` route is the only editor.
Its build combines the released editor shell and schema with records from the exact site source used for that deployment.
Generated editor inputs are static output, not canonical metadata or durable curation state.

The editor exposes both:

- **Download bundle**, which remains credential-free; and
- **Propose via GitHub**, which uses the configured curation service.

Repository identity comes from the trusted build.
`site.curation_service` is an optional service override; the central Orinoco Lite service is the default.

## Browser handoff

The downstream owns file selection, warnings, changed-path summary, and final confirmation.
The service popup owns GitHub authentication and transport.

The channel binds the downstream origin, service origin, opener and popup windows, repository, operation, and a one-time nonce.
The unchanged bounded bundle crosses only that verified channel after the popup signals readiness.
Tokens and session cookies remain at the service origin.

If browser policy breaks the opener relationship, the curator may download the bundle, reselect it on the same downstream `/edit/` route, and start a new session.
A framed editor refuses direct GitHub submission while retaining bundle download.

Shared `github.io` deployments display a clear origin-wide security warning and custom-domain guidance.
They do not require a SHACL-specific acknowledgment checkbox.
Unique and custom origins use the normal flow.

## Git handoff

After explicit confirmation, the service creates or updates a same-repository draft pull request with one temporary fixed-path bundle commit.
It MUST verify:

- installed repository and curator write permission;
- trusted downstream and service origins;
- source commit and current exact head;
- allowed bundle format, size, record coordinates, and changed paths; and
- the one-time session grant.

The service MUST NOT retarget a stale bundle, create a cross-repository pull request, convert metadata, or retain the bundle after processing.

## Trusted replacement

A trusted workflow runs released engine code against an isolated checkout of the handoff parent.
It verifies the bundle and allowed paths, applies the edits, validates all records and the joined graph, and replaces the temporary handoff with one ordinary metadata commit.

The verified curator is the author and automation is the committer.
The temporary bundle is removed from branch history.
Earlier source-adapter proposal and review commits remain unchanged.

Failure leaves the draft pull request visibly blocked and does not modify canonical metadata.
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
