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
A downstream may set one `site.curation_service` HTTPS origin to use a compatible self-hosted service.
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
