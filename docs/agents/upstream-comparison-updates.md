# Update the upstream comparison

Run **Actions → Update upstream comparison** in `orinoco-lite-dev`.
It updates `ORINOCO-Lite/psychoinformatics-downstream` and its separately published `ORINOCO-Lite/psychoinformatics-site-specific` dataset.

Select a template revision and, optionally, a package revision; the package defaults to the engineering commit running the workflow.
**Retained capture** recomputes from saved records.
**Refresh from Pool** records a new acquisition first.
Both synchronize imported upstream site inputs using the selected package.
The workflow records template/package selection and preparation with the existing DataLad commands, then builds and verifies the site.

Leave the site-input revision blank to keep the parent's pin.
Selecting a revision records its fast-forward advance separately.
Publishing new child commits requires the selected child base to equal its current `main`; when the parent trails it, review that difference before selecting `main`.

Clear **Publish draft pull requests** to retain the prepared bundles without publishing.
An unchanged result creates no PR.
Conflicted template updates and failed builds produce drafts with their status; incomplete preparation stops the run.
Child commits are published first, and the parent PR links their draft.
Preserve those child commits when merging before accepting the parent gitlinks.

## Publication setup

Set the organization secret `UPSTREAM_UPDATE_TOKEN`, available to `orinoco-lite-dev`.
Use a fine-grained PAT scoped to the two target repositories with **Contents**, **Pull requests**, and **Workflows** write permissions.
Workflow permission allows template updates to change the parent's workflow files.

Restrict the engineering repository's `upstream-comparison` environment to `main`, with any required reviewers.
Only the separate publishing job uses the token; pull requests are opened as its owner.
The generic downstream template and curation service require no changes.
