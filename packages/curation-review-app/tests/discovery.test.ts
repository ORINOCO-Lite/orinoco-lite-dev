import { afterEach, describe, expect, it, vi } from "vitest";
import { onRequest as discoveryAuthorizationStart } from "../functions/api/auth/discovery-start";
import { onRequest as discoverReviews } from "../functions/api/discovery";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env, EventContext } from "../functions/lib/pages";

const ORIGIN = "https://review.example";
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("retired central review discovery", () => {
  it.each([
    ["discovery", discoverReviews, "/api/discovery?repository=example%2Fsite"],
    [
      "discovery authentication",
      discoveryAuthorizationStart,
      "/api/auth/discovery-start?repository=example%2Fsite",
    ],
  ])(
    "returns a tombstone for %s without contacting GitHub",
    async (_label, handler, path) => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      await expect(
        handler(context(new Request(`${ORIGIN}${path}`))),
      ).rejects.toMatchObject({
        code: "review_discovery_retired",
        status: 410,
      });
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it.each([
    ["/api/discovery", discoverReviews],
    ["/api/auth/discovery-start", discoveryAuthorizationStart],
  ])("rejects non-GET requests to %s", async (path, handler) => {
    await expect(
      handler(context(new Request(`${ORIGIN}${path}`, { method: "POST" }))),
    ).rejects.toMatchObject({ code: "method_not_allowed", status: 405 });
  });
});
