# Agent instructions

## Scope

- This repository owns the Orinoco Lite engine, engineering tests, release assembly, and reusable CI.
- Keep reusable website behavior in the engine or template.
Keep site content, configuration, and source-adapter extensions in the downstream repository.
- Treat `centerforopenneuroscience.org` and its deployment as read-only unless the user explicitly includes them in a task.

## Keep the project lightweight

- Prefer one source of truth.
Do not add a manifest, ledger, decision register, or coordinate inventory that restates information already available from repository configuration, a package lock, Git history, or GitHub.
- Do not retain one-time migration notes or acceptance evidence as current configuration or required agent reading.
Git history and merged pull requests provide the historical record.
- Use commit identifiers only where the software needs them: dependency locks, release inputs, and concurrency checks around a GitHub write.
Do not require commit hashes, per-file origin records, or before-and-after inventories for ordinary content, planning, testing, or rollback.
- Prefer a tested repair or Git revert for rollback.
Do not build a separate rollback evidence system.
- Extend an existing configuration or document only when the runtime or a maintainer consumes the new information.
Otherwise leave it out.

## Development

- Test engine-only, template-only, or combined working-tree changes with `pixi run test-downstream-candidate` before publishing them when practical.
- Use `leej3/orinoco-lite-demo` as the development downstream baseline.
- Keep credentials, caches, browser output, downloaded files, and build output outside tracked repository state.
- Use Conventional Commits and keep commit text near 80 columns.
- Run the relevant tests and formatting checks for the files changed.
