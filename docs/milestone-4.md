# Milestone 4: single-repository distribution

Status: active implementation

Parent engineering branch: `codex/milestone-4`

Accepted source site commit: `26907c487efaa2c31bba9d02398aa201ab6f774b`

Reviewed upstream website base: `a9ac9d5abc3898fd13d9b8392008f0c323c8dcd8`

Planning source: [`milestone-4-prompt.md`](milestone-4-prompt.md)

Decision register: [`milestone-4-decisions.md`](milestone-4-decisions.md)

## Outcome

Milestone 4 turns the proven multi-repository Orinoco Lite engineering system into a supported single-repository downstream distribution.
The engineering workspace may retain submodules, reviewed upstream rebases, component pins, comparison fixtures, and preservation history.
A downstream site must not need to understand any of them.

The first consumer is `test-orinoco-downstream-website`.
It is a realistic, replaceable integration target, but it is not a reduced fixture: it contains the complete accepted Milestone 3 CON profile, its provenance, all declared assets, the full publication integration evidence needed by the supported workflow, and a traceably complete test contract.

The real `centerforopenneuroscience.org` repository remains untouched throughout this milestone.
Graduation of the real site is a later, separately reviewed operation.

## Full-fidelity source contract

The flattened consumer starts from all accepted Milestone 3 CON inputs:

- 186 canonical records: 33 people, 24 projects, 126 publications, one instrument, one organization, and one topic;
- 13 supporting reference records;
- ten editorial sources and their declared routes;
- 71 declared assets, including all 55 ordinary-Git and 16 annex-backed payload contracts;
- seven provenance ledgers;
- the complete 199-record committed projection, 185 rendered record pages, 186-node and 467-edge graph, and both reviewed digests;
- the static editor catalog for all 186 canonical records; and
- the complete Zotero source snapshot, mappings, review policy, and promotion evidence needed to explain and repeat the publication integration.

The German upstream content tree is not CON content and is not copied into the consumer.
German routes and graph nodes remain negative isolation fixtures in engineering and release acceptance.

## Distribution architecture

Milestone 4 has five explicit boundaries:

1. The engineering workspace reviews `www-from-model` and component changes, runs upstream and release acceptance, and assembles immutable releases.
2. A versioned Orinoco Lite engine provides validation, projection, static assembly, editor-patch handling, and artifact audits through a narrow CLI.
3. A checksummed runtime release supplies schemas, reviewed website templates, graph support, the static editor, license material, and compatibility metadata without exposing component repositories.
4. One Copier source produces the GitHub template snapshot and owns only the downstream framework surface.
5. Each consumer directly owns metadata, editorial content, assets, provenance, presentation policy, integrations, and supported extensions.

The minimum downstream commands are:

```text
pixi run validate
pixi run build
pixi run serve
pixi run test
pixi run test-all
pixi run update-orinoco --check
pixi run update-orinoco --to <version>
```

An optional `serve-full-stack` interface may expose the four-collection local Dump Things and SHACL Vue stack.
It is not required for validation, the static build, Pages, patch download/application, or deployment.

## Ownership contract

Downstream paths have one declared owner:

| Ownership | Examples | Update behavior |
| --- | --- | --- |
| Site-owned | `metadata/`, `editorial/`, `assets/`, `integrations/`, presentation policy | Never overwritten silently |
| Template-owned | workflow launchers, Pixi command facade, update plumbing, test launchers | Updated through Copier; conflicts fail visibly |
| Structured | `orinoco.yaml` | Versioned field migrations with an explicit diff |
| Engine-locked | `orinoco.lock` | Updated only by a reviewed framework update |
| Generated | `generated/` | Replaced only after validation and recorded in a separate update section |
| Extension | `extensions/` | Stable site-owned hook surface |
| Local state | `build/`, tokens, stores, caches, browser output | Ignored and never published |

The initial distribution retains the committed generated projection because stale-output detection, review, and editor source binding currently depend on it.
A later milestone may reconsider this only after equivalent review and rollback behavior is proven.

## Packaging contract

Use a combined release model:

- a Python package, installed and locked through Pixi, for the normal local and hosted engine;
- a custom immutable release archive for non-Python runtime resources;
- one generated GitHub template snapshot for repository creation;
- Copier for version-aware framework updates and migrations;
- a thin reusable workflow or action pinned by full commit SHA; and
- an optional digest-pinned multi-architecture OCI image for the advanced full stack.

A long-lived fork is not a supported downstream update mechanism.
Generated source archives and mutable tags are not accepted runtime pins.

## Test-preservation contract

No existing behavioral assertion disappears.
A checked-in traceability ledger maps every current test to one or more successor tests and owners:

- engineering: upstream review, rebases, gitlinks, component resolution, preservation, release extraction, and German comparison;
- engine/release: schemas, native relationships, projection, assembly, assets, editor security, deterministic builds, and release integrity;
- consumer: complete content, presentation, routes, Pages, project paths, downloaded patches, update preservation, customization, and rollback; and
- integrations: Zotero acquisition/transformation and SHACL Vue component behavior.

The baseline contains 106 parent Python methods, five Playwright definitions with nine Chromium/WebKit executions, 42 Zotero tests, and eight SHACL Vue tests.
Topology-specific tests receive released-interface successors rather than being copied nonsensically into the no-submodule consumer.

## Implementation sequence and gates

### 1. Preservation and exact inventory

Record the accepted parent, site, upstream, component, asset, content, and test coordinates.
Work from a separate branch and worktree.
Do not create even a local ref in the real site repository.

Gate: all accepted clean, Milestone 2, and Milestone 3 coordinates resolve as recorded, and the current complete suite establishes the baseline.

### 2. Location-independent engine

Replace assumptions about `submodules/`, `profiles/con`, CON-specific collection names, and the Pages repository slug with explicit project, runtime, component, and output roots.
Preserve the existing layout as a compatibility fixture while extracting the public CLI.

Gate: the current Milestone 3 layout still passes unchanged, and equivalent flattened inputs produce the same semantic artifact.

### 3. Immutable release boundary

Build the engine package and checksummed runtime archive, record every source commit and license, and verify the release from a clean checkout without engineering gitlinks.

Gate: a consumer can validate and build without cloning a component repository.

### 4. Template and ownership

Create one versioned Copier source and mechanically render the GitHub template snapshot.
Record answers, ownership classes, migrations, conflict policy, and the exact release lock.

Gate: the rendered template matches its recorded Copier version and contains no submodule or hidden engineering dependency.

### 5. Complete test consumer

Instantiate `test-orinoco-downstream-website` from the template and import the complete Milestone 3 CON bundle without a selection policy.

Gate: exact PID, reference, editorial, asset, provenance, projection, route, graph, and editor-catalog parity; no German leakage; and complete test traceability.

### 6. Creation, customization, update, and rollback proof

Exercise an initial release and a second framework release.
Preserve a site-owned customization, surface a deliberate framework conflict, generate a reviewable update pull request, build its preview, and restore the prior release through an ordinary revert or update.

Gate: no site-owned input changes unless a separately declared semantic migration requires and explains it.

### 7. Remote acceptance

Publish the package/release and template, create the public test consumer, configure least-privilege Actions and project Pages, and exercise one real automated update pull request.
Do not merge automatically.

Gate: public shallow checkout, local commands, hosted validation, Pages, static editing, update review, and rollback all succeed.

## Update pull-request contract

Every framework update pull request reports:

- old and new template tags and commits;
- old and new engine versions and verified artifact digests;
- runtime, workflow, and compatibility changes;
- the ownership class of every changed path;
- before/after hashes for all site-owned inputs;
- explicit semantic migrations, if any;
- generated changes isolated from hand-authored changes;
- complete test and deterministic-build results;
- unresolved conflicts; and
- a deployable preview artifact.

Update automation may create a branch and pull request.
It may not merge one, change canonical content silently, deploy pull-request code to the shared Pages environment, or gain permissions beyond its declared update job.

## External authorization and real-site boundary

The user authorizes repository creation, project Pages configuration, workflow write permissions, Orinoco Lite package/release publication, and operations in the test consumer required by this milestone.

No authorization is granted for any interaction that mutates `centerforopenneuroscience.org`, including its local refs, remote refs, files, settings, workflows, Pages configuration, deployment, default branch, legacy history, DNS, or production domain.
Reading the accepted source commit for mechanical extraction and parity checking is permitted.

## Deferred

Milestone 4 does not include:

- graduation or cutover of the real CON repository;
- production-domain, DNS, redirect, or custom-domain changes;
- automatic merging of framework updates;
- hosted browser credentials or direct editor writes;
- a persistent public Dump Things service;
- resolution of outstanding Milestone 3 content decisions merely because the content is redistributed;
- replacement of all annex custody or a claim of complete offline support;
- support for every operating-system architecture in the initial release; or
- unrelated upstream contributions.
