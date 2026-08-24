import { describe, expect, it } from "vitest";
import { exchangeCode } from "../functions/lib/oauth";
import type { Env } from "../functions/lib/pages";
import {
  createSessionCookie,
  readSessionCookie,
} from "../functions/lib/session";
import { base64urlEncode } from "../functions/lib/encoding";

const env: Env = {
  GITHUB_CLIENT_ID: "Iv1.example",
  GITHUB_CLIENT_SECRET: "secret",
  PUBLIC_ORIGIN: "https://review.example",
  SESSION_SEAL_KEY: base64urlEncode(new Uint8Array(32).fill(7)),
};

describe("short-lived GitHub authentication", () => {
  it("seals the access token in a host-only session cookie", async () => {
    const cookie = await createSessionCookie(
      env,
      { access_token: "ghu_secret", csrf_token: "csrf", login: "octocat" },
      28_800,
    );
    expect(cookie).toContain("__Host-orinoco_session=");
    expect(cookie).toContain("HttpOnly; Secure; SameSite=Lax");
    expect(cookie).not.toContain("ghu_secret");
    const request = new Request("https://review.example/api/session", {
      headers: { Cookie: cookie.split(";", 1)[0] ?? "" },
    });
    await expect(readSessionCookie(request, env)).resolves.toMatchObject({
      access_token: "ghu_secret",
      login: "octocat",
    });
  });

  it("rejects a tampered session", async () => {
    const cookie = await createSessionCookie(
      env,
      { access_token: "ghu_secret", csrf_token: "csrf", login: "octocat" },
      28_800,
    );
    const cookiePair = cookie.split(";", 1)[0] ?? "";
    const separator = cookiePair.indexOf("=");
    const fields = cookiePair.slice(separator + 1).split(".");
    const ciphertext = fields[2] ?? "";
    fields[2] = `${ciphertext.startsWith("A") ? "B" : "A"}${ciphertext.slice(1)}`;
    const encoded = `${cookiePair.slice(0, separator + 1)}${fields.join(".")}`;
    await expect(
      readSessionCookie(
        new Request("https://review.example", { headers: { Cookie: encoded } }),
        env,
      ),
    ).rejects.toThrow("session is invalid");
  });

  it("accepts an expiring GitHub App user token and discards refresh data", async () => {
    const fetchMock = async (): Promise<Response> =>
      Response.json({
        access_token: "ghu_short_lived",
        expires_in: 28_800,
        refresh_token: "ghr_must_not_be_retained",
        refresh_token_expires_in: 15_897_600,
        scope: "",
        token_type: "bearer",
      });
    await expect(
      exchangeCode(
        env,
        "code",
        "verifier",
        "https://review.example/api/auth/callback",
        fetchMock,
      ),
    ).resolves.toEqual({
      accessToken: "ghu_short_lived",
      expiresIn: 28_800,
    });
  });

  it("rejects a non-expiring token response", async () => {
    const fetchMock = async (): Promise<Response> =>
      Response.json({
        access_token: "ghu_long_lived",
        scope: "",
        token_type: "bearer",
      });
    await expect(
      exchangeCode(
        env,
        "code",
        "verifier",
        "https://review.example/api/auth/callback",
        fetchMock,
      ),
    ).rejects.toThrow("invalid expiring user token");
  });
});
