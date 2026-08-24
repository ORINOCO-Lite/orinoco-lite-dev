# GitHub source-adapter curation profile

Status: normative profile incorporated by [`source-adapters.md`](source-adapters.md)

This document defines the initial hosted implementation of the host-neutral review contract in [`source-adapters.md`](source-adapters.md).
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
- support SHACL Vue bundle application through the project-locked Pixi/DataLad task;
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

## Hosted review application

The supported decision interface is a deployed web application backed by a minimal stateless GitHub App user-to-server authorization service.
Native pull-request Markdown is an accessible summary and fallback, not a substitute for mutually exclusive controls or complete-submission validation.

The application MUST:

- accept or link directly to a repository, pull-request number, and artifact ID;
- use the authenticated GitHub API to load the current pull request, proposal commit, metadata diff, workflow run, and exact Actions artifact;
- display responsive before-and-after record diffs and identify records primarily by friendly IDs and labels;
- expose source identifiers, paths, blockers, and hashes as secondary details;
- provide exactly one mutually exclusive `accept`, `reject`, or `defer` control for every current candidate;
- support filtering, a changed-only view, keyboard navigation, and complete submission validation;
- bind submission to the repository, pull-request number, proposal SHA, current head SHA, exact source coordinate including revision, and complete candidate mapping; and
- post the complete structured decision payload as an authenticated pull-request comment on behalf of the GitHub user.

The application reads GitHub proposal and Actions objects produced by the trusted workflow.
It MUST NOT run an adapter, reacquire an external source, execute pull-request code, or infer candidate facts that the trusted Action must regenerate.
It is a review surface and authenticated comment transport, not another execution boundary.

The initial service accepts at most 225 candidates, 450 changed metadata paths, and 16 MiB of loaded record text per review.
These are application resource-safety bounds, not pull-request Markdown or native-diff conformance limits.

## Authenticated submission

The structured comment MUST begin with the exact line `/curation submit` and contain one JSON object whose `format` is `orinoco-lite-curation-submission-v1`.
That object contains exactly `format`, `repository`, `pull_request`, `proposal_sha`, `head_sha`, `adapter`, `source_coordinate`, and `decisions`.

Each decision contains exactly the initial proposal's canonical `pid`, `record_path`, `operation`, and the human's `disposition`.
The browser serializes decisions in deterministic record-path order, but ordering is not authority.
The Action compares the complete PID, path, and operation mapping independent of browser order.
The browser MUST NOT supply reviewer identity.
The Action derives identity, time, repository, pull request, and comment URL from the authenticated GitHub event.

The GitHub App requests only repository metadata read, contents read, Actions read, and pull requests write access for selected repositories.
It uses a short-lived user access token so the comment is attributed to the authenticated user and the App.
Signed or encrypted OAuth state and a short-lived authentication session are operational state.

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

The central `https://orinoco-curation-review.pages.dev/` deployment is the default hosted option.
A downstream selects its review-application origin independently, and that origin is not part of the PR-body or submission machine protocol.
The same application code MAY be deployed elsewhere by setting `PUBLIC_ORIGIN`; the profile does not require a particular hosting provider.
A conforming deployment MAY serve the static application and stateless authorization routes from one Cloudflare Pages or Workers deployment.
It MUST NOT require a durable database, object store, metadata service, candidate store, or decision store.

Cloudflare project provisioning, GitHub App registration, secrets, and a live deployment are external operational changes.
They require separately reviewed acceptance coordinates and are not implied by implementation of this profile.
