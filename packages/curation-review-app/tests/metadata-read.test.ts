// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { GitHubClient } from "../functions/lib/github";
import { metadataReadAccess } from "../functions/lib/metadata-read";
import { AppAuthentication } from "../functions/lib/workflow-access";
import type { Env } from "../functions/lib/pages";
const head = "a".repeat(40),
  merged = "b".repeat(40),
  workflow = "c".repeat(40);
const env: Env = {
  PUBLIC_ORIGIN: "https://review.example",
  GITHUB_CLIENT_ID: "test",
  GITHUB_CLIENT_SECRET: "test",
  SESSION_SEAL_KEY: "test",
};
const identity = {
  repository: "owner/site",
  repository_id: "1",
  event_name: "pull_request_target",
  ref: "refs/heads/main",
  workflow_ref:
    "owner/site/.github/workflows/shacl-vue-proposal.yml@refs/heads/main",
  workflow_sha: workflow,
  run_attempt: "1",
  run_id: "4",
};
const request = { repository: "owner/site", pull_request: 7, head };
const author = { login: "curator", id: 3 };
function setup() {
  const auth = new AppAuthentication(env);
  auth.token = vi.fn(async (repo: string) => ({
    token: repo,
    expires_at: "later",
  }));
  auth.revoke = vi.fn(async () => undefined);
  vi.spyOn(GitHubClient.prototype, "pullRequest").mockResolvedValue({
    state: "open",
    head: {
      sha: head,
      ref: "curation/edit",
      repo: { full_name: "owner/site" },
    },
    base: { ref: "main", repo: { full_name: "owner/site" } },
  });
  vi.spyOn(GitHubClient.prototype, "siteSubmodule").mockResolvedValue({
    repository: "owner/data",
    sha: merged,
  });
  vi.spyOn(GitHubClient.prototype, "requireCurator").mockResolvedValue();
  const json = vi
    .spyOn(GitHubClient.prototype, "json")
    .mockImplementation(async (path) => {
      if (path === "/repos/owner/site")
        return { id: 1, default_branch: "main" };
      if (path.endsWith("/actions/runs/4"))
        return {
          id: 4,
          repository: { id: 1 },
          path: ".github/workflows/shacl-vue-proposal.yml",
          event: "pull_request_target",
          head_sha: head,
          run_attempt: 1,
          status: "in_progress",
        };
      if (path.includes("/pulls?"))
        return [
          {
            merged_at: "now",
            merge_commit_sha: merged,
            body: "Website branch: https://github.com/owner/site/tree/curation%2Fedit",
            user: author,
          },
        ];
      throw new Error(`Unexpected ${path}`);
    });
  return { auth, json };
}
afterEach(() => vi.restoreAllMocks());
describe("private metadata validation", () => {
  it("grants read access to the merged metadata linked to the website proposal", async () => {
    const s = setup();
    await expect(
      metadataReadAccess(env, identity, request, s.auth),
    ).resolves.toEqual({ token: "owner/data", expires_at: "later" });
    expect(s.auth.token).toHaveBeenCalledWith("owner/data");
    expect(GitHubClient.prototype.requireCurator).toHaveBeenCalledWith(
      "owner/site",
      "curator",
      3,
    );
    expect(GitHubClient.prototype.requireCurator).toHaveBeenCalledWith(
      "owner/data",
      "curator",
      3,
    );
    expect(s.auth.revoke).toHaveBeenCalledWith("owner/site");
  });
  it("rejects a merged PR for a different website branch", async () => {
    const s = setup();
    const original = s.json.getMockImplementation()!;
    s.json.mockImplementation(async (path, ...rest) =>
      path.includes("/pulls?")
        ? [
            {
              merged_at: "now",
              merge_commit_sha: merged,
              body: "unrelated",
              user: author,
            },
          ]
        : original(path, ...rest),
    );
    await expect(
      metadataReadAccess(env, identity, request, s.auth),
    ).rejects.toThrow();
    expect(s.auth.revoke).toHaveBeenCalledWith("owner/data");
  });
  it("rejects an unrelated workflow identity", async () => {
    const s = setup();
    await expect(
      metadataReadAccess(
        env,
        {
          ...identity,
          workflow_ref:
            "owner/site/.github/workflows/other.yml@refs/heads/main",
        },
        request,
        s.auth,
      ),
    ).rejects.toThrow();
    expect(s.auth.token).toHaveBeenCalledTimes(1);
  });
});
