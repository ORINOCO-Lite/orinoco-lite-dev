# Repository workflows and central authentication

This is the active implementation plan for the maintainers working on issue 249.
It records the requested replacement architecture and pending design choices.
It is not a new runtime contract or a compatibility requirement.
Promote the settled design into the existing contracts and remove this plan when implementation is complete.

## Agreed outcome

The central GitHub authentication service authenticates people and GitHub Actions jobs and issues short-lived GitHub credentials.
Repository workflows own proposal creation, metadata materialization, validation, template updates, and website gitlink updates.
The shared GitHub App remains the GitHub identity and installation mechanism for those credentials.

GitHub collaborators use the editor without additional Orinoco operation opt-ins or current-default-head authorization requirements.
SHACL Vue submission requires the signed-in user's GitHub write access to the website repository and, when separate, the metadata repository.
App installation does not substitute for that user's access or create standing authority between repositories.
Proposals may start from the deployed source even when a default branch has advanced.
GitHub permissions, repository rules, PR checks, and merge conflicts govern adoption.
Authentication does not decide whether a bundle is valid, a named validation job passed, or a proposal is ready to publish.

Breaking existing downstream workflows is accepted.
Do not add migration shims, legacy endpoints, or compatibility modes to preserve the old service.
The user has asked to stop implementation and return to design whenever a material choice is unresolved.

## Submission and repository authority

### Initial submission

Agreed with the user: the downstream editor receives a repository-scoped GitHub user access token, holds it only in memory, uploads the unchanged bundle to a temporary submission branch, and starts a repository workflow.
The workflow creates the actual proposal and applies the edits.
The central service neither receives the bundle nor makes these GitHub writes.

This initial upload is a repository write performed by the browser.
The user explicitly accepted this browser write; workflows perform the subsequent processing and proposal writes.
GitHub can restrict the token by repository and permission, but not to the submission branch or one file.
The credential remains limited by the signed-in user's GitHub access.
Check access to both participating repositories before beginning the upload.
If the user cannot write the website repository, refuse the submission even when they can write its metadata repository.
Enforce this through the authenticated submission path, not only by disabling a browser button.
Scope it to the required repository, omit workflow-file write permission for ordinary editing, and revoke it after submission.
Check the scoped token's actual expiry behaviour before relying on it.

GitHub supports [scoped user access tokens](https://docs.github.com/en/rest/apps/apps#create-a-scoped-access-token).
The editor currently accepts 10 MiB bundles, whereas a [repository dispatch payload](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event) must be smaller than 64 KB.
Use GitHub to retain the uploaded input and dispatch its commit coordinate; do not shrink the editor's limit or introduce a central upload store to fit dispatch.
Private metadata bundles must stay in the metadata repository, even when the website repository is public.

Do not retain a central submission proxy or describe browser writes as authentication.

### User authority, without a standing repository connection

The user rejected standing connections between repository workflows.
Submission must follow the signed-in user's GitHub permissions.
Do not add repository pairing, cross-repository trust lists, or an App-installation shortcut that lets a metadata-only contributor submit a website update.
Preserve the GitHub-authenticated submitter's identity; a browser-supplied login or Git commit author field is not proof of that identity.

GitHub's [workflow token](https://docs.github.com/en/actions/concepts/security/github_token) is limited to its own repository.
The service can authenticate a running job through [GitHub OIDC](https://docs.github.com/en/actions/reference/security/oidc), but that identity alone does not grant access to another repository on a user's behalf.
Credential delivery must follow the user's established authority for the submission.
Do not silently replace user access with broader installation access.
Whether later workflow writes use user tokens or a submission-specific delegation requires a concrete design that preserves this rule; checking a generic collaborator role is not proof that a bot has identical GitHub privileges.

### Delayed completion

Alice has write access to both repositories and submits an edit.
Bob has write access only to the metadata repository and later merges its PR.
Agreed with the user: the workflows automatically finish Alice's existing website proposal under her original submission authorization.
Bob cannot use that authorization to submit a new website edit through SHACL Vue.
This is distinct from granting the repositories standing access to one another.

Credential delivery must distinguish completion of this submission from a new request.
Do not infer permission-revocation semantics or introduce repeated consent checks from the submission rule alone.
Expiring [GitHub user tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/refreshing-user-access-tokens) last eight hours; a later merge cannot assume the browser's submission token is still available.
The implementation must neither retain credentials in repository data nor fall back to the rejected standing connection.

## Component changes

| Component | Resulting responsibility |
| --- | --- |
| GitHub App registration and installations | GitHub identity and repository permission grants |
| Authentication service | OAuth, origin-bound credential delivery, scoped user tokens, Actions OIDC verification, authorized workflow credentials, revocation |
| Downstream editor and review interface | Edit/review interaction, authenticated submission, status and recovery links |
| Metadata repository workflows | Apply submitted metadata changes, create/update metadata PRs, react to merges |
| Website repository workflows | Validate the composed website, create/update website PRs and gitlinks, run source adapters and template updates |
| Orinoco package | Reusable bundle, metadata, validation, composition, and workflow operations |
| Template and repository setup | Install the small workflow definitions, without standing cross-repository grants |

For metadata stored directly in the website repository, the website workflows perform both roles.
For submodules, ordinary content writes should run in the repository that owns the content.
Exact placement of composed validation and event delivery must preserve the user-authorized submission.

The existing service write paths are SHACL proposal creation in `shacl-proposal.ts`, review comment submission in `api/submit.ts`, and merge-time gitlink mutation in `metadata-merge.ts`.
The operation-specific credential routes also contain proposal, validation-job, retry, and branch-state decisions.
Move product behaviour to repository code and delete those service responsibilities.
Template updates already publish from a workflow; simplify their credential exchange rather than replacing their updater.

Keep `tool.orinoco.service.url` as the authentication service coordinate.
A source-directory rename is not necessary to establish the new boundary.
Revise the existing authentication, editor, source-review, and source-adapter contracts, project design, setup guidance, and affected development/deployment skills together.
Remove obsolete operation options and tests instead of retaining ignored settings.
Actual scheduling choices belong in workflow triggers, not in service permission checks.

## Implementation sequence

1. **Implement submission-specific credential delivery.**
   User permissions at submission, the absence of standing repository connections, and automatic completion of Alice's proposal are agreed.
   Reuse the existing signed authorization mechanism to bind the authenticated submitter, participating repositories, uploaded input, and workflow implementation for this submission.
   OIDC proves the later caller is that workflow; repository code owns the proposal processing and completion checks.
   Preserve the selected workflow revision for delayed completion, without comparing it to a subsequently advanced default head.
   Prove that another user or workflow cannot reuse this authorization to submit different changes or obtain unrelated access.
2. **Prove GitHub's required primitives.**
   In the designated demo, exercise scoped user tokens, browser API/CORS behaviour, private input retrieval, and dispatch with an immutable uploaded input.
   Check review-artifact access as well as editor submission.
   Verify that the proposed scopes preserve user access and that credentials cannot reach unrelated repositories.
   Test that metadata write access without website write access cannot start a SHACL proposal.
   Return to design if direct browser access requires another transport component.
3. **Implement the small authentication service.**
   Reuse OAuth, session sealing, GitHub token issuance, and OIDC verification.
   Separate credential authentication from proposal processing.
   Remove central comments, branches, commits, PR creation, and merge webhook processing.
   The service may read GitHub identity and credential-authority configuration; it does not interpret bundles, curation decisions, job names, or validation results.
4. **Implement a complete editor path.**
   Add browser submission and repository workflow processing together.
   Reuse existing bundle parsing and materialization.
   Build proposals from their source snapshots, create normal PRs, and expose pending, successful, and failed workflow states in the editor.
   The final proposal branch should contain ordinary metadata commits; use the separate submission branch to retain input during processing.
5. **Complete submodule coordination.**
   Install the metadata workflow as part of the same setup operation.
   Keep private input private; validate the website with the selected metadata.
   After metadata merge, obtain the resulting GitHub merge commit and update the website proposal under the agreed completion authority, including squash and rebase merges.
   Workflow retries must resume existing work and preserve concurrent edits.
6. **Move source review and simplify template updates.**
   Submit review decisions through the agreed downstream-to-GitHub path and let workflows record/finalize them.
   Preserve source-adapter semantics and existing DataLad provenance.
   Use the same credential mechanism for template publishing and private metadata reads.
   Remove the old operation-specific service gates and unused settings.
7. **Exercise the final candidate end to end.**
   Run the real editor and review UI against exact package/template candidates in the leej3 demos.
   Complete the checks below after the final relevant change, rather than relying on the previous architecture's test.
8. **Deliver and deploy the verified replacement.**
   Prepare reviewable package and template changes, with retained package pins after merge.
   Preserve the human-edited description of template PR 98.
   Deploy the tested service and matching demo workflows as one deliberate cutover, then remove the obsolete production webhook.
   Preserve the prior deployment for recovery; do not turn downstream compatibility into a release gate.

## Behaviour to preserve and prove

- A real browser edit creates a working PR after either default branch advances.
  The source snapshot remains identifiable; GitHub exposes actual merge conflicts.
- A user with metadata write access but no website write access cannot submit through SHACL Vue, including by calling the submission endpoints directly.
  The same applies when website access exists but required metadata access does not.
  A known access failure is reported before creating submission branches or proposals.
- An existing proposal can receive another edit, and a failed workflow can be rerun without reauthentication solely because a branch advanced or the run attempt increased.
- Metadata creation, updates, invalid bundles, and actual conflicting edits produce understandable results without losing the downloaded/uploaded input.
- A private metadata repository works with a public website repository without publishing private bundle contents or credentials in the website repository, public artifacts, or logs.
  Any intentionally public generated site content remains a downstream publication choice.
- Metadata merge updates the website gitlink and runs the website checks under the agreed completion authority.
  Exercise ordinary and squash/rebase merge results, duplicate delivery, and a concurrent edit to the website proposal.
- A retry after an uncertain submission finds the existing submission or proposal rather than duplicating it.
  Partial cross-repository completion is recoverable by rerunning the owning workflow.
- A source review submission finalizes the existing proposal through a workflow, and a template update publishes its PR through the same authentication mechanism.
- Credential tests cover an unrelated installed repository, a forged/expired OIDC identity, an untrusted PR workflow, missing GitHub grants, and revoked access.
  Do not use proposal freshness or named CI steps as substitutes for authenticating the caller.
- Repository rules remain effective; credentials and OIDC access are kept out of jobs that execute untrusted proposal code.
  Git updates preserve concurrent work through ordinary merge/forward-update behaviour and leases where needed, with recoverable conflicts instead of silent overwrites.
- The deployed central service performs only authentication/credential operations and the reads needed to authorize them.
  Verify that no proposal, comment, commit, ref-update, or merge handler remains in its active routes.

Use existing tests, GitHub runs and PRs, deployment history, and direct browser observations as evidence.
Do not add a new ledger or proof framework.

## Current state

The current implementation and GitHub APIs have been inspected.
The user agreed that the editor uploads with a repository-scoped user token and workflows process the submission.
The user rejected standing repository connections and requires website write access for SHACL Vue submission.
The user agreed that automation finishes Alice's authorized proposal even when Bob, who lacks website write access, merges its metadata PR.
Implementation is proceeding under those decisions; return to design if a further material choice arises.
No replacement service or workflow has been deployed.
