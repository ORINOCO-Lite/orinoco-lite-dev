# RDF comparison and future conversion work

Stage C review evidence, 22 September 2026, for maintainers of PR #170.
Retire this report after the conversion decisions are resolved; dependency declarations and Git remain authoritative.

## Implemented scope

Record preservation, RDF graph equality, original JSON representation, and website behavior are separate checks.
JSONL/YAML remains the primary record path.
RDF conversion is an optional diagnostic, not an approved lossless round-trip.

`dev records jsonl-to-rdf` calls the selected writer without the reader.
The selected pyclient already exposes a streaming `json2ttl` command: it emits one JSON-encoded Turtle document per record, using the same `FormatConverter.convert(data, target_class)` API.
It does not merge those documents into a graph.
Our wrapper retains the original Turtle files and uses PyOxigraph's existing `rename_blank_nodes=True` parser option for the standard RDF merge, producing one ordinary graph in `graph.nt`.
It adds no upstream graph identities or synthetic named graphs.

`dev rdf compare LEFT RIGHT --report DIRECTORY` composes released PyOxigraph 0.5.11 parsing and `Dataset.canonicalize(RDFC_1_0)` across each complete output.
The small `rdf_compare` module owns a subprocess boundary with a five-second deadline, including parsing and canonicalization.
It can be replaced without changing conversion or report consumers; no custom canonicalizer or backend registry is introduced.
Equality means RDF structure modulo blank-node renaming, with RDF term distinctions, named-graph boundaries, and shared blank-node identity preserved; there is no entailment reasoning.
Default graphs and blank graph names are supported.

Both selected PyOxigraph and RDFLib dataset loaders discard empty named graphs in a TriG probe.
RDFC-1.0 canonicalizes quads, which cannot encode that existence.
The TriG path therefore uses RDFLib's existing parser and sink interface to detect empty named graphs before native comparison; their presence produces **not evaluated**.
This is an inventory check, not another RDF parser or equality implementation.
It adds substantial cost for large TriG files, and is included in the deadline.
Turtle and N-Triples graph inputs and N-Quads dataset inputs do not need that additional pass.
Parser failures, unsupported input, and deadlines remain unevaluated; fresh output directories preserve earlier evidence.

`--by-record` adds a separate report comparing the original per-record Turtle documents where source and conversion digests match.
`--record PID` limits only that diagnostic.
It identifies changed emitted RDF and added/removed source records, retaining the source JSONL, conversion description, and original RDF documents for findings.
It does not attribute cause, compute minimal assertion edits, or decompose whole-output inequality: independent contributions can change while the combined graph stays equal.
Unavailable attribution leaves the complete result unchanged.
Reports use new comparator identities, so earlier partial record-container reports cannot be reused as whole-output evidence.

Sources: selected [streaming converter](https://github.com/ORINOCO-Lite/dump-things-pyclient/blob/1e79391195ad4412286344189dc5f81a06accb90/dump_things_pyclient/commands/json2ttl.py), [PyOxigraph parser options](https://pyoxigraph.readthedocs.io/en/stable/io.html), and selected [RDFLib TriG parser](https://github.com/RDFLib/rdflib/blob/7.6.0/rdflib/plugins/parsers/trig.py).

List findings retain raw order and every duplicate.
A typed JSON multiset summary distinguishes “same items, different order” from added/removed occurrences, retaining nested sequence order.
This classification does not approve order changes, normalize records, or declare a field unordered.
Author order and first-selected values remain relevant to the website.

## Measured alternatives

Bounded serial experiments used retained downloads, Python 3.12.13 and Node 22.23.2 on the maintainer's Mac; no live source was refreshed.
The pair contains 5,030 graphs and 142,865 quads per side, with 32,320 blank nodes and no cross-graph blank-node sharing.
These are individual measurements, not runtime guarantees.

| Implementation | Evidence | Integration and limits |
| --- | --- | --- |
| Selected RDFLib 7.6.0 and current main `b3e60e7` | Both exceeded 30 seconds on each of the two largest records (9,819 and 7,387 triples). | Existing graph APIs; no applicable configuration fix found. Profiling spent 29.95 seconds in initial refinement, before symmetry search. |
| PyOxigraph 0.5.11 RDFC-1.0 | Direct TriG full-pair parse 0.618 s, canonicalize 0.690 s, compare 0.051 s. Integrated per-record adapter: **1.79 s**, including process startup and all parsing/comparison; a copied full dataset with one controlled addition took **1.68 s** and identified the one changed graph. | One native wheel, locked for Linux and macOS. Five-second deadline bounds pathological cases. |
| Node `rdf-canonize` 5.0.0 + N3 2.7.12 | Full N-Quads pair 1.42 s, excluding TriG conversion. | Credible alternative; extra runtime/packages, work-factor configuration needed for a tiny cyclic control. |
| PyLD 3.3.0 URDNA2015 | Full N-Quads pair 14.2 s, excluding TriG conversion. | Correct tested dataset controls, slower; URDNA2015 is a different canonicalization algorithm. |
| Apache Jena | Not benchmarked; no JVM available. | `IsoMatcher` offers dataset comparison, unlike graph-only `rdfcompare`; higher integration cost without demonstrated benefit here. |

The complete-output implementation was also measured on the site repository's retained 5,030 records: each graph has 142,865 triples.
The equal pair took **2.00 s** including worker startup: parsing 0.863 s, canonicalization 0.907 s, and comparison 0.079 s.
The full CLI, including retained report artifacts, took **3.14 s**.
These results are close to a second for canonicalization, not a one-second end-to-end operation.
The former per-record TriG evidence exceeded the new five-second deadline during its additional inventory-check path; full CLI time was 6.15 s including failure reporting.
Whole-output comparison of a controlled title change completed and optional attribution identified its source record.
Copying all unchanged per-record documents made optional reports expensive; the implementation now copies original RDF documents only for findings, plus source JSONL and conversion descriptions.

Controls cover renamed blank nodes, reordered triples, changed literals, lexical integers (`01` versus `1`), language tags, plain versus explicit `xsd:string`, cyclic structures, ordered lists, duplicate list items, named-graph additions/removals, default graphs, blank graph names, and blank nodes shared across graphs. Separate attribution controls cover missing or edited metadata, selected records, additions/removals, and changes that cancel in the combined graph.
RDFLib's default literal normalization can erase lexical distinctions before comparison; native parsing avoids that in retained RDF comparison.
The upstream writer still uses its selected RDFLib behavior: this does not establish preservation from original JSON.

References: [PyOxigraph API](https://pyoxigraph.readthedocs.io/en/stable/model.html), [RDFC specification](https://www.w3.org/TR/rdf-canon/), [RDFLib comparator](https://github.com/RDFLib/rdflib/blob/b3e60e79c9b0b85d760832fb7bd4d0da3392bb76/rdflib/compare.py), [performance issue #2528](https://github.com/RDFLib/rdflib/issues/2528), [RDFC request #3557](https://github.com/RDFLib/rdflib/issues/3557), [rdf-canonize limits](https://github.com/digitalbazaar/rdf-canonize#complexity-control), [PyLD](https://github.com/digitalbazaar/pyld), [Jena dataset matcher](https://github.com/apache/jena/blob/509136074c4bd8b4771c08d20da4b2821fccdf37/jena-arq/src/main/java/org/apache/jena/sparql/util/IsoMatcher.java).
Store subtraction, SPARQL `MINUS`, serialization byte equality, and RDFLib's `similar` heuristic do not prove blank-node graph equality.

## Conversion findings and upstream resolution

The selected pyclient's Turtle extra resolves Dump Things Service 6.3.6 (`9f101d9`), which selects LinkML/Runtime 1.11.1; the active environment resolves RDFLib 7.6.0.
The selected Things Schema is `cb6c791`, including its recursive imports.

**Annotation representation.** Compact and expanded annotations produce isomorphic RDF.
The service's generated Pydantic model retains compact values, but its dataclass loader expands them through patched `_normalize_inlined` before RDF writing.
The reader reconstructs annotation objects and JSONDumper emits their expanded form.
RDF preserves the valid tag/value example but cannot recover which JSON shape was supplied, because both inputs map to the same graph. See the selected [converter](https://github.com/ORINOCO-Lite/dump-things-service/blob/9f101d97c7f15d491f602db5a9c33ad9a19ad8bf/dump_things_service/converter.py), [normalizer patch](https://github.com/ORINOCO-Lite/dump-things-service/blob/9f101d97c7f15d491f602db5a9c33ad9a19ad8bf/dump_things_service/patches/yamlutils.py), and [reader patch](https://github.com/ORINOCO-Lite/dump-things-service/blob/9f101d97c7f15d491f602db5a9c33ad9a19ad8bf/dump_things_service/patches/rdflib_loader.py).

An existing selected API, `ReferenceValidator.normalize_to_collection_form`, can expand then compact mixed annotation maps.
Direct SimpleDict slot normalization instead lost scalar entries in a mixed-map probe; whole-record normalization rejected `dlthings:Thing`, and full `expand_all` processing stringified annotation objects.
These functions remain unchanged at inspected main `b4c3261`.
Use a scoped upstream composition only after validating key/tag consistency and edge cases; do not introduce a parallel compactor or hide raw findings. Sources: [selected validator](https://github.com/linkml/linkml/blob/v1.11.1/packages/linkml_runtime/src/linkml_runtime/processing/referencevalidator.py), [current validator](https://github.com/linkml/linkml/blob/b4c3261fddcad14f0221ba980f6e84f9d88eb873/packages/linkml_runtime/src/linkml_runtime/processing/referencevalidator.py).

**Ordering and duplicates.** No induced slot in the selected schema closure declares `list_elements_ordered`.
The selected writer emits repeated predicate/object triples and the reader uses graph iteration order. `inlined_as_list` is a JSON container choice, not sequence semantics. Repeated URI values collapse into one triple, while separately allocated inline blank nodes can preserve repeated objects. The retained six-to-three `obo:NCIT_C19924.close_mappings` change merges CURIE/full-IRI spellings of three resources: JSON occurrences are lost without distinct RDF assertions being lost.
The [publication template](https://github.com/ORINOCO-Lite/www-from-model/blob/a2e4534bc38a6dc0f30effed354773f1da984a18/page_templates/publication.md.j2) consumes author order and first matching dates/identifiers, so absence of schema ordering cannot justify ignoring these sequences.

**Available versus pending.** LinkML [PR #3407](https://github.com/linkml/linkml/pull/3407), merged as `88afd7a`, adds a PyOxigraph canonical graph serializer, absent selected 1.11.1.
This is a useful future upstream replacement for applicable serialization work; it does not solve ordering or offer general dataset comparison.
Ordered-list [PR #3693](https://github.com/linkml/linkml/pull/3693), inspected at `b7ff88d`, remains unmerged and addresses writer, reader, and SHACL paths; [issue #3531](https://github.com/linkml/linkml/issues/3531) tracks the gap.
The service replaces reader methods, so a LinkML upgrade alone will not enable that implementation.
Current service 6.3.7 (`d65d9b0`) changes its version tag; relevant conversion files match selected 6.3.6.
No service or schema repin was justified by this investigation.

## Smallest next steps and unresolved checks

1. Keep the released native comparison and bounded failure behavior as optional diagnostics; retain JSONL/YAML for record preservation.
2. After ordered-list support lands, deliberately update LinkML, rebase or remove the service's reader patches, and have upstream declare order on semantically ordered schema fields.
   Test scalar/object sequences, duplicates, empty lists, and SHACL against the actual service before considering RDF round-trip use.
3. Reproduce and report upstream normalization defects separately; validate mixed forms, missing/empty values, conflicting keys, and nested annotations before using upstream compaction for presentation. Neither compaction nor ordered RDF reconstructs original compact/expanded shape or CURIE spelling.
4. Render controlled author-order and first-selected-value examples before approving any field-specific unordered comparison for website claims.
5. The full W3C canonicalization suite was not rerun locally; the selected native implementation and focused graph/dataset controls supply current coverage.
   Before adopting RDF 1.2 terms or empty named-graph equality, test an upstream implementation that explicitly represents them.
   For faster TriG comparison, first find or add an upstream parser inventory API that retains empty graph declarations; do not drop the check or flatten graphs to obtain a faster result.
