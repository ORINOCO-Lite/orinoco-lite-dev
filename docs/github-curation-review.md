# GitHub source-adapter curation profile

Status: normative profile incorporated by [`source-adapters.md`](source-adapters.md)

This document defines the supported GitHub review implementation of the shared metadata and finalization behavior in [`source-adapters.md`](source-adapters.md).
The source-adapter specification remains authoritative for metadata semantics, candidate identity, decisions, provenance, finalization, and repository history.
This profile owns only the GitHub workflow, authenticated review transport, and user interface.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## GitHub workflow

The initial supported profile MUST:

- start from a default-branch `workflow_dispatch` and open one draft pull request;
- create the proposal with one inline `datalad run --explicit` commit;
- put the actual reviewable metadata changes under `metadata/records/` in the pull request's **Files changed** view, with machine PAV confined to mirrored companions under `metadata/overlays/annotations/`;
- render an accessible pull-request fallback and a review-application link containing the repository, pull-request number, and exact Actions artifact ID;
- publish exactly one untracked, expiring, reproducible Actions presentation artifact for that proposal;
- support normal GitHub collaboration on the same branch, including attributed comment suggestions and direct metadata commits;
- accept a complete structured decision state through an exact `/curation submit` comment posted on behalf of the authenticated reviewer;
- accept submissions only from collaborators with `write` or `admin` access;
- load executable workflow and adapter code from the trusted default branch;
- treat the pull-request branch and external source checkout only as data while a write token is available;
- re-read and regenerate candidate facts with trusted code before applying a submitted decision;
- preserve later attributed human metadata changes while applying the complete decision state;
- restrict automated writes to the two declared metadata trees and the adapter-owned compact decision cache;
- validate the joined graph before committing;
- push against the exact observed head with a lease; and
- dispatch normal validation without approving, merging, deploying, or writing to an external source.

The trusted proposal workflow performs all adapter and source execution.
It produces the actual Git diff, an accessible Markdown fallback, and the ephemeral presentation artifact from the candidate plan.
Pull-request Markdown MAY be edited using normal GitHub collaboration and is never parsed as a machine protocol or candidate authority.
GitHub's native fallback-rendering limits are not curation conformance limits.

The artifact MUST be named `orinoco-curation-review-<proposal_sha>`.
Its ZIP is at most 8 MiB compressed and contains exactly one regular top-level `review-bundle.json` entry of at most 16 MiB uncompressed.
The JSON object has format `orinoco-lite-curation-review-bundle-v1` and exactly these top-level fields: `format`, `repository`, `pull_request`, `workflow_run_id`, `adapter`, `metadata_base_sha`, `proposal_sha`, `source_coordinate`, and `candidates`.
Each candidate has exactly `pid`, `friendly_id`, `label`, `source_namespace`, `source_record_id`, `record_path`, `paths`, `operation`, `blockers`, and `claim_sha256`.
`record_path` is the full repository record path and `paths` contains the exact changed record path and optional mirrored annotation path for that candidate.

The application MUST derive candidate membership and add, modify, or delete operations from the proposal commit's actual metadata diff.
It verifies the artifact repository, workflow run, proposal, source, paths, operations, and record PIDs against the selected pull request and Git objects before displaying the bundle's presentation facts.
It loads baseline record blobs at `metadata_base_sha`, initial proposed blobs at `proposal_sha`, and current branch data at the pull-request head.
The initial blobs verify the bundle PID and operation; later authorized deletion, restoration, or PID edits remain visible current-head data and do not retarget the reviewed candidate.
The artifact's friendly IDs, labels, source identifiers, hashes, and blockers remain presentation facts that the trusted Action regenerates before finalization.
Artifact expiry or absence makes the hosted presentation unavailable but cannot change metadata, a decision, or review history.

Reviewers MAY inspect and edit the metadata diff through GitHub's browser tools or a local checkout.
Neither path changes the candidate, provenance, validation, or finalization rules in the source-adapter specification.

SHACL Vue proposal editing follows the separate normative [`GitHub SHACL Vue human-edit profile`](github-shacl-vue-edit.md) and is not a bundle input to this decision-review application or trusted finalizer.
Decision-review operations use repository contents read access only.
The shared App's contents-write permission is confined to the other profile's explicit, path-restricted human handoff operation.

## Downstream static review application

The supported decision interface is the downstream's deployed static `/review/` route, backed by a minimal stateless GitHub App user-to-server authorization and transport service.
Native pull-request Markdown is an accessible summary and fallback, not a substitute for mutually exclusive controls or complete-submission validation.

The static application and service together MUST:

- accept or link directly to a repository, pull-request number, and artifact ID;
- use the authenticated GitHub API to load the current pull request, proposal commit, metadata diff, workflow run, and exact Actions artifact;
- display responsive before-and-after record diffs and identify records primarily by friendly IDs and labels;
- expose source identifiers, paths, blockers, and hashes as secondary details;
- provide exactly one mutually exclusive `accept`, `reject`, or `defer` control for every current candidate;
- provide a bulk initializer that applies one selected disposition to every currently unresolved candidate while preserving existing per-record choices and allowing every initialized choice to be overridden before submission;
- support filtering, a changed-only view, keyboard navigation, and complete submission validation;
- bind submission to the repository, pull-request number, proposal SHA, current head SHA, exact source coordinate including revision, and complete candidate mapping; and
- post the complete structured decision payload as an authenticated pull-request comment on behalf of the GitHub user.

The canonical exact-review route is `review/` below the downstream's configured `site.base_url`.
The workflow supplies the repository, pull-request number, and artifact ID directly; the central service is not a discovery or review destination.

The service reads GitHub proposal and Actions objects produced by the trusted workflow and transports the verified proposal to the exact static opener.
It MUST NOT run an adapter, reacquire an external source, execute pull-request code, infer candidate facts that the trusted Action must regenerate, or render a second candidate-review interface.
The bulk initializer changes only in-browser decision state.
It is not a disposition until the reviewer submits the complete authenticated decision comment, and it does not weaken exact-head, completeness, or trusted regeneration checks.

The initial service accepts at most 225 candidates, 450 changed metadata paths, and 16 MiB of loaded record text per review.
These are application resource-safety bounds, not pull-request Markdown or native-diff conformance limits.

The static route generates a fresh 256-bit nonce and opens the service's authorization route in a popup with exact repository, pull-request, artifact, operation, and origin coordinates.
OAuth runs in that popup so the main browser remains on downstream `/review/`.
The sealed, expiring session grant binds those coordinates.
Repository identity MUST be derived from the trusted downstream build or its general project identity rather than a second curation-specific setting.
Before sending proposal data, the service verifies the repository against the GitHub objects and App installation, verifies `site.base_url` and any explicit `site.curation_service` override from `orinoco.yaml` at the proposal metadata base, resolves an omitted override to the released central-service default, and completes an exact ready/request handshake with the same window, origin, operation, nonce, and coordinates.
Neither tokens nor CSRF material cross that channel.

The static application sends one complete decision submission back through the same one-shot channel.
The downstream MUST display the authenticated login, repository, pull request, proposal and head commits, and every record path and disposition.
Only an explicit user confirmation on that downstream route may instruct the popup to post the comment.
Replayed, mismatched, stale, framed, timed-out, or duplicate messages fail closed.

The service sends a typed `post-started` message before the authenticated request and classifies its result.
Only an explicit retry-safe pre-write rejection may unlock the static reviewer and replace its transport while preserving decisions.
A network failure, server failure, malformed GitHub success response, timeout, or unknown result keeps the submission locked and instructs the curator to inspect the pull request before another action.

Legacy central discovery routes return HTTP 410 `review_discovery_retired`.
They do not start OAuth, inspect a session, or contact GitHub.
The central root, review, upload, and confirmation routes expose no static application; they return a small `404` or compatibility `410` response.

### Downstream origin policy

A custom domain or another origin dedicated to one downstream receives the normal review and submission flow.
The template MUST guide maintainers through adding and verifying that domain.

On a shared `github.io` origin, the static application MUST explain that browser messaging authenticates the whole origin rather than its `/review/` path and that another compromised page on that hostname could impersonate the intended route.
It MUST classify the actual browser origin at runtime; configured or link coordinates MUST NOT bypass the gate while the page is running on `github.io`.
It MUST require an explicit in-memory acknowledgment of that limitation before enabling the direct GitHub submission action.
The acknowledgment is informed consent, not authorization or proof of path identity.
It MUST NOT be stored in local storage, a cookie, service state, or tracked configuration or weaken the exact-channel or server-side checks.
Native pull-request review and the accessible Markdown summary remain available without using the hosted direct-submission flow.

## Authenticated submission

The structured comment MUST begin with the exact line `/curation submit`.
The application emits the following exact Markdown envelope, with the details element closed by default so that the complete payload does not dominate the pull-request conversation:

````markdown
/curation submit

<details>

<summary>Complete curation submission JSON</summary>

```json
{
  "format": "orinoco-lite-curation-submission-v1"
}
```

</details>
````

The fenced block contains one JSON object whose `format` is `orinoco-lite-curation-submission-v1`.
The trusted host accepts this exact envelope and the former exact unwrapped fenced-JSON envelope so historical comments and event replays remain valid; it MUST NOT accept other wrapper variations.
Collapsing the payload changes only its GitHub presentation: the raw comment remains the authenticated durable decision record, and `/curation submit` remains visible as the workflow trigger.
That object contains exactly `format`, `repository`, `pull_request`, `proposal_sha`, `head_sha`, `adapter`, `source_coordinate`, and `decisions`.

Each decision contains exactly the initial proposal's canonical `pid`, `record_path`, `operation`, and the human's `disposition`.
The browser serializes decisions in deterministic record-path order, but ordering is not authority.
The Action compares the complete PID, path, and operation mapping independent of browser order.
The browser MUST NOT supply reviewer identity.
The Action derives identity, time, repository, pull request, and comment URL from the authenticated GitHub event.

For this profile, the GitHub App uses only repository metadata read, contents read, Actions read, and pull requests write access for selected repositories.
The shared App registration also has contents write for the distinct SHACL Vue human-edit profile, but this decision path MUST NOT use it.
It uses a short-lived user access token so the comment is attributed to the authenticated user and the App.
Signed or encrypted OAuth state and a short-lived authentication session are operational state.
The GitHub App callback MUST be the service's exact `/api/auth/callback` URL.
Post-install setup redirects MUST use a separate setup URL and MUST NOT be sent to that OAuth callback.

The service MUST NOT retain the proposal, candidate plan, decision payload, metadata, source data, user access token, or refresh token after submission or session expiry.
It MUST NOT become a metadata, decision, candidate, provenance, or credential store.

## Trusted commit boundary

The default-branch GitHub Action is the trusted commit boundary.
For every submitted comment it MUST:

1. re-read the pull request, proposal commit, current head, and source coordinate;
2. regenerate the adapter candidate plan with trusted code and the exact source revision;
3. verify the proposal diff and the complete candidate mapping;
4. regenerate source-native identifiers and claim digests independently of the ephemeral presentation bundle;
5. reject stale, incomplete, unauthorized, or inconsistent submissions;
6. apply the decisions while preserving conforming human edits;
7. validate the complete joined graph; and
8. commit the metadata and compact decision cache with the authenticated human as author and automation as committer.

The Action MUST NOT choose a disposition, approve, merge, deploy, or write to an external source.
No second copy of the proposal or decisions is retained by the service.

## Public retention and history

In a public repository, proposed metadata remains visible in Git history even if review later rejects it.
The workflow MUST disclose that retention and require explicit acknowledgment before proposing public data.
Secrets and data not approved for repository history MUST be excluded before the proposal commit.

Adapter review pull requests MUST use merge commits.
Squash and rebase merges rewrite required DataLad or human-review commits and are not conformant.
The pull-request opening text MUST state this requirement prominently, and the repository MUST permit exact-commit-preserving merges.

Reviewers MUST NOT need a local checkout.
Local execution MAY expose the same deterministic operations for development and reproduction.

## Hosting boundary

The central `https://orinoco-curation-review.pages.dev/` deployment is the default backend-only authorization and verified GitHub-transport option.
It is not the canonical review page.
An omitted `site.curation_service` selects that default; the field is only an optional override for a compatible independently hosted service.
The downstream's trusted build supplies repository identity, while its own `site.base_url` owns `/review/`.
The same service code MAY be deployed elsewhere by setting `PUBLIC_ORIGIN`; the profile does not require a particular hosting provider.
It MUST NOT require a durable database, object store, metadata service, candidate store, or decision store.
It MUST NOT deploy static presentation assets or expose a landing, review, confirmation, upload, receiver, or editor application.
It MAY return a minimal backend-generated, restrictive-CSP OAuth callback and popup transport document that retains host-only cookies while the downstream static site remains the only user interface.

Browser messaging binds an origin, not a URL path.
A project site on a shared GitHub Pages hostname therefore shares its browser trust boundary with other pages on that hostname.
The explanation and explicit acknowledgment above are required for that deployment shape in addition to the repository-derived checks, exact one-shot channel, selected-repository App installation, and complete server-side revalidation.
A custom or otherwise unique origin narrows that boundary and receives the normal low-friction flow.

Cloudflare project provisioning, GitHub App registration, secrets, and a live deployment are external operational changes.
They require separately reviewed acceptance coordinates and are not implied by implementation of this profile.
