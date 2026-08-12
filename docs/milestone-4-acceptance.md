# Milestone 4 acceptance record

Status: implementation in progress

This record is populated from exact commits, release artifacts, workflow runs, test manifests, and public URLs as each stop/go gate completes.
It must not claim acceptance from planned or partial evidence.

## Fixed source coordinates

| Source | Commit |
| --- | --- |
| Parent inventory baseline | `0df9ed8c9b32fb72f78d1c6aba101d03e563a1c7` |
| Accepted Milestone 3 site | `26907c487efaa2c31bba9d02398aa201ab6f774b` |
| Reviewed upstream website | `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8` |
| Accepted parent clean migration | `f54cf5fdb2b5ae4bf03fe6939246316fd9ec818d` |
| Accepted site clean migration | `a122e506de9e4a13473edbe8d74a950d74032a16` |
| Accepted parent Milestone 2 | `7ce44a28c13954e514c8b7e9ab6f1eaade77d891` |
| Accepted site Milestone 2 | `d60f274b4bf8af3e513d83d1727cfe3e6c9bb8af` |

The exact implementation source commit is recorded only after the carried Milestone 3 documentation and Milestone 4 implementation are committed.

## Required release coordinates

Pending:

- engine package name, version, wheel and source-distribution digests;
- runtime archive name, digest, attestation, and immutable release URL;
- template repository, tag, commit, and rendered-tree digest;
- test consumer initial and update commits;
- reusable workflow/action commit pin;
- optional OCI manifest and platform digests; and
- update pull request, workflow runs, artifacts, and Pages URL.

## Full-fidelity parity

Acceptance requires recorded evidence for all of the following:

| Contract | Required result | Evidence |
| --- | --- | --- |
| Canonical metadata | 186 records, exact PID and semantic parity | Pending |
| Reference closure | 13 records | Pending |
| Editorial sources | 10 declared sources and routes | Pending |
| Assets | 71 declarations and exact available payload digests | Pending |
| Provenance | 7 ledgers plus exact extraction coordinates | Pending |
| Projection | 199 records and 185 rendered pages | Pending |
| Graph | 186 nodes and 467 native edges | Pending |
| Static editor | all 186 canonical records and backend-free patch export | Pending |
| German isolation | no German route or graph node | Pending |
| Downstream topology | no `.gitmodules`, gitlinks, or component checkout | Pending |

## Test traceability

Acceptance requires a machine-readable mapping and passing evidence for:

- all 106 parent Python unit and contract methods;
- all five Playwright definitions and nine configured Chromium/WebKit executions;
- all 42 Zotero integration tests; and
- all eight SHACL Vue tests.

The mapping may retain an assertion in engineering, move it to the engine, add a consumer equivalent, or do more than one.
An unmapped or silently deleted assertion is an acceptance failure.

## User-level scenario

A fresh ordinary clone of `test-orinoco-downstream-website` must let a user who does not know the engineering topology:

1. edit a canonical record;
2. validate it locally;
3. build and serve the complete site;
4. exercise project-path Pages behavior;
5. edit through the backend-free static editor and download a review bundle;
6. validate and apply that bundle locally;
7. review a generated framework update pull request;
8. confirm their content and customization remain intact; and
9. restore the previous framework version without changing canonical content.

## Engineering-level scenario

The engineering workspace must continue to review a new `www-from-model` commit, run its existing rebase and comparison acceptance, publish an immutable Orinoco Lite release, and prove that the consumer update is equivalent over the released contract.
None of those operations enters the consumer interface.

## External-state audit

Authorized Milestone 4 external state is limited to the Orinoco Lite package and release, template repository, test-consumer repository, their workflows and required permissions, project Pages, and reviewed update pull requests.

Acceptance must explicitly confirm that `centerforopenneuroscience.org`, its refs, settings, Pages, default branch, deployment, DNS, and custom domain were not changed.
