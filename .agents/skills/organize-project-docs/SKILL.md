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

- Inspect existing instructions, indexes, links, and conventions first.
- State the document's reader, lifetime, and source of truth before expanding it.
- Prefer links to active canonical material over duplicated explanation.
- Preserve useful current material when reorganizing files; rely on Git for retired history.
- Never store credentials, tokens, private keys, or browser secrets in docs.
- Report ambiguous classification instead of silently turning tentative notes into durable policy.
