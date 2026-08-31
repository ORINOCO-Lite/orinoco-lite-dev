# GitHub source-adapter review

This profile defines the hosted review of a source-adapter proposal.
The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are normative.

## Workflow

1. A trusted workflow runs the adapter with released code and opens a draft pull request containing one proposal commit.
2. The pull request identifies the adapter, links to the downstream `/review/` route, and places the source coordinate in a closed details block.
3. The workflow publishes one expiring review artifact derived from the proposal.
The artifact is presentation input, not durable authority.
4. The downstream review page authenticates the curator through the configured GitHub App service and displays the complete proposal.
5. The curator selects one disposition for every candidate and explicitly submits the decision state.
6. The service revalidates repository, permission, pull request, proposal, artifact, and current head, then posts one authenticated GitHub comment.
7. A trusted workflow reads that comment, updates the compact decision cache, finalizes the proposal, validates the complete graph, and records the result on the same branch.

The final bot message SHOULD say: `Recorded human acceptance decisions in <commit>. Ready for merging.` It does not need an AI-draft disclaimer or a statement about actions it did not take.

## Downstream review page

The deployed downstream owns `/review/`.
A bare route SHOULD show a friendly link or asynchronously populated list of relevant open curation pull requests.
An exact proposal URL remains the deterministic entry point.

The page MUST display:

- authenticated GitHub identity;
- repository, pull request, proposal, and current head;
- adapter and source coordinate;
- every candidate with friendly identity, operation, and metadata diff;
- explicit accept, reject, and defer controls; and
- a complete confirmation summary before submission.

The source coordinate is shown for inspection but is not duplicated into a new tracked manifest.
Pull-request Markdown is an accessible summary, not a machine protocol.

On a shared `github.io` origin, `/review/` explains the origin-wide browser trust boundary and requires a fresh in-memory acknowledgment before direct submission.
A unique or custom origin uses the normal flow.

## Authentication and submission

The service uses a GitHub App with expiring user tokens.
It MUST request only the permissions needed for metadata, Actions artifact reads, pull-request comments, and the separately specified SHACL handoff.

Before posting, it independently verifies:

- the installed repository and authenticated curator permission;
- trusted downstream and service origins;
- the pull request, base, proposal commit, and current exact head;
- the expected review artifact and proposal-derived candidate set; and
- complete, valid decisions for every candidate.

Browser parameters are routing hints, not authority.
OAuth state, sessions, and tokens are short-lived operational state and MUST NOT enter repository content, logs, analytics, or browser storage.

A retry before a write begins may start a new session.
An uncertain result after a write begins requires inspection of the pull request rather than an automatic duplicate submission.

## Trusted workflow boundary

Untrusted pull-request code MUST NOT receive write credentials.
Finalization runs trusted released code against the identified proposal and submitted head.
Each automated write uses an exact-head compare-and-swap so a concurrent change cannot be silently overwritten.

Metadata changes run full validation.
A decision-cache-only update may run the smaller joined-graph validation.
Multiple GitHub events for one update MUST NOT cancel the only useful validation run.

The workflow MUST NOT invent decisions, approve, merge, deploy, or write to the external source.

## Hosting boundary

All review, warning, and confirmation UI remains on the downstream origin.
The central or self-hosted service supplies only OAuth, verified GitHub reads, and authenticated transport.
It MUST NOT host a landing page, review application, editor, upload interface, metadata converter, database, or decision store.

Git commits, the authenticated comment, and the compact decision cache are the durable review state.
Expired artifacts can be regenerated and require no recovery ledger.
