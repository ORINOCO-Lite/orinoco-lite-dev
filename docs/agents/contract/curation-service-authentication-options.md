# Curation service authentication

The downstream site owns `/edit/` and `/review/`.
The curation service supplies only short-lived GitHub authentication, verified reads, and authenticated GitHub transport.
It has no landing page, editor, review UI, or durable store.

## Curator authentication

Curators sign in through the Orinoco Lite GitHub App.
This provides GitHub's repository installation and collaborator controls without requesting account email access.
The service uses the GitHub user ID and login for identity.

The App uses OAuth state, PKCE, expiring user tokens, secure short-lived cookies, and an exact callback URL.
Tokens, cookies, OAuth codes, and bundle contents are never logged or stored as repository data.

Before every write, the service revalidates the installed repository, curator permission, trusted downstream configuration, origins, pull request, commits, current head, and submitted artifact or bundle.

## Service operator authentication

Hosting-provider access is separate from curator GitHub authorization.
For Cloudflare, an operator may authenticate directly to Cloudflare, while CI uses a narrowly scoped Cloudflare API token.
Cloudflare's optional “Sign in with GitHub” account login may request a GitHub email address; the Orinoco GitHub App does not need that relationship.

| Method | Benefit | Cost |
| --- | --- | --- |
| Direct Cloudflare login | Keeps hosting administration independent of GitHub | Separate account and login |
| Scoped Cloudflare API token | Narrow automation access | Token rotation and secret management |
| Cloudflare social login through GitHub | Convenient operator login | Exposes the GitHub account email to Cloudflare |

## Downstream configuration

Repository identity is derived by the trusted build.
Downstreams do not repeat it in curation-specific configuration.

The released central service is the default.
A downstream may set one `tool.orinoco.service.url` HTTPS origin to use a compatible self-hosted service.
Browser-supplied values are hints; the service verifies the effective origin and repository from trusted base configuration before a write.

## Browser trust

Unique or custom-domain origins receive the normal direct-GitHub flow.
Shared `github.io` origins explain that repositories under the same account share one browser origin.

SHACL `/edit/` displays the warning.
**Download bundle** remains available without GitHub sign-in or service access.

The custom-domain guide should lead maintainers through GitHub domain verification, Pages configuration, DNS, HTTPS, and a final `/edit/` and `/review/` check.

## Security boundary

The service trusts GitHub collaborators who already have repository write or admin permission as authorized curators.
It protects credentials from untrusted repository code and external source data, but does not add a parallel identity, authorization, transaction, or audit system.

GitHub and Git remain authoritative.
Failures are retried before a write, inspected after an uncertain write, or repaired through an ordinary pull request or revert.

## App credentials and automated completion

Downstreams MUST need only the same curation App installed on each participating repository, with no additional App, personal access token, or private key.
This product requirement includes template maintenance as well as metadata proposals.
Reuse the existing Actions OIDC verification, App signing key, installation-token issuance, and revocation; add only the authorization checks required by the operation.
When a product operation needs additional GitHub permissions or backend support, extend the same App and service.
Automated pull requests and messages use the App's bot identity; interactive curator actions retain the authenticated user's identity.
Installation alone MUST NOT authorize cross-repository access.
The operator MUST protect signing keys in backend secret storage with restricted access, rotation, and revocation; keys MUST NOT enter source, browsers, downstream secrets, artifacts, or logs.

Interactive operations MUST use expiring user access tokens; installation tokens MUST NOT substitute for failed user authorization.
Automated materialization MUST remain bound to the curator-authorized proposal: immutable repository and curator identities, bundle, source and handoff commits, permitted operation, trusted workflow revision, and a short expiry.
Before granting write access, the service MUST recheck installations, curator permissions, both draft heads, and successful validation.
Expired, revoked, stale, or ambiguous authorizations and replayed writes MUST fail closed.

Workflow callers MUST authenticate through GitHub-signed Actions OIDC with verified signature, issuer, audience, expiry, repository, event, workflow revision, and run identity.
Proposal content MUST remain data; untrusted code MUST NOT receive credentials or an OIDC capability that can obtain them.
Installation tokens MUST be limited to required repositories and permissions, exposed only to trusted transport steps, and revoked when finished.
Because tokens are not path- or branch-scoped, the trusted workflow MUST enforce allowed paths and exact-head leases.
The App MUST NOT acquire bypass permissions, modify repository protections, or merge proposals to complete materialization.

## Functionality and permissions

This mapping is the normative permission requirement for each operation, not a separate runtime registry.
Read access is included in write access; Metadata read is the GitHub-required baseline.
Permissions used for verification need not be included in the later write token.

| Functionality | App repository permissions used | Purpose |
| --- | --- | --- |
| App installation | Metadata: read | GitHub-required repository identity baseline |
| Review source proposals | Contents: read; Pull requests: read; Actions: read | Read proposed records, pull requests, and workflow artifacts/results |
| Submit edits and curation decisions | Contents: write; Pull requests: write | Record authorized changes and create or comment on proposals |
| Automated SHACL proposal materialization | Actions: read; Contents: write; Pull requests: read | Verify the authorized handoff and record its materialized metadata |
| Automated curation completion | Actions: read; Contents: write; Pull requests: write | Verify the originating workflow and publish its authorized result |
| Template updates | Actions: read; Contents: write; Pull requests: write; Workflows: write | Verify the run, push the Copier update including `.github/workflows/`, and open a bot-owned draft |
| Editing from a development deploy preview | Commit statuses: read, in addition to edit permissions | Verify the successful preview for the exact draft head before allowing edits |

An App registration requests the union of permissions needed by the features its operator supports.
A self-hosted service may use its own App registration with a smaller permission set.
GitHub grants requested repository permissions together; existing installation owners may decline additions and retain their previous grants.
Per-operation installation tokens MUST request only the repositories and permissions needed for that stage, within the installation's grants.
See [GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app) and [installation-token restrictions](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation).

### Downstream operation choices

The downstream owner MUST be able to opt into automated operations independently of the App's installed permission set.

`tool.orinoco.operations` in `pyproject.toml` contains independent boolean choices:

```toml
[tool.orinoco.operations]
shacl_materialization = false
automated_curation = false
template_updates = false
preview_editing = false
```

These respectively enable automated SHACL proposal materialization, automated curation completion, template-update proposals, and editing from verified development previews.
Missing choices are disabled; unknown names and nonboolean values are invalid.
Local editing, bundle downloads, and read-only review do not opt into automation or preview editing.
Creating a SHACL handoff for automated materialization requires `shacl_materialization`; preview-origin proposals additionally require `preview_editing`.
The single-repository SHACL workflow also checks current default-branch policy before publishing with its workflow token.

Copier initializes public site settings but MUST NOT ask operation-permission questions.
The App post-install setup page explains the operations and required permissions and directs owners to edit `[tool.orinoco.operations]` in root `pyproject.toml`.
That site-owned configuration is authoritative at runtime, not Copier's answer history.
The configuration boundary is defined in [Downstream configuration files](../../configuration-files.md).
The configuration schema and user-facing controls MUST expose the operation, required permissions, and purpose from this mapping.
Template updates MUST NOT silently enable additional operations or broaden an existing choice.

Before issuing write access or performing a write, the service MUST read the current downstream policy from its trusted default branch and require the operation to be enabled.
The operation's required permissions MUST fit both the downstream's enabled choices and the App installation's actual grants; otherwise the service MUST reject it with the missing choice or permission identified.
A workflow input, proposed configuration change, update branch, or browser request MUST NOT authorize itself or broaden that policy.
Changing a workflow file alone MUST NOT bypass the service's decision.
A disabled operation MUST NOT be authorized merely because the App has the corresponding GitHub permission.
These controls govern this service's use of its authority; they do not revoke GitHub-level grants or prevent independent repository collaborators from making changes.

Authorization tests MUST exercise allowed operations, disabled operations despite sufficient App permissions, missing GitHub grants, and attempted opt-in through untrusted request or proposed-branch configuration.
Test observable grants and rejections rather than maintaining another permission inventory or checking documentation text.

## Development credentials

A scoped development token may be used to isolate a test or unblock development.
State which behavior it tests and which central-App behavior remains unverified; a successful PAT-based write does not verify App authorization or bot attribution.
When requesting a token, provide a creation link with the required permissions, the repository selection and expiry, and `gh secret set SECRET_NAME --repo OWNER/REPO` so the user can enter the value interactively.
Keep temporary test credentials out of the downstream product requirements.

## Template update automation

Template updates reuse the installed curation App and Actions OIDC authentication.
The service verifies the dispatch actor’s repository write permission, immutable repository identity, current update base, active run, and workflow content against the default branch.
Only the separate publishing job may receive a repository-scoped installation token after update preparation completes.
Package installation, Copier, and candidate validation run without write credentials or OIDC access in the preparation job.
The publishing job transports recorded commits, opens the bot-owned draft, reports the result, and revokes access without executing updated code.
Its token requires contents, pull request, and workflow write permissions; it never merges the update.
Workflow files under `.github/workflows/` are part of the Copier scaffold, so a template update can change them along with other template-owned files.
GitHub's workflow write permission authorizes those file changes; merely running an existing workflow or posting a pull-request description does not require it.
The template authorization route is part of the existing central service and shares its credentials; deploying that code and approving the App's additional GitHub permission are separate operator actions.
