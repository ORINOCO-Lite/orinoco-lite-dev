---
name: compare-orinoco-provenance
description: Compare Orinoco metadata and generated outputs across upstream and Lite paths or revisions, locate transformation boundaries that introduce differences, verify propagated effects through controlled replay, and carry scoped human decisions forward. Use for staged semantic comparison, unexplained metadata loss, and reviewing retained adaptations; not ordinary source-adapter candidate curation or generic code review.
---

# Compare Orinoco provenance

Produce an inspectable explanation of what changed, where it first changed, and which later effects are verified consequences.
Keep detection, causal explanation, and the human decision separate.
Explain meaningful differences and minimize unnecessary local behavior; reducing the reported difference count is not the objective.
A dependency is evidence of possible influence, not proof that it caused the observed difference.
This is an investigation procedure, not an implementation checklist requiring every stage to produce lineage or causal explanations.
Start with stage outputs, same-input comparisons, and the complete-path comparison.
Escalate to replay or instrumentation only for a concrete unresolved question; report remaining uncertainty when that work is outside scope.

## Establish the comparison

- Identify whether the question compares upstream with Lite, two revisions, or two input captures.
  Resolve the selected code, schema, www-from-model, template, inputs, and environment from Git, gitlinks, declarations, and locks; do not create a second coordinate inventory.
  Distinguish original upstream from a selected revision that already contains retained Lite commits.
- Inspect available CLI help and implementation before choosing commands.
  Command names in an active plan may not exist yet.
  Prefer existing operations; if a boundary cannot be observed, report the gap or implement the smallest seam when implementation is authorized.
- Use retained captures and disposable outputs.
  Keep source data and human edits intact; do not refresh a live source while isolating another change.
  Use the locked environment and the existing CLI-owned DataLad recording path where recording is required.
  Downstream diagnosis must not require Git Annex.
- Read the selected schema and relevant repository contracts as task inputs.
  Do not infer curation policy or broaden a prior human decision.

## Observe the boundaries that can change meaning

Trace the actual execution, including branches and overrides, rather than imposing a second pipeline.
In Orinoco, distinguish these boundaries when they participate:

| Boundary | Evidence to inspect |
| --- | --- |
| API capture | Retained records and acquisition/completeness limitations |
| JSONL to stored YAML and companions, then joined export | Identity, assertions, attribution, scalar types, list order and multiplicity, null versus missing |
| Joined records to RDF and any return conversion | Preserved and lost assertions, identifier representation, datatype and collection behavior |
| Selection and projection | Included/excluded records, generated pages, links, graph nodes and edges |
| Hugo assembly | Configuration, layouts, themes, resources, authored content, and override precedence |
| Rendering | HTML, routes, assets, and relevant browser behavior |

Do not substitute graph-visualization JSON for the RDF conversion boundary.
A storage round-trip can pass while RDF conversion loses information.
For missing outputs, inspect failed selection, conversion, joins, unavailable targets, and overwritten outputs; lineage of surviving output alone is insufficient.

Use a comparator appropriate to each representation.
Mapping key order may be irrelevant; do not erase list order, duplicates, types, missing values, or provenance without a reviewed semantic rule.
RDF graph isomorphism removes blank-node naming noise, not arbitrary semantic differences or information already lost in conversion.
Do not use generated blank-node labels as durable cross-run identities.
Report ambiguous assertion matching rather than guessing identity from array position or a changed value's digest.
Retain raw differences alongside any normalized view, and state exactly what normalization ignores.

## Separate input effects from operation effects

First compare both operations on identical input to identify differences introduced at that boundary.
Also compare the complete paths using their respective inputs; isolated agreement does not prove that the stages compose.

When stage outputs leave attribution uncertain and both incoming data and the operation differ, consider this controlled replay where the inputs are valid for both operations:

| | Input A | Input B |
| --- | --- | --- |
| Upstream operation | Upstream(Input A) | Upstream(Input B) |
| Lite operation | Lite(Input A) | Lite(Input B) |

Across a row, hold the operation fixed and observe the input effect.
Down a column, hold the input fixed and observe the operation effect.
Use meaningful run labels in the actual report.
For a revision comparison, substitute the earlier and candidate operations for upstream and Lite.
If the operations disagree only on one input, retain that interaction as a finding; do not dismiss it as inherited noise.
An incompatible replay is an evidence limit, not a passing comparison.
Control clocks, random inputs, and environment where possible; report remaining nondeterminism instead of masking semantic fields.

For opaque operations, inspect existing outputs first, then use selective replay if needed.
Add fine-grained instrumentation only when those observations cannot answer the concrete question.
Prefer diagnostic capture beside the owning operation over a separate model that can drift from it.
Use schema-valid subsets or change sets to reduce a reproducer when useful, preserving required relationships and the same observed failure.
A reduced example supports a diagnosis for that case; it does not prove a universal rule or a unique cause.

## Group effects only as far as evidence supports

Present one originating finding with linked downstream effects when replay or an inspected derivation verifies the relationship for the compared runs.
Keep raw effects inspectable and label attribution as:

- **Verified for these runs:** a controlled replay or derivation supports the stated explanation.
- **Possible dependency:** lineage identifies influence, but attribution is untested or incomplete.
- **Unexplained:** no supported explanation yet.

Do not suppress a difference merely because it shares a record, field, output file, or upstream ancestor with a reviewed finding.
Multiple sufficient causes, cancellations, and interactions may prevent a unique explanation.
Record that limit and keep the effect visible rather than forcing it into one group.
An agent may propose an explanation; reproducible evidence, not confidence in the prose, determines its status.

## Carry the decision at its owning boundary

Classify findings as required, human-agreed Orinoco adaptations, upstream defects, local defects, or unexplained differences.
An upstream reference establishes observed behavior, not correctness; check preservation and other requirements independently.
Acknowledging a report does not approve its behavior.
Existing source-adapter accept/reject/defer decisions govern curation claims; do not repurpose their cache for engineering differences.

For an existing human decision, identify its precise behavior, input conditions, owning operation, reason, and removal or reconsideration condition.
Reuse existing comparison rules, focused tests, and the change's PR explanation.
If an actual recurring decision cannot be recognized with existing checks, propose a narrow expectation or bounded semantic approval fixture beside the owning comparison when implementation is authorized.
Approval fixtures and machine-readable decision scope are not prerequisites for every comparison; where recognition remains manual, say so and retain the human explanation.
Do not automatically approve generated output or turn a tolerated defect into a claim of correctness.
Retain adaptations as separable changes with their tests so they can be removed independently.
For a retained patch or workaround, use its existing commit, issue, or PR to explain its purpose, originating defect, verified downstream effects, upstream submission or inclusion status, and removal condition.
Explain why a change must remain downstream when it is not suitable for upstream; an upstream rejection alone does not justify retention.
Passing checks must not hide the original defect or make a workaround an approved adaptation.

Reapply the decision only while its conditions and observed behavior still match.
Changed values, expanded effects, changed relevant transformation behavior, or failed expectations require review.
A vanished difference calls for checking whether its expectation or adaptation can be retired.
Retiring an adaptation requires testing without it against the selected upstream, not just observing agreement while it remains active.

## Report check outcomes separately

Use these familiar terms for checks with stated expectations, independently of finding classification and patch maintenance status:

| Outcome | Meaning |
| --- | --- |
| PASS | Meets the stated expectation, including a human-agreed adaptation; keep any upstream difference visible. |
| FAIL | Violates the expectation without a matching acknowledged expected failure. |
| XFAIL | Fails in the documented, acknowledged way for the specified inputs and effect scope; retain the linked defect. |
| XPASS | Meets an expectation previously marked as failing; review the defect and removal condition. |
| ERROR | Execution or evaluation failed to produce a trustworthy comparison. |
| SKIP | Deliberately not evaluated; state the reason and coverage gap. |

A known failure must not absorb new or expanded differences; report those separately.
Keep findings without a stated expectation unexplained rather than manufacturing a verdict.
Acknowledging an expected failure does not authorize a workaround, and successful execution alone is not PASS.

Choose tooling for the comparison, not to reproduce this vocabulary.
Use focused pytest checks when inputs, comparison, and assertions fit naturally; constrain expected failures to the known cause and use strict XPASS handling to prompt review.
For exploratory, expensive, or multi-stage comparisons, existing commands and inspectable reports may be more appropriate.
No pytest suite or new reporting framework is required merely to use these outcome labels.

## Present and repeat

For each finding, show the first observed boundary, entity/assertion or artifact, before/after effect, explanation and its evidence, existing decision if any, and next action.
Link commands and inspectable outputs sufficient to reproduce the claim.
Distinguish new or changed findings, unchanged unresolved findings, and expectations that no longer match.
An unchanged unresolved finding stays visible without requesting the same decision again.
Clearly separate a comparison that ran cleanly from one that could not run.

After a relevant repin or change, rerun affected boundaries and the complete path within the requested validation scope.
If that scope excludes a necessary integration check, state the remaining uncertainty.
For upstream patch maintenance, review the retained Git layer separately from comparisons against the already patched selection.
Use properties over supported inputs where possible, rather than only preserving the first reproducer.

Generate detailed traces and reports on demand outside tracked state.
Keep durable state in existing code, tests, reviewed fixtures, Git, and PR explanations.
Do not add a lineage service, exception registry, per-file provenance inventory, or new workflow engine merely to execute this procedure.
If the operation genuinely needs new durable state, identify the unsupported user operation and obtain agreement on that design first.

## Established practices

Borrow concepts and existing tools where they fit; these references do not require a new patch format or test framework:

- [Debian DEP-3](https://dep-team.pages.debian.net/deps/dep3/) supplies patch purpose, origin, upstream issue, forwarding, and inclusion conventions; keep this information with the change.
- [Yocto upstream patch status](https://docs.yoctoproject.org/4.0.27/contributor-guide/recipe-style-guide.html#patch-upstream-status) distinguishes submission, backport, rejection, and downstream-specific maintenance states.
- [Approval testing](https://github.com/Amey-Thakur/AI-SKILLS/blob/main/skills/testing/approval-testing/SKILL.md) supports reviewable expected output; approving a snapshot does not establish correctness or justify divergence.
- [pytest expected failures](https://pytest.org/en/stable/how-to/skipping.html) provides executable expected-failure checks where appropriate; report vocabulary can be used independently of pytest.
