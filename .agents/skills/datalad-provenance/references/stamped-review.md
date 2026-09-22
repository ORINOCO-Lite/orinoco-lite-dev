# Scoped STAMPED review

Apply these seven lenses to the operation the user wants to trust.
This is a project-specific review aid, not a claim of formal STAMPED compliance.
Start read-only.
Do not execute pipelines, publish, change storage, or add licensing work merely because an assessment suggests it.

| Principle | Useful evidence and question |
| --- | --- |
| Self-containment | Can a clone obtain the retained inputs and referenced components without the original workspace? Saved supplied bytes are valid inputs; subdatasets are optional. |
| Tracking | Do Git history, run records, package selection, lock, and gitlinks identify the state actually used? Distinguish known acquisition provenance from an undocumented supplied snapshot. |
| Actionability | Are the recorded public commands executable, with explicit input/output paths and an understandable order? |
| Modularity | Can capture, conversion, and import be explored independently without copying workflow machinery into each downstream? |
| Portability | Do paths, tools, credentials, and dependencies remain meaningful elsewhere? Relative paths can still escape into host-specific state. |
| Ephemerality | Can the execution environment be recreated from its specification without relying on a populated editable checkout or hidden cache? A container is not required. |
| Distributability | Are the referenced versions and bytes available to the intended recipient? A configured remote or gitlink alone does not prove availability. For a requested distribution assessment, report known access/rights gaps without inventing grants or expanding implementation scope. |

Report concrete findings as observed, partial, or not tested, with supporting commands or paths.
Do not award compliance because a filename or tool is present.
Prioritize fixes that change whether the requested operation works.
Reuse Git and DataLad evidence rather than adding provenance inventories or score registries.

## Calibration examples

- Recorded `cp ../../../Users/person/source.jsonl sourcedata/records.jsonl`: the destination may be recoverable, but the copy cannot be claimed portable.
  Prefer recording acquisition or a copy from a recoverable versioned source.
  If only supplied bytes are available, ingest and save them, disclose the source-provenance gap, and replay downstream transformations from that saved boundary.
- Same command after a package upgrade: useful recomputation, not automatically a historical reproduction.
  Check which environment actually executed it.
- A clone without the original source path successfully transforms retained data: evidence for that transformation's portability, not for replaying acquisition or accessing every remote on another person's machine.
- Parent revision restored with an unchanged child worktree: insufficient evidence of historical replay.
  Inspect the actual subdataset state.

Discovery reference: the [community STAMPED assessment](https://github.com/bcmcpher/my-skills/tree/main/plugins/datalad-cli/skills/datalad-stamped-assess) and its companion principles reference informed the review lenses.
This skill contains its operating guidance locally and does not require that plugin.
