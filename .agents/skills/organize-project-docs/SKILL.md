---
name: organize-project-docs
description: Organize project documentation by audience and lifecycle, separating concise durable guidance, agent operating context, milestone records, decisions, and temporary notes. Use when creating, placing, auditing, compressing, retiring, or reorganizing repository documentation.
---

# Organize Project Docs

Treat documentation as a context budget.
Keep active material short and rely on Git when completed working context is no longer useful in the current tree.

## Classify before writing

| Location | Purpose |
| --- | --- |
| `docs/project-design.md` | Concise, high-level human design and project direction |
| `docs/agents/contract/` | Normative active engineering contracts |
| `docs/agents/` | Active plans, open decisions, and agent context |

Create a directory only when it contains a real document.
Choose one canonical home and do not maintain equivalent copies.

## Preserve instruction discovery

Keep recognized instruction entry points such as `AGENTS.md` where agent harnesses discover them.
They should contain only current constraints, commands, and routing to active material.

Keep `docs/project-design.md` readable without the detailed agent documents.
It should say what the project is building, how its main parts fit together, and the principles that guide implementation.

Files under `docs/agents/contract/` are normative for their named behavior.
Other files under `docs/agents/` may accumulate the detail needed to coordinate active implementation, but are not automatically authoritative.
Link only the small current subset needed by an instruction entry point or active task.

## Write from the shared model outward

Order material by dependency: purpose and shared mental model, necessary terminology, high-level boundaries, then links to precise downstream detail.
Introduce a concept where the reader first needs it, after its prerequisites; do not explain implementation detail early merely to make a later sentence possible.

Prefer plain English.
Use a specialized, ambiguous, or overloaded term only when it improves precision or compresses repeated explanation.
Define it before first necessary use in the document's terminology section, and use it consistently with that definition.
If a concise definition cannot justify and constrain the term, replace it with plain language.

Keep detail at its narrowest authoritative layer:

- high-level design owns the shared mental model, durable intent, and system boundaries;
- contracts own exact supported behavior and authority boundaries;
- agent guidance owns repeatable procedures and routing; and
- code, configuration, workflows, and tests own implementation mechanics and executable facts.

Move detail to the narrowest authoritative source and link to it instead of repeating it at broader layers.
Do not make a high-level document independently sufficient for implementation.

## Compress without making readers guess

Before adding or removing text, identify its load-bearing claims: definitions, obligations, exclusions, conditions, defaults, and unresolved choices.
Preserve each claim once at its authoritative layer.
Different scopes are not duplicates; apparently similar statements must be reconciled rather than silently merged.

For every precision pass:

1. remove restatements and implementation detail available from a linked authority;
2. hoist repeated qualifications or definitions to the earliest appropriate location;
3. scan the edited document and linked authorities for conflicting scope or terminology;
4. prefer a net reduction or unchanged size unless the edit adds durable intent; and
5. stop when another deletion would force a cold reader to infer a project-specific rule.

Measure success by preserved meaning, correct placement, and reduced ambiguity—not by the shortest possible text.

## Keep milestones bounded

A substantial active milestone may use:

```text
docs/agents/milestones/
  007-example/
    plan.md
    progress.md
    completion.md
```

Create only the files that carry distinct information.
Rewrite `progress.md` as a compact restart point instead of appending a diary.
Promote lasting product requirements into a concise normative document.

## Retire completed context

At a milestone boundary:

1. Promote lasting high-level direction into `docs/project-design.md` and only essential operating constraints into `AGENTS.md`.
2. Promote any lasting normative detail into the relevant active contract.
3. Delete completed plans, reports, decisions, and explanations that no longer guide current work.
4. Remove links to retired documents from current instructions and indexes.
5. Delete scratch material when its lack of continuing value is clear.

Git provides history on demand without exposing retired documents to ordinary repository searches.
Do not create archive directories merely to retain superseded project context.

## Working rules

- Inspect existing instructions, indexes, links, conventions, and terminology before editing.
- State the document's reader, lifetime, and source of truth before expanding it.
- Preserve useful current material when reorganizing files; rely on Git for retired history.
- Never store credentials, tokens, private keys, or browser secrets in docs.
- Report ambiguous classification instead of silently turning tentative notes into durable policy.
