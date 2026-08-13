# Milestone 3 static editing handoff

Status: implementation complete; draft human review open

**Historical editor contract.** The credential-free review-bundle principle remains current, but the released engine and downstream template now own the supported bundle/application interface.
See [`milestone-4.md`](milestone-4.md).

## Outcome

The Pages preview includes the production SHACL Vue interface under `/orinoco-lite-dev/edit/`, but it has no backend, authentication flow, service token, or GitHub credential.
It loads the pinned public records and schema from the same static artifact.

An editor can change a record in the browser and download a deterministic RDF review bundle.
A checked-in local helper validates that bundle against the exact site commit and canonical YAML before showing a repository-relative diff.
Applying the diff remains an explicit local action.

## Browser workflow

1. Open a record in the Pages preview and select **Edit this record**.
2. Change the record in SHACL Vue and select **Save**.
This saves only in the browser's in-memory review queue; it does not send a request.
3. Open the download panel, select the intended records, and choose **Download review bundle**.
4. Preserve the downloaded JSON file unchanged for local validation.

The bundle records the site commit, canonical PID, schema type, source path, source digest, and edited RDF.
It contains no credential and does not nominate or create a pull request.

## Local validation and application

Use a clean parent checkout with its site submodule at the bundle's recorded commit.
From the parent repository, inspect a bundle without changing files:

```text
pixi run review-editor-bundle ~/Downloads/con-review-….json
```

The helper rejects an unknown PID, stale site commit or source digest, changed schema type or PID, path escape, invalid RDF, relationship/reference failure, ignored input, or dirty canonical checkout.
A successful dry run prints a unified diff with paths relative to the site repository.

After reviewing that diff, apply the same validated update explicitly:

```text
pixi run review-editor-bundle ~/Downloads/con-review-….json --apply
```

Review and commit the resulting YAML in the site repository.
A parent change then deliberately advances the site gitlink.
Milestone 3 does not automate either commit or open a component pull request.

This repository placement is settled.
`centerforopenneuroscience.org` owns the canonical CON content on its upstream-derived, rebasable site branch; the account mirror is only a transport for that branch.
The parent gitlink update is ordinary component-version coordination among the parent's many submodules.
Legacy CON branches and tags remain preserved as separate reachable history in the site repository.

## Security and publication boundary

- the browser performs only static `GET` and `HEAD` requests;
- the editor config disables service and token modes;
- shapes, records, class definitions, and deployment config are local, relative, digest-bound files;
- the Pages artifact contains no loopback service, German editor endpoint, token-shaped value, symlink, Git state, or `CNAME`;
- downloaded bundles are size- and record-count-bounded and fail closed; and
- authenticated branch creation, direct pull-request submission, hosted tokens, and production writes remain deferred.

Playwright exercises the complete browser path at the project URL: it follows a generated edit link, loads Yaroslav Halchenko from static RDF, changes a field, downloads a bundle, verifies that the browser made no write request, and passes the bundle through the local dry-run validator without modifying canonical YAML.
