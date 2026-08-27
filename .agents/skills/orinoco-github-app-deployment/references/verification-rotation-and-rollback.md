# Verification, rotation, and rollback

Verify in increasing order of authority.
Record response codes and immutable coordinates, but do not record cookies, OAuth codes, access tokens, client secrets, or the session-seal key.

## Deployment verification

### 1. Build and configuration

- Confirm the checkout is clean and at the reviewed application commit/tree.
- Re-run `npm ci --ignore-scripts` and `npm run check` using declared tools.
- Verify the runtime archive, manifest digest, and staged directory name.
- Confirm all five configuration keys exist with the correct public/secret classification.
- Confirm there are no durable storage bindings and no token or cookie logging.
- Confirm the deployment has an immutable identifier and known rollback target.

### 2. Anonymous, non-mutating probes

- `/`, `/review/`, and `/edit/` return the expected application content.
- `/review` and `/edit` redirect exactly once to their slash forms.
- One staged `/editor-runtime/<digest>/...` resource returns the expected immutable bytes and content type.
- `/api/session` returns HTTP 200 with `authenticated: false` while anonymous.
- A callback probe with exactly `code=probe`, `state=probe`, and `iss=https://github.com/login/oauth`, but no OAuth-state cookie, returns HTTP 401 `missing_oauth_state` before any token exchange.
An `iss`-only probe is malformed and correctly returns HTTP 400 `invalid_oauth_callback`.
- Authorization starts with a 302 to GitHub containing the exact client ID, callback, state, and PKCE challenge, and no OAuth scope.
- Security and `no-store` response headers are present, and the callback adapter emits two distinct `Set-Cookie` fields in the actual wire/header-list representation, not one comma-joined field.

Do not treat a green root-page probe as backend evidence.
It proves only that static hosting works.

### 3. Authenticated read-only browser proof

Use one selected integration repository and complete a real sign-in.
Without submitting a review or proposing a handoff, verify:

- the session identifies the expected user;
- repository-scoped discovery succeeds for the selected installed repository;
- a source-adapter proposal renders after exact artifact/head verification;
- an exact-head SHACL editor route renders the staged released editor; and
- logout clears the session.

Also verify that repository-scoped discovery rejects a read-only user or an uninstalled repository when such a safe fixture is available.

### 4. Explicitly authorized write proof

Only after separate authorization, use a disposable or designated integration repository to test the comment and/or fixed-path handoff flow.
Record the exact test repository, pull request, head, artifact, written refs, and cleanup.
Verify trusted replacement and absence of the temporary bundle from the final branch.
Never use the real production site as a write fixture.

## Failure guide

| Symptom | Likely causes |
| --- | --- |
| `github_oauth_error` with the safe client-credentials message | Host and GitHub client secrets do not match, or the wrong App client ID is deployed. The raw GitHub error is intentionally not exposed. |
| `missing_oauth_state` after login | Cookie lost through origin/proxy behavior, folded `Set-Cookie`, wrong callback origin, or ten-minute expiry. |
| `invalid_oauth_callback` | Wrong callback or setup URL, stale application revision, duplicate/foreign fields, or unexpected issuer. |
| Editor `configuration_error` | Missing asset binding, manifest-digest mismatch, missing staged runtime, redirect, or transformed asset response. |
| GitHub 403/404 | App not installed, permission approval pending, user lacks write/admin, or session token expired. |
| Artifact failure | Egress blocked, redirect auto-followed/rewritten, destination host rejected, or provider size limit exceeded. |
| Static UI works but APIs 404 | Only `dist/` was deployed; Functions or the provider adapter is absent. |

Both the successful OAuth callback and logout emit two cookies in one response.
Exercise both paths when validating an adapter's header behavior.

## Rotation

### Client secret

1. Create a second, overlapping GitHub client secret.
2. Update the hosting secret without exposing it.
3. Deploy and complete a real OAuth flow.
4. Only after proof, delete the old GitHub secret.

Do not delete the working secret first.
After deletion, a rollback that still expects it cannot authenticate.

### Session seal key

Only one seal key is supported.
Rotation immediately invalidates every OAuth state and session cookie.
Schedule a forced sign-in, replace the secret, deploy, and repeat the OAuth proof.
Never attempt to preserve or decrypt old cookies.

### Origin

Coordinate TLS/DNS or provider routing, `PUBLIC_ORIGIN`, GitHub callbacks, and every downstream `CURATION_REVIEW_APP_ORIGIN`.
Existing cookies are origin-bound; require a fresh sign-in.
During a migration, temporarily retain the old exact callback and add the new exact callback with wildcard matching disabled.
Deploy and verify the new origin read-only, cut downstreams over and disable writes through the old origin, then remove the old callback.
Never replace the only working callback before the new flow is proven or leave both origins write-capable through an ambiguous cutover.

### GitHub App ownership or permissions

After transfer, confirm the owner, App ID, public client ID, callback, expiring token option, permissions, and selected installations.
Permission increases may remain pending until an installation owner approves them.
Repeat authenticated verification even when the client ID and secret were retained.

## Rollback and evidence

Treat these as one rollback unit:

- application commit/tree and hosting adapter;
- public values;
- staged runtime directory and manifest digest;
- route/header configuration; and
- compatible secret generation.

Retain the prior immutable deployment coordinate until the new deployment has passed authenticated verification.
Roll back the whole unit; do not mix old code with a new editor digest or vice versa.

Record:

- timestamp and operator/agent attribution;
- application commit, tree, and clean-state proof;
- runtime release URL, archive digest, manifest digest, and staging report;
- public origin and client ID;
- App ID, owner, permissions, and selected repositories;
- immutable deployment ID/URL and provider runtime class;
- build and probe results;
- authorized write-test coordinates, if any; and
- rollback coordinate and rotation consequences.

Never record secret values, OAuth codes, cookies, access or refresh tokens, or raw provider logs that contain them.
Historical deployments may be useful examples, but they are not defaults or substitutes for current evidence.
