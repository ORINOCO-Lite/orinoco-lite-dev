import { describe, expect, it, vi } from "vitest";
import { GitHubClient } from "../functions/lib/github";
import { HttpError } from "../functions/lib/http";
import { checkShaclAccess } from "../functions/lib/shacl-proposal";
import { ORINOCO_CONFIG } from "./fixtures";

const sha = "a".repeat(40);
const grant = {
  repository: "website/site",
  editor_origin: "https://site.example",
  expected_head_sha: null,
  pull_request: null,
  handoff_nonce: "b".repeat(64),
};
function client(config = ORINOCO_CONFIG) {
  const github = new GitHubClient("test");
  vi.spyOn(github, "requireInstallationAccess").mockResolvedValue();
  vi.spyOn(github, "currentUser").mockResolvedValue({
    id: 1,
    login: "curator",
  });
  vi.spyOn(github, "requireCurator").mockResolvedValue();
  vi.spyOn(github, "repository").mockResolvedValue({
    defaultBranch: "main",
    fullName: grant.repository,
  } as Awaited<ReturnType<GitHubClient["repository"]>>);
  vi.spyOn(github, "branchHead").mockResolvedValue({ sha } as Awaited<
    ReturnType<GitHubClient["branchHead"]>
  >);
  vi.spyOn(github, "json").mockResolvedValue({ default_branch: "main" });
  vi.spyOn(github, "contents").mockImplementation(
    async (_repo, requests) =>
      new Map(requests.map((request) => [request.key, config])),
  );
  vi.spyOn(github, "siteSubmodule").mockResolvedValue({
    repository: "metadata/records",
    sha,
  });
  return github;
}

describe("read-only editor access", () => {
  it("checks website access without guessing which metadata snapshot will be submitted", async () => {
    const github = client();
    await checkShaclAccess(github, grant, "https://review.example");
    expect(github.requireInstallationAccess).toHaveBeenNthCalledWith(
      1,
      "website/site",
    );
    expect(github.siteSubmodule).not.toHaveBeenCalled();
  });
  it("does not require a separate editor operation opt-in", async () => {
    const github = client();
    await expect(
      checkShaclAccess(github, grant, "https://review.example"),
    ).resolves.toBeUndefined();
    expect(github.requireInstallationAccess).toHaveBeenCalledTimes(1);
  });
  it("does not relabel a network failure as missing curator permission", async () => {
    const github = client();
    vi.mocked(github.requireCurator).mockRejectedValueOnce(
      new HttpError(502, "github_error", "GitHub unavailable"),
    );
    await expect(
      checkShaclAccess(github, grant, "https://review.example"),
    ).rejects.toMatchObject({ code: "github_error" });
  });
});
