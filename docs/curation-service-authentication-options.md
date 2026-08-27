# Curation service and authentication options

Status: accepted design rationale; normative requirements are in [`milestone-6.md`](milestone-6.md), [`github-curation-review.md`](github-curation-review.md), and [`github-shacl-vue-edit.md`](github-shacl-vue-edit.md)

John Lee accepted this architecture and its shared-origin policy on 2026-08-27 as M6-D007 and HR-229.
This note preserves the authentication options and design rationale without creating a second normative contract.

## Accepted outcome

The downstream deployment owns both user interfaces:

- `/edit/` is the SHACL Vue editor and exposes **Download bundle** and **Propose via GitHub** for the same unchanged bundle; and
- `/review/` is the source-adapter decision interface.

The main browser remains on those downstream routes.
The central Orinoco Lite service has no landing page, editor, review application, upload page, or final confirmation page.
It supplies only short-lived GitHub authorization and verified GitHub transport.
Self-hosting replaces that service without changing the downstream interfaces.

## Downstream configuration

Repository identity is a property of the downstream build, not a curation service preference.
The normal GitHub build already has a trusted repository coordinate in `GITHUB_REPOSITORY`, and the template knows the repository it is creating.
The build writes that coordinate into generated `/edit/` and `/review/` configuration.
A user does not repeat it in a special curation setting.

`site.curation_service` is an optional override.
When it is absent, the released integration uses the Orinoco Lite central-service origin.
When it is present, it names a credential-free HTTPS origin running the same service contract.
The self-hosting skill changes one override and verifies the replacement host and GitHub App rather than teaching the editor and reviewer another repository coordinate.

For a non-GitHub or locally assembled build, repository identity may still be supplied as a general build input.
It does not become a second curation-only knob.
Regardless of how the static build obtained the value, the service must verify it independently against GitHub objects, the App installation, and the trusted repository configuration.
Browser configuration is a routing hint, not authorization.

## Two different authentication relationships

The curator and the service operator authenticate to different systems for different reasons.
Combining them makes Cloudflare deployment permissions look like curator permissions when they are not.

### Curator to GitHub

The product-facing **Sign in with GitHub** flow remains a GitHub App user-to-server authorization.
GitHub App user tokens use the App's fine-grained permissions rather than OAuth App scopes.
Effective access is the intersection of:

- repositories selected for the App installation;
- the App's declared repository permissions; and
- the signed-in curator's own access.

The App does not need account-email permission, and the service does not need the curator's email address.
It needs the authenticated GitHub login and stable GitHub account identifier for display and audit correlation, plus GitHub's authorization decision for the exact repository operation.
The service continues to check `write` or `admin` access immediately before a write.

This differs from a GitHub OAuth App: `user:email` is an OAuth scope that grants access to email addresses.
It is not requested here.
See GitHub's [GitHub App user-token documentation](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app), [permission guidance](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app), and [OAuth App scope reference](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps).

### Operator to Cloudflare

Cloudflare authentication is needed only when a maintainer deploys or changes the backend.
It is not part of a curator session.

| Operator method | Advantages | Costs and privacy properties | Recommended use |
| --- | --- | --- | --- |
| Cloudflare account login without GitHub social login | Interactive and avoids granting Cloudflare access to GitHub account data for login | The operator still has a Cloudflare account and its normal account email; account recovery and MFA remain Cloudflare concerns | Preferred for an interactive maintainer |
| Narrow Cloudflare API token | Can be limited to the required account, resources, and deployment permissions; suitable for CI | A bearer secret must be stored, rotated, and kept out of the repository and browser | Preferred for CI or repeatable headless deployment |
| **Sign in with GitHub** on Cloudflare's own login page | Convenient when the operator already uses that login | Cloudflare says it uses the primary GitHub email to find or create the Cloudflare account; this is unnecessary exposure for Orinoco and cannot be changed by the Orinoco App | Optional operator choice, not an Orinoco requirement |

Cloudflare documents that its GitHub social login uses the account's primary GitHub email.
A GitHub username is not an interchangeable account key in that Cloudflare-managed login flow.
Avoiding that email grant therefore means using another Cloudflare login method or a scoped API token, not changing the Orinoco curator flow.
See Cloudflare's [login-method documentation](https://developers.cloudflare.com/fundamentals/user-profiles/login/) and [API-token guidance](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/).

## Backend-only browser flow

Removing the central application is achievable.
Removing every service-origin browser document is not compatible with all of the desired security properties.
OAuth must return to a browser context, and that context must retain the service's host-only, `HttpOnly` session cookie without exposing the GitHub token to downstream JavaScript or relying on third-party cookies.

The accepted flow is:

1. The downstream `/edit/` or `/review/` route creates a random one-time nonce and opens `/api/auth/start` at the configured service origin in a popup.
2. The service binds the exact downstream origin, repository, operation, popup relationship, and nonce into expiring OAuth state, sets a host-only session cookie, and redirects the popup to GitHub.
3. GitHub redirects the popup to `/api/auth/callback`.
The backend exchanges the code and returns a tiny, generated, content-security-policy-locked transport document.
This is a protocol endpoint, not a navigable application or landing page.
4. The popup and its exact opener complete a nonce-bound `postMessage` or `MessageChannel` handshake.
Tokens and CSRF material never cross it.
5. The downstream displays the authenticated login, repository, pull request, commits, paths, dispositions, and public-history warning.
The user confirms there.
The popup uses its same-origin session to perform the verified GitHub request and then closes.
6. If the live SHACL handoff fails, the user keeps the downloaded bundle and selects it again on the downstream `/edit/` route before retrying.
The service does not host an upload fallback or retain the bundle.

The root service URL and obsolete presentation routes return a small `404` or `410` response.
Deployment may use a Cloudflare Worker, Pages Functions, or another suitable runtime; the contract does not require a Pages frontend or any static assets.
Calling the current deployment “Pages” describes its hosting product, not a product requirement.

## Accepted browser trust policy

Moving the final confirmation from the central origin to the downstream is the material security tradeoff in this design.
Browser messaging authenticates an origin, not a path.
A GitHub Pages project site can share its origin with other pages under the same account hostname, so another compromised page on that origin cannot be distinguished merely because the intended UI is at `/edit/` or `/review/`.

The accepted shared-origin mitigation is defense in depth:

- exact opener-window, origin, operation, repository, and nonce binding;
- short-lived, one-shot sealed state and host-only secure cookies;
- a minimal callback document with a restrictive CSP, no storage, no third-party scripts, and no framing;
- selected-repository GitHub App installation and minimum App permissions;
- server-side revalidation of collaborator access, repository, pull request, commits, artifact or bundle, permitted paths, and exact head immediately before any write; and
- a complete downstream confirmation summary before the final click.

These controls substantially constrain an attack, but they do not make two paths on one origin separate principals.
A unique downstream origin is the stronger option if path-level impersonation is unacceptable.
A static secret embedded in the site cannot solve this because any script on the same origin can read it.

A custom or otherwise unique downstream origin therefore receives the normal low-friction direct-GitHub flow.
A shared `github.io` deployment shows a clear origin-wide security explanation and requires a visible, explicit, in-memory acknowledgment before enabling a direct GitHub write.
The acknowledgment is not stored in local storage, a cookie, service state, or tracked configuration and is not treated as authorization or path proof.
The SHACL editor keeps **Download bundle** enabled without that acknowledgment, GitHub sign-in, or a reachable service.

The template and deployment skill guide maintainers through GitHub's current [domain verification](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages), [custom-domain configuration](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site), and [HTTPS enablement](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https).
They do not freeze mutable DNS targets.

## Options considered

| Option | Main URL | Token isolation | User-facing central page | Assessment |
| --- | --- | --- | --- | --- |
| Downstream UI plus minimal service popup transport | Remains downstream | Yes | No | Accepted, with the shared-origin acknowledgment or a unique downstream origin |
| Central confirmation or upload page | Remains downstream except for popup | Yes | Yes | Current direction; rejected because it duplicates the product interface |
| Full-window OAuth redirect and return | Temporarily leaves downstream | Yes | Callback only | Avoids a popup but loses in-page state and violates the requested URL behavior |
| Give a credential to downstream JavaScript and call GitHub or the service directly | Remains downstream | No | No | Reject: downstream XSS or another same-origin page could obtain the credential |
| Download and manual GitHub submission only | Remains downstream | Yes | No | Safe fallback, but does not provide the requested direct proposal experience |

## Implementation consequences

The central React presentation surface is not part of the final service.
The normative profiles and human-decision register record the accepted policy.
Implementation:

1. make the central service origin a default with one downstream override;
2. derive repository identity at trusted build time;
3. move both confirmation experiences and SHACL file reselection downstream;
4. replace the central routes with API handlers and the minimal callback/transport response;
5. remove root, `/edit/`, review, upload, and final-confirmation presentation routes and assets; and
6. validate editor proposal creation and source review end to end while the browser's main URL remains on the deployed downstream site.
