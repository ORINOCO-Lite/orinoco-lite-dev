---
name: explain-orinoco-system
description: Create or revise high-level ORINOCO and Orinoco Lite system diagrams that help readers understand the components, released adaptation, downstream GitHub curation loop, and generated representations. Use for architecture overviews, system-organization diagrams, and diagram-label reviews; do not use for detailed protocols, repository maintenance, or decorative illustrations.
---

# Explain the ORINOCO System

Build a reader's mental model of the system, not an inventory of implementation facts.
Show the few components, artifacts, and interactions needed to explain how metadata becomes a graph and other representations, how Orinoco Lite adapts that machinery, and how a downstream uses it.

## Preserve the explanatory model

Keep these three levels distinct:

1. **ORINOCO component ecosystem** provides interoperating components for creating, editing, validating, converting, querying, and presenting metadata.
2. **Orinoco Lite release** combines exact versions of selected ORINOCO components with a thin adaptation for GitHub-based curation and static-site construction.
3. **Downstream GitHub repository** uses pull requests and GitHub Actions to change its metadata and regenerate its graph, website data, and static site.

Do not present source repositories, the Orinoco Lite package, build operations, and generated outputs as peers.
Use a boundary or transition when the diagram moves between those levels.

Exclude facts that do not help explain a component or interaction.
Terms such as *owned*, *trusted*, *human-curated*, *provenance-tracked*, and *byte-identical* do not belong in the system overview unless the user's question specifically concerns that property.
Keep maintenance-only mechanisms out of the operating view.

## Choose one viewpoint

Before drawing, state in one sentence what the reader should understand after seeing the diagram.
Choose the smallest structure that answers that question:

- use a flowchart for transformations and operating loops;
- use nested boundaries for composition or containment; and
- use a sequence diagram only when event order is the subject.

Keep one dominant reading path.
Add a branch only when it explains a materially different input, output, or interaction.

## Use a consistent label grammar

Treat boxes and arrows as parts of sentences:

- Boxes use concise noun phrases naming a component, artifact, interface, or system level.
- Arrows use active verb phrases such as `creates`, `validates`, `opens`, `updates`, `generates`, or `publishes`.
- Reading `source box → arrow label → target box` should form a grammatical and accurate statement.

Prefer one line per box.
When a second line is essential, make its relationship explicit with one consistent qualifier among peer boxes, such as `Components:`, `Includes:`, `Provides:`, or `Routes:`.
Do not use punctuation such as `·`, `/`, `+`, commas, or line breaks to imply an unstated relationship between unrelated fragments.
Use `/` only where it is literal, such as `/edit/`.

Do not combine an operation and an unexplained component list in one label.
For example, replace `Query and project / query-things · www-from-model` with either a component box named `Projection components` whose second line begins `Components:`, or separate component and artifact boxes connected by a verb-labeled arrow.

Use parallel wording for peers:

- component boxes name component categories;
- artifact boxes name the material being transformed or produced;
- interfaces name the operation surface; and
- boundaries name the containing system or release.

## Draft before implementation

For a new or substantially revised diagram:

1. List the intended boxes by kind: component, artifact, interface, or boundary.
2. Write every edge as a plain-English sentence.
3. Remove any box that does not participate in one of those sentences.
4. Check that adjacent boxes use the same abstraction level.
5. Present the proposed labels and relationships in text when the user wants review before modification.

Do not edit the diagram until that requested review is complete.

## Verify the rendered result

After implementation:

1. Format the containing document with its normal project formatter.
2. Parse every changed Mermaid block with an available Mermaid renderer.
3. Inspect the rendered image, not only the source.
4. Check reading order, wrapping, edge crossings, boundary meaning, and whether each arrow forms a sentence with its endpoints.
5. Remove unsupported HTML and presentation tricks that obscure the label grammar.

If no renderer is available, report that limitation rather than claiming the diagram renders correctly.
