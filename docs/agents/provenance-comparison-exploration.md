# Exploration: explaining and retaining Orinoco differences

Account of the design and skill exploration with John on 18 September 2026.
Audience: maintainers reviewing the staged validation proposal.
This is active implementation context, not a normative contract or evidence that the proposed commands work.
The reusable procedure lives in [compare-orinoco-provenance](../../.agents/skills/compare-orinoco-provenance/SKILL.md).
Retire this account after the comparison design and implementation have absorbed its useful conclusions; retain history in Git.

## Problem and revised assessment

The [staged validation plan](staged-upstream-validation.md) proposes comparisons from captured records through storage, projection, assembly, and rendering.
The goal is to locate changes where they arise, fix or report them there, and avoid asking maintainers to decide on the same propagated difference at every later layer.
Retained adaptations should remain easy to carry forward or remove.

Comparing each operation on identical input is a sound starting point.
However, it does not establish safe composition with Lite's own changed input, and the plan's promise to report a known difference once did not specify how its later effects would be recognized.
JSON/YAML preservation also leaves a separate RDF conversion boundary unobserved.
A clean comparison against a selected upstream revision containing Lite patches does not prove those patches remain necessary.

John explicitly supported making RDF conversion visible and adding a recurring maintenance procedure.
He challenged demonstrating the design only through the existing date-marker case: an implementation could fit that example without generalizing.
The exploration therefore shifted from example-specific regression handling to schema-aware provenance differencing and controlled replay.
John then requested a project-owned skill tuned to this workflow.
That authorizes the procedure, not a new lineage platform or automatic acceptance of metadata changes.

The revised assessment is that automatic grouping of explained effects is feasible within a bounded, observable pipeline.
No inspected source establishes universal causal deduplication across arbitrary code, nor automatic reuse of human decisions without explicit scope.
The schema helps identify comparable facts and valid experiments; transformation semantics and execution evidence are also necessary.

## Research foundations

| Source | Relevant contribution | Limit or implication here |
| --- | --- | --- |
| [PDIFF: provenance and data differencing](https://arxiv.org/html/1406.0905v1) | Compares execution traces, locates divergence, and supports user-defined semantic data comparators. | Closest foundation for paired stage comparisons; not a ready-made Orinoco integration. |
| [Why-Diff, 2019](https://eprints.ncl.ac.uk/256703) | Compares similar but non-identical workflow traces and produces delta graphs for explanations of output differences. | Reported research implementation; present-day adoption suitability was not established. The abstract was inspected; the full-text download timed out. |
| [Provenance in Databases: Why, How, and Where](https://homepages.inf.ed.ac.uk/jcheney/publications/provdbsurvey.pdf) | Distinguishes value origins, sufficient contributing facts, and their derivations. | A flat dependency list loses alternative derivations and does not establish causality. |
| [PUG: why and why-not provenance](https://arxiv.org/abs/1808.05752) | Explains present and missing query answers through relevant derivations. | Missing assertions require inspecting failed conversion, selection, joins, or overrides, not only surviving outputs. |
| [Functional causality for query answers](https://arxiv.org/abs/0912.5340) | Explains answers using changes to data or query operations. | Motivates controlled replay; several causes and interactions may coexist. |
| [Provenance as Dependency Analysis](https://homepages.inf.ed.ac.uk/jcheney/publications/drafts/prov-dep-jv.pdf) | Gives correctness criteria and explains limitations of precise dependency tracking. | Possible influence must remain distinct from verified explanation. |
| [Delta debugging](https://www.debuggingbook.org/html/DeltaDebugger.html) | Reduces inputs or changes while preserving a failure. | A small reproducer is not proof of a universal rule or unique cause. |
| [GProM](https://www.cs.iit.edu/~dbgroup/projects/gprom.html) | Computes provenance on demand through instrumentation and replay for supported database operations. | Supports the design direction of temporary diagnostic traces; does not require adopting its database architecture. |
| [W3C RDF Dataset Canonicalization](https://www.w3.org/TR/rdf-canon/) | Compares RDF datasets independently of blank-node labeling. | Graph isomorphism is not arbitrary semantic equivalence or proof of lossless conversion. |

These sources were consulted as methodological evidence, not installed or benchmarked tools.
Differential Dataflow was also considered as a change-propagation approach; incremental computation alone does not decide which observed differences a human has accepted.

## Skill discovery

Two search rounds used Workshop memory, pinned local sources, ASM, GitHub skill search, and Vercel discovery, supplemented by web search and direct primary-source inspection.
The first searched differential/regression and approval testing.
The second searched provenance differencing, data lineage, delta debugging, and counterfactual replay, plus targeted web queries for PDIFF, Why-Diff, semiring provenance, and why-not explanations in skills.

| Inspected candidate | Useful part | Fit assessment |
| --- | --- | --- |
| [Systematic debugging](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md) | Boundary evidence and controlled causal hypotheses. | Supporting method; no persistent decision semantics. |
| [Property-based testing](https://github.com/trailofbits/skills/blob/main/plugins/property-based-testing/skills/property-based-testing/SKILL.md) | Round-trip, invariant, idempotence, and reference-agreement properties. | Helps generalize beyond one observed failure. |
| [Approval testing](https://github.com/Amey-Thakur/AI-SKILLS/blob/main/skills/testing/approval-testing/SKILL.md) | Human-readable received/approved output and versioned expectations. | Useful for bounded semantic reports; approval does not prove correctness or causality. |
| [Astronomer upstream lineage](https://github.com/astronomer/agents/blob/main/skills/tracing-upstream-lineage/SKILL.md) and [downstream lineage](https://github.com/astronomer/agents/blob/main/skills/tracing-downstream-lineage/SKILL.md) | Trace transformations and affected consumers. | Airflow/SQL-specific; no paired execution comparison. |
| [Astronomer OpenLineage extractors](https://github.com/astronomer/agents/blob/main/skills/creating-openlineage-extractors/SKILL.md) | Capture lineage beside the operation rather than maintain a drifting parallel model. | Useful instrumentation principle; platform-specific implementation. |
| [DataHub lineage](https://github.com/datahub-project/datahub-skills/blob/main/skills/datahub-lineage/SKILL.md) | Field-level paths and explicit incomplete-result handling. | Requires DataHub; upstream traversal is not causal verification. |
| [Google lineage summary](https://github.com/google/skills/blob/main/skills/cloud/datalineage-summary/SKILL.md) | Readable scoped lineage reports. | Requires Google Cloud lineage; no retained comparison decisions. |
| [Trail of Bits differential review](https://github.com/trailofbits/skills/blob/main/plugins/differential-review/skills/differential-review/SKILL.md) | Evidence-backed security code review. | Similar name, different primary problem. |

The project's existing upstream-convergence skill covers Git patch maintenance separately.
A locally indexed DataLad run skill was also inspected as a recording/replay candidate, not adopted as the comparison procedure.
No verified candidate covered paired semantic traces, causal replay, and scoped decision reuse together.
That is a bounded search result, not a claim that no such skill exists.

Freshness checks fetched source status without advancing checkouts.
The scientific-agent-skills checkout lagged upstream and the con-skills checkout lagged its remote; the other registered sources were current at inspection.
GitHub skill search hit a rate limit on the data-lineage query.
Several skills.sh pages were inaccessible through the web reader; canonical GitHub sources supplied the inspected candidate text instead.
No external candidate was installed, and none was behaviorally evaluated on Orinoco.

## Chosen direction and remaining evidence

Use a small project-owned procedure to combine stage comparison, diagnostic lineage, controlled replay, and scoped human decisions.
Keep its instructions self-contained; use live repository configuration and contracts as task inputs rather than copying their semantics into a new framework.
The skill distinguishes intended behavior, tolerated defects, and undecided findings, and keeps uncertain attribution visible.
It requires the RDF boundary and a recurring check after relevant input, code, or dependency changes.

The procedure does not implement the proposed commands or introduce a new exception registry.
Existing code, tests, bounded reviewed expectations, and PR explanations should hold current decisions; Git supplies history.
Generated traces and detailed comparison reports remain disposable.

Before claiming this approach works, exercise more than the first date-marker reproducer.
Useful contrasting cases include a propagated value change, a new later-stage regression on the same record, a missing result, alternative derivations, ambiguous identity, and an obsolete adaptation.
Check that unknown effects remain visible, a failed comparison is never called clean, and a reviewed expectation does not silently expand its scope.
These are future behavioral checks, not completed evaluation results.
