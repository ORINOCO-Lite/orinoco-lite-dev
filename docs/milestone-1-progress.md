# Milestone 1 progress

Status: complete
Completed: 2026-07-31

The CON vertical slice is implemented at
`2c4f7e5a19d8ade7aee25ef1e8dc786bfdb3a577` on `orinoco-lite`.

- Preview: <https://leej3.github.io/centerforopenneuroscience.org/>
- Successful Pages run: <https://github.com/leej3/centerforopenneuroscience.org/actions/runs/30664229176>
- Draft review PR: <https://github.com/con/centerforopenneuroscience.org/pull/84>
- Candidate fork branch: <https://github.com/leej3/centerforopenneuroscience.org/tree/orinoco-lite>

## Exit criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| A canonical change deterministically changes the preview | Met | `scripts/test-milestone.sh` builds a baseline and byte-identical repeat, then mutates the canonical DataLad title and verifies that its rendered page changes. |
| Selected records validate through upstream Orinoco | Met | Five records pass the pinned Dump Things 6.3.6 collection endpoint. |
| Invalid records stop publication | Met | Negative schema and dangling-relationship fixtures are both rejected before Hugo runs. |
| No persistent metadata service is required | Met | `scripts/build.sh` starts the pinned service on localhost, validates, projects, and always stops it with a cleanup trap. The deployed result is static. |
| The connected slice and representative assets are visible | Met | The organization, person, project, publication, software output, 11 checked relationships, CON/DataLad branding, and selected person depiction are published. |
| Candidate files plus pinned dependencies are sufficient | Met | Python packages are locked in `uv.lock`; Orinoco repositories, the schema snapshot, Hugo, Congo, and workflow actions are pinned by commit, version, or checksum. |
| CON-specific and reusable work remain distinguishable | Met | `UPSTREAM.md`, `provenance/adopted-files.yaml`, and `provenance/schema-compatibility.yaml` record exact adoption and downstream boundaries. No broad upstream fix is claimed. |
| Production remains unchanged | Met | `origin/master` remains `e6e9200a0987a65097afff896105ff838be1659e`; no production `CNAME`, DNS, domain, or deployment setting was changed. |

## Execution sequence

1. **Hydrate and preserve the legacy site — complete.** The Git history and
   local/origin `git-annex` refs report zero missing Git objects. `legacy-site`
   and annotated tag `legacy-site-2026-07-31` both peel to
   `e6e9200a0987a65097afff896105ff838be1659e` locally and on the writable fork.
   The selected Yaroslav image had no annex copies; it was recovered from the
   deployed legacy site, matched the annex key's MD5 and size, and is now a
   normal Git object with provenance recorded.
2. **Create the candidate branch and review boundary — complete.** `orinoco-lite`
   descends from the CON `master` history, is published to the `leej3` fork,
   and is the head of draft PR #84. The production branch was not moved.
3. **Capture the deployed baseline — complete.** `provenance/legacy/` contains
   pinned HTML and 1280x720 screenshots for the homepage, DataLad project, and
   Yaroslav profile, plus public URL and design-value inventories.
4. **Identify upstream inputs — complete.** The adopted collection shape,
   templates, scripts, qri entry points, and exclusions are recorded against
   the reviewed `www-from-model` revision in `UPSTREAM.md` and
   `provenance/adopted-files.yaml`.
5. **Import minimum scaffold — complete.** Focused commits add Hugo, Congo,
   qri projection, and build scaffolding without merging or grafting upstream
   history.
6. **Select reviewed CON records — complete.** The slice is sourced from
   `con/dump-research-info` commit
   `1c7e99ec6f296d5e6cb6a61e3b786227190802da`; selection, omissions, and
   evidence are recorded in `provenance/metadata-selection.yaml`.
7. **Create canonical YAML — complete.** Individual records under
   `metadata/records/` represent CON (`ror:04tfhh831`), Yaroslav O. Halchenko,
   DataLad, the DataLad JOSS publication (`10.21105/joss.03262`), and a DataLad
   software output.
8. **Preserve content, assets, URLs, and design — complete.** The prototype
   retains representative editorial copy, the CON and DataLad marks, the
   recovered person image, Open Sans/Source Code Pro, legacy blue values,
   `/projects`, `/whoweare`, `/engage`, and `/support` compatibility paths,
   legacy anchors, and the CON favicon.
9. **Run Dump Things ephemerally — complete.** Validation uses the upstream
   service at pinned commit `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf`
   and never requires a continuously running service.
10. **Project with qri and build with Hugo — complete.** Validated records are
    copied into a transient collection, streamed through qri as generated
    JSONL, adapted to explicit stable page paths, and rendered by Hugo 0.154.5
    with Congo v2.13.0.
11. **Publish a fork Pages preview — complete.** A repository-local workflow
    with immutable action pins builds the combined candidate tree. GitHub Pages
    is enabled only on the fork, with `orinoco-lite` permitted by its preview
    environment; run 30664229176 built and deployed successfully.
12. **Record divergence — complete.** Toolchain, adoption, metadata decisions,
    legacy assets, and the temporary schema/API compatibility workaround are
    versioned under `provenance/`.

## Acceptance evidence

The final local contract and the fork workflow ran at the same candidate commit.

- 5 of 5 canonical records accepted by Dump Things
- 0 validation failures
- invalid-schema record rejected as expected
- invalid relationship target rejected as expected
- 11 relationships checked across one connected five-record component
- 20 Hugo pages, 8 compatibility paths, 6 required assets, and 39 site files
- 524 internal links checked at a repository Pages base path
- CON web manifest and relative SVG icon checked
- repeat build byte-identical to the baseline
- canonical DataLad mutation changed the generated project page
- homepage, project, person, manifest, and favicon returned HTTP 200 from the
  deployed preview; the deployed homepage was also inspected visually

Implementation commits after the provenance baseline are:

- `f803157` — adopt the upstream Hugo scaffold
- `35f2b40` — add the reviewed DataLad metadata slice
- `596d267` — add the pinned ephemeral publication pipeline
- `39d8862` — preserve the legacy comparison baseline
- `d7fdcb8` — publish the fork Pages preview
- `2c4f7e5` — preserve CON branding under Pages base paths

## Pinned boundaries

- Clean `www-from-model` mirror: local `main`, `origin/main`, and
  `upstream/main` all remain at
  `6945272e5f3fcf353627b8e1c3e68bcaf76cc2ce` with no local changes.
- Dump Things service: `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf`
  (6.3.6)
- qri/query-things: `ef1141430a471455d4a5f4e07d7989ec717f56f4`
- Dump Things Python client: `1e79391195ad4412286344189dc5f81a06accb90`
- schema: things-schemas
  `d26ea4135e28c25b134c64de1cdc15d15cd2f9f0`, vendored snapshot SHA-256
  `c21bb112d2275e0fcf3d68094c343005040ad59a26724917b3549e537e60968e`
- Python environment: uv 0.7.19 with 137 locked packages; CI uses Python 3.12
- static site: Hugo 0.154.5 extended and Congo v2.13.0 at
  `3623fa505ee42fee899844d94a4ff7f5a1ae9096`

## Known temporary divergence

The pinned Dump Things generated API and its internal LinkML loader do not
accept a common type discriminator for native `Association`, `Attribution`,
`Generation`, `DOI`, and `ISSN` records. Milestone 1 therefore preserves the
reviewed target PIDs in string-valued `dlthings:AttributeSpecification`
relationships and generic identifiers. `scripts/check_relationships.py`
enforces target existence, expected class, reciprocal links, connectivity, and
DOI/ISSN formats; the projection interprets only the fixed reviewed predicates.

This loses machine-readable lead/author roles and native graph-edge semantics.
The exact probes, losses, and removal condition are recorded in
`provenance/schema-compatibility.yaml`. Native qualified relationships and
typed identifiers must be restored before the complete migration once a tested
schema/service/toolchain combination round-trips them through Dump Things and
qri.

## Deferred scope

Milestone 2 and later retain the full CON metadata migration, production
cutover and DNS, pixel-level completion, action/template extraction, reusable
workflow generalization, graphical editing, published RDF/JSONL contracts,
secondary projections, and broad submodule or upstream refactoring.
