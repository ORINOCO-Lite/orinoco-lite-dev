# GitHub App configuration

Resolve the exact App owner, App name, public origin, and selected downstream repositories before changing GitHub.
App registration, ownership transfer, permission changes, secret creation/deletion, and installation changes are external mutations; confirm them when required by the operating environment.

## Required App settings

- Set the required homepage URL to `PUBLIC_ORIGIN/` unless the operator has a more appropriate stable service landing page.
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
It uses state and PKCE S256, rejects callbacks that did not begin at its own start route, rejects non-bearer or non-expiring tokens, discards refresh tokens, and independently checks that the signed-in curator has `write` or `admin` collaborator permission.

`Contents: write` supplies repository reads for both product profiles and is used for writes only by the explicitly requested fixed-path SHACL Vue handoff.
The source-adapter review path posts authenticated pull-request comments but does not write repository contents.

## Ownership, installation, and deployment are separate

A GitHub App's owner controls its settings and client secrets.
Transferring the App does not by itself:

- move or reconfigure the hosting project;
- change `PUBLIC_ORIGIN` or downstream `site.repository` and `site.curation_service` values;
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
- a curator with repository `write` or `admin`; and
- `site.repository` set to its exact GitHub `owner/repository` and `site.curation_service` set to the credential-free HTTPS receiver origin with no path, query, fragment, or credentials.

Do not publish a SHACL editor-input Actions artifact for this path.
The central service does not acquire static editor files or assemble an editor.

Do not put the client ID or either secret in a downstream repository.
A public client ID belongs at the service deployment, and both secrets belong only in the host's encrypted secret store.

## Minimal operator inputs

Ask for only values that cannot be discovered safely:

1. whether central hosting is acceptable or independent custody is required;
2. the chosen provider/account and intended public origin;
3. GitHub App owner and name, or the exact existing App;
4. the downstream repositories that may be installed; and
5. whether a write-path test is authorized in a named integration repository.

Discover the application commit, current settings, repository identities, and provider capabilities read-only before asking the operator to repeat them.
