# Milestone 7: sustainable downstream ownership

Status: planning; starts after Milestone 6 closes

Predecessor: [`milestone-6.md`](milestone-6.md)

Normative source-adapter contract: [`source-adapters.md`](source-adapters.md)

GitHub review profiles: [`github-curation-review.md`](github-curation-review.md) and [`github-shacl-vue-edit.md`](github-shacl-vue-edit.md)

Current human-policy queue: [`human-review-decisions.md`](human-review-decisions.md)

## Planning boundary

Milestone 7 reduces the cost and risk of changing Orinoco Lite after the Milestone 6 metadata paths have been exercised end to end.
It does not close, reinterpret, or add acceptance evidence to Milestone 6.
Its implementation begins from the exact accepted Milestone 6 release and downstream coordinates.

Small changes that do not alter metadata semantics, authority, provenance, repository ownership, or the new path contract may proceed as separate pull requests while this plan is reviewed.
In particular, user-facing bot copy and the empty `/review/` fallback can be corrected independently.
Validation-event classification, data relocation, generic-code relocation, and autonomous curation are not quick-copy changes and remain workstreams below.

## Outcome

Milestone 7 makes ordinary Orinoco Lite development a one-way promotion rather than a repeated three-repository debugging cycle.

It will:

- give every downstream one obvious root for its site-specific data;
- make a useful site render from records and structured site data without requiring downstream-authored Markdown;
- move generic presentation, projection, curation, and workflow behavior into released engine or template ownership;
- exercise a complete generated downstream locally in the engineering workspace before a change propagates;
- keep one fast, explicitly AI-authorized integration fixture separate from the human-governed reference downstream;
- distribute skills for both the fast integration loop and ordinary downstream maintenance; and
- remove legacy copied framework and content only after the migration is proved reversible and both retained downstreams adopt it.

The milestone succeeds when a generic correction is implemented and tested once at its owning layer, not copied independently into two consumers and then debugged again after deployment.

## Direction established for this plan

### M7-D001 — Put site-specific data under one root

The downstream data boundary is `site-specific/`.
Canonical metadata, compact curation state, source configuration and policy, site identity, editorial data, and site-owned assets must not remain scattered among `metadata/`, `custom/`, `site/`, and `source-adapters/`.

This is an ownership and configuration migration, not merely a directory rename.
Exact record, annotation, decision-cache, editor-bundle, workflow, and allowlist paths change together through a versioned contract and a tested migration command.

### M7-D002 — Generate the normal site from structured data

The template supplies useful default pages, navigation, layouts, projection, and copy.
A downstream supplies records and a small structured site description.
Generic Markdown and templates contain no `CON` literal or other consumer identity.

Optional downstream Markdown remains available for genuinely bespoke prose or pages.
It is an extension, not a prerequisite for a useful generated site and not a second manually synchronized representation of people, projects, or other record-derived lists.

### M7-D003 — Give the two downstreams different, explicit roles

`leej3/orinoco-lite-demo` is the fast integration fixture.
Its default branch records a separate, versioned fixture-authority policy that reflects the human grant without creating or broadening it.
Its eventual automation skill verifies that policy and fails closed unless the immutable repository ID, expected repository coordinate, and remote also match.
Within the authority explicitly resolved below, the fixture can exercise branches, pull requests, browser flows, curation, merges, Pages, and recovery without waiting for ordinary human review.

`ORINOCO-Lite/test-orinoco-downstream-website` is the human-governed reference downstream.
It demonstrates what a normal adopter receives, including the template update path, required review, ordinary validation, and human-first curation skills.

The fast fixture is not evidence that an ordinary downstream should disable review.
The reference fixture is not the first place a generic change is debugged.

### M7-D004 — Promote in one direction

The normal implementation sequence is:

1. prove the owning engine or template change against a hermetically generated downstream in the engineering workspace;
2. release or otherwise pin the immutable generic implementation;
3. exercise it in the fast personal integration fixture; and
4. propose it to the organization reference fixture through the ordinary downstream update path.

A failure moves back to the owning layer.
It is not patched independently in each later consumer unless the behavior is genuinely site-specific.

## Target ownership and layout

The provisional public shape is:

```text
site-specific/
  site.yaml
  content/
    pages/
  static/
    manifest.yaml
    files/
  curation-records/
    <adapter>.yaml
  sources/
    <adapter>/
      source.yaml
      policy/
      evidence/
  metadata/
    records/
    overlays/
      annotations/
extensions/
  source-adapters/
  site/
```

The exact `curation-records/` boundary remains M7-Q001.
The provisional model keeps only compact current decisions there and keeps source coordinates, mapping policy, and retained source evidence under `sources/`.
Both are site-specific data.
Git remains the event and historical record; Milestone 7 does not introduce a second curation event store.

| Surface | Milestone 7 authority |
| --- | --- |
| `site-specific/metadata/records/**` | Human-facing canonical semantic records |
| `site-specific/metadata/overlays/annotations/**` | Machine-managed annotation companions |
| `site-specific/curation-records/**` | Compact adapter decision caches, subject to M7-Q001 |
| `site-specific/sources/**` | Source coordinates, mappings, policy, and retained evidence |
| `site-specific/site.yaml` | Site identity, navigation, contact data, route choices, and presentation groups |
| `site-specific/content/**` | Optional site-owned prose and page data that extends generated defaults |
| `site-specific/static/**` | Site-owned files and one structured asset manifest |
| `extensions/source-adapters/**` | Truly consumer-specific adapter executable code |
| `extensions/site/**` | Optional site-specific styles, layouts, or presentation code that cannot be expressed as data |
| Engine/runtime | Generic path handling, validation, projection, curation mechanics, review application, and reusable commands |
| Template | Generic downstream configuration, workflows, layouts, generated pages, update mechanics, and ordinary maintenance skill |
| Repository root | Legal, contributor, lock, and workspace files plus a small versioned pointer to the site-data contract |

Generic Zotero behavior, curation runners, workflow logic, projection tools, index-page generation, layouts, and common configuration must not remain create-once consumer copies.
A CON-only adapter may remain an extension, but its source coordinate, policy, evidence, and decisions still belong under `site-specific/`.

The existing presentation snapshot cannot simply be copied into a distributed runtime or template until its redistribution terms are established.
The Congo theme can move with its notice; other material needs a verified license, permission, or a clean generic replacement.

## Workstream 1: engineering dry-run harness

Add one documented command that constructs an ordinary downstream in a fresh temporary directory from the candidate template and exact engine/runtime coordinates.
It must not discover a sibling checkout or depend on a developer's untracked state.

The harness exercises, as applicable:

- template render and update;
- configuration and ownership validation;
- representative source acquisition from a recorded fixture;
- candidate planning and curation finalization through a deterministic test oracle;
- canonical and joined metadata validation;
- projection and static build;
- `/edit/` and `/review/` route generation and focused browser checks; and
- a second identical ingestion that produces no proposal.

Network-hosted GitHub and Pages checks remain a later integration layer.
The local harness must catch path, template, workflow-rendering, content, and build errors before a release reaches either downstream.

Acceptance:

1. the command succeeds from a clean clone on macOS ARM64 and Linux x86-64;
2. it identifies every immutable input and fails when an input is absent or at the wrong coordinate;
3. it creates no tracked or sibling-worktree state; and
4. generic pull requests run it before release or promotion.

## Workstream 2: extract generic presentation and curation behavior

Classify every copied downstream file as generic framework, structured site-specific data, optional extension, generated output, test fixture, legal material, or obsolete state.
Move generic behavior to its owning release or template before relocating consumer data.

At minimum, this work covers:

- projection templates and tools;
- generated section and index pages;
- common Hugo layouts, menus, configuration, and static application shells;
- the generic Zotero adapter and curation runner;
- reusable curation workflow behavior and its tests; and
- the `/edit/` and `/review/` integration configuration.

Thin downstream workflows may call immutable reusable workflows.
Site-specific adapter coordinates and policy remain data inputs rather than copied workflow implementations.

Acceptance:

1. an ownership scan finds no byte-identical generic implementation classified as create-once site content in both retained downstreams;
2. a generic fix has one implementation owner and one focused test location;
3. generated consumers still expose ordinary source for inspection and local builds; and
4. redistribution notices and licenses accompany every distributed framework asset.

## Workstream 3: make the presentation data-driven

Define and validate the structured `site.yaml` and asset manifest.
Generate default home, about, people, projects, publications, instruments, contact, engagement, support, and navigation surfaces from those inputs and canonical records where appropriate.

Remove manually duplicated lists.
For example, one structured presentation selection must drive a project or people view; it must not also be hand-copied into Markdown.
Site-specific headings and explanatory copy are fields or optional Markdown overrides, not literals in generic templates.

Acceptance:

1. a new downstream with records, `site.yaml`, and assets builds a useful site without writing a Markdown page;
2. generic sources contain no `CON`, Center for Open Neuroscience, fixture repository, or personal-demo identity;
3. optional Markdown overrides compose with generated defaults without replacing the updateable framework; and
4. the two retained downstreams exercise different site data against the same generic renderer.

## Workstream 4: introduce the versioned site-data contract

Add configurable record, annotation, curation, source, and asset roots.
Remove fixed old-path constants from the engine, backend allowlists, editor bundles, workflows, adapters, validation, and tests.

Ship one explicit migration command for a clean supported consumer.
It:

- verifies the exact source contract and expected ownership hashes;
- moves site data while preserving bytes and useful Git history;
- renders the new generic framework and records every intentional conflict;
- stops rather than overwriting edited site-owned content;
- updates configuration and generated workflow contracts atomically;
- validates the joined graph and built route inventory; and
- is idempotent after successful migration.

Old-layout curation pull requests must be completed or closed before cutover unless a separately reviewed compatibility design proves their exact safe finalization.
Immutable old releases remain available for rollback.
The normal runtime does not carry indefinite v2/v3 dual-path behavior.

Acceptance compares semantic graph content, record and annotation counts, decision-cache bytes, asset digests, published routes, `/edit/`, `/review/`, and clean-clone builds.
Byte-identical generated bundles are not required when they truthfully embed new repository paths.

## Workstream 5: review experience, bot copy, and validation events

The empty `/review/` route first provides a repository-bound link to open curation pull requests.
A later enhancement may populate an in-page selector asynchronously while keeping an exact proposal URL the primary deterministic entry point.
The central backend remains authentication and verified transport, not a new discovery or landing service.

Curation pull-request bodies identify the source adapter, preserve the merge-commit warning and review-artifact retention note, link to the downstream review application, and put canonical source coordinates in a closed `<details>` block.
GitHub Actions bot output does not use an AI-draft disclaimer intended for agent-authored prose.
Finalization copy reports the recorded decision commit and the actual validation state without claiming readiness before asynchronous validation has passed.

Validation redesign is coordinated across the template-owned validation workflow and its curation callers.
It must distinguish:

- a metadata proposal that needs full validation;
- an authenticated decision-cache finalization that needs trusted joined-graph validation at the exact head;
- ordinary framework or content changes;
- the explicit trusted dispatch used to avoid approval-gated bot-created pull request runs; and
- default-branch and manual runs.

A base-branch-owned classifier must never check out or execute untrusted pull request code with elevated credentials.
Event-specific concurrency must not let a later approval-gated run cancel an already running trusted dispatch.

Acceptance has no duplicate approval-gated run for the same required result, no skipped run presented as missing validation, and no weakening of exact-head or untrusted-code boundaries.

## Workstream 6: skills and explicit authority profiles

### Fast engineering fixture

Create the project-owned skill `.apm/skills/exercise-orinoco-ai-fixture/SKILL.md` in the engineering repository.
APM owns deployment to `.agents/skills/`; skills-workshop audits, tests, remembers, and records use of the canonical skill.
The generated `.agents/` copy is never edited directly.

Record the authorized operation and editorial scope separately in a reviewed fixture-owned policy on the personal demo's default branch.
The policy records an authority granted by the human owner; neither that file nor the skill creates authority by itself.
The skill fails closed unless the trusted default-branch policy, repository ID `1345606064`, full name `leej3/orinoco-lite-demo`, and expected SSH remote agree.
Subject to the open authority questions, it may:

- create branches, commits, and pull requests in that fixture;
- run exact-head local checks and hosted workflows;
- navigate its deployed `/edit/` and `/review/` browser flows;
- exercise declared non-authoritative curation choices;
- merge fixture pull requests before hosted CI completes when the local gate has passed;
- observe Pages publication; and
- immediately fix forward or revert if post-merge validation fails.

It does not thereby authorize engine or template releases and merges, changes to the organization fixture, the real site, external-source writes, secret or App changes, repository or organization settings, branch-protection changes, destructive ref rewrites, or deletion.
Those require their ordinary authority.

“Human never in the loop” describes steady-state review and merge decisions in the designated fixture.
It cannot bypass login, two-factor authentication, or platform confirmations that require the account holder.

The skill does not make an AI action a human action.
Autonomous live curation waits for M7-Q002 and M7-Q003 so that durable reviewer, author, comment, and commit provenance remain truthful.

### Ordinary downstream maintenance

Add a template-owned `maintain-orinoco-site` skill and update the existing content and source-adapter skills for the new paths.
It guides an agent to:

- inspect immutable upstream, template, and runtime coordinates;
- render an update check before changing site-owned data;
- preserve site-owned bytes and surface semantic migrations for review;
- update content or adapter configuration only under the downstream's stated policy;
- validate locally and prepare a focused pull request; and
- stop before merge, publication, or unresolved semantic decisions unless the downstream explicitly grants that authority.

The template skill is copied through the normal Copier release and update mechanism.
It is a template release artifact rather than a project-owned experimental skill, so generated downstreams do not need APM merely to receive it.
If a downstream develops its own local skill, that downstream may use `.apm/skills/` and APM deployment without editing the template-owned copy.
It remains human-first and must not inherit the personal fixture's fast-lane authority.

Acceptance includes skill validation, independent forward testing of the fixture skill, a skills-workshop audit/use record, a wrong-repository fail-closed test, and a generated downstream exercise of the normal maintenance skill.

## Workstream 7: release, migrate, and remove legacy state

Promote each independently reviewed layer in the order in M7-D004.
Record exact engine/runtime and template releases, generated-template commits, migration commits, downstream heads, workflow runs, Pages deployments, rollback coordinates, and ownership classifications in a concise Milestone 7 acceptance record.

Only after both downstreams adopt the new contract:

- remove obsolete `custom/**` and old metadata roots;
- remove copied generic site and curation implementation;
- remove duplicate Markdown lists, configuration, and stale paths;
- update repository skills and contributor documentation; and
- make the ownership scanner reject newly introduced site data outside `site-specific/`, except an explicit short list of legal and repository infrastructure files.

## Non-goals

Milestone 7 does not:

- close or rewrite Milestone 6 acceptance;
- modify, deploy, migrate, or graduate the real CON site;
- write to Zotero or another external source;
- treat an AI action as human review or attribute an agent decision to John by implication;
- remove ordinary human review from the organization reference downstream;
- weaken engine, template, schema, provenance, security, or release gates to make the personal fixture faster;
- add a persistent metadata, curation, credential, or proposal service;
- carry two writable site-data layouts indefinitely; or
- redistribute framework material without established permission.

## Milestone acceptance

Milestone 7 is complete when:

1. the hermetic engineering command validates a generated consumer end to end before downstream promotion;
2. all site-specific data is under the accepted `site-specific/` contract, optional executable overrides are isolated under `extensions/`, and generic behavior has a single engine or template owner;
3. a new downstream builds a useful site from structured data and records without required custom Markdown;
4. the one-time migration is conflict-safe, idempotent, semantically stable, and adopted by both retained downstreams;
5. `/review/`, bot copy, and validation behavior meet Workstream 5 without a second frontend or redundant approval-gated run;
6. the personal fixture completes the authorized autonomous ingestion, curation, edit, build, merge, deployment, no-op, and recovery path with truthful agent provenance;
7. the organization fixture completes the ordinary human-governed update and curation path using the distributed maintenance skill; and
8. ownership, release, deployment, rollback, and cross-platform evidence are recorded without duplicating Git history.

## Open planning questions

### M7-Q001 — What belongs in `curation-records/`?

Should `curation-records/` contain only compact current decision caches, with source coordinates, mapping policy, and retained evidence in sibling `sources/`, or should it contain all site-owned source-adapter data?

The provisional recommendation is the narrower decision-cache meaning shown above.
It gives source inputs and human decisions distinct names while keeping both under the single site-specific root.

### M7-Q002 — Which durable identity represents autonomous curation?

The current human profile derives reviewer and commit author from the authenticated GitHub user.
Driving John's browser session would therefore record the AI's choices as John's review and authorship, which is not truthful.
The exact `/curation submit` protocol also cannot carry the repository-required agent-comment attribution.

Milestone 7 should generalize the fixture profile from a human reviewer to a versioned authorized-curator actor record and exercise that profile with a dedicated permitted bot or test identity.
The exact identity and delegation fields remain to be accepted.
Truthful structured actor provenance must be implemented before autonomous live submissions.

### M7-Q003 — What editorial authority does the fast fixture grant?

May the AI make substantive identity, eligibility, licensing, and editorial decisions over real imported metadata in the personal demo, or must autonomous curation use synthetic or explicitly non-authoritative fixture decisions?

The recommendation is synthetic or non-authoritative decisions by default.
Broader editorial authority can be granted explicitly without changing the organization fixture or the real-site boundary.

### M7-Q004 — What does the fast merge gate mean?

The proposed fast lane runs exact-head local checks, permits a personal-fixture merge without waiting for hosted CI, and requires immediate fix-forward or revert if post-merge CI fails.
It does not mean no tests and does not authorize changing branch protection.

Confirm whether this is the intended interpretation of “merge without CI tests for speed.”

### M7-Q005 — How small should the fast fixture be?

Should the personal demo retain the complete imported content so it exercises production-scale paths, or become a smaller deterministic canary while the organization fixture retains the complete normative consumer contract?

A small canary is faster; a full corpus exposes scale and migration failures.
The recommended compromise is a small mandatory smoke corpus plus a separately invocable full-corpus exercise before release promotion.

### M7-Q006 — May the presentation intentionally change?

Should the migration preserve the current rendered routes and presentation as closely as possible, or may the data-driven renderer improve navigation and default content during the same milestone?

The recommendation is semantic and route parity for the migration itself, followed by separately reviewed presentation improvements.
This makes data loss and intentional design change distinguishable.
