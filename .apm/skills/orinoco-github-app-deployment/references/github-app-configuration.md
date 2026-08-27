# GitHub App configuration

Resolve the exact App owner, App name, public origin, and selected downstream repositories before changing GitHub.
App registration, ownership transfer, permission changes, secret creation/deletion, and installation changes are external mutations; confirm them when required by the operating environment.

## Required App settings

- Set GitHub's required homepage URL to the stable Orinoco Lite project or service-documentation page selected by the operator.
Do not create a service landing page merely to satisfy this field; `PUBLIC_ORIGIN/` may intentionally return `404` or `410`.
- Enable expiring user-to-server access tokens.
- Disable **Request user authorization (OAuth) during installation**. Start OAuth only through this application's `/api/auth/*-start` routes so it can create the encrypted state cookie and PKCE verifier before GitHub returns to the callback.
- Disable Device Flow; this browser service does not implement it.
- For a stable deployment, set the callback URL to exactly `PUBLIC_ORIGIN/api/auth/callback`.
- Disable callback-URL wildcard matching.
Every accepted callback must be the one exact production URL.
- If using a post-install setup URL, keep it separate from the callback.
The setup URL must never send GitHub's installation callback fields into OAuth.
- Grant repository permissions:
  - Metadata: read;
  - Actions: read;
  - Contents: write; and
  - Pull requests: write.
- Install the App only on the selected downstream repositories.
- Disable the webhook **Active** setting and subscribe to no webhook events.
This service consumes none.

Choose the App visibility deliberately:

- For an independently hosted downstream, prefer **Only on this account** with an App owned by that downstream's user or organization, then install it on selected repositories only.
This makes the account boundary enforceable.
- Use **Any account** only for a deliberately shared, public service.
A public App owner cannot prevent an external account from installing it; each installing account controls its own selected-repository scope, while the service still enforces App installation and curator permission on every request.

To minimize manual entry, an agent may generate GitHub's current official prefilled registration URL with the resolved homepage, exact callback, visibility choice, permission values, OAuth-on-install disabled, and webhook disabled.
Treat the URL as an operator convenience, not authority: GitHub's supported query parameters may change, it must contain no secrets, and the created App's settings must still be read back and verified field by field.

The service requests no OAuth scopes and rejects a nonempty returned scope.
The GitHub App does not need account-email permission: the authenticated login and stable account identifier plus the exact GitHub authorization decision are sufficient.
It uses state and PKCE S256, rejects callbacks that did not begin at its own start route, rejects non-bearer or non-expiring tokens, discards refresh tokens, and independently checks that the signed-in curator has `write` or `admin` collaborator permission.

`Contents: write` supplies repository reads for both product profiles and is used for writes only by the explicitly requested fixed-path SHACL Vue handoff.
The source-adapter review path posts authenticated pull-request comments but does not write repository contents.

## Ownership, installation, and deployment are separate

A GitHub App's owner controls its settings and client secrets.
Transferring the App does not by itself:

- move or reconfigure the hosting project;
- change `PUBLIC_ORIGIN`, the released central-service default, or a downstream's optional `site.curation_service` override;
- install the App on the new owner's repositories;
- approve newly requested permissions on existing installations; or
- rotate the client secret already configured at the host.

After a transfer, verify the visible owner and App ID, inspect the exact visibility, permission set, callback and toggle state, check for pending installation approval, and list selected repositories.
Retain the App ID and public client ID in evidence, but never a client secret.

Repository transfer can also change Pages origins and installation scope.
Reinstall or approve the App only for the repositories in scope, then repeat authenticated verification from the final deployment origin.

## Downstream readiness

Backend deployment is necessary but not sufficient.
Each downstream must have:

- the App installed on that repository;
- a trusted default-branch workflow that produces the exact source-adapter review artifact;
- trusted default-branch SHACL handoff replacement and validation behavior;
- a static site built from its exact source commit with the released editor and schema, including both **Download bundle** and **Propose via GitHub**;
- the released static source-review shell bound at `site.base_url/review/` with workflow links pointing there rather than to the central service;
- a curator with repository `write` or `admin`;
- its exact GitHub `owner/repository` derived by the trusted build from `GITHUB_REPOSITORY` or the equivalent general project identity; and
- either an omitted `site.curation_service`, which selects the released central default, or an explicit credential-free compatible backend origin with no path, query, fragment, or credentials.

For a downstream on a custom domain, verify the domain for the GitHub account or organization, configure it for the Pages site, verify its DNS and TLS, and confirm that the actual browser origin matches `site.base_url` before treating it as a unique origin.
Use GitHub's current [domain-verification](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages), [custom-domain](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site), and [HTTPS](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https) instructions rather than copying mutable DNS targets into this skill.
A downstream that remains on a shared `github.io` origin must expose the accepted explanation and explicit in-memory acknowledgment gate before either direct GitHub write path; **Download bundle** remains available without it.

Do not publish a SHACL editor-input Actions artifact for this path.
The central service does not acquire either static interface's files, assemble an editor, or render source-adapter candidates.

Do not put the client ID or either secret in a downstream repository.
A public client ID belongs at the service deployment, and both secrets belong only in the host's encrypted secret store.

## Minimal operator inputs

Ask for only values that cannot be discovered safely:

1. whether the released central service is acceptable or independent backend custody is required;
2. the chosen provider/account and intended public origin;
3. GitHub App owner and name, or the exact existing App;
4. the downstream repositories that may be installed; and
5. whether a write-path test is authorized in a named integration repository.

When the operator also asks to configure a downstream custom domain, ask only for the intended domain and discover its repository, Pages state, current DNS, verified-domain state, and `site.base_url` before requesting another value.

Discover the application commit, current settings, repository identities, and provider capabilities read-only before asking the operator to repeat them.
