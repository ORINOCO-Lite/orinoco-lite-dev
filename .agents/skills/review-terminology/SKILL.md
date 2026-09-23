---
name: review-terminology
description: Delegate investigation of ambiguous or newly introduced shared terminology in code, configuration, architecture, and agent guidance. Use before establishing or changing a component name, interface term, or cross-cutting concept, or when one term appears to denote different things. Not for routine local variable names, spelling, or prose formatting.
---

# Review terminology

Resolve what a name denotes before it becomes a shared convention.
The parent agent owns the task and final choice; a sub-agent performs the exploratory review and returns concise recommendations.

## Required handoff

The parent MUST delegate the terminology investigation to a sub-agent.
Give it a bounded, read-only assignment while continuing independent task work.
Do not repeat its searches in the parent or finalize affected names before its findings arrive.
If delegation is unavailable, report that limitation and leave the naming decision unresolved; continue work that does not depend on it.

Send only the context needed to understand the decision:

- the intended operation, audience, and names under consideration;
- relevant file paths, selected upstream dependencies, and a few representative uses;
- user decisions and constraints, including any external interfaces affected; and
- the instruction to read this skill and return recommendations without editing files or posting messages externally.

Prefer a fresh sub-agent context over copying the full conversation.
Batch related terms into one assignment.
Do not send the entire repository or require an exhaustive vocabulary audit.
The assigned reviewer performs the review directly and MUST NOT delegate again merely because it reads this skill.

## Reviewer investigation

Trace each term to the concrete object, action, or relationship it denotes.
Inspect representative definitions and callers, plus the selected upstream's terminology where relevant.
Existing repetition is evidence of usage, not proof that a name is suitable.
Distinguish an established domain term from an internal convention or a broad descriptive word.

Check whether:

- one term denotes different things, or different terms denote the same thing;
- an upstream component or operation already supplies a suitable name;
- the proposed name distinguishes adjacent concepts without requiring implementation knowledge; and
- an aggregate has a useful common role and a clear boundary, rather than collecting unrelated things under one convenient label.

Broad nouns such as “context,” “state,” “resource,” and “layer” are prompts to investigate, not forbidden words.
Prefer concrete component names and verbs when they express the intended meaning.
Retain a general term when its scope is clear and useful.
A glossary must describe a settled concept; it must not conceal unresolved distinctions.
Do not invent a design decision to make a name appear precise.

Consider prose, internal identifiers, paths, configuration keys, and serialized interfaces separately.
Report the consequences of a rename, including compatibility and coordinated updates, without treating existing names as permanent or authorizing changes beyond the task.
Stop exploring once the evidence supports a choice or identifies the specific missing decision.

## Return to the parent

Return a compact decision brief, not a search transcript or new tracked report.
For each disputed term, give:

- its observed meanings and a small number of source references;
- a recommended name or explicit recommendation to retain it, with reasons;
- a meaningful alternative and tradeoff when there is one; and
- affected interfaces and any uncertainty requiring a user decision.

Keep the brief proportionate to the decision, normally within 500 words.
Separate observed facts from inference.
Do not generate alternatives merely to fill a quota.

The parent assesses the recommendations against the task, asks the user only about unresolved intent or material choices, and continues implementation.
Apply the chosen terminology consistently across the affected code, configuration, help, tests, and guidance within the authorized scope.
Do not add a glossary, registry, banned-word linter, or migration framework just to record the review.
