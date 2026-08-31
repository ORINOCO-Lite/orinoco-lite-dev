# CURIE-only schema contract for the clean migration

Status: verified implementation guide

Date: 2026-08-11

## Conclusion

The clean migration does not need the LinkML discriminator trial or the later Things Schemas identity candidate.

The verified path uses the checked-out source schema at commit `cb6c791`, the released LinkML stack pinned below, and explicit `dlthings:*` CURIEs in record type designators.
That schema commit differs from the original `d26ea413` acceptance fixture only by declaring the `pav:` prefix; its classes and recursive structure are unchanged.
With that combination, native `Association`, `Attribution`, `Generation`, `DOI`, and `ISSN` values pass JSON to RDF to JSON conversion and live Dump Things validation.

Equivalent full-URI spellings are not supported by this contract.
Records must retain the CURIE spelling expected by the source schema and the downstream qri and template code.

## What the schema pin means

Orinoco Lite does not validate against whatever schema happens to be described by the latest upstream documentation.
It validates against one exact checkout of the schema sources together with one exact, tested set of conversion, validation, query, and presentation tools.
That complete selection is the **schema and runtime contract**.

“Things v1” alone is not a sufficient name for this contract because several independent versioning layers appear in the working system:

| Layer | Pinned selection | Meaning |
| --- | --- | --- |
| Schema source | Things Schemas commit `cb6c791aec4c5309775437df4bd58e94e1bfcc3c` | The exact schema files available to the build. Later upstream additions are absent until this Git pin is deliberately advanced. |
| Root composite | `src/demo-research-information/unreleased.yaml` | The application schema loaded by Dump Things. Its `unreleased` label is distinct from the versions of the modules it imports. |
| Imported modules | Components such as `things-prov/v1` and `things-publications/v1` | Version labels for individual schema modules, not a version of the complete ORINOCO stack. |
| Identifier namespace | `dlthings:` expands under `https://concepts.datalad.org/s/things/v2/` | The identity assigned to schema terms. It does not say that the build follows a moving “Things v2” release. |
| Runtime tuple | Dump Things, LinkML, LinkML Runtime, Pydantic, RDFLib, qri, graph, and template pins | The tools that must agree on validation, conversion, class selection, relationships, and presentation. |

This means that a new class, slot, mapping, constraint, or generated representation appearing upstream—or on the current documentation website—does not enter Orinoco Lite automatically.
The existing records continue to use the pinned source files, exact `dlthings:*` CURIE spellings, and tested runtime behavior.

Adopting an upstream change requires a deliberate compatibility update:

1. select an exact candidate schema commit and all affected tool versions;
2. review any metadata or semantic migration implied by that selection;
3. run the complete positive and negative conversion, validation, qri, graph, and template fixtures;
4. record the new immutable coordinates and evidence; and
5. advance the release pin only after that combination is reviewed as the next known-good contract.

This guide establishes that contract for Orinoco Lite.
It does not establish which exact schema/runtime tuple is deployed by every other ORINOCO installation.

## Verified runtime

The verified environment is:

| Component | Exact selection |
| --- | --- |
| Things Schemas | `cb6c791aec4c5309775437df4bd58e94e1bfcc3c` |
| Root schema | `src/demo-research-information/unreleased.yaml` |
| Dump Things | `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf` |
| Dump Things release | `6.3.6` |
| LinkML | `1.11.1` |
| LinkML Runtime | `1.11.1` |
| Pydantic | `2.13.4` |
| RDFLib | `7.6.0` |

The complete root-schema path is:

```text
submodules/things-schemas/
  src/demo-research-information/unreleased.yaml
```

The parent Pixi environment installs Dump Things from its pinned local submodule and locks the Python dependencies.
The service reads the schema YAML directly from the pinned Things Schemas checkout.

Things Schemas is not installed as a Python development package in this path.
Its install-time `tools/patch_linkml` process therefore does not modify the Pixi environment.
The Dump Things source and its runtime behavior at the pinned service commit are part of the verified combination.

## Record spelling contract

Use these exact values for `schema_type`:

| Native class | Required designator |
| --- | --- |
| Association | `dlthings:Association` |
| Attribution | `dlthings:Attribution` |
| Generation | `dlthings:Generation` |
| DOI | `dlthings:DOI` |
| ISSN | `dlthings:ISSN` |

For example:

```yaml
schema_type: dlthings:Association
```

Do not expand that value before validation, conversion, storage, or projection.

The source modules use `default_prefix: dlthings`.
The `dlthings` prefix maps to this namespace:

```text
https://concepts.datalad.org/s/things/v2/
```

The component files are named `things-prov/v1` and `things-publications/v1`.
Those module names, the root schema's `UNRELEASED` label, and the `/things/v2/` identifier namespace describe different layers.
They do not require a type designator to use a module-derived full URI.

## What was verified

Positive fixtures for all five native classes were exercised against the source schema and pinned runtime.
They pass both of the publication-relevant boundaries:

1. JSON is loaded, converted to RDF, and converted back to JSON without losing the intended native type.
2. The records pass validation through the live local Dump Things collection endpoint using the same pinned schema and package set.

This is the relevant evidence for the clean migration.
A Hugo build of already generated Markdown is not schema evidence because it does not load LinkML or Dump Things.

The downstream publication tools also favor one stable lexical form. qri class selection, graph dispatch, and existing templates compare type designators as strings.
Using the source-schema CURIEs from ingestion through projection avoids a second normalization layer.

## Full URIs remain unsupported

The CURIE contract does not promise that a full URI is interchangeable with its compact spelling.
For example, this value is outside the supported input contract:

```text
https://concepts.datalad.org/s/things/v2/Association
```

Module-derived values are also outside the contract:

```text
https://concepts.datalad.org/s/things-prov/v1/Association
https://concepts.datalad.org/s/things-publications/v1/DOI
```

Full-URI designators continue to fail the generated-model path at the pinned versions.
The clean migration should reject them rather than rewrite them implicitly.
An input migration should convert a known supported value to the required CURIE explicitly and review that semantic change.

Supporting full URIs later would be a separate compatibility feature.
It would need its own LinkML, Dump Things, qri, graph, and template tests.
It is not a prerequisite for the clean migration.

## Why the earlier diagnosis was wrong

The earlier CON candidate did not exercise the source schema above.
It used this vendored resolved schema:

```text
submodules/centerforopenneuroscience.org/
  metadata/schema/demo-research-information.static.yaml
```

That generated artifact flattened the imports and added explicit expanded `class_uri` values.
For the affected classes it used module-derived identities such as:

```text
https://concepts.datalad.org/s/things-prov/v1/Association
https://concepts.datalad.org/s/things-prov/v1/Attribution
https://concepts.datalad.org/s/things-prov/v1/Generation
https://concepts.datalad.org/s/things-publications/v1/DOI
https://concepts.datalad.org/s/things-publications/v1/ISSN
```

Those expanded identities changed the generated type-designator behavior.
The resulting failures demonstrated a problem with the resolved artifact and full-URI path, not a failure of the source schema's `dlthings:*` CURIE path.

The previous synthetic reproducer also declared an explicit full class URI.
It remains useful evidence that the full-URI path is unsupported, but it does not model the verified CURIE-only publication contract.

Claims that no single designator works at these released package versions are therefore superseded.
The verified source-schema CURIEs work without the proposed LinkML changes.

## Explicitly excluded work

Do not merge, cherry-pick, install, or otherwise depend on the separate LinkML discriminator trial.
This exclusion includes every commit from the parent trial branch:

```text
codex/linkml-discriminator-trial
```

It also excludes any local composite of proposed LinkML pull-request heads.

The clean migration does not use proposed LinkML changes for:

- full-URI subclass dispatch;
- CURIE/full-URI equivalence in generated JSON Schema;
- URI compaction fallback; or
- cross-generator compliance for explicit full class URIs.

Do not adopt the later Things Schemas candidate that adds explicit `class_uri` declarations for the five classes.
In particular, commit `33604b1a` and its prerequisite candidate commits are outside the clean-migration dependency set.

The original clean-migration evidence used `d26ea413`.
Contract 2 deliberately advances to `cb6c791`, whose only change is the reviewed `pav:` prefix declaration required for upstream-aligned provenance.
The release must not advance that pin indirectly while updating another submodule or regenerating a resolved schema.

## Build and test rules

The implementation should preserve these rules:

1. Read the source root schema from the pinned Things Schemas checkout.
2. Store the five native designators as the exact `dlthings:*` CURIEs above.
3. Do not use the vendored resolved static schema as a validation input.
4. Do not normalize supported CURIEs to full URIs between service and qri.
5. Keep Dump Things, LinkML, LinkML Runtime, Pydantic, and RDFLib locked as one tested environment.
6. Retain positive JSON-to-RDF-to-JSON and live-validation fixtures for all five classes.
7. Retain negative fixtures showing that full-URI designators are outside the supported contract.
8. Re-run the entire fixture set before changing any schema or package pin.

The static deployment remains a generated projection and requires no continuously running metadata service.
Dump Things may start ephemerally for validation and projection, then stop before the Hugo artifact is deployed.

## Recursive model-generation compatibility

The source schema's inheritance graph is acyclic.
It has 82 classes, 98 inheritance edges, and a maximum inheritance depth of five.
Nevertheless, the pinned LinkML Pydantic generator needs more than Python's default recursion limit while executing its generated module.

This is a generator/runtime interaction, not a cycle in the schema.
LinkML expands the inlined, type-designated `Thing.relations` range into a union of `Thing` and all 48 descendants.
That wide recursive union is repeated on the descendant models.
Serialization and Python compilation succeed, but Pydantic 2.13.4 exhausts the default stack while `Thing.model_rebuild()` constructs the recursive core schema.
The same failure occurs with LinkML directly, before loading Dump Things patches.
Authoritative upstream Dump Things has carried its own workaround since commit `b748d8a`: it catches the failure, raises the process-wide recursion limit in increments of 1,000, and retries.
Dump Things 6.3.6 therefore succeeds at 2,000 for this schema but leaves the higher process-wide limit in place.

Orinoco contains that existing fallback at the integration boundary.
It builds the paired JSON/RDF converters under a lock with a temporary limit of 2,000, then restores the caller's exact prior limit on success or failure.
This keeps the pinned schema and validation semantics unchanged, avoids a warning during normal builds, and prevents a dependency workaround from leaking global process state.

The durable upstream fix belongs in LinkML's Pydantic generator.
A named recursive type alias (`TypeAliasType`) for the shared descendant union lets Pydantic compile this schema at the default limit; a plain assignment alias or an added discriminator does not.
Until an upstream release carries and tests that representation, the narrow Orinoco compatibility boundary remains part of the locked runtime contract.

## Evidence boundaries

This guide establishes the tested local clean-migration contract.
It does not claim that:

- full URIs work as type designators;
- CURIE and full-URI spellings are accepted interchangeably;
- the German production pool uses this exact package set;
- a resolved static schema is equivalent to its source imports;
- the excluded LinkML or Things Schemas candidates are incorrect for other use cases; or
- a successful static Hugo build proves metadata validation.

Within those boundaries, the implementation choice is simple: use the pinned source schema, keep explicit `dlthings:*` CURIEs, and leave the experimental LinkML and schema-remediation branches out of the clean migration.
