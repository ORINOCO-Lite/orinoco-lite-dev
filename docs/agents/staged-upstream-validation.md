# Staged upstream validation specification

Active build specification for maintainers implementing the comparison commands and diff review application.
Updated 28 September 2026; retire implementation sequencing when the system is delivered and promote lasting contracts.
The [application README](../../packages/diff-review-application/README.md) describes the later web interface for reviewers.
The [design charter](../project-design.md) supplies project constraints; this document specifies the planned interfaces, behavior, and delivery sequence.
The commands and application described here are implementation targets.
The [exploration](provenance-comparison-exploration.md) records the research behind the [investigation procedure](../../.agents/skills/compare-orinoco-provenance/SKILL.md).

## Psychoinformatics downstream update plan

The next integration target is [psychoinformatics-downstream](https://github.com/ORINOCO-Lite/psychoinformatics-downstream).
Prepare updates as a sequence of DataLad-recorded operations and propose their commits in a draft pull request.
John may use the comparison commands locally when a change warrants investigation; comparison reports and the review application are not prerequisites for every update.
This section plans the integration work; it does not authorize resetting downstream history, adopting mirror refs, merging pull requests, or deploying a site.

### Prerequisites and order

1. Apply the review principles proposed in [#190](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/190): explain meaningful differences and justify retained adaptations independently of passing checks.
   Keep findings and check outcomes separate, with existing issues and commits providing the explanation.
   No new decision registry or mandatory comparison pipeline is needed.
2. Resolve [#180](https://github.com/ORINOCO-Lite/orinoco-lite-dev/issues/180) while rebasing [#170](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/170) onto current `main`.
   Remove the date-marker reader workaround and use the selected upstream converter directly, as decided below.
   The current projection round-trip guard rejects the captured marker with the unadapted reader; removing the workaround alone will not make the build succeed.
   Inspect the upstream conversion and projection path, then remove any unsupported Lite preservation requirement at that boundary without broadly suppressing conversion errors or changing retained source records.
   Verify ordinary projection and editor readback separately, retaining evidence of upstream's omission.
3. Address [#182](https://github.com/ORINOCO-Lite/orinoco-lite-dev/issues/182) and [#189](https://github.com/ORINOCO-Lite/orinoco-lite-dev/issues/189).
   For #182, exercise minimal second-lab inputs and same-path authored overrides, then fix only demonstrated gaps in defaults, import, or media placement.
   For #189, make the exact imported `www-from-model` revision available as a Git submodule/DataLad input and pass that checkout explicitly to import.
   Derive its revision from the package's controlled upstream selection; the downstream gitlink records the input used rather than introducing an independently selected upstream version.
   Verify retrieval from a fresh clone, including required Annex content, and include the subdataset among the run's declared inputs.
4. Complete [#188](https://github.com/ORINOCO-Lite/orinoco-lite-dev/issues/188) using the existing preparation, projection, build, and publication operations.
   Preserve preparation-only setup as the default and add an explicit way to continue through projection and a complete build.
   Reuse [#191](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/191)'s recorded projection and publication bundle where applicable; preparing a bundle must not itself deploy or push publication refs.
   Verify the full retained-input path after the #180, #182, and #189 changes.
   The prerequisite implementation uses `--build` and a fixed `sourcedata/www-from-model` subdataset; it does not add a stage dispatcher.
5. Rebase the unique changes in [#171](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/171), [#172](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/172), and [#173](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/173) in order.
   Keep RDF, service, website, and local review functionality separately reviewable.
   Reuse the useful behavior and review findings from the predecessor PRs listed below; do not resurrect their separate renderer or deployment harness.
   Repeat affected checks on the rebased commits; earlier successful runs do not validate the new stack.

### Initial dataset and recurring updates

Use a disposable dataset to prove setup and one subsequent update before replacing the existing downstream history.
Use `setup-upstream` with exact, recoverable package and template selections, retained capture bytes or a recorded acquisition, and the explicit upstream input from #189.
Keep acquisition, record conversion, authored-site import, and generated projection separately identifiable in DataLad history.
Dataset creation, saved supplied inputs, and human conflict resolutions may be ordinary DataLad saves; do not fabricate run records for commands that were not executed.

The recurring downstream operation should compose existing commands:

1. Start an update branch from the accepted downstream commit and resolve the requested template and package selections to immutable commits.
2. Use [#192](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/192)'s `orinoco-lite template update` to record the Copier transformation and any package override.
   Preserve the site-owned settings, content, extensions, and submodule selections protected by [#198](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/198).
   Start a fresh locked Pixi invocation before running the selected package.
3. When an upstream-input refresh is requested, record that subdataset's new selection and rerun the relevant import and conversion operations.
   A template-only update must not implicitly refetch live Pool data or replace site inputs.
   Recompute against retained captures by default for this comparison site; a live refresh is a separate acquisition with its own recorded outputs.
4. Validate and build the candidate, then publish the existing DataLad commits in a draft PR using the template-update workflow's separation between candidate execution and trusted publishing.
   Resolve how changed `site-specific` child commits are published before proposing the parent gitlink: both must be retrievable from their configured remotes.
   The current template updater preserves submodule selections; coordinated input publication is additional work, not an existing updater capability.
   Leave conflicts and failed checks visible, skip empty updates, and leave acceptance and deployment to their existing review workflows.
5. When useful, inspect the candidate locally with #170–#173's comparisons.
   Record conclusions with the relevant change; keep generated diagnostic reports outside tracked state by default.

Reserve **mirror rebase** for replaying retained Orinoco commits onto an accepted upstream base under the existing `main`, `latest-upstream`, and `orinoco-lite-diff` convention.
That operation produces candidate dependency commits before downstream repinning; it must not rewrite accepted downstream DataLad history.
An automated observer advances `latest-upstream` only; adopting a rebased mirror layer remains a reviewed operation.
Validate nested pins and required content before downstream adoption, and retain adopted commits on maintained default branches or release tags.
PR-only commits remain temporary test candidates.

Use `datalad rerun --report` before replaying a selected range.
Historical reproduction restores the recorded environment and subdataset revisions; updated recomputation selects and records the new versions first.
Do not replay template selection or live acquisition accidentally as part of a transformation range.
Installed DataLad help warns that `rerun --onto` does not reset subdataset worktrees, so restore those explicitly.

### Acceptance and history choices

Before rollout, demonstrate a fresh setup, one template update, one retained-input recomputation, and replay from a fresh clone at another location without the original workspace.
Inspect the run commands, environment selections, declared inputs and outputs, child commits, and parent gitlinks.
Exercise unchanged selections and a real conflict or failed-build boundary; the workflow must report each honestly and retain reviewable commits.
Inspect the draft PR to verify that the recorded commits survived publication and that no build or publishing step silently added unrelated source changes.

Preserve individual DataLad run commits when accepting update PRs; squash merging collapses the replayable sequence.
A merge commit can retain those records but does not produce a strictly linear history.
If a strictly linear chain is required, agree on and test an acceptance method that retains the run records and any referenced commit identities.
Keep generated projection and website publication refs under the existing #191 lifecycle rather than adding built files to the source branch merely to show completion.

Decide the downstream reset, preservation of its existing PRs and input repositories, and the final acceptance method after the disposable rehearsal.
The present request expresses an intention to consider a reset, not permission to perform it.

## Earlier comparison implementation sequence

The letters identify proposed PRs, not GitHub PR numbers.
Cleanup #160 and the upstream comparison charter principle in #162 are merged.
The terminology charter principle in #167 and this specification remain separate PRs against `main`.
After agreeing on the plan, start the capture PR from `main`.
Later command PRs may stack on their predecessor until it merges.
Then rebase their unique changes onto `main` and repeat the affected checks.

| PR | Scope | What the reviewer runs and inspects |
| --- | --- | --- |
| A — Cleanup | Retain reusable checkout, service, and worktree-preservation operations. Remove the coupled preview orchestration and its wiring tests. | Helper behavior tests, temporary-service record checks, and CLI help. |
| B — Capture and recording | Expose #152's capture operation as `dev records get`. Provide an explicit DataLad acquisition task. | Capture records, inspect their source information, reuse them, and inspect the portable DataLad command. |
| C1 — Downstream preparation | Capture, JSONL → YAML → JSONL, record comparison, site import, and DataLad replay in an immutable package environment. | Verify direct JSONL equality and replay without the original checkouts. Review and merge before RDF. |
| C2 — RDF comparison | Separate follow-up for RDF generation, comparison, and attribution using the selected upstream converter. | Review RDF semantics and failure boundaries independently of preparation. |
| D — Service round-trip | Upload the exported records to a temporary service and capture the returned records. | Compare export with returned dump, then original capture with returned dump for the complete round-trip. Use a raw-capture service run as a diagnostic control if needed. |
| E — Site-data import | Separate import of psychoinformatics site settings, authored pages, and site-owned files from record conversion. Reuse the pinned `www-from-model` and template layers. | Inspect copied bytes, transformed settings, and page-resource placement against their sources. |
| F — Hugo projection | Expose upstream and Lite Hugo projection from an explicit record stream. Extract #152's selection and annotation-rendering fixes. | Compare selected pages, front matter, Markdown, links, and graph data before the Hugo build. |
| G — Hugo input assembly | Separate assembly of Hugo inputs from building the website. Apply authored-input fixes from #152 and the site-input PR. | Compare complete Hugo inputs, including page resources and configuration, using the same generated content. |
| H — Hugo build and comparison | Build the website from the supplied Hugo input tree. Expose HTML, file, and browser checks through the CLI. Use #154's tool evaluation. | Inspect new website differences, then run the complete generation comparison. |

Complete and review B–H through the CLI before starting the web application.
Each stage delivers its operations, retained intermediate outputs, machine-readable comparison report, and readable summary together.
The summary identifies inputs, operations, comparison scope, detected differences, and failures, with paths to inspect the evidence and commands to reproduce it.
Reviewers must be able to follow the data flow and assess each stage without a browser application.

Introduce CLI decision matching with D and extend it with subsequent stage reports.
After H, validate complete-path comparison, scoped decision reuse across two runs, and report compatibility through the CLI.
Only after maintainers have reviewed that behavior should a separate application PR add portable bundling, serving, viewers, and decision editing over the established reports.
The application must reuse the CLI comparison and matching behavior.

Review each stage's implementation and comparison outputs before merging its PR.
Keep the existing #152 discussion available while extracting its changes.
Its commit history mixes these steps, so extract net file changes and individual patches.

## Comparison and application contract

### Ownership and execution

`packages/diff-review-application/` owns the maintainer single-page application.
The Python package owns operations, comparisons, report generation, and decision matching.
The application reads their outputs and edits review decisions; it does not implement a second comparator or run transformations in the browser.
Use `orinoco-lite` for routine operations and `orinoco-lite dev` for diagnostic operations; Pixi and CI call the same interfaces.

In the later application phase, expose `dev review bundle REPORT... --output DIRECTORY --decisions FILE` to collect explicit stage reports and their referenced artifacts into a portable review directory.
Expose `dev review serve DIRECTORY` to serve that directory and the application locally on loopback.
Bundling must not silently run missing stages, fetch dependencies, or declare integration success.
The directory contains `review.json`, a snapshot of the supplied decisions, and relative artifact paths; it is untracked generated output.
No absolute machine paths, credentials, or live-service access are required to open it.
Git selections and locks remain authoritative.
Reports record the revisions and inputs used to produce their evidence.

Operations write only their declared outputs.
In the later review phase, comparisons accept `--report DIRECTORY` and produce a machine-readable report alongside a readable summary.
Expose `dev review summarize REPORT... --decisions FILE --output DIRECTORY` before the application phase to validate report compatibility and produce readable and machine-readable decision-matching results.
Omit `--decisions` for an initial review; all findings then have no prior decision.
Maintainers can edit the scoped decision file directly and inspect its Git diff, then rerun this command to validate and apply the decisions to the reports.
This command neither runs transformations nor changes the reports or decision file.
Exit codes are 0 for a completed comparison without raw differences, 1 for completed comparisons with raw differences, and 2 for execution or validation failure.
A retained decision does not change raw comparison results or exit codes.
A bundle may contain failed and skipped stages, but must display failed, skipped, and unevaluated stages prominently.

### Stage boundaries

| Stage | Inputs and comparison | Required inspection |
| --- | --- | --- |
| Capture | Retained API response stream and acquisition information | Source, pagination failures, and limits on capture completeness |
| Storage | Raw JSONL versus export joining stored records and overlay files | Record/assertion additions, removals, value and attribution changes |
| RDF conversion | Joined records, selected record-to-RDF conversion, selected inverse conversion | Intermediate RDF, returned records, and field-level preservation failures |
| Service | Export versus upload/dump from a temporary service | Returned records, service failures, and separate conversion evidence |
| Site input import | Selected upstream site data versus imported site inputs | Copied bytes, mapped settings, authored content and resources |
| Projection | Same record stream through upstream and Lite projection | Selection, front matter, Markdown, links, and visualization graph data |
| Assembly | Same projected content through both assembly operations | File tree, configuration, overlays, authored replacements, and resources |
| Rendering | Same assembled tree through both build operations | Routes, HTML, assets, browser differences, and site-check failures |
| Complete paths | Each path consumes its own preceding outputs | Integrated effects and interactions absent from isolated comparisons |

Hugo layouts, assets, and the Congo theme come from the selected `www-from-model` gitlink and that revision's dependency declarations.
The template layers its adaptation and bounded assets over it; site-specific settings and overrides apply afterward.
Authored content overlays generated content.
Importing site data does not copy the Hugo dependency tree into a downstream.
The upstream side must call the selected upstream operations, not the Lite renderer under another name.
Label a selected revision containing retained Lite patches accordingly.

Record comparators preserve scalar types, missing versus null, list order, and duplicates.
Before implementing the record matcher in C, inspect representative assertion collections in the selected schema and retained records.
Document in the comparator's rules and focused tests which collections have stable identity, which allow unambiguous structural matching, and which remain unmatched.
Use schema-defined entity and assertion identities where available.
The existing annotation path plus assertion digest can identify unchanged assertions; it is not a stable identity for an assertion whose value changed.
Ambiguous identities produce unmatched items for review, not guessed matches based on array position or a whole-record hash.
Keep raw changes available when reporting a reviewed representation equivalence.
RDF comparison must account for blank-node renaming without treating blank-node labels as persistent identities; canonical RDF equality does not establish record-round-trip preservation.
Reuse existing snapshot and Pool-diff comparison helpers after checking their type, ordering, and multiplicity behavior against these rules.
For RDF graphs, use the existing RDFLib dependency's `isomorphic` and `graph_diff` operations where applicable; canonical blank-node labels are not cross-run assertion identities.
File comparison reports added, removed, and changed paths; structured viewers expose front matter and graph fields separately from text and byte differences.
Rendering adapters may incorporate SiteDiff after the existing tool evaluation; the application contract must also accommodate route, HTML, asset, and screenshot evidence without that dependency.

### Report format

Version the JSON contract with `schema_version: 1` and validate it on both production and import.
Reject unsupported versions with an actionable message rather than partially interpreting them.
Stage reports expose their execution context, scope, findings, and artifacts before the application exists.
CLI aggregation validates the same evidence that the later bundle imports.
A bundle contains these fields:

| Field | Content |
| --- | --- |
| `run_id` | Unique identifier for this execution, never a decision-matching key |
| `context` | Selected repository revisions, schema and comparator versions, input artifact digests, and dirty-worktree indication where applicable |
| `stages` | Stage identifier, comparison mode (`isolated` or `complete-path`), left/right operations and inputs, comparison scope, status, diagnostics, findings, and artifact references |
| `decisions` | Snapshot of current decisions and digest of the source file used to create it |

Each stage status is `complete`, `failed`, or `skipped`.
Record partial artifacts and diagnostics after failures; they cannot support a clean result or a retired finding.
An omitted stage means not evaluated, not unchanged.
Each report states the evaluated subject, field, class, route, or file scope as applicable, including exclusions and selection policy, derived from the actual command and comparator.
Stage completion alone does not establish that a previous decision's comparison scope was evaluated.
Use `not-evaluated` unless the matcher can establish that the decision's scope was evaluated successfully.
Each artifact reference contains its relative path, media type, and digest; reject path traversal and missing or mismatched artifacts.
This inventory exists only to open and verify the review evidence.
When aggregating reports, validate input/output artifact digests and relevant operation selections along every claimed data-flow link.
An isolated replay may deliberately use a shared input; record the actual link rather than infer it from directory names or stage order.
Preserve each report's execution context when reports come from different runs.
Mixed or incompatible reports may be inspected together, but must be marked as such and cannot establish integration agreement or verified cross-stage attribution without compatible linking evidence.

A finding has a run-local `id`, stage, stable subject identity when available, structured location, change kind, typed before/after values or artifact references, comparator rule/version, and evidence references.
Store the first observed boundary separately from any claimed cause.
A causal link identifies originating and consequent finding IDs, its status (`possible` or `verified`), and supporting evidence.
Verification records the replay inputs, operations, outputs, and tested claim; a manual attribution records its author and rationale but does not become verified merely by being saved.
Permit multiple contributing findings and interactions; do not require a tree with one cause per effect.

Same-input comparisons localize effects introduced by an operation.
Use selective replay when required to establish propagation: hold input or implementation fixed, and where compatible compare both implementations on both inputs.
A verified link applies to those tested conditions.
Recompute or revalidate it for a new run; never inherit causal verification solely from matching record IDs or output paths.
Keep incompatible, inconclusive, and unexplained results visible.
The producer may propose links; humans or agents may supply inspectable replay evidence through the same report contract.

### Saved decisions and subsequent runs

The user-facing operation requiring durable state is reopening the review of a dependency update without deciding unchanged findings again.
Use one explicitly selected Git-tracked JSON decision file for that review scope, owned by the repository where the engineering review is maintained.
It contains current decisions, not generated runs, copied dependency locks, or an inventory of patches.
Git supplies history.
Do not use source-adapter `curation-records` for these engineering decisions.

Each decision contains an ID, disposition (`intended`, `tolerated`, or `undecided`), rationale, operation responsible for the difference, subject/location selector, expected change, schema/comparator compatibility, relevant input conditions, evidence links, and a reconsideration/removal condition. `undecided` records a deferred issue without accepting its behavior. The initial matcher supports exact subject/location, change kind, and typed before/after values within a stage and compatible schema/comparator versions.
Input conditions explicitly name the relevant input values or scope.
Whole-run IDs and dependency SHAs do not by themselves prevent reuse after a repin; changed behavior or unmet conditions do.
When a dependency-specific condition is required, save and evaluate it explicitly.

Broader recurring patterns require a named, versioned comparator rule with behavioral tests and a reviewed decision selecting it.
Do not offer executable browser predicates, unrestricted regular-expression suppression, or automatic widening of scopes.
When applicability cannot be established, present the previous decision as context and require renewed review.
Multiple conflicting matches, changed values, ambiguous identity, and incompatible versions require review rather than choosing a match arbitrarily.
A decision is never a blanket acceptance of all future changes in a field or file.

Matching produces `new`, `changed`, or `matched` (a saved decision applies) for current findings, plus `not-observed` for findings previously matched to a saved decision whose scope was completely evaluated.
Use `not-evaluated` when the relevant comparison scope was not evaluated successfully.
Matched tolerated and undecided findings stay visible as outstanding work without a new decision prompt.
Not-observed findings are candidates for retirement, not automatic proof that a retained patch is unnecessary.
Require a run without the adaptation before recommending its removal.

Verified effects may group under their originating finding; possible links cannot remove items from the review queue.
Grouping an effect with its cause does not establish that the effect matches a saved decision.
A new or materially changed consequence remains actionable even when its cause matches a saved decision and its propagation is verified.
Only effects within the reviewed decision scope may collapse out of the new-or-changed queue.
Apply these rules to CLI summaries and subsequent web views alike.
Retain access to all raw differences, including matched findings and collapsed effects.
Additional differences not explained by the earlier change still require review, even when they affect the same page as a change that matches a saved decision.

In the later application phase, the application exports decision changes as a JSON document containing the original decision-file digest and explicit additions, updates, or removals.
This document describes edits to the decision file; it is not a Git patch.
`dev review apply CHANGES --decisions FILE` validates the schema and base digest, previews the changes, and writes only that file; stale edits must be reopened against the current file.
The operation does not commit, modify metadata, change retained patches, or post to GitHub.
Reviewers inspect and commit the resulting Git diff through their normal workflow.

### Later web review interface

The initial page shows execution context, comparison scope and stage status, and a queue of new or changed findings.
Show unchanged outstanding findings and retirement candidates in separate accessible views.
Selecting a finding shows the before/after values, boundary, rationale, existing decision, and evidence needed to reproduce or question the attribution. Stage navigation provides record/assertion, RDF, file/content, and rendered-site views within one application.
A reviewer can return from a downstream effect to its originating finding and from that finding to every linked effect.

A reviewer can record intent, tolerate an issue, defer a judgment, or revise/retire a decision with a reason.
Fixing code and reporting upstream remain normal repository operations linked from the finding.

Do not make byte-identical builds an acceptance requirement.
Show meaningful record, content, and behavior changes; recurring incidental variation needs explicit bounded treatment, with raw evidence still available.
Render report text as data.
Serve generated pages on an isolated origin or in a sandbox without script privileges; do not allow inspected HTML to execute in the application's origin or access its decision state.
Offer downloaded artifacts when safe inline inspection is unavailable.

### Acceptance checks

Test observable review behavior across multiple schema-valid cases, not just the date-marker reproducer:

- A storage loss is identified before projection; its reviewed, verified page effects group under it while an independent page change remains new.
- An originating finding that matches a saved decision acquires a new verified consequence; the consequence still requires review.
- An RDF-only loss appears at the conversion boundary even when JSONL/YAML preservation passes.
- A second run carries unchanged decisions forward; changed values, changed scope, and ambiguous matches reopen review.
- A tolerated or deferred issue remains visible without asking for the same judgment again.
- A failed, omitted, or successfully completed but out-of-scope comparison cannot retire a finding or appear clean for that scope.
- Reports with valid artifacts but incompatible stage inputs or operation selections cannot establish integration agreement.
- Multi-cause effects and cancellation remain inspectable when isolated and complete-path results disagree.
- A removed adaptation is assessed against the unpatched selection before its decision is retired.
- Stable, structurally matchable, and ambiguous assertions exercise their respective matching rules across more than one record shape.
- Raw evidence remains accessible after grouping in CLI summaries.

Use unit tests for comparator and matcher semantics and CLI integration tests for write boundaries and report interchange.
Exercise at least two successive review runs after B–H, and review their readable outputs before starting application work.
The later application adds browser tests for equivalent review interactions, portable bundles, invalid artifact paths, unsupported versions, stale decision changes, and isolation of inspected HTML.
Do not make web-interface completion a prerequisite for accepting a command stage.

## Command review examples

Run these proposed commands from the downstream directory after activating its [Pixi environment](../../README.md#command-environment).
The path names show how one command supplies the next command's input.
Dependency selection comes from the downstream and package, without repeating upstream pins in command arguments.

### Capture and record preservation

```console
orinoco-lite dev records get
orinoco-lite dev records jsonl-to-yaml
orinoco-lite dev records yaml-to-jsonl
cmp sourcedata/downloaded/records.jsonl sourcedata/yaml-jsonl/records.jsonl
orinoco-lite dev records diff --summary
```

For a downstream, `pixi run setup-upstream` composes template application, package selection, capture, conversion, and site import with DataLad provenance.
`dev upstream populate --reuse-dump` retains the records dump and repeats conversion and site import.
Overlay files preserve machine attribution separately and rejoin it for JSONL reconstruction.
Record comparison preserves scalar types, null versus missing values, array order, and duplicates.
A diff exit code of 1 means differences.

RDF and temporary-service operations belong to subsequent PRs and are not part of the preparation merge.
The later interfaces below remain design targets.

### Site-data import and Hugo projection

```console
orinoco-lite dev upstream import-from-www --destination site-specific
orinoco-lite dev inputs diff site-specific
orinoco-lite dev hugo project upstream build/upstream/projection --records build/records/joined.jsonl
orinoco-lite dev hugo project lite build/lite/projection --records build/records/joined.jsonl
orinoco-lite dev content diff build/upstream/projection build/lite/projection
```

The import reads selected site data from `www-from-model` and any referenced file sources, preserving required page-resource placement.
Its diff compares those inputs with their imported forms in `site-specific`, including settings mapped into `pyproject.toml` (`tool.orinoco.site`).
Hugo projection produces pages and graph data from the same joined records on both sides.
The content diff reports page and graph differences separately.

### Hugo assembly and build

These examples assemble both sets of Hugo inputs from the upstream generated content.

```console
orinoco-lite dev hugo assemble upstream build/upstream/projection build/upstream/assembly --inputs site-specific
orinoco-lite dev hugo assemble lite build/upstream/projection build/lite/assembly --inputs site-specific
orinoco-lite dev content diff build/upstream/assembly build/lite/assembly
```

Then use the upstream Hugo input tree for the build comparison.

```console
orinoco-lite dev hugo build upstream build/upstream/assembly build/upstream/site --base-url /
orinoco-lite dev hugo build lite build/upstream/assembly build/lite/site --base-url /
orinoco-lite dev site diff build/upstream/site build/lite/site
orinoco-lite dev site check build/upstream/site
orinoco-lite dev site check build/lite/site
```

`dev hugo build` consumes the supplied Hugo input tree without reassembling it.
The ordinary `orinoco-lite build` runs projection, assembly, and the website build together.
For the final comparison, project upstream content from the raw retained capture and Lite content from the converted records.
Give each path its own generated content and Hugo input tree, then compare the rendered sites.
This required final run checks how the reviewed steps work together, including interactions that same-input comparisons cannot expose.

## Carrying a decision forward

Identify the operation that introduces a difference, then fix or account for it there.
Later isolated comparisons use identical reviewed input on both sides so earlier differences do not contaminate that operation's comparison.
For each finding, report the first observed boundary, affected assertion or artifact, before/after effect, evidence, existing decision if any, and next action.
Distinguish intended behavior, a tolerated unresolved defect, and an undecided finding; acknowledging a report does not approve its behavior.
Link an existing human decision with its input conditions, expected behavior, operation responsible for the difference, and reconsideration or removal condition.
Reuse it only while those conditions and behavior still match.

The final comparison may group verified downstream consequences under one originating finding, with raw differences still inspectable.
Shared record identity, field, or output file alone does not establish that relationship.
Keep unexplained effects and changed values or behavior outside the reviewed scope as new findings.
Keep unchanged unresolved findings visible without asking for the same decision again.
Report failed or unavailable comparisons separately from clean results.

Keep raw captures unchanged when correcting conversion or rendering behavior.
Put site-data corrections in site inputs and reusable fixes in the package or upstream dependency.
Keep each temporary fix beside the code that needs it, with a focused regression test.
Document its reason, upstream follow-up, and removal condition in that change's PR.
Use existing comparison rules for intentional representation differences.
Add a focused test expectation or a reviewed expected comparison result for specified inputs only when needed to recognize a recurring reviewed difference.
Such expected results are optional, not prerequisites for every stage, and must not automatically approve changed output.
The application stores scoped review decisions under “Saved decisions and subsequent runs”; executable comparison rules and regression tests remain with their owning code.
Do not duplicate source-adapter curation decisions or maintain another patch inventory.

### Escalate an uncertain diagnosis

Start with stage outputs and existing checks.
When they cannot distinguish propagation from a new defect, selectively replay the affected operation while holding either its input or implementation fixed.
Where compatible, run both implementations on both inputs to expose interactions.
Keep incompatible or inconclusive experiments visible as evidence limits.
Add fine-grained diagnostic lineage only when a concrete question remains unanswered by outputs and replay.
Neither a general lineage framework nor automatic causal deduplication is required to land the staged commands.

### Repeat during maintenance

After relevant input, code, or dependency changes, rerun affected boundary comparisons and the complete generation paths before claiming integration agreement.
Present new or changed findings, unchanged unresolved findings, and expectations that no longer match.
Revisit decisions whose conditions or effects have changed; investigate disappeared differences for retirement.
When upstream appears to fix an adaptation, test without that adaptation against the selected upstream before removing it.
Review retained Git patches separately: agreement between paths using the same patched upstream does not establish that its local patches remain necessary.
Use existing Git history, tests, and PR evidence for this review, not a second maintenance inventory.

### Decision: use upstream date-marker conversion

John's 28 September direction supersedes the earlier decision to retain the RDF reader workaround for `at_time: "-"`.
Remove that workaround from #170 and align conversion with the selected upstream behavior.
Keep the original capture and lossless stored record representations intact; this decision concerns derived RDF readback and does not authorize editing source assertions.
Show the upstream omission as a known conversion limitation, without claiming that the marker is a valid datetime or that RDF round-tripping preserves it.
Adjust the projection checks and affected editor expectations to the intended upstream contract, and verify the build without the workaround as part of #180/#188.
Do not substitute another marker-specific normalization or invent a missing-date meaning.

## DataLad recording

DataLad recording is composed outside the CLI through explicit tasks; comparisons leave reports uncommitted.
Required recording for automated metadata proposals and finalization follows the [source-adapter contract](contract/source-adapters.md).

Record the public command, relative paths, declared inputs, and only the operation's outputs.
Use the project's locked tools instead of absolute Python paths or a separately resolved `pixi exec` environment.
External inputs use retrievable repository or service URLs.
Repository owners control DataLad storage policy.
Check portability by cloning into a different directory and rerunning a recorded conversion from the retained capture.

Use the downstream and its pinned site-specific submodule together as the rerun unit.
Reuse the downstream tool lock and record both the input change and the parent submodule pointer.

## Existing PRs and review

| Existing PR | Place in this work |
| --- | --- |
| [Terminology charter #167](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/167) | One sentence on upstream terminology and operation reuse under the existing reuse principle. |
| [Comparison charter #162](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/162) | Merged. One sentence on upstream comparison under the existing reuse principle. |
| [Plan #161](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/161) | This specification and detailed agent guidance, proposed directly against `main`. |
| [Cleanup #160](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/160) | Merged. Retains reusable operations and removes the old preview orchestration. |
| [Package #152](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/152) | Source for the split. Retain its discussion until replacement PRs cover the useful changes. |
| [Package #154](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/154) | Tool research for H. Promote the chosen procedure, then retire the dated report. |
| [Package #142](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/142) | Reuse authored-content and resource preservation in E/G and record, content, and route checks in C/F/G/H. Retire its separate builder after those stages cover it. |
| [Site inputs #1](https://github.com/ORINOCO-Lite/psychoinformatics-site-specific/pull/1) | Separate record preservation for C from authored content and resource placement for E/G. |
| [Downstream #3](https://github.com/ORINOCO-Lite/psychoinformatics-downstream/pull/3) | Integration candidate. Advance package and site-input selections with the verified steps. |

Yarik's message supplied by John establishes the staged review approach.
The five GitHub threads below come from `yarikoptic-gitmate` and identify themselves as Claude-generated reviews.
Address them in the replacement PRs while preserving the original comments.

| Thread | Action |
| --- | --- |
| [Document lifetime and reproducibility](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/152#discussion_r4025790917) | Keep design in the charter, instructions with commands, and dated results in PR evidence. |
| [Difference-table readability](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/152#discussion_r4025791408) | Report each new difference with its effect and next action. |
| [Broken upstream link](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/152#discussion_r4025791960) | Link to the selected file in the upstream repository. |
| [Native procedure and obsolete scripts](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/152#discussion_r4025792747) | Separate reusable operations from preview orchestration in A; provide CLI operations in D–H. |
| [Terminology and charter scope](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/152#discussion_r4025793492) | Keep high-level constraints in the charter and command and recording details here. |

Rewrite #152's stale summary when the replacements are ready.
No comments were present on #142 or #154 during the initial review.

## Implementation details

- `upstream_snapshot` and record split/join code already exist on `main`.
  The new record export must include overlay files.
  It writes JSONL from Lite's stored records; upstream `dtc export` and `dtc import` instead transfer service collections to and from their filesystem format.
- Conversion must update only the records and overlay files it owns.
  Preserve the capture, authored inputs, and repository state in an existing `site-specific` directory.
  The current converter replaces its output directory, so C must separate that write boundary before reusing it.
- Implement `dev hugo project upstream` with the selected `query-things` operations, including `render-record`, and the upstream graph producer.
  Expose Lite Hugo projection through the existing projection code, with an explicit record input.
- Extract shared Hugo input assembly and build functions from `site.py`.
  Ordinary `build` should call them too.
  Its current implementation recreates the assembly before invoking Hugo.
- Move user-facing operations out of recorded `python -m` calls in `instantiate.py` and `development.py`.
  Retain internal Python functions for code reuse.
- Cleanup retains the tested checkout and worktree-preservation helpers.
  It extracts temporary-service configuration and process cleanup beside the existing upload and read-back helpers, with exact record checks against a real filesystem-backed service.
  D can reuse these operations while adding the CLI, retained returned dump, and raw-capture control.
  Prefer the pinned `dtc get-records` and `dtc post-records` operations for capture and service round-trips before adding more HTTP code.
- Use the pinned upstream record reader for B. Reuse #142's authored section and page-resource preservation and its behavioral record, content, and route checks in their owning stages. #142's generator calls the Lite renderer, so upstream generation still needs the selected upstream commands.
  Keep #142 available until the useful behavior has been carried across.
- The retained Pool-diff tool is self-contained.
  Cleanup updates its missing-capture message to select an existing capture instead of referring to removed tasks.
- Resolve the original capture's unknown acquisition time by retaining it as historical input and recording fresh capture facts accurately.
  Pagination completeness checks do not detect every concurrent source edit.
- The legacy capture contains 5,030 records.
  The initial local review found exact agreement with retained upstream YAML. #152 and site-input #1 preserve the date marker after annotation normalization.
- Initial extraction checks passed 19 capture tests and 19 record-preservation tests.
  Content-generation changes applied cleanly.
  Service round-trip and content-tree comparisons remain implementation work.
- Template #75 and #76 are merged.
  Read the selected template from the downstream rather than adding another template PR by default.
