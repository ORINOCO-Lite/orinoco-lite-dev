import { createRequire } from "node:module";
import { describe, expect, it, vi } from "vitest";
import { onRequest as transport } from "../functions/api/transport";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env, EventContext } from "../functions/lib/pages";

const { JSDOM, VirtualConsole } = createRequire(import.meta.url)("jsdom") as {
  JSDOM: new (
    html: string,
    options: Record<string, unknown>,
  ) => { window: Window & typeof globalThis };
  VirtualConsole: new () => unknown;
};

const ORIGIN = "https://review.example";
const CLIENT_ORIGIN = "https://site.example";
const NONCE = "a".repeat(64);
const env: Env = {
  GITHUB_CLIENT_ID: "Iv1.example",
  GITHUB_CLIENT_SECRET: "client-secret",
  PUBLIC_ORIGIN: ORIGIN,
  SESSION_SEAL_KEY: base64urlEncode(new Uint8Array(32).fill(7)),
};

function context(request: Request): EventContext {
  return {
    data: {},
    env,
    functionPath: "",
    next: async () => new Response(null, { status: 204 }),
    params: {},
    passThroughOnException: () => undefined,
    request,
    waitUntil: () => undefined,
  };
}

function reviewUrl(): string {
  const url = new URL("/api/transport", ORIGIN);
  url.searchParams.set("kind", "review");
  url.searchParams.set("artifact_id", "123");
  url.searchParams.set("handoff_nonce", NONCE);
  url.searchParams.set("pull_request", "42");
  url.searchParams.set("repository", "example/site");
  url.searchParams.set("review_origin", CLIENT_ORIGIN);
  return url.toString();
}

function shaclUrl(): string {
  const url = new URL("/api/transport", ORIGIN);
  url.searchParams.set("kind", "shacl");
  url.searchParams.set("repository", "example/site");
  url.searchParams.set("editor_origin", CLIENT_ORIGIN);
  url.searchParams.set("handoff_nonce", NONCE);
  return url.toString();
}

function reviewUrlWithOrigin(origin: string): string {
  const url = new URL(reviewUrl());
  url.searchParams.set("review_origin", origin);
  return url.toString();
}

describe("minimal downstream OAuth transport", () => {
  it.each([
    ["source-review", reviewUrl()],
    ["SHACL", shaclUrl()],
  ])("serves a CSP-nonced API transport for %s", async (_label, url) => {
    const response = await transport(context(new Request(url)));
    const html = await response.text();
    const policy = response.headers.get("content-security-policy") ?? "";
    const policyNonce = policy.match(/script-src 'nonce-([^']+)'/)?.[1];
    const documentNonce = html.match(/<script nonce="([^"]+)">/)?.[1];

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("cross-origin-opener-policy")).toBe(
      "unsafe-none",
    );
    expect(response.headers.get("cross-origin-resource-policy")).toBe(
      "same-origin",
    );
    expect(response.headers.get("x-frame-options")).toBe("DENY");
    expect(policy).toContain("default-src 'none'");
    expect(policy).toContain("connect-src 'self'");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).not.toContain("'unsafe-inline'");
    expect(policyNonce).toBeTruthy();
    expect(documentNonce).toBe(policyNonce);
    expect(html.match(/<script\b/g)).toHaveLength(1);
    expect(html).toContain("const source = window.opener;");
    expect(html).toContain("event.source !== source");
    expect(html).toContain("event.origin !== target.client_origin");
    expect(html).toContain('credentials: "same-origin"');
    expect(html).not.toMatch(/<(?:button|form|input|textarea)\b/i);
    expect(html).not.toContain("Download bundle");
    expect(html).not.toContain("Confirm and");
  });

  it.each([
    [
      "wrong service origin",
      reviewUrl().replace(ORIGIN, "https://other.example"),
    ],
    ["unexpected field", `${reviewUrl()}&extra=value`],
    ["duplicate kind", `${reviewUrl()}&kind=review`],
    ["unsafe client origin", reviewUrlWithOrigin("http://site.example")],
  ])("rejects %s before emitting HTML", async (_label, url) => {
    await expect(transport(context(new Request(url)))).rejects.toMatchObject({
      status: 400,
    });
  });

  it("accepts GET only", async () => {
    await expect(
      transport(context(new Request(reviewUrl(), { method: "POST" }))),
    ).rejects.toMatchObject({ code: "method_not_allowed", status: 405 });
  });

  it("executes the SHACL protocol with exact opener, nonce, grant, and CSRF binding", async () => {
    const url = shaclUrl();
    const response = await transport(context(new Request(url)));
    const opener = {
      closed: false,
      postMessage: vi.fn(),
    };
    const result = {
      commit_sha: "b".repeat(40),
      commit_url: `https://github.com/example/site/commit/${"b".repeat(40)}`,
      pull_request: 43,
      pull_request_url: "https://github.com/example/site/pull/43",
    };
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/session") {
          return Response.json({
            authenticated: true,
            csrf_token: "csrf-token",
            login: "octocat",
            review_grant: null,
            shacl_grant: {
              editor_origin: CLIENT_ORIGIN,
              expected_head_sha: null,
              handoff_nonce: NONCE,
              pull_request: null,
              repository: "example/site",
            },
          });
        }
        if (String(input) === "/api/shacl/propose") {
          expect(init).toMatchObject({
            credentials: "same-origin",
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
              "X-CSRF-Token": "csrf-token",
            },
            method: "POST",
          });
          return Response.json(result, { status: 201 });
        }
        throw new Error(`Unexpected transport request: ${String(input)}`);
      },
    );
    const virtualConsole = new VirtualConsole();
    const dom = new JSDOM(await response.text(), {
      beforeParse(window: Window & typeof globalThis) {
        Object.defineProperty(window, "opener", { value: opener });
        window.fetch = fetchMock as unknown as typeof window.fetch;
      },
      runScripts: "dangerously",
      url,
      virtualConsole,
    });

    await vi.waitFor(() =>
      expect(opener.postMessage).toHaveBeenCalledWith(
        {
          format: "orinoco-lite-shacl-proposal-ready-v1",
          handoff_nonce: NONCE,
          repository: "example/site",
        },
        CLIENT_ORIGIN,
      ),
    );

    const proposal = {
      bundle: {
        format: "orinoco-shacl-review-bundle",
        records: [],
        source_commit: "a".repeat(40),
        version: 2,
      },
      format: "orinoco-lite-shacl-proposal-v1",
      repository: "example/site",
      target: { kind: "standalone" },
    };
    const wrong = new dom.window.Event("message");
    Object.defineProperties(wrong, {
      data: {
        value: {
          format: "orinoco-lite-shacl-proposal-message-v1",
          handoff_nonce: NONCE,
          proposal,
          repository: "example/site",
        },
      },
      origin: { value: "https://attacker.example" },
      source: { value: opener },
    });
    dom.window.dispatchEvent(wrong);
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const message = new dom.window.Event("message");
    Object.defineProperties(message, {
      data: {
        value: {
          format: "orinoco-lite-shacl-proposal-message-v1",
          handoff_nonce: NONCE,
          proposal,
          repository: "example/site",
        },
      },
      origin: { value: CLIENT_ORIGIN },
      source: { value: opener },
    });
    dom.window.dispatchEvent(message);

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(opener.postMessage).toHaveBeenCalledWith(
      {
        format: "orinoco-lite-shacl-proposal-started-v1",
        handoff_nonce: NONCE,
        repository: "example/site",
      },
      CLIENT_ORIGIN,
    );
    await vi.waitFor(() =>
      expect(opener.postMessage).toHaveBeenCalledWith(
        {
          error: null,
          format: "orinoco-lite-shacl-proposal-result-v1",
          handoff_nonce: NONCE,
          repository: "example/site",
          result,
          retry_safe: false,
        },
        CLIENT_ORIGIN,
      ),
    );
    dom.window.close();
  });
});
