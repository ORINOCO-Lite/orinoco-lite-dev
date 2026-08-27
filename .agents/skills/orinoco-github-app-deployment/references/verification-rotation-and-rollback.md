# Verification, rotation, and rollback

Verify in increasing order of authority.
Record response codes and immutable coordinates, but do not record cookies, OAuth codes, access tokens, client secrets, or the session-seal key.

## Deployment verification

### 1. Build and configuration

- Confirm the checkout is clean and at the reviewed application commit and tree.
- Re-run `npm ci --ignore-scripts` and `npm run check` using the declared tools.
- Confirm the deployment contains both the static application and the checked Functions adapter.
- Confirm exactly the two public values `PUBLIC_ORIGIN` and `GITHUB_CLIENT_ID` and the two encrypted secrets `GITHUB_CLIENT_SECRET` and `SESSION_SEAL_KEY` are available.
- Confirm `EDITOR_RUNTIME_MANIFEST_SHA256`, staged editor files, editor-input artifacts, and durable storage bindings are absent.
- Confirm there is no token, cookie, or received-bundle logging.
- Confirm the deployment has an immutable identifier and a known successful production rollback target.

The backend has no runtime release or manifest coordinate.
The downstream static-site release remains responsible for its immutable editor shell, schema, and exact-source inputs.

### 2. Anonymous, non-mutating probes

- `/`, `/review/`, and `/edit/` return the expected application surfaces.
- `/review` and `/edit` redirect exactly once to their slash forms.
- `/edit/?repository=<owner%2Frepository>` describes a lightweight sign-in, unchanged-bundle receiver or file selector, confirmation, and GitHub proposal flow; it does not render or frame SHACL Vue.
- `/api/shacl/editor` is not registered and no `/editor-runtime/` tree serves an editor shell or schema.
- `/api/session` returns HTTP 200 with `authenticated: false` while anonymous.
- A callback probe with exactly `code=probe`, `state=probe`, and `iss=https://github.com/login/oauth`, but no OAuth-state cookie, returns HTTP 401 `missing_oauth_state` before any token exchange.
An `iss`-only probe is malformed and correctly returns HTTP 400 `invalid_oauth_callback`.
- Authorization starts with a 302 to GitHub containing the exact client ID, callback, state, and PKCE challenge, and no OAuth scope.
- Security and `no-store` response headers are present, and the callback adapter emits two distinct `Set-Cookie` fields in the actual wire or header-list representation, not one comma-joined field.

Do not treat a green root-page probe as backend evidence.
It proves only that static hosting works.

### 3. Authenticated read-only browser proof

Use one selected integration repository and complete a real sign-in.
Without submitting a review or proposing a handoff, verify:

- the session identifies the expected user;
- repository-scoped discovery succeeds for the selected installed repository;
- a source-adapter proposal renders after exact artifact and head verification;
- `/edit/` remains only the receiver and file-upload fallback, with no editor shell, schema, RDF catalog, iframe, or second editing session;
- the static editor at the downstream's exact source commit exposes both **Download bundle** and **Propose via GitHub**;
- opening **Propose via GitHub** carries only the expected repository, exact static-editor origin, and one-time nonce, and the receiver's readiness message is bound to the exact two windows, origins, repository, and nonce; and
- logout clears the session.

Do not send a bundle or invoke the proposal API during this read-only proof.
Also verify that repository-scoped discovery rejects a read-only user or an uninstalled repository when such a safe fixture is available.

### 4. Explicitly authorized write proof

Only after separate authorization, use a disposable or designated integration repository to test the source-adapter comment and/or fixed-path SHACL handoff.
Record the exact test repository, static source commit, pull request, head, artifact when applicable, written refs, and cleanup.
Verify trusted replacement and absence of the temporary bundle from the final branch.
Never use the real production site as a write fixture.

## Failure guide

| Symptom | Likely causes |
| --- | --- |
| `github_oauth_error` with the safe client-credentials message | Host and GitHub client secrets do not match, or the wrong App client ID is deployed. The raw GitHub error is intentionally not exposed. |
| `missing_oauth_state` after login | Cookie lost through origin or proxy behavior, folded `Set-Cookie`, wrong callback origin, or ten-minute expiry. |
| `invalid_oauth_callback` | Wrong callback or setup URL, stale application revision, duplicate or foreign fields, or unexpected issuer. |
| Receiver never becomes ready | Popup or opener was lost, browser policy intervened, or editor origin, service origin, repository, window identity, or nonce does not match. Use the identical downloaded-file fallback rather than weakening the checks. |
| Bundle is rejected | Wrong format or keys, more than 50 records, over 10 MiB, invalid record coordinates, repository mismatch, source commit mismatch, stale head, or missing public-data acknowledgment. |
| GitHub 403/404 | App not installed, permission approval pending, user lacks write or admin, or session token expired. |
| Artifact failure | Egress blocked, redirect auto-followed or rewritten, destination host rejected, or provider size limit exceeded. This applies to the source-adapter review artifact, not SHACL editor input. |
| Static UI works but APIs 404 | Only `dist/` was deployed; Functions or the provider adapter is absent. |
| A second editor or `/editor-runtime/` is still available | A superseded application revision or stale build directory was deployed. Rebuild from the reviewed receiver-only revision. |

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

Coordinate TLS or provider routing, `PUBLIC_ORIGIN`, GitHub callbacks, and each downstream's `site.curation_service`.
Existing cookies are origin-bound; require a fresh sign-in.
During a migration, temporarily retain the old exact callback and add the new exact callback with wildcard matching disabled.
Deploy and verify the new origin read-only, update downstreams to the new `site.curation_service`, disable writes through the old origin, then remove the old callback.
Never replace the only working callback before the new flow is proven or leave both origins write-capable through an ambiguous cutover.

### GitHub App ownership or permissions

After transfer, confirm the owner, App ID, public client ID, callback, expiring token option, permissions, and selected installations.
Permission increases may remain pending until an installation owner approves them.
Repeat authenticated verification even when the client ID and secret were retained.

## Rollback and evidence

Treat these as one backend rollback unit:

- application commit and tree plus hosting adapter;
- public values;
- route and header configuration; and
- compatible secret generation.

Retain the prior immutable successful production deployment until the new deployment has passed authenticated verification.
For Cloudflare Pages, rollback only to that successful production deployment through the Pages rollback control or deployment API; a preview is not a valid target.
Read back the target's captured trigger commit, `commit_dirty` state, Functions presence, and public and secret configuration-key inventory before relying on it.

A historical rollback target may contain the superseded hosted editor and its runtime-digest variable.
That can be a valid emergency backend rollback, but record explicitly that it temporarily restores the duplicate-editor behavior and do not use its old configuration as the template for the next deployment.

Record:

- timestamp and operator or agent attribution;
- application commit, tree, and clean-state proof;
- public origin and client ID;
- App ID, owner, permissions, and selected repositories;
- each exercised downstream's `site.repository`, `site.curation_service`, and exact static source commit;
- immutable deployment ID and URL, provider runtime class, source trigger, clean-trigger flag, Functions presence, and configuration-key inventory with secret values redacted;
- build and probe results, including absence of hosted editor routes and assets;
- authorized write-test coordinates, if any; and
- rollback deployment ID and URL plus rotation and duplicate-editor consequences.

Do not record a runtime release, archive digest, manifest digest, or staging report as backend evidence because the receiver-only service consumes none.
Keep those coordinates with the downstream static-site release evidence.

Never record secret values, OAuth codes, cookies, access or refresh tokens, or raw provider logs that contain them.
Historical deployments may be useful examples, but they are not defaults or substitutes for current evidence.
