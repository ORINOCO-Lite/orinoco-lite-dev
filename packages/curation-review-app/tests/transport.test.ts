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
    expect(html).not.toContain("window.close()");
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

  it("delivers credentials only to the bound opener and never accepts a bundle", async () => {
    const url = shaclUrl();
    const response = await transport(context(new Request(url)));
    const opener = { closed: false, postMessage: vi.fn() };
    const credential = {
      token: "scoped-fixture-token",
      expires_at: "2999-01-01T00:00:00Z",
    };
    const fetchMock = vi.fn(
      async (path: RequestInfo | URL, init?: RequestInit) => {
        if (String(path) === "/api/session")
          return Response.json({
            authenticated: true,
            csrf_token: "csrf-token",
            login: "alice",
            review_grant: null,
            shacl_grant: {
              editor_origin: CLIENT_ORIGIN,
              expected_head_sha: null,
              handoff_nonce: NONCE,
              pull_request: null,
              repository: "example/site",
            },
          });
        expect(init).toMatchObject({
          credentials: "same-origin",
          method: "POST",
          headers: {
            "X-CSRF-Token": "csrf-token",
            "Content-Type": "application/json",
          },
        });
        if (String(path) === "/api/auth/credentials")
          return Response.json({ credentials: { "example/site": credential } });
        if (String(path) === "/api/auth/authorize-submission")
          return Response.json({ authorization: "signed-input" });
        if (String(path) === "/api/auth/revoke")
          return Response.json({ revoked: true });
        throw new Error("Unexpected request: " + String(path));
      },
    );
    const dom = new JSDOM(await response.text(), {
      beforeParse(window: Window & typeof globalThis) {
        Object.defineProperty(window, "opener", { value: opener });
        window.fetch = fetchMock as typeof window.fetch;
      },
      runScripts: "dangerously",
      url,
      virtualConsole: new VirtualConsole(),
    });
    await vi.waitFor(() =>
      expect(opener.postMessage).toHaveBeenCalledWith(
        {
          format: "orinoco-authentication-ready-v1",
          handoff_nonce: NONCE,
          repository: "example/site",
          login: "alice",
        },
        CLIENT_ORIGIN,
      ),
    );
    const message = {
      format: "orinoco-authentication-request-v1",
      handoff_nonce: NONCE,
      repository: "example/site",
      id: "a".repeat(32),
      method: "credentials",
      input: { source_commit: "b".repeat(40) },
    };
    const send = (data: unknown, origin = CLIENT_ORIGIN, source = opener) =>
      dom.window.dispatchEvent(
        new dom.window.MessageEvent("message", {
          data,
          origin,
          source: source as unknown as Window,
        }),
      );
    send(message, "https://unrelated.example");
    send(message, CLIENT_ORIGIN, { closed: false, postMessage: vi.fn() });
    send({ ...message, handoff_nonce: "wrong" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    send(message);
    await vi.waitFor(() =>
      expect(opener.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          id: message.id,
          result: { credentials: { "example/site": credential } },
          error: null,
        }),
        CLIENT_ORIGIN,
      ),
    );
    send(message); // duplicate messages do not issue additional credentials
    expect(fetchMock).toHaveBeenCalledTimes(2);
    send({
      ...message,
      id: "c".repeat(32),
      method: "authorize",
      input: { bundle: "must stay downstream" },
    });
    await vi.waitFor(() =>
      expect(opener.postMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "c".repeat(32),
          error: expect.objectContaining({
            message: "Invalid authorization request.",
          }),
        }),
        CLIENT_ORIGIN,
      ),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    send({
      ...message,
      id: "d".repeat(32),
      method: "authorize",
      input: {
        scope_proof: "proof",
        input_repository: "example/site",
        input_commit: "b".repeat(40),
      },
    });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    send({ ...message, id: "e".repeat(32), method: "release", input: {} });
    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/revoke",
        expect.objectContaining({
          body: JSON.stringify({ token: credential.token }),
        }),
      ),
    );
    expect(
      fetchMock.mock.calls.every(
        ([path]) =>
          String(path) === "/api/session" ||
          String(path).startsWith("/api/auth/"),
      ),
    ).toBe(true);
    dom.window.close();
  });
});
