import { beforeEach, describe, expect, it, vi } from "vitest";
import { onRequest } from "../functions/api/shacl/access";
import { checkShaclAccess } from "../functions/lib/shacl-proposal";
import { base64urlEncode } from "../functions/lib/encoding";
import { createSessionCookie } from "../functions/lib/session";
import type { Env, EventContext } from "../functions/lib/pages";
vi.mock("../functions/lib/shacl-proposal", () => ({
  checkShaclAccess: vi.fn(),
}));
const origin = "https://review.example";
const env: Env = {
  GITHUB_CLIENT_ID: "test",
  GITHUB_CLIENT_SECRET: "test",
  PUBLIC_ORIGIN: origin,
  SESSION_SEAL_KEY: base64urlEncode(new Uint8Array(32).fill(7)),
};
const grant = {
  repository: "website/site",
  editor_origin: "https://site.example",
  expected_head_sha: null,
  pull_request: null,
  handoff_nonce: "b".repeat(64),
};
async function context(
  overrides: Record<string, string> = {},
  withGrant = true,
): Promise<EventContext> {
  const cookie = (
    await createSessionCookie(
      env,
      {
        access_token: "test",
        csrf_token: "csrf",
        login: "curator",
        shacl_grant: withGrant ? grant : null,
      },
      600,
    )
  ).split(";")[0]!;
  return {
    env,
    request: new Request(`${origin}/api/shacl/access`, {
      method: "POST",
      headers: { origin, cookie, "x-csrf-token": "csrf", ...overrides },
    }),
  } as EventContext;
}
beforeEach(() => vi.clearAllMocks());
describe("access check session boundary", () => {
  it("returns only readiness and leaves the submission grant intact", async () => {
    const response = await onRequest(await context());
    expect(await response.json()).toEqual({ ready: true });
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(checkShaclAccess).toHaveBeenCalledWith(
      expect.anything(),
      grant,
      origin,
      expect.any(Function),
    );
  });
  it.each([
    [{ origin: "https://untrusted.example" }, "invalid_origin"],
    [{ "x-csrf-token": "wrong" }, "invalid_csrf"],
    [{ cookie: "" }, "authentication_required"],
  ])(
    "rejects an invalid session boundary before GitHub reads",
    async (headers, code) => {
      await expect(onRequest(await context(headers))).rejects.toMatchObject({
        code,
      });
      expect(checkShaclAccess).not.toHaveBeenCalled();
    },
  );
  it("requires an editor sign-in grant", async () => {
    await expect(onRequest(await context({}, false))).rejects.toMatchObject({
      code: "shacl_grant_required",
    });
    expect(checkShaclAccess).not.toHaveBeenCalled();
  });
});
