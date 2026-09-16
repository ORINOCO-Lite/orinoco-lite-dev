# Accepted native-versus-Lite differences

These rules apply to the same-capture [comparison](upstream-comparison.md).
Report their presence briefly.
Ask for review only when a difference exceeds its rule.

| Difference | Accepted scope | Revisit when |
| --- | --- | --- |
| Static editing | Lite record pages link to `/edit/` and include its callback route instead of the Pool editor. | A record links to the wrong editor input or editing stops working. |
| Build information | Lite adds package and source links in the footer. | It replaces upstream content rather than adding build information. |
| Mobile navigation | Lite includes the existing Collaboration hub link in the mobile menu. This is retained presentation debt. | The adaptation is removed or proposed upstream. |
| Outputs tooltip | Lite's desktop Outputs menu adds `title="Outputs"` to the same label and empty destination. This is retained presentation debt. | The label, destination, or tooltip changes. |
| Explore height | Lite's graph shortcode uses 55vh with a 320px minimum instead of the native full viewport. This is retained presentation debt. | The shortcode layout changes or graph controls become unusable. |
| HTML source formatting | Line wrapping may differ in ordinary paragraphs when rendered words, spacing, and links match. SiteDiff can still show these changes. | Rendered text changes, or whitespace affects code, preformatted text, scripts, or layout. |
| Generated graph identifiers | Edge IDs, order, and request cache suffixes may differ. Full node objects and counted source/target pairs must match. | Edges gain other fields, nodes differ, or relationship counts change. |
| Graph layout | Force-layout positions and visible labels may vary when graph data, filters, and navigation match. | A seeded browser check finds a behavioral difference. |

The [SiteDiff profile](../../tools/site-diff/psychoinformatics.yaml) accounts for the exact known HTML changes.
The default report shows other changes; the unfiltered report retains all changes.
The [repeat procedure](upstream-comparison.md#show-differences-that-need-review) checks the two expected extra editor pages and tests that the rules preserve meaningful differences.
Graph content and behavior still need their separate checks.

Shared upstream defects are not deployment differences.
Do not include them in this report or change source data to remove them.
Site-specific logos, copyright, favicons, authored content, and downloads must match the selected upstream inputs.
