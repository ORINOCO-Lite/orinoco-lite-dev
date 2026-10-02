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
  it("checks installations in different organizations without making GitHub writes", async () => {
    const github = client();
    const automation = vi.fn();
    await checkShaclAccess(github, grant, "https://review.example", automation);
    expect(github.requireInstallationAccess).toHaveBeenNthCalledWith(
      1,
      "website/site",
    );
    expect(github.requireInstallationAccess).toHaveBeenNthCalledWith(
      2,
      "metadata/records",
    );
    expect(github.requireCurator).toHaveBeenCalledWith(
      "metadata/records",
      "curator",
    );
    expect(github.json).toHaveBeenCalledExactlyOnceWith("/repos/website/site");
    expect(automation).toHaveBeenCalledOnce();
  });
  it("reports disabled policy separately after successful installation checks", async () => {
    const github = client(
      ORINOCO_CONFIG.replace(
        "shacl_materialization = true",
        "shacl_materialization = false",
      ),
    );
    await expect(
      checkShaclAccess(github, grant, "https://review.example", vi.fn()),
    ).rejects.toMatchObject({ code: "operation_disabled", status: 403 });
    expect(github.requireInstallationAccess).toHaveBeenCalledTimes(2);
  });
  it("identifies the missing metadata installation", async () => {
    const github = client();
    vi.mocked(github.requireInstallationAccess).mockImplementation(
      async (repository) => {
        if (repository === "metadata/records")
          throw new HttpError(
            403,
            "installation_access_required",
            `Install the App on ${repository}.`,
          );
      },
    );
    await expect(
      checkShaclAccess(github, grant, "https://review.example", vi.fn()),
    ).rejects.toMatchObject({
      code: "installation_access_required",
      message: "Install the App on metadata/records.",
    });
  });
  it("does not relabel a network failure as missing curator permission", async () => {
    const github = client();
    vi.mocked(github.requireCurator).mockRejectedValueOnce(
      new HttpError(502, "github_error", "GitHub unavailable"),
    );
    await expect(
      checkShaclAccess(github, grant, "https://review.example", vi.fn()),
    ).rejects.toMatchObject({ code: "github_error" });
  });
});
