import { describe, expect, it } from "vitest";
import type { GitHubClient } from "../functions/lib/github";
import {
  loadReviewProposal,
  MAX_REVIEW_CANDIDATES,
} from "../functions/lib/proposal";
import {
  BASE_SHA,
  generatedSummary,
  HEAD_SHA,
  PROPOSAL_SHA,
  summary,
} from "./fixtures";

function client(
  files?: unknown[],
  pullBaseSha: string = BASE_SHA,
  body: string = summary(),
): GitHubClient {
  const content = new Map([
    [
      `metadata/records/example/first.yaml@${BASE_SHA}`,
      "pid: example:first\ntitle: Original first\n",
    ],
    [
      `metadata/records/example/first.yaml@${PROPOSAL_SHA}`,
      "pid: example:first\ntitle: Proposed first\n",
    ],
    [
      `metadata/records/example/first.yaml@${HEAD_SHA}`,
      "pid: example:first\ntitle: Current first\n",
    ],
    [
      `metadata/records/example/second.yaml@${PROPOSAL_SHA}`,
      "pid: example:second\ntitle: Second\n",
    ],
    [
      `metadata/records/example/second.yaml@${HEAD_SHA}`,
      "pid: example:second\ntitle: Second\n",
    ],
  ]);
  return {
    commit: async () => ({
      files: files ?? [
        { filename: "metadata/records/example/first.yaml", status: "modified" },
        {
          filename: "metadata/overlays/annotations/example/first.yaml",
          status: "modified",
        },
        { filename: "metadata/records/example/second.yaml", status: "added" },
        {
          filename: "metadata/overlays/annotations/example/second.yaml",
          status: "added",
        },
      ],
    }),
    contents: async (
      _repository: string,
      requests: Array<{ key: string; path: string; ref: string }>,
    ) =>
      new Map(
        requests.map((request) => [
          request.key,
          content.get(`${request.path}@${request.ref}`) ?? null,
        ]),
      ),
    firstPullRequestCommit: async () => ({
      sha: PROPOSAL_SHA,
      parents: [{ sha: BASE_SHA }],
    }),
    pullRequest: async () => ({
      base: { repo: { full_name: "Example/Site" }, sha: pullBaseSha },
      body,
      head: { sha: HEAD_SHA },
      html_url: "https://github.com/Example/Site/pull/42",
      number: 42,
      state: "open",
    }),
  } as unknown as GitHubClient;
}

describe("GitHub proposal loading", () => {
  it("derives candidates from the actual proposal commit and current head", async () => {
    const result = await loadReviewProposal(client(), "example/site", 42);
    expect(result.repository).toBe("Example/Site");
    expect(result.candidates).toHaveLength(2);
    expect(result.candidates[0]?.before).toContain("Original first");
    expect(result.candidates[0]?.after).toContain("Current first");
    expect(result.candidates[1]?.operation).toBe("add");
  });

  it("keeps a clean proposal reviewable after the default branch advances", async () => {
    const result = await loadReviewProposal(
      client(undefined, "d".repeat(40)),
      "example/site",
      42,
    );
    expect(result.candidates[0]?.before).toContain("Original first");
  });

  it("rejects proposal writes outside the two metadata roots", async () => {
    await expect(
      loadReviewProposal(
        client([{ filename: ".github/workflows/pwn.yml", status: "added" }]),
        "example/site",
        42,
      ),
    ).rejects.toThrow("outside the metadata roots");
  });

  it("rejects mismatch between visible summary and Git diff", async () => {
    await expect(
      loadReviewProposal(
        client([
          {
            filename: "metadata/records/example/first.yaml",
            status: "modified",
          },
        ]),
        "example/site",
        42,
      ),
    ).rejects.toThrow("does not cover every changed record");
  });

  it("rejects an annotation change unrelated to the candidate records", async () => {
    await expect(
      loadReviewProposal(
        client([
          {
            filename: "metadata/records/example/first.yaml",
            status: "modified",
          },
          { filename: "metadata/records/example/second.yaml", status: "added" },
          {
            filename: "metadata/overlays/annotations/example/unrelated.yaml",
            status: "added",
          },
        ]),
        "example/site",
        42,
      ),
    ).rejects.toThrow("outside the candidate record companions");
  });

  it("rejects an annotation rename even when its destination is a candidate companion", async () => {
    await expect(
      loadReviewProposal(
        client([
          {
            filename: "metadata/records/example/first.yaml",
            status: "modified",
          },
          { filename: "metadata/records/example/second.yaml", status: "added" },
          {
            filename: "metadata/overlays/annotations/example/first.yaml",
            previous_filename: ".github/workflows/curation.yml",
            status: "renamed",
          },
        ]),
        "example/site",
        42,
      ),
    ).rejects.toThrow("renames and repeated paths are not supported");
  });

  it("rejects candidate sets beyond the Cloudflare Free support envelope", async () => {
    await expect(
      loadReviewProposal(
        client(
          undefined,
          BASE_SHA,
          generatedSummary(MAX_REVIEW_CANDIDATES + 1),
        ),
        "example/site",
        42,
      ),
    ).rejects.toThrow(`at most ${MAX_REVIEW_CANDIDATES} candidates`);
  });
});
