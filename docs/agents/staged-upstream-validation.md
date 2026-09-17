# Upstream diff detection

Active plan for John and Yarik, updated 17 September 2026.
The [design charter](../project-design.md) sets the high-level constraints.
This plan defines the validation commands and recording rules and arranges their implementation into reviewable PRs.

## Review path

Review the charter principle and this implementation plan independently against `main`, then review each command group in order.
Each PR supplies commands, example inputs, and inspectable outputs for its step.
Use the same reviewed inputs for both sides of each comparison.
After those comparisons pass, compare the complete upstream and Lite generation paths.

`orinoco-lite` is the public interface for routine operations; development operations belong under `orinoco-lite dev`.
Pixi tasks may shorten common commands, and CI uses those tasks or the CLI.
Direct scripts and Python module execution are for development and debugging.
The command names below are proposed interfaces.
Existing functions provide much of the implementation.
Keep `dev setup`, `dev enable`, and `dev disable` as convenience operations built from the same code.

### Prepare and review inputs

First check record preservation and authored inputs.
Rounded boxes identify reviewed inputs; dotted arrows show how comparisons inform a maintainer's selection.

```mermaid
flowchart LR
  subgraph records["Record preservation"]
    direction TB
    pool["Pool"] -->|supplies| raw["Captured records"]
    raw -->|convert to| stored["Site-specific metadata"]
    stored -->|is exported as| joined["Joined records"]
    joined -->|round-trip through a temporary service as| returned["Returned records"]
    raw -->|provide the reference for| storedcheck["Stored-record comparison"]
    joined -->|are checked by| storedcheck
    raw -->|provide the reference for| servicecheck["Service comparison"]
    returned -->|are checked by| servicecheck
    storedcheck -.->|informs selection of| reviewed(["Reviewed records"])
    servicecheck -.->|informs selection of| reviewed
  end
  subgraph authored["Authored inputs"]
    direction TB
    upstream["Selected www-from-model"] -->|supplies| files["Authored content and files"]
    upstream -->|provides the reference for| inputcheck["Authored-input comparison"]
    files -->|are checked by| inputcheck
    inputcheck -.->|informs selection of| inputs(["Reviewed authored inputs"])
  end
  %% Keep the independent input reviews beside each other.
  records ~~~ authored
```

### Compare each generation step

Then compare generation, composition, and rendering using the same reviewed inputs for upstream and Lite.
Select one reviewed output for the next comparison.

```mermaid
flowchart TB
  records(["Reviewed records"])
  records -->|feed| genup["dev content generate upstream"]
  records -->|feed| genlite["dev content generate lite"]
  genup -->|supplies pages and graph to| contentdiff["dev content diff"]
  genlite -->|supplies pages and graph to| contentdiff
  contentdiff -.->|informs selection of| projection(["Reviewed generated content"])

  inputs(["Reviewed authored inputs"])
  projection -->|supplies content to| shared["Shared composition inputs"]
  inputs -->|supply authored files to| shared
  shared -->|feed| composeup["dev content compose upstream"]
  shared -->|feed| composelite["dev content compose lite"]
  composeup -->|supplies Hugo inputs to| assemblydiff["dev content diff"]
  composelite -->|supplies Hugo inputs to| assemblydiff
  assemblydiff -.->|informs selection of| assembly(["Reviewed Hugo inputs"])

  assembly -->|feed| renderup["dev site render upstream"]
  assembly -->|feed| renderlite["dev site render lite"]
  renderup -->|produces one of| sites["Rendered websites"]
  renderlite -->|produces one of| sites
  sites -->|are compared by| sitediff["dev site diff"]
  sites -->|are checked by| check["dev site check"]
```

Raw comparisons remain available beside the summary of new differences.

## Proposed PR stack

The letters identify proposed PRs, not GitHub PR numbers.
Cleanup #160 is merged.
The charter principle and this command plan remain separate PRs against `main`.
After agreeing on the plan, start the capture PR from `main`.
Later command PRs may stack on their predecessor until it merges.
Then rebase their unique changes onto `main` and repeat the affected checks.

| PR | Scope | What the reviewer runs and inspects |
| --- | --- | --- |
| A — Cleanup | Retain reusable checkout, service, and worktree-preservation operations. Remove the coupled preview orchestration and its wiring tests. | Helper behavior tests, temporary-service record checks, and CLI help. |
| B — Capture and recording | Extract #152's capture command. Add shared CLI-owned DataLad recording and `--no-record`. | Capture records, inspect their source information, reuse them, and inspect the portable DataLad command. |
| C — Record conversion | Expose conversion, joined export, and field-level comparison. Carry the reviewed date-preservation fix from #152. | Convert the capture, export joined records, and inspect changed identifiers, fields, and values. |
| D — Service round-trip | Upload the exported records to a temporary service and capture the returned records. | Compare the returned records with the original capture. Run a raw-capture control to locate service-side changes. |
| E — Authored inputs | Separate acquisition of authored content, configuration, images, and downloads from record conversion. | Inspect copied bytes, transformed configuration, and file placement against the selected upstream inputs. |
| F — Content generation | Expose upstream and Lite page generation from an explicit record stream. Extract #152's selection and annotation-rendering fixes. | Compare selected pages, front matter, Markdown, links, and graph data before Hugo. |
| G — Composition | Separate composition from rendering in the existing builder. Apply authored-input fixes from #152 and the site-input PR. | Compare complete Hugo inputs, including page resources and configuration, using the same reviewed projection. |
| H — Rendering and comparison | Render an inspected assembly. Expose HTML, file, and browser checks through the CLI. Use #154's tool evaluation. | Inspect new rendering differences, then run the complete generation comparison. |

A difference must be corrected or explicitly accepted before its PR merges.
Keep the existing #152 discussion available while extracting its changes.
Its commit history mixes these steps, so extract net file changes and individual patches.

## Command review examples

Run these proposed commands from the downstream directory through its locked Pixi environment.
The path names show how one command supplies the next command's input.
Dependency selection comes from the downstream and package, without repeating upstream pins in command arguments.

### Capture, conversion, and service round-trip

```console
pixi run --locked orinoco-lite dev capture site-specific/sources/pool/records.jsonl
pixi run --locked orinoco-lite dev records convert site-specific/sources/pool/records.jsonl site-specific
pixi run --locked orinoco-lite dev records export site-specific build/records/joined.jsonl
pixi run --locked orinoco-lite dev records diff site-specific/sources/pool/records.jsonl build/records/joined.jsonl
pixi run --locked orinoco-lite dev records roundtrip build/records/joined.jsonl build/records/returned.jsonl
pixi run --locked orinoco-lite dev records diff site-specific/sources/pool/records.jsonl build/records/returned.jsonl
```

Annotation companions keep machine attribution for record assertions separate for human readability.
The export rejoins them with the records without generating pages.
The round-trip command manages the temporary service and retains the returned dump for inspection.
The diff shows raw field changes and identifies reviewed annotation-equivalent changes separately.
It preserves list order, duplicate values, scalar types, and the distinction between null and missing values.

### Authored inputs and generated content

```console
pixi run --locked orinoco-lite dev inputs acquire site-specific
pixi run --locked orinoco-lite dev inputs diff site-specific
pixi run --locked orinoco-lite dev content generate upstream build/upstream/projection --records build/records/joined.jsonl
pixi run --locked orinoco-lite dev content generate lite build/lite/projection --records build/records/joined.jsonl
pixi run --locked orinoco-lite dev content diff build/upstream/projection build/lite/projection
```

Input acquisition uses the selected `www-from-model` and preserves required page-resource placement.
Its diff compares those source files with their destinations in `site-specific`.
Generation produces pages and graph data from the same joined records on both sides.
The content diff reports page and graph differences separately.

### Composition and rendering

After reviewing the generation comparison, select one output as the shared input for composition.
These examples use the upstream output.

```console
pixi run --locked orinoco-lite dev content compose upstream build/upstream/projection build/upstream/assembly --inputs site-specific
pixi run --locked orinoco-lite dev content compose lite build/upstream/projection build/lite/assembly --inputs site-specific
pixi run --locked orinoco-lite dev content diff build/upstream/assembly build/lite/assembly
```

Then select the reviewed assembly for the rendering comparison.

```console
pixi run --locked orinoco-lite dev site render upstream build/upstream/assembly build/upstream/site --base-url /
pixi run --locked orinoco-lite dev site render lite build/upstream/assembly build/lite/site --base-url /
pixi run --locked orinoco-lite dev site diff build/upstream/site build/lite/site
pixi run --locked orinoco-lite dev site check build/upstream/site
pixi run --locked orinoco-lite dev site check build/lite/site
```

Rendering consumes the supplied assembly without recomposing it.
For the final comparison, generate upstream content from the raw retained capture and Lite content from the converted records.
Give each path its own projection and assembly, then compare the rendered sites.
This final run checks how the reviewed steps work together.

## Carrying a decision forward

Identify the operation that introduces a difference, then fix or account for it there.
Later isolated comparisons consume the reviewed output.
The final comparison reports a known difference once and links its explanation.
A changed value or behavior outside the accepted scope appears as a new difference.

Keep raw captures unchanged when correcting conversion or presentation behavior.
Put site-data corrections in site inputs and reusable fixes in the package or upstream dependency.
Keep each temporary fix beside the code that needs it, with a focused regression test.
Document its reason, upstream follow-up, and removal condition in that change's PR.
Use existing comparison rules for intentional representation differences.
Do not create a separate exception registry.

### Decision: preserve the source date marker

Preserve `at_time: "-"`.
Keep the adaptation and its regression tests in one commit while deciding how to align with upstream without that commit.
Preserve that commit when merging C instead of squashing it with the new CLI operations.

The adaptation belongs at record conversion in C. #152 preserves the value in storage and adapts the RDF reader where it otherwise disappears.
Investigate the upstream conversion behavior before choosing its permanent correction.
Remove the adaptation when the selected upstream code handles this case and the record-preservation test still passes.

## DataLad recording

Retained-input changes record by default, while comparisons leave reports uncommitted.
The CLI owns recording and uses `--no-record` for the inner command to prevent nested recording.
The same flag allows development runs without a DataLad commit.
Pixi tasks and CI call that same interface.
Required recording for automated metadata proposals and finalization follows the [source-adapter contract](contract/source-adapters.md).

Record the public command, relative paths, declared inputs, and only the operation's outputs.
Use the project's locked tools instead of absolute Python paths or a separately resolved `pixi exec` environment.
External inputs use retrievable repository or service URLs.
Use ordinary Git without requiring Git Annex.
Check portability by cloning into a different directory and rerunning a recorded conversion from the retained capture.

Use the downstream and its pinned site-specific submodule together as the rerun unit.
Reuse the downstream tool lock and record both the input change and the parent submodule pointer.

## Existing PRs and review

| Existing PR | Place in this work |
| --- | --- |
| [Charter #162](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/162) | One sentence on upstream comparison under the existing reuse principle. |
| [Plan #161](https://github.com/ORINOCO-Lite/orinoco-lite-dev/pull/161) | This command plan and detailed agent guidance, proposed directly against `main`. |
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
  The new record export must include annotation companions.
- Conversion must update only the records and annotation companions it owns.
  Preserve the capture, authored inputs, and repository state in an existing `site-specific` directory.
  The current converter replaces its output directory, so C must separate that write boundary before reusing it.
- Reuse the selected upstream query/Jinja commands for upstream page generation.
  Expose Lite generation through the existing projection code, with an explicit record input.
- Extract shared composition and rendering functions from `site.py`.
  Ordinary `build` should call them too.
  Its current implementation recreates the assembly before rendering.
- Move user-facing operations out of recorded `python -m` calls in `instantiate.py` and `development.py`.
  Retain internal Python functions for code reuse.
- Cleanup retains the tested checkout and worktree-preservation helpers.
  It extracts temporary-service configuration and process cleanup beside the existing upload and read-back helpers, with exact record checks against a real filesystem-backed service.
  D can reuse these operations while adding the CLI, retained returned dump, and raw-capture control.
  Consider the upstream `dtc` client there before adding more HTTP code.
- Use #152's capture implementation for B. Reuse #142's authored section and page-resource preservation and its behavioral record, content, and route checks in their owning stages. #142's generator calls the Lite renderer, so upstream generation still needs the selected upstream commands.
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
