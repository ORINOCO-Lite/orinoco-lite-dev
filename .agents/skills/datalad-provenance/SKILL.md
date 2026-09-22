---
name: datalad-provenance
description: Design or review DataLad capture, save, run, and rerun workflows in Orinoco Lite; assess their recoverability using STAMPED principles. Use for supplied snapshots, recorded transformations, historical replay, or recomputation with updated software or data. Not an installation guide or an automatic publication audit.
---

# DataLad provenance

Use DataLad's existing operations.
A recorded command is evidence of execution, not proof that another clone can recover its inputs or environment.

## Choose the provenance boundary

- **Acquisition:** wrap the actual acquisition command in `datalad run` and declare its outputs, so execution and output recording stay together.
  Do not replace a recordable acquisition with a bare command followed by `datalad save`.
  Retain its output for historical replay.
  Repeating a request to a changing server is a new acquisition; it need not reproduce the original bytes.
- **Snapshot from a recoverable versioned source:** reference the source and its revision, for example through a pinned input subdataset.
  Record any copy or transformation with `datalad run`, declaring that recoverable source as input and the destination as output.
  Copying is a valid recorded operation; an unversioned machine-local source is the portability problem.
- **Supplied bytes without a recoverable source:** ingest and use `datalad save -m "chore: retain supplied capture" -- sourcedata/records.jsonl` to establish a versioned input boundary.
  Preserve any supplied acquisition metadata and state what is unknown; do not invent the generating operation.
  This fallback records the supplied bytes, not their acquisition, and is not equivalent to capturing execution with `datalad run`.
  Subsequent reproducible transformations consume those saved bytes.
- **Transformation:** use `datalad run` with explicit, dataset-relative inputs and outputs, including relevant configuration and environment selections.
  Invoke public executables.
  Keep independently useful stages separately runnable.
- **Inspection:** run read-only inspection without creating run records.

A relative path such as `../../../Users/person/project/capture.jsonl` still depends on the original host.
`--assume-ready inputs` skips retrieval; it does not version, retain, or make an external input available.
Do not use it to conceal that gap.
Existing historical records remain evidence; correct future workflow rather than rewriting old provenance without an explicit request.

## Execute in the selected environment

Use the project's Pixi environment.
A Bash workflow launched through Pixi can call bare `datalad` and package executables until an explicit environment switch is needed.
Do not repeat `pixi run` mechanically inside that shell.

Keep the package selection and lock committed.
A run record does not capture its outer launcher automatically or restore software on rerun.
Record an exceptional bootstrap invocation in the run message when necessary.
Avoid editable/local-only software for a claimed independently recoverable result; exact available commits are sufficient without requiring releases or additional ledgers.

Inspect `datalad status` before writing, and save only the intended paths.
Preserve unrelated changes.
This project uses ordinary Git data; do not introduce Git Annex or containers merely to satisfy a checklist.
For subdataset outputs, check both the child commit and the parent's gitlink.
Replay from the dataset identified by the run record, not an arbitrary child containing a duplicate record.

## Select the replay question

- **Historical reproduction:** use the retained capture, the corresponding configuration, package/lock, and subdataset revisions in an isolated checkout.
  Activate that environment before replay.
  Exclude live acquisition when testing the transformation of historical data.
- **Updated recomputation:** commit the intended new data or software selection, activate it, then replay selected transformation commands against that state.
  Inspect the resulting diff; differences can be the expected result.

Inspect `datalad rerun --report REVISION` before a nontrivial replay.
Consult the installed `rerun --help` for ranges and `--onto`; do not assume that checking out the parent also resets subdataset worktrees or selects the software environment.

## Check the actual semantics

Use installed help and the official references below when flags matter.
`run --dry-run basic` describes execution without executing the command.
`--explicit` limits what gets saved; it does not require manual pre-unlocking.
DataLad prepares declared outputs, but ordinary Git files can remain present: use the application's supported overwrite option when reruns require it, scoped to declared generated outputs.
A successful no-change run may create no commit.
Do not interpret an exit code alone as evidence that output content agrees.

For a portability claim, exercise the smallest relevant transformation from a fresh clone at a different location with the original external capture unavailable.
Inspect the recorded command, inputs, output bytes, and resulting Git state.
Report separately what was tested and what remains dependent on network access or software availability.
Do not create a new test framework just for this check.

For a requested assessment, read [the scoped STAMPED review](references/stamped-review.md).

Official command references: [run](https://docs.datalad.org/en/stable/generated/man/datalad-run.html), [save](https://docs.datalad.org/en/stable/generated/man/datalad-save.html), and [rerun](https://docs.datalad.org/en/stable/generated/man/datalad-rerun.html).
