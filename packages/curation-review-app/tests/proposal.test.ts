import { describe, expect, it } from "vitest";
import type { ReviewBundle } from "../functions/lib/bundle";
import type { GitHubClient } from "../functions/lib/github";
import { loadReviewProposal } from "../functions/lib/proposal";
import {
  ARTIFACT_ID,
  BASE_SHA,
  HEAD_SHA,
  PROPOSAL_SHA,
  WORKFLOW_RUN_ID,
  proposalCommitMessage,
  reviewBundle,
  reviewBundleArchive,
} from "./fixtures";

const defaultFiles = [
  { filename: "metadata/records/example/second.yaml", status: "added" },
  {
    filename: "metadata/overlays/annotations/example/second.yaml",
    status: "added",
  },
  { filename: "metadata/records/example/first.yaml", status: "modified" },
  {
    filename: "metadata/overlays/annotations/example/first.yaml",
    status: "modified",
  },
];

interface ClientOptions {
  artifactHeadSha?: string;
  artifactName?: string;
  body?: unknown;
  bundle?: ReviewBundle;
  contents?: Map<string, string>;
  files?: unknown[];
  message?: string;
  pullBaseSha?: string;
  runConclusion?: string | null;
  runEvent?: string;
  runHeadSha?: string;
  runStatus?: string;
}

function contentFixture(): Map<string, string> {
  return new Map([
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
      "pid: example:second\ntitle: Proposed second\n",
    ],
    [
      `metadata/records/example/second.yaml@${HEAD_SHA}`,
      "pid: example:second\ntitle: Current second\n",
    ],
  ]);
}

function client(options: ClientOptions = {}): GitHubClient {
  const bundle = options.bundle ?? reviewBundle();
  const archive = reviewBundleArchive(bundle);
  const content = options.contents ?? contentFixture();
  return {
    artifactArchive: async () => archive,
    artifactMetadata: async () => ({
      expired: false,
      id: ARTIFACT_ID,
      name: options.artifactName ?? `orinoco-curation-review-${PROPOSAL_SHA}`,
      size_in_bytes: archive.byteLength,
      workflow_run: {
        head_sha: options.artifactHeadSha ?? BASE_SHA,
        id: WORKFLOW_RUN_ID,
      },
    }),
    commit: async () => ({
      files: options.files ?? defaultFiles,
      sha: PROPOSAL_SHA,
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
      commit: { message: options.message ?? proposalCommitMessage() },
      parents: [{ sha: BASE_SHA }],
      sha: PROPOSAL_SHA,
    }),
    pullRequest: async () => ({
      base: {
        repo: { full_name: "Example/Site" },
        sha: options.pullBaseSha ?? BASE_SHA,
      },
      body: options.body ?? null,
      head: { sha: HEAD_SHA },
      html_url: "https://github.com/Example/Site/pull/42",
      number: 42,
      state: "open",
    }),
    workflowRun: async () => ({
      conclusion:
        "runConclusion" in options ? options.runConclusion : "success",
      event: options.runEvent ?? "workflow_dispatch",
      head_sha: options.runHeadSha ?? BASE_SHA,
      id: WORKFLOW_RUN_ID,
      repository: { full_name: "example/site" },
      run_attempt: 1,
      status: options.runStatus ?? "completed",
    }),
  } as unknown as GitHubClient;
}

describe("artifact-backed GitHub proposal loading", () => {
  it("derives candidate membership and operations from the proposal diff", async () => {
    const result = await loadReviewProposal(
      client(),
      "example/site",
      42,
      ARTIFACT_ID,
    );

    expect(result.repository).toBe("Example/Site");
    expect(result.candidates.map((candidate) => candidate.record_path)).toEqual(
      [
        "metadata/records/example/first.yaml",
        "metadata/records/example/second.yaml",
      ],
    );
    expect(result.candidates[0]?.before).toContain("Original first");
    expect(result.candidates[0]?.after).toContain("Current first");
    expect(result.candidates[1]?.operation).toBe("add");
  });

  it("does not parse or authorize candidate facts from the pull-request body", async () => {
    const result = await loadReviewProposal(
      client(),
      "example/site",
      42,
      ARTIFACT_ID,
    );
    expect(result.candidates).toHaveLength(2);
    expect(result.adapter).toBe("zotero");

    const edited = await loadReviewProposal(
      client({ body: "<!-- arbitrary -->\n\n## Human notes\n\nEdited." }),
      "example/site",
      42,
      ARTIFACT_ID,
    );
    expect(edited.candidates).toHaveLength(2);
  });

  it("keeps a proposal reviewable after the default branch advances", async () => {
    const result = await loadReviewProposal(
      client({ pullBaseSha: "d".repeat(40) }),
      "example/site",
      42,
      ARTIFACT_ID,
    );
    expect(result.candidates[0]?.before).toContain("Original first");
  });

  it("rejects proposal writes outside the metadata roots", async () => {
    await expect(
      loadReviewProposal(
        client({
          files: [{ filename: ".github/workflows/pwn.yml", status: "added" }],
        }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("outside the metadata roots");
  });

  it("rejects incomplete or operation-mismatched presentation bundles", async () => {
    const incomplete = reviewBundle();
    incomplete.candidates.pop();
    await expect(
      loadReviewProposal(
        client({ bundle: incomplete }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("does not cover the proposal metadata diff");

    const mismatch = reviewBundle();
    const first = mismatch.candidates[0];
    if (first === undefined) throw new Error("missing fixture candidate");
    first.operation = "delete";
    await expect(
      loadReviewProposal(
        client({ bundle: mismatch }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("operation does not match");
  });

  it("binds artifact name, run, repository, proposal, and source coordinates", async () => {
    await expect(
      loadReviewProposal(
        client({ artifactName: "wrong" }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("expired, mismatched, or too large");
    await expect(
      loadReviewProposal(
        client({ runEvent: "pull_request" }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("workflow run does not match");
    await expect(
      loadReviewProposal(
        client({ artifactHeadSha: "d".repeat(40) }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("no valid workflow run");
    await expect(
      loadReviewProposal(
        client({ runConclusion: "failure" }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("workflow run does not match");
    await expect(
      loadReviewProposal(
        client({ runConclusion: null, runStatus: "in_progress" }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).resolves.toMatchObject({ proposal_sha: PROPOSAL_SHA });

    const wrongSource = reviewBundle();
    wrongSource.source_coordinate = { group: 1, library_version: 451 };
    await expect(
      loadReviewProposal(
        client({ bundle: wrongSource }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("does not match the selected proposal");
  });

  it("rejects a presentation PID mismatch against the initial proposal", async () => {
    const wrongPid = reviewBundle();
    const first = wrongPid.candidates[0];
    if (first === undefined) throw new Error("missing fixture candidate");
    first.pid = "example:wrong";
    await expect(
      loadReviewProposal(
        client({ bundle: wrongPid }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("PID does not match");
  });

  it("presents later human deletion, restoration, and PID edits as head data", async () => {
    const deletedAddition = contentFixture();
    deletedAddition.delete(`metadata/records/example/second.yaml@${HEAD_SHA}`);
    const deleted = await loadReviewProposal(
      client({ contents: deletedAddition }),
      "example/site",
      42,
      ARTIFACT_ID,
    );
    expect(deleted.candidates[1]?.operation).toBe("add");
    expect(deleted.candidates[1]?.after).toBeNull();

    const retargeted = contentFixture();
    retargeted.set(
      `metadata/records/example/first.yaml@${HEAD_SHA}`,
      "pid: example:human-edit\ntitle: Human retarget\n",
    );
    const edited = await loadReviewProposal(
      client({ contents: retargeted }),
      "example/site",
      42,
      ARTIFACT_ID,
    );
    expect(edited.candidates[0]?.pid).toBe("example:first");
    expect(edited.candidates[0]?.after).toContain("example:human-edit");

    const deletionBundle = reviewBundle();
    deletionBundle.candidates = deletionBundle.candidates.slice(1);
    const deletion = deletionBundle.candidates[0];
    if (deletion === undefined) throw new Error("missing deletion candidate");
    deletion.operation = "delete";
    const restoredContents = new Map([
      [
        `metadata/records/example/second.yaml@${BASE_SHA}`,
        "pid: example:second\ntitle: Initial second\n",
      ],
      [
        `metadata/records/example/second.yaml@${HEAD_SHA}`,
        "pid: example:restored\ntitle: Human restoration\n",
      ],
    ]);
    const restored = await loadReviewProposal(
      client({
        bundle: deletionBundle,
        contents: restoredContents,
        files: deletion.paths.map((filename) => ({
          filename,
          status: "removed",
        })),
      }),
      "example/site",
      42,
      ARTIFACT_ID,
    );
    expect(restored.candidates[0]?.operation).toBe("delete");
    expect(restored.candidates[0]?.pid).toBe("example:second");
    expect(restored.candidates[0]?.after).toContain("example:restored");
  });

  it("accepts .yml paths using the same candidate path policy", async () => {
    const bundle = reviewBundle();
    bundle.candidates = bundle.candidates.slice(0, 1);
    const first = bundle.candidates[0];
    if (first === undefined) throw new Error("missing fixture candidate");
    first.record_path = "metadata/records/example/first.yml";
    first.paths = [first.record_path];
    const contents = new Map([
      [`${first.record_path}@${BASE_SHA}`, "pid: example:first\n"],
      [`${first.record_path}@${PROPOSAL_SHA}`, "pid: example:first\n"],
      [`${first.record_path}@${HEAD_SHA}`, "pid: example:first\n"],
    ]);

    const result = await loadReviewProposal(
      client({
        bundle,
        contents,
        files: [{ filename: first.record_path, status: "modified" }],
      }),
      "example/site",
      42,
      ARTIFACT_ID,
    );
    expect(result.candidates[0]?.record_path).toBe(first.record_path);
  });
});
