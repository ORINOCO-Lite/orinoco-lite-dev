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

The supported downstream setup MUST require only the curation App installation on each participating repository.
A downstream MUST NOT need another App, a personal access token, or the curation App's private key.
Installation alone MUST NOT authorize an arbitrary user, workflow, or repository to exercise the App's access to another repository.

The service MUST follow [GitHub's App security guidance](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app) and [private-key guidance](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps).
The operator MUST keep signing keys in protected backend secret storage, restrict access, and support rotation and revocation.
A non-exportable, sign-only key vault SHOULD be used where supported.
Keys MUST NOT enter source, browser assets, downstream secrets, workflow artifacts, or logs.
Operator secrets are configuration, not retained curator sessions.

Interactive operations MUST use expiring user access tokens so GitHub enforces both user and App permissions, including organization access controls.
An installation token MUST NOT substitute for failed user authorization.
Automated materialization MAY act as the App only within the explicit, authenticated proposal previously authorized by the curator in both repositories.
The service MUST bind that authorization to the immutable repository and curator identities, submitted bundle, exact source and handoff commits, permitted operation, trusted workflow code, and a short expiry.
It MUST recheck current installations, curator permissions, and both draft heads before granting automated write access.
An expired, replayed after completion, revoked, stale, or ambiguous authorization MUST fail closed.

A workflow caller MUST authenticate with GitHub-signed Actions OIDC claims with verified signature, issuer, audience, expiry, immutable repository identity, event, workflow revision, and run identity.
A repository name, workflow name, browser input, or successful check alone is insufficient authority.
The approved workflow MUST execute trusted source code and treat proposal content as data; untrusted code MUST NOT receive credentials or an OIDC capability that can obtain them.
Any installation token MUST be limited to the required repository and permissions, exposed only to trusted transport steps, and revoked when finished.
GitHub installation tokens are not path- or branch-scoped: allowed paths, validation, and exact-head leases MUST also be enforced by the trusted implementation.
The App MUST NOT acquire ruleset bypass, modify repository protections, or merge proposals to complete this operation.

Tests MUST cover unauthorized repositories and workflows, forged or expired grants, revoked access, changed heads, replay, disallowed paths, and partial cross-repository failure, as well as successful completion.
A passing functional test is not evidence that these authorization boundaries hold.
