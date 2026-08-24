import { describe, expect, it, vi } from "vitest";
import { renderEditorPage } from "../functions/lib/editor-page";
import type { ExactHeadEditorInput } from "../functions/lib/editor-input";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env } from "../functions/lib/pages";

const DIGEST = "d".repeat(64);
const HEAD = "a".repeat(40);
const INDEX = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <script type="module" crossorigin src="./assets/index-ABC123.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-ABC123.css">
  </head>
  <body><div id="app"></div></body>
</html>
`;

function input(unsafe = false): ExactHeadEditorInput {
  const text = unsafe
    ? '</script><script id="injected">globalThis.injected = true</script>'
    : "<urn:example> a <urn:Thing> .\n";
  return {
    artifactId: 123,
    files: {
      "edit/config.json": new TextEncoder().encode(
        JSON.stringify({ app_name: text }),
      ),
      "edit/data/record-sources.json": new TextEncoder().encode(
        JSON.stringify({
          format: "orinoco-static-record-sources",
          records: [],
          source_commit: HEAD,
          version: 2,
        }),
      ),
      "edit/records.ttl": new TextEncoder().encode(text),
    },
    headSha: HEAD,
    sourceCommit: HEAD,
    workflowRunId: 456,
  };
}

function environment(
  assets: (request: Request) => Promise<Response> = async () =>
    new Response(INDEX, {
      headers: {
        "Content-Length": String(new TextEncoder().encode(INDEX).byteLength),
        "Content-Type": "text/html; charset=utf-8",
      },
    }),
): Env {
  return {
    ASSETS: { fetch: vi.fn(assets) },
    EDITOR_RUNTIME_MANIFEST_SHA256: DIGEST,
    GITHUB_CLIENT_ID: "Iv1.example",
    GITHUB_CLIENT_SECRET: "secret",
    PUBLIC_ORIGIN: "https://review.example",
    SESSION_SEAL_KEY: base64urlEncode(new Uint8Array(32).fill(7)),
  };
}

describe("exact-head SHACL Vue page rendering", () => {
  it("loads the immutable runtime coordinate and injects data before released assets", async () => {
    const env = environment();
    const response = await renderEditorPage(
      env,
      "https://review.example/api/shacl/editor?repository=example%2Fsite",
      "example/site",
      input(),
    );
    const assets = vi.mocked(env.ASSETS?.fetch);
    const request = assets?.mock.calls[0]?.[0];
    expect(request).toBeInstanceOf(Request);
    expect((request as Request).url).toBe(
      `https://review.example/editor-runtime/${DIGEST}/index.html`,
    );
    expect((request as Request).headers.get("cookie")).toBeNull();
    expect((request as Request).headers.get("authorization")).toBeNull();

    const html = await response.text();
    const base = `<base href="/editor-runtime/${DIGEST}/">`;
    expect(html.indexOf(base)).toBeGreaterThan(0);
    expect(html.indexOf(base)).toBeLessThan(html.indexOf("./assets/"));
    expect(html).toContain('"config.json"');
    expect(html).toContain('"data/record-sources.json"');
    expect(html).toContain('"records.ttl"');
    expect(html).toContain('"config_default_xyzri.yaml"');
    expect(html).toContain('"dlschemas_owl.ttl"');
    expect(html).toContain('"dlschemas_shacl.ttl"');
    expect(html).toContain("Object.hasOwn(encoded, relative)");
    expect(html).toContain('format: "orinoco-lite-shacl-bundle-message-v1"');
    expect(html).toContain('repository: "example/site"');
    expect(html).toContain("window.parent.postMessage");
    expect(html).toContain("window.location.origin");

    const policy = response.headers.get("content-security-policy") ?? "";
    const nonce = policy.match(/'nonce-([A-Za-z0-9_-]+)'/)?.[1];
    expect(nonce).toBeTruthy();
    expect(html).toContain(`<script nonce="${nonce}">`);
    expect(policy).toContain("frame-ancestors 'self'");
    expect(policy).not.toContain("frame-ancestors 'none'");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("x-frame-options")).toBe("SAMEORIGIN");
  });

  it("base64-encodes untrusted editor input instead of creating HTML", async () => {
    const response = await renderEditorPage(
      environment(),
      "https://review.example/api/shacl/editor?repository=example%2Fsite",
      "example/site",
      input(true),
    );
    const html = await response.text();
    expect(html).not.toContain('<script id="injected">');
    expect(html).not.toContain("globalThis.injected = true");
    expect(html.match(/<script\b/g)).toHaveLength(2);
  });

  it("rejects a missing coordinate, oversized index, and ambiguous shell shape", async () => {
    const missing = environment();
    delete missing.EDITOR_RUNTIME_MANIFEST_SHA256;
    await expect(
      renderEditorPage(
        missing,
        "https://review.example/api/shacl/editor",
        "example/site",
        input(),
      ),
    ).rejects.toMatchObject({ code: "configuration_error", status: 500 });

    await expect(
      renderEditorPage(
        environment(
          async () =>
            new Response("x", {
              headers: {
                "Content-Length": "262145",
                "Content-Type": "text/html",
              },
            }),
        ),
        "https://review.example/api/shacl/editor",
        "example/site",
        input(),
      ),
    ).rejects.toThrow("too large");

    const ambiguous = INDEX.replace("<head>", '<head><base href="/bad/">');
    await expect(
      renderEditorPage(
        environment(
          async () =>
            new Response(ambiguous, {
              headers: { "Content-Type": "text/html" },
            }),
        ),
        "https://review.example/api/shacl/editor",
        "example/site",
        input(),
      ),
    ).rejects.toThrow("invalid shape");
  });
});
