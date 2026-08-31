---
name: organize-project-docs
description: Organize project documentation by audience and lifecycle, separating concise durable guidance, agent operating context, milestone records, decisions, temporary notes, and retired history. Use when creating, placing, auditing, compressing, or reorganizing repository documentation.
---

# Organize Project Docs

Treat documentation as a context budget.
Keep active material short and move completed working context out of normal discovery without erasing history.

## Classify before writing

| Location | Purpose |
| --- | --- |
| `docs/project-design.md` | Concise, high-level human design and project direction |
| `docs/agents/contract/` | Normative active engineering contracts |
| `docs/agents/` | Active plans, open decisions, and agent context |
| `docs/archived/` | Retired human-facing explanations retained only for history |
| `docs/agents/archived/` | Retired agent plans, milestone records, reports, and decision queues |

Create a directory only when it contains a real document.
Choose one canonical home and do not maintain equivalent copies.

## Preserve instruction discovery

Keep recognized instruction entry points such as `AGENTS.md` where agent harnesses discover them.
They should contain only current constraints, commands, and routing to active material.
Do not point current instructions or indexes to archived documents.

Keep `docs/project-design.md` readable without the detailed agent documents.
It should say what the project is building, how its main parts fit together, and the principles that guide implementation.

Files under `docs/agents/contract/` are normative for their named behavior.
Other files under `docs/agents/` may accumulate the detail needed to coordinate active implementation, but are not automatically authoritative.
Link only the small current subset needed by an instruction entry point or active task.

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
2. Move completed human explanations to `docs/archived/`.
3. Move completed agent plans, reports, decisions, and milestone working context to `docs/agents/archived/`.
4. Remove links to those archives from current instructions and indexes.
5. Delete scratch material only when its lack of continuing value is clear.

Archives provide history on demand.
They are not fallback instructions, required reading, or a second source of current policy.

## Working rules

- Inspect existing instructions, indexes, links, and conventions first.
- State the document's reader, lifetime, and source of truth before expanding it.
- Prefer links to active canonical material over duplicated explanation.
- Preserve history with ordinary file moves when reorganizing existing files.
- Never store credentials, tokens, private keys, or browser secrets in docs.
- Report ambiguous classification instead of silently turning tentative notes into durable policy.
