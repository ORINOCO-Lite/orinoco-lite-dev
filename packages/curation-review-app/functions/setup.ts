import { withApiHeaders } from "./lib/http";

/** GitHub App post-install instructions; installation itself enables no operations. */
export function onRequest(): Response {
  return withApiHeaders(
    new Response(
      `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Choose Orinoco Lite operations</title></head><body>
<main><h1>Choose permitted operations</h1>
<p>The App installation grants GitHub permissions. Automated operations remain disabled until you enable them for each website repository.</p>
<p>Edit the root <code>pyproject.toml</code> on your repository's default branch. Add the table below, or edit it if it already exists. Set only the operations you want to <code>true</code>.</p>
<pre>[tool.orinoco.operations]
shacl_materialization = false
automated_curation = false
template_updates = false
preview_editing = false</pre>
<ul>
<li><strong>SHACL materialization:</strong> turn editor proposals into metadata commits. Uses Actions read, Contents write, and Pull requests read.</li>
<li><strong>Automated curation:</strong> publish completed source-adapter proposals. Uses Actions read, Contents write, and Pull requests write.</li>
<li><strong>Template updates:</strong> open draft update pull requests, including workflow changes. Uses Actions read, Contents write, Pull requests write, and Workflows write.</li>
<li><strong>Preview editing:</strong> allow edits from verified development previews. Uses Commit statuses read in addition to edit permissions.</li>
</ul>
<p>GitHub grants the App's requested permissions together. These choices control how Orinoco uses them; they do not remove GitHub grants. Missing choices stay disabled. An update or proposal branch cannot enable itself.</p>
<p>The central service is the default. For an independently deployed service, set its HTTPS origin:</p>
<pre>[tool.orinoco.service]
url = "https://curation.example.org"</pre>
<p>See the <a href="https://github.com/ORINOCO-Lite/orinoco-lite-dev/blob/main/docs/agents/contract/curation-service-authentication-options.md#functionality-and-permissions">operation and permission specification</a> for the complete requirements.</p>
<p>Return to your website editor or GitHub Actions after saving your choices.</p>
</main></body></html>`,
      { headers: { "Content-Type": "text/html; charset=utf-8" } },
    ),
  );
}
