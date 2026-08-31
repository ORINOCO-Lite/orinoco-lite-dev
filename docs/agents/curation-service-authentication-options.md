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

The source-adapter `/review/` flow requires a fresh in-memory acknowledgment on a shared origin.
SHACL `/edit/` displays the warning without a checkbox.
**Download bundle** remains available without GitHub sign-in, service access, or origin acknowledgment.

The custom-domain guide should lead maintainers through GitHub domain verification, Pages configuration, DNS, HTTPS, and a final `/edit/` and `/review/` check.

## Security boundary

The service trusts GitHub collaborators who already have repository write or admin permission as authorized curators.
It protects credentials from untrusted repository code and external source data, but does not add a parallel identity, authorization, transaction, or audit system.

GitHub and Git remain authoritative.
Failures are retried before a write, inspected after an uncertain write, or repaired through an ordinary pull request or revert.
