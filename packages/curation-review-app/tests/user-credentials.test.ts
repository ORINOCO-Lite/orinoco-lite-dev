// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { GitHubClient } from "../functions/lib/github";
import type { Env } from "../functions/lib/pages";
import {
  revokeUserCredential,
  scopedUserCredential,
  writableUserRepository,
} from "../functions/lib/user-credentials";

const env: Env = {
  GITHUB_CLIENT_ID: "test-client",
  GITHUB_CLIENT_SECRET: "test-secret",
  PUBLIC_ORIGIN: "https://auth.example",
  SESSION_SEAL_KEY: "test-key",
};
const repository = {
  id: 12,
  ownerId: 34,
  name: "owner/site",
  defaultBranch: "main",
};

describe("user-scoped repository credentials", () => {
  it("uses GitHub's effective write permission rather than a list of role names", async () => {
    const github = new GitHubClient(
      "test-user-token",
      vi.fn(async () =>
        Response.json({
          id: 12,
          owner: { id: 34 },
          full_name: "owner/site",
          default_branch: "main",
          role_name: "custom-editor",
          permissions: { pull: true, push: true },
        }),
      ),
    );
    await expect(writableUserRepository(github, "owner/site")).resolves.toEqual(
      repository,
    );
  });

  it("refuses website submission for a user without website write permission", async () => {
    const github = new GitHubClient(
      "test-user-token",
      vi.fn(async () =>
        Response.json({
          id: 12,
          owner: { id: 34 },
          full_name: "owner/site",
          default_branch: "main",
          permissions: { pull: true, push: false },
        }),
      ),
    );
    await expect(
      writableUserRepository(github, "owner/site"),
    ).rejects.toMatchObject({
      status: 403,
      code: "curator_permission_required",
    });
  });

  it("requests one repository and only the browser's required permissions", async () => {
    const expires_at = new Date(Date.now() + 3600_000).toISOString();
    const fetcher = vi.fn(async () =>
      Response.json({ token: "scoped-test-token", expires_at }),
    );
    await expect(
      scopedUserCredential(env, "root-test-token", repository, fetcher),
    ).resolves.toEqual({ token: "scoped-test-token", expires_at });
    const [url, init] = fetcher.mock.calls[0]! as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe(
      "https://api.github.com/applications/test-client/token/scoped",
    );
    expect(init.redirect).toBe("manual");
    expect(JSON.parse(String(init.body))).toEqual({
      access_token: "root-test-token",
      target_id: 34,
      repository_ids: [12],
      permissions: {
        contents: "write",
        pull_requests: "read",
        actions: "read",
      },
    });
  });

  it("does not expose GitHub's token error response", async () => {
    const fetcher = vi.fn(async () =>
      Response.json({ token: "must-not-appear" }, { status: 403 }),
    );
    await expect(
      scopedUserCredential(env, "root-test-token", repository, fetcher),
    ).rejects.toThrow(
      "GitHub could not issue the repository credential (HTTP 403).",
    );
  });

  it.each([null, "invalid", "2000-01-01T00:00:00Z"])(
    "rejects missing or expired token expiry: %s",
    async (expires_at) => {
      const fetcher = vi.fn(async () =>
        Response.json({ token: "test-token", expires_at }),
      );
      await expect(
        scopedUserCredential(env, "root-test-token", repository, fetcher),
      ).rejects.toMatchObject({ code: "github_credential_error" });
    },
  );

  it("revokes the scoped token without deleting the user's App authorization", async () => {
    const fetcher = vi.fn(async () => new Response(null, { status: 204 }));
    await revokeUserCredential(env, "scoped-test-token", fetcher);
    const [url, init] = fetcher.mock.calls[0]! as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("https://api.github.com/applications/test-client/token");
    expect(init.method).toBe("DELETE");
    expect(JSON.parse(String(init.body))).toEqual({
      access_token: "scoped-test-token",
    });
  });
});
