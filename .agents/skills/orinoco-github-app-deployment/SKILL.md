---
name: orinoco-github-app-deployment
description: Deploy, migrate, verify, rotate, or roll back the stateless Orinoco Lite curation-review GitHub App backend on any suitable hosting provider. Use for self-hosting the review/edit service, evaluating a provider, configuring its GitHub App and secrets, moving an existing deployment, or recording deployment evidence. Do not use merely to point a downstream at the existing central service.
---

# Orinoco Github App Deployment

Deploy the browser application and authorization routes as one stateless, same-origin service.
Keep the hosting choice separate from the application contract.

## Workflow

1. Decide whether a new deployment is necessary.
Prefer the central service when the downstream does not require its own origin, GitHub App, or custody.
2. Resolve the exact reviewed application commit and immutable Orinoco Lite runtime release.
Refuse a mutable branch, mutable runtime URL, or dirty checkout as production authority.
3. Read [runtime-and-hosting-contract.md](references/runtime-and-hosting-contract.md) and compare every required capability with the proposed provider before provisioning it.
The checked implementation is Pages-Functions-shaped; another provider needs a thin, reviewed adapter.
Static `dist/` alone is not a backend deployment.
If the request is only to evaluate a provider, return the completed capability matrix and unresolved gaps here; do not create an App, secrets, hosting resources, or a deployment.
4. Read [github-app-configuration.md](references/github-app-configuration.md), then create or update the GitHub App and restrict its installation to the intended repositories.
Keep the setup URL distinct from the OAuth callback.
5. Build the application and separately stage the editor shell and schema from the selected immutable runtime.
Advance code, public configuration, staged runtime, and runtime-manifest digest as one deployment unit.
6. Put public values in reviewed provider configuration, tracked when the provider supports configuration-as-code.
Put secrets only in the encrypted hosting control plane.
Never put secret values in Git, command output, logs, evidence, or browser-visible configuration.
Do not add durable storage.
7. Deploy atomically from the clean reviewed revision.
Record an immutable deployment identifier and a previously working rollback coordinate.
8. Follow [verification-rotation-and-rollback.md](references/verification-rotation-and-rollback.md): run non-mutating probes first, then a real authenticated read-only browser flow.
Require explicit authorization before any comment, branch, commit, or pull-request write, and use only a disposable or designated integration repository for that proof.
9. Configure each self-hosted downstream's `CURATION_REVIEW_APP_ORIGIN` only after the deployment and App installation both pass verification.
10. Record evidence without secrets: application commit/tree and clean state, runtime release and digests, public origin and client ID, App ID/owner and permission set, selected repositories, deployment ID, probe results, and rollback coordinate.

## Guardrails

- GitHub is the durable authority.
Do not introduce a database, object store, artifact cache, queue, candidate store, decision store, metadata service, or analytics-backed curation storage.
- Preserve the exact external HTTPS origin in every request.
Browser pages, APIs, cookies, and staged runtime assets must share that origin.
- Do not weaken PKCE, OAuth state, expiring-token, cookie, redirect-host, exact-head, artifact, or runtime-digest checks to fit a provider.
- Do not stage executable editor code or schema from a downstream pull request or Actions artifact.
Those artifacts contain data only.
- Treat secret rotation, an origin change, a GitHub App ownership transfer, installation changes, and write-path verification as distinct external mutations.
Resolve exact targets and obtain any required confirmation at the point of action.
- Stop when provider limits cannot satisfy the accepted maxima or its adapter cannot preserve the response, cookie, redirect, and crypto semantics.
Report the incompatible capability instead of silently reducing the contract.
