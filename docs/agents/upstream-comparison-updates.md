# Update the upstream comparison

Run **Actions → Update upstream comparison** in `orinoco-lite-dev`.
It updates `ORINOCO-Lite/psychoinformatics-downstream` and its separately published `ORINOCO-Lite/psychoinformatics-site-specific` dataset.

Prepare two updates in order:

1. **Software only:** select the full SHA of a template candidate whose package declaration pins the desired package SHA.
   The workflow records the template update, recomputes metadata from the retained Pool capture, and builds with the package-selected upstream software and dependencies.
   It preserves the authored site inputs.
   Compatibility failures remain visible in this PR.
2. **Data refresh:** select the software-update branch as `base_branch`, leave `template_revision` empty.
   This run retains the software selection, captures Pool again, converts records, imports site inputs as separate DataLad operations.

If the software update changed metadata in `site-specific`, use its published branch as `site_base_branch` for the stacked data refresh.
Otherwise keep `main`.
Publication requires that branch head to match the parent's selected child gitlink; reconcile a stale pin before publishing.

The upstream-comparison downstream always uses development mode with `.orinoco-lite/orinoco-lite-dev` tracked as a Git submodule.
Its editable package selects one nested `www-from-model` checkout for rendering, projection, assets, and site-input imports.
The bundled rendering subset used by ordinary downstream builds does not supply authored upstream website inputs.
Imported settings, content, identity images, and static files come from that checkout, including its Annex media.
The importer does not copy theme or other software dependencies.

For local recomputation use `dev upstream populate --reuse-dump --records-only`.
Ordinary `populate` imports from the package-selected checkout.
Local package selection remains available through the package and template CLIs.

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

For a new imported subdataset, pass `--site-specific-url https://github.com/ORINOCO-Lite/psychoinformatics-site-specific.git` to `setup-upstream`.
Setup records its clone URL and configures the local child remote; repository creation and publication remain explicit.
