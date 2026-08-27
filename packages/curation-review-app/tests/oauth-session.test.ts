import { describe, expect, it } from "vitest";
import { exchangeCode } from "../functions/lib/oauth";
import type { Env } from "../functions/lib/pages";
import {
  createSessionCookie,
  readSessionCookie,
} from "../functions/lib/session";
import { base64urlEncode } from "../functions/lib/encoding";
import type { ReviewGrant } from "../shared/contracts";

const env: Env = {
  GITHUB_CLIENT_ID: "Iv1.example",
  GITHUB_CLIENT_SECRET: "secret",
  PUBLIC_ORIGIN: "https://review.example",
  SESSION_SEAL_KEY: base64urlEncode(new Uint8Array(32).fill(7)),
};
const REVIEW_GRANT: ReviewGrant = {
  artifact_id: 123456789,
  handoff_nonce: "e".repeat(64),
  pull_request: 42,
  repository: "example/site",
  review_origin: "https://site.example",
};

describe("short-lived GitHub authentication", () => {
  it("seals the access token in a host-only session cookie", async () => {
    const cookie = await createSessionCookie(
      env,
      { access_token: "ghu_secret", csrf_token: "csrf", login: "octocat" },
      28_800,
    );
    expect(cookie).toContain("__Host-orinoco_session=");
    expect(cookie).toContain("Max-Age=3600");
    expect(cookie).toContain("HttpOnly; Secure; SameSite=Lax");
    expect(cookie).not.toContain("ghu_secret");
    const request = new Request("https://review.example/api/session", {
      headers: { Cookie: cookie.split(";", 1)[0] ?? "" },
    });
    await expect(readSessionCookie(request, env)).resolves.toMatchObject({
      access_token: "ghu_secret",
      login: "octocat",
      review_grant: null,
    });
  });

  it("round-trips the exact downstream review transport grant", async () => {
    const cookie = await createSessionCookie(
      env,
      {
        access_token: "ghu_secret",
        csrf_token: "csrf",
        login: "octocat",
        review_grant: REVIEW_GRANT,
      },
      28_800,
    );
    const request = new Request("https://review.example/api/session", {
      headers: { Cookie: cookie.split(";", 1)[0] ?? "" },
    });

    await expect(readSessionCookie(request, env)).resolves.toMatchObject({
      review_grant: REVIEW_GRANT,
    });
  });

  it.each([
    {
      grant: { ...REVIEW_GRANT, review_origin: "http://site.example" },
      label: "an unsafe review origin",
    },
    {
      grant: { ...REVIEW_GRANT, handoff_nonce: "not-random" },
      label: "an invalid review nonce",
    },
  ])("rejects a sealed grant with $label", async ({ grant }) => {
    const cookie = await createSessionCookie(
      env,
      {
        access_token: "ghu_secret",
        csrf_token: "csrf",
        login: "octocat",
        review_grant: grant,
      },
      28_800,
    );
    const request = new Request("https://review.example/api/session", {
      headers: { Cookie: cookie.split(";", 1)[0] ?? "" },
    });

    await expect(readSessionCookie(request, env)).rejects.toMatchObject({
      code: "invalid_session",
      status: 401,
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

  it("reports a non-expiring token response without exposing response data", async () => {
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
    ).rejects.toThrow("valid user token expiration");
  });

  it("classifies OAuth exchange errors without reflecting GitHub details", async () => {
    const knownError = async (): Promise<Response> =>
      Response.json({
        error: "bad_verification_code",
        error_description: "sensitive upstream diagnostic",
      });
    await expect(
      exchangeCode(
        env,
        "code",
        "verifier",
        "https://review.example/api/auth/callback",
        knownError,
      ),
    ).rejects.toThrow("expired or already-used authorization code");
    await expect(
      exchangeCode(
        env,
        "code",
        "verifier",
        "https://review.example/api/auth/callback",
        knownError,
      ),
    ).rejects.not.toThrow("sensitive upstream diagnostic");

    const unknownError = async (): Promise<Response> =>
      Response.json({
        error: "unrecognized_error",
        error_description: "sensitive upstream diagnostic",
      });
    await expect(
      exchangeCode(
        env,
        "code",
        "verifier",
        "https://review.example/api/auth/callback",
        unknownError,
      ),
    ).rejects.toThrow("rejected the authorization exchange");
  });

  it.each([
    {
      expected: "invalid user access token",
      response: {
        access_token: " ",
        expires_in: 28_800,
        scope: "",
        token_type: "bearer",
      },
    },
    {
      expected: "valid user token expiration",
      response: {
        access_token: "ghu_short_lived",
        expires_in: "28800",
        scope: "",
        token_type: "bearer",
      },
    },
    {
      expected: "unexpected user token type",
      response: {
        access_token: "ghu_short_lived",
        expires_in: 28_800,
        scope: "",
        token_type: "mac",
      },
    },
    {
      expected: "unexpected user-token scopes",
      response: {
        access_token: "ghu_short_lived",
        expires_in: 28_800,
        scope: "repo",
        token_type: "bearer",
      },
    },
  ])(
    "reports a fixed diagnostic for $expected",
    async ({ expected, response }) => {
      const fetchMock = async (): Promise<Response> => Response.json(response);
      await expect(
        exchangeCode(
          env,
          "code",
          "verifier",
          "https://review.example/api/auth/callback",
          fetchMock,
        ),
      ).rejects.toThrow(expected);
    },
  );
});
