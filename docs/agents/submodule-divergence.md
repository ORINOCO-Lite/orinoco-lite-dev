# Submodule divergence

[The CSV](submodule-divergence.csv) shows the direct and nested submodules selected by this package.
Gitlinks select commits; Git history supplies merge bases, distances, descriptions, and exact local commit subjects.
The report is generated output, not dependency configuration.

Run setup once, then stage intended gitlink or `.gitmodules` changes before refreshing the report:

```console
python3 tools/setup_submodule_remotes.py
python3 tools/submodule_divergence.py
```

The report uses the configured authoritative `upstream` remote for mirrors and `origin` for direct dependencies such as Congo.
It compares against the branch declared in the selected parent's `.gitmodules`, including a mirror of that branch.
When no branch is declared, it uses the authoritative remote's default branch.
Nested declarations come from the exact selected parent commit, not its working checkout.
Local commits on top are expected and are listed verbatim without a title or intent policy.
`comparison_url` links the mirror's comparison against the selected upstream branch when local commits exist.

Generation fetches upstream refs and atomically replaces the CSV only after every row succeeds.
Review and stage that file with the dependency change.
It does not repin submodules, advance mirror branches, rewrite history, or create pull requests.
Use `--no-fetch` to refresh from locally cached refs; `--check` checks the entire working report against those refs without writing.
Missing refs or shallow history need a normal fetch-enabled run.

The pre-commit hook uses `--staged-check`.
It checks only changed staged dependency selections and report rows against `HEAD`, without fetching, initializing submodules, or editing files.
Unchanged historical drift and existing local commits do not block unrelated commits.
A changed selection needs its corresponding report row staged; a correct but unstaged report cannot satisfy the hook.
Upstream movement alone does not block a commit.
Use an explicit full refresh when reviewing upstream updates.

Generation exits 0 on success, including when it updates the CSV.
Checks exit 1 for stale rows; operational errors exit 2.
