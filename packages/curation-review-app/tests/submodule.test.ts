import { describe, expect, it, vi } from "vitest";
import {
  GitHubClient,
  githubSubmoduleRepository,
} from "../functions/lib/github";
import { loadSiteCoordinates } from "../functions/lib/proposal";
import { ORINOCO_CONFIG, SITE_DATA } from "./fixtures";

const SOURCE = "a".repeat(40);
const METADATA = "b".repeat(40);

describe("exact site-specific Git resolution", () => {
  it.each([
    "https://github.com/example/metadata.git",
    "git@github.com:example/metadata.git",
    "ssh://git@github.com/example/metadata.git",
  ])("resolves %s", (url) => {
    expect(githubSubmoduleRepository(url)).toBe("example/metadata");
  });
  it.each([
    "file:///tmp/metadata",
    "https://github.com.evil/owner/repo",
    "https://user:secret@github.com/owner/repo",
    "../metadata.git",
    "https://github.com/owner/repo?ref=main",
    "-upload-pack=evil",
  ])("rejects %s", (url) => {
    expect(() => githubSubmoduleRepository(url)).toThrow();
  });
  it("binds URL and gitlink reads to the deployed website commit", async () => {
    const github = new GitHubClient("token");
    const json = vi
      .spyOn(github, "json")
      .mockResolvedValueOnce({
        tree: [
          {
            path: "site-specific",
            mode: "160000",
            type: "commit",
            sha: METADATA,
          },
        ],
        truncated: false,
      })
      .mockResolvedValueOnce({
        path: "site-specific",
        sha: METADATA,
        submodule_git_url: "git@github.com:example/metadata.git",
      });
    expect(await github.siteSubmodule("example/site", SOURCE)).toEqual({
      repository: "example/metadata",
      sha: METADATA,
    });
    expect(json.mock.calls.map((call) => call[0])).toEqual([
      `/repos/example/site/git/trees/${SOURCE}`,
      `/repos/example/site/contents/site-specific?ref=${SOURCE}`,
    ]);
  });
  it("rejects a mismatched contents response", async () => {
    const github = new GitHubClient("token");
    vi.spyOn(github, "json")
      .mockResolvedValueOnce({
        tree: [
          {
            path: "site-specific",
            mode: "160000",
            type: "commit",
            sha: METADATA,
          },
        ],
        truncated: false,
      })
      .mockResolvedValueOnce({
        path: "site-specific",
        sha: SOURCE,
        submodule_git_url: "git@github.com:example/metadata.git",
      });
    await expect(github.siteSubmodule("example/site", SOURCE)).rejects.toThrow(
      "matching repository URL",
    );
  });
  it("reads trusted site origins from site.yaml at the pinned metadata commit", async () => {
    const github = new GitHubClient("token");
    vi.spyOn(github, "siteSubmodule").mockResolvedValue({
      repository: "example/metadata",
      sha: METADATA,
    });
    const contents = vi
      .spyOn(github, "contents")
      .mockResolvedValueOnce(new Map([["site-config", ORINOCO_CONFIG]]))
      .mockResolvedValueOnce(new Map([["site-data", null]]))
      .mockResolvedValueOnce(new Map([["site-data", SITE_DATA]]));
    const result = await loadSiteCoordinates(github, "example/site", SOURCE);
    expect(result.coordinates.editorSiteUrl).toContain("https://site.example");
    expect(contents.mock.calls[2]?.slice(0, 2)).toEqual([
      "example/metadata",
      [{ key: "site-data", path: "site.yaml", ref: METADATA }],
    ]);
  });
});

describe("installed-repository authority", () => {
  it("does not infer installation access from public repository visibility", async () => {
    const github = new GitHubClient("token");
    vi.spyOn(github, "json")
      .mockResolvedValueOnce({
        installations: [
          {
            id: 1,
            account: { login: "example" },
            permissions: { contents: "write", pull_requests: "write" },
          },
        ],
      })
      .mockResolvedValueOnce({
        repositories: [{ full_name: "example/other" }],
      });
    await expect(
      github.requireInstallationAccess("example/metadata"),
    ).rejects.toThrow("Install the curation GitHub App");
  });
  it("requires repository membership and write installation permissions", async () => {
    const github = new GitHubClient("token");
    vi.spyOn(github, "json")
      .mockResolvedValueOnce({
        installations: [
          {
            id: 1,
            account: { login: "example" },
            permissions: { contents: "write", pull_requests: "write" },
          },
        ],
      })
      .mockResolvedValueOnce({
        repositories: [{ full_name: "example/metadata" }],
      });
    await expect(
      github.requireInstallationAccess("example/metadata"),
    ).resolves.toBeUndefined();
  });
});
