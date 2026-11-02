// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { GitHubClient } from "../functions/lib/github";
import { advanceWebsiteGitlink } from "../functions/lib/metadata-merge";
import { AppAuthentication } from "../functions/lib/workflow-access";
import { onRequest } from "../functions/api/shacl/metadata-merge";
import type { Env, EventContext } from "../functions/lib/pages";

const head = "a".repeat(40),
  merged = "b".repeat(40),
  websiteHead = "c".repeat(40),
  tree = "d".repeat(40),
  newTree = "e".repeat(40),
  commit = "f".repeat(40);
const env: Env = {
  PUBLIC_ORIGIN: "https://review.example",
  GITHUB_CLIENT_ID: "id",
  GITHUB_CLIENT_SECRET: "secret",
  SESSION_SEAL_KEY: "seal",
  GITHUB_WEBHOOK_SECRET: "webhook-secret",
};
const payload = {
  action: "closed",
  repository: { full_name: "owner/metadata" },
  pull_request: {
    merged: true,
    body: "Website branch: https://github.com/owner/site/tree/curation%2Fedit",
    merge_commit_sha: merged,
    head: { sha: head },
    user: { login: "curator", id: 3 },
  },
};
afterEach(() => vi.restoreAllMocks());

describe("metadata merge coordination", () => {
  it("advances the existing website PR to the actual merged commit", async () => {
    const auth = new AppAuthentication(env);
    auth.token = vi.fn(async () => ({ token: "test", expires_at: "later" }));
    auth.revoke = vi.fn(async () => undefined);
    vi.spyOn(GitHubClient.prototype, "requireCurator").mockResolvedValue();
    vi.spyOn(GitHubClient.prototype, "siteSubmodule").mockResolvedValue({
      repository: "owner/metadata",
      sha: head,
    });
    const json = vi
      .spyOn(GitHubClient.prototype, "json")
      .mockImplementation(async (path) => {
        if (path.includes("/pulls?"))
          return [
            {
              head: {
                ref: "curation/edit",
                sha: websiteHead,
                repo: { full_name: "owner/site" },
              },
            },
          ];
        if (path.endsWith(`/git/commits/${websiteHead}`))
          return { tree: { sha: tree } };
        if (path.endsWith("/git/trees")) return { sha: newTree };
        if (path.endsWith("/git/commits")) return { sha: commit };
        if (path.includes("/git/refs/heads/"))
          return { object: { sha: commit } };
        throw new Error(`Unexpected ${path}`);
      });
    await expect(advanceWebsiteGitlink(env, payload, auth)).resolves.toBe(true);
    expect(json).toHaveBeenCalledWith(
      "/repos/owner/site/git/trees",
      expect.objectContaining({
        body: JSON.stringify({
          base_tree: tree,
          tree: [
            {
              path: "site-specific",
              mode: "160000",
              type: "commit",
              sha: merged,
            },
          ],
        }),
      }),
    );
    expect(json).toHaveBeenCalledWith(
      "/repos/owner/site/git/refs/heads/curation%2Fedit",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ sha: commit, force: false }),
      }),
    );
    expect(auth.revoke).toHaveBeenCalledWith("test");
  });
  it("ignores an unmerged proposal and does not obtain credentials", async () => {
    const auth = new AppAuthentication(env);
    auth.token = vi.fn();
    await expect(
      advanceWebsiteGitlink(
        env,
        {
          ...payload,
          pull_request: { ...payload.pull_request, merged: false },
        },
        auth,
      ),
    ).resolves.toBe(false);
    expect(auth.token).not.toHaveBeenCalled();
  });
  it("does not overwrite a website branch whose gitlink changed", async () => {
    const auth = new AppAuthentication(env);
    auth.token = vi.fn(async () => ({ token: "test", expires_at: "later" }));
    auth.revoke = vi.fn(async () => undefined);
    vi.spyOn(GitHubClient.prototype, "requireCurator").mockResolvedValue();
    vi.spyOn(GitHubClient.prototype, "siteSubmodule").mockResolvedValue({
      repository: "owner/metadata",
      sha: tree,
    });
    const json = vi.spyOn(GitHubClient.prototype, "json").mockResolvedValue([
      {
        head: {
          ref: "curation/edit",
          sha: websiteHead,
          repo: { full_name: "owner/site" },
        },
      },
    ]);
    await expect(advanceWebsiteGitlink(env, payload, auth)).resolves.toBe(
      false,
    );
    expect(json).toHaveBeenCalledTimes(1);
  });
  it("accepts an authentic GitHub event and ignores unrelated events", async () => {
    const bytes = new TextEncoder().encode(JSON.stringify(payload));
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(env.GITHUB_WEBHOOK_SECRET!),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    const digest = new Uint8Array(await crypto.subtle.sign("HMAC", key, bytes));
    const signature = Array.from(digest, (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
    const request = new Request(
      "https://review.example/api/shacl/metadata-merge",
      {
        method: "POST",
        body: bytes,
        headers: {
          "x-hub-signature-256": `sha256=${signature}`,
          "x-github-event": "ping",
        },
      },
    );
    const response = await onRequest({ env, request } as EventContext);
    expect(await response.json()).toEqual({ updated: false });
  });
  it("rejects a webhook without GitHub's signature", async () => {
    const request = new Request(
      "https://review.example/api/shacl/metadata-merge",
      { method: "POST", body: JSON.stringify(payload) },
    );
    await expect(
      onRequest({ env, request } as EventContext),
    ).rejects.toMatchObject({ status: 401 });
  });
});
