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
- render an accessible pull-request summary headed by friendly labels and canonical PIDs, with source-native identifiers, paths, blockers, and hashes as secondary details and a link to the review application;
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
It produces the actual Git diff and the accessible summary from the ephemeral candidate plan.
The summary is a human-facing fallback and navigation aid, not a tracked proposal, hidden candidate descriptor, or separate authority.

The summary uses one visible `## Curation proposal` section containing `Adapter`, `Proposal commit`, and `Source coordinate` fields, followed by one visible `## Candidate review` section.
The source coordinate is the canonical single-line JSON object rendered in a fenced `json` block.
Each candidate is a level-three heading using its friendly ID and label, followed by visible `PID`, `Source record`, `Record path`, `Operation`, `Claim SHA-256`, and `Blockers` fields.
`Blockers` is either `None` or an indented list.
The workflow renders candidate sections in deterministic candidate-plan order.

The application MUST derive the candidate set and add, modify, or delete operations from the proposal commit's actual record changes.
It cross-checks the visible summary fields against those paths and operations and refuses an incomplete or inconsistent rendering.
Source-native identifiers, labels, claim hashes, and blockers remain display facts that the trusted Action regenerates before finalization.
The summary therefore adds no hidden candidate block, aggregate attestation, or durable authority beyond the pull request and its actual diff.

Reviewers MAY inspect and edit the metadata diff through GitHub's browser tools or a local checkout.
Neither path changes the candidate, provenance, validation, or finalization rules in the source-adapter specification.

## Hosted review application

The supported decision interface is a deployed web application backed by a minimal stateless GitHub App user-to-server authorization service.
Native pull-request Markdown is an accessible summary and fallback, not a substitute for mutually exclusive controls or complete-submission validation.

The application MUST:

- accept or link directly to a repository and pull-request number;
- use the authenticated GitHub API to load the current pull request, trusted workflow summary, proposal commit, and metadata diff;
- display responsive before-and-after record diffs and identify records primarily by friendly IDs and labels;
- expose source identifiers, paths, blockers, and hashes as secondary details;
- provide exactly one mutually exclusive `accept`, `reject`, or `defer` control for every current candidate;
- support filtering, a changed-only view, keyboard navigation, and complete submission validation;
- bind submission to the repository, pull-request number, proposal SHA, current head SHA, exact source coordinate including revision, and complete ordered candidate set; and
- post the complete structured decision payload as an authenticated pull-request comment on behalf of the GitHub user.

The application reads GitHub proposal objects produced by the trusted workflow.
It MUST NOT run an adapter, reacquire an external source, execute pull-request code, or infer candidate facts that the trusted Action must regenerate.
It is a review surface and authenticated comment transport, not another execution boundary.

## Authenticated submission

The structured comment MUST begin with the exact line `/curation submit` and contain one JSON object whose `format` is `orinoco-lite-curation-submission-v1`.
That object contains exactly `format`, `repository`, `pull_request`, `proposal_sha`, `head_sha`, `adapter`, `source_coordinate`, and `decisions`.

Each decision contains exactly the initial proposal's canonical `pid`, `record_path`, `operation`, and the human's `disposition`.
Decisions MUST use deterministic candidate-plan order and cover the complete candidate set.
The browser MUST NOT supply reviewer identity.
The Action derives identity, time, repository, pull request, and comment URL from the authenticated GitHub event.

The GitHub App requests only repository metadata read, contents read, and pull requests write access for selected repositories.
It uses a short-lived user access token so the comment is attributed to the authenticated user and the App.
Signed or encrypted OAuth state and a short-lived authentication session are operational state.

The service MUST NOT retain the proposal, candidate plan, decision payload, metadata, source data, user access token, or refresh token after submission or session expiry.
It MUST NOT become a metadata, decision, candidate, provenance, or credential store.

## Trusted commit boundary

The default-branch GitHub Action is the trusted commit boundary.
For every submitted comment it MUST:

1. re-read the pull request, proposal commit, current head, and source coordinate;
2. regenerate the adapter candidate plan with trusted code and the exact source revision;
3. verify the proposal diff and the complete ordered candidate set;
4. verify source-native identifiers and claim digests represented in the workflow-generated summary;
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

The profile does not require a particular hosting provider.
A conforming deployment MAY serve the static application and stateless authorization routes from one Cloudflare Pages or Workers deployment.
It MUST NOT require a durable database, object store, metadata service, candidate store, or decision store.

Cloudflare project provisioning, GitHub App registration, secrets, and a live deployment are external operational changes.
They require separately reviewed acceptance coordinates and are not implied by implementation of this profile.
