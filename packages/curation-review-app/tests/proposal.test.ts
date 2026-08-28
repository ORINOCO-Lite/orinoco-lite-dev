import { describe, expect, it } from "vitest";
import type { ReviewBundle } from "../functions/lib/bundle";
import type { GitHubClient } from "../functions/lib/github";
import {
  loadReviewProposal,
  MAX_REVIEW_CANDIDATES,
  MAX_REVIEW_PATHS,
} from "../functions/lib/proposal";
import { metadataRoots } from "../shared/metadata";
import {
  ARTIFACT_ID,
  BASE_SHA,
  HEAD_SHA,
  ORINOCO_CONFIG,
  PROPOSAL_SHA,
  WORKFLOW_RUN_ID,
  proposalCommitMessage,
  reviewBundle,
  reviewBundleArchive,
} from "./fixtures";

const defaultFiles = [
  {
    filename: "site-specific/metadata/records/example/second.yaml",
    status: "added",
  },
  {
    filename: "site-specific/metadata/overlays/annotations/example/second.yaml",
    status: "added",
  },
  {
    filename: "site-specific/metadata/records/example/first.yaml",
    status: "modified",
  },
  {
    filename: "site-specific/metadata/overlays/annotations/example/first.yaml",
    status: "modified",
  },
];

interface ContentRequest {
  key: string;
  path: string;
  ref: string;
}

interface ClientOptions {
  artifactHeadSha?: string;
  artifactName?: string;
  body?: unknown;
  bundle?: ReviewBundle;
  contentRequests?: ContentRequest[][];
  contents?: Map<string, string>;
  files?: unknown[];
  message?: string;
  pullBaseSha?: string;
  runConclusion?: string | null;
  runEvent?: string;
  runHeadSha?: string;
  runStatus?: string;
  siteConfig?: string | null;
}

function contentFixture(): Map<string, string> {
  return new Map([
    [
      `site-specific/metadata/records/example/first.yaml@${BASE_SHA}`,
      "pid: example:first\ntitle: Original first\n",
    ],
    [
      `site-specific/metadata/records/example/first.yaml@${PROPOSAL_SHA}`,
      "pid: example:first\ntitle: Proposed first\n",
    ],
    [
      `site-specific/metadata/records/example/first.yaml@${HEAD_SHA}`,
      "pid: example:first\ntitle: Current first\n",
    ],
    [
      `site-specific/metadata/records/example/second.yaml@${PROPOSAL_SHA}`,
      "pid: example:second\ntitle: Proposed second\n",
    ],
    [
      `site-specific/metadata/records/example/second.yaml@${HEAD_SHA}`,
      "pid: example:second\ntitle: Current second\n",
    ],
  ]);
}

function rootedOptions(recordRoot: string): ClientOptions {
  const current = metadataRoots("site-specific/metadata/records");
  const selected = metadataRoots(recordRoot);
  const rewrite = (path: string): string => {
    if (path.startsWith(`${current.records}/`)) {
      return `${selected.records}/${path.slice(current.records.length + 1)}`;
    }
    if (path.startsWith(`${current.annotations}/`)) {
      return `${selected.annotations}/${path.slice(current.annotations.length + 1)}`;
    }
    return path;
  };
  const bundle = structuredClone(reviewBundle());
  for (const candidate of bundle.candidates) {
    candidate.record_path = rewrite(candidate.record_path);
    candidate.paths = candidate.paths.map(rewrite);
  }
  return {
    bundle,
    contents: new Map(
      [...contentFixture()].map(([coordinate, value]) => {
        const separator = coordinate.lastIndexOf("@");
        return [
          `${rewrite(coordinate.slice(0, separator))}${coordinate.slice(separator)}`,
          value,
        ];
      }),
    ),
    files: defaultFiles.map((file) => ({
      ...file,
      filename: rewrite(file.filename),
    })),
    siteConfig: ORINOCO_CONFIG.replace(
      "site-specific/metadata/records",
      recordRoot,
    ),
  };
}

function client(options: ClientOptions = {}): GitHubClient {
  const bundle = options.bundle ?? reviewBundle();
  const archive = reviewBundleArchive(bundle);
  const content = options.contents ?? contentFixture();
  const siteConfig =
    "siteConfig" in options ? options.siteConfig : ORINOCO_CONFIG;
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
    contents: async (_repository: string, requests: ContentRequest[]) => {
      options.contentRequests?.push(
        requests.map((request) => ({ ...request })),
      );
      return new Map(
        requests.map((request) => [
          request.key,
          request.path === "orinoco.yaml" && request.ref === BASE_SHA
            ? (siteConfig ?? null)
            : (content.get(`${request.path}@${request.ref}`) ?? null),
        ]),
      );
    },
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

function expectOnlySiteConfig(requests: ContentRequest[][]): void {
  expect(requests).toEqual([
    [{ key: "site-config", path: "orinoco.yaml", ref: BASE_SHA }],
  ]);
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
        "site-specific/metadata/records/example/first.yaml",
        "site-specific/metadata/records/example/second.yaml",
      ],
    );
    expect(result.candidates[0]?.before).toContain("Original first");
    expect(result.candidates[0]?.after).toContain("Current first");
    expect(result.candidates[1]?.operation).toBe("add");
    expect(result.review_service_origin).toBe("https://review.example");
    expect(result.review_site_url).toBe("https://site.example/review/");
  });

  it.each([
    ["legacy", "metadata/records"],
    ["custom", ".site-data/catalog/records"],
    ["trailing slash", ".site-data/catalog/records/"],
  ])("accepts %s configured metadata roots", async (_label, recordRoot) => {
    const result = await loadReviewProposal(
      client(rootedOptions(recordRoot)),
      "example/site",
      42,
      ARTIFACT_ID,
    );

    expect(result.candidates[0]?.record_path).toBe(
      `${metadataRoots(recordRoot).records}/example/first.yaml`,
    );
  });

  it("rejects out-of-root artifact paths before loading record blobs", async () => {
    const bundle = reviewBundle();
    const first = bundle.candidates[0];
    if (first === undefined) throw new Error("missing fixture candidate");
    first.record_path = "other/metadata/records/example/first.yaml";
    first.paths = [
      first.record_path,
      "other/metadata/overlays/annotations/example/first.yaml",
    ];
    const contentRequests: ContentRequest[][] = [];

    await expect(
      loadReviewProposal(
        client({ bundle, contentRequests }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("Candidate record_path is invalid");
    expectOnlySiteConfig(contentRequests);
  });

  it.each([
    {
      config: null,
      expected: "has no orinoco.yaml",
      label: "a missing config",
    },
    {
      config: "contract_version: [\n",
      expected: "orinoco.yaml is invalid",
      label: "malformed YAML",
    },
    {
      config: `${ORINOCO_CONFIG}contract_version: 2\n`,
      expected: "orinoco.yaml is invalid",
      label: "duplicate keys",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "base_url: https://site.example/",
        "base_url: !untrusted https://site.example/",
      ),
      expected: "orinoco.yaml is invalid",
      label: "an unknown YAML tag",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "name: Example site",
        "name: &site-name Example site\n  copied_name: *site-name",
      ),
      expected: "orinoco.yaml is invalid",
      label: "a YAML alias",
    },
    {
      config: `${ORINOCO_CONFIG}---\ncontract_version: 2\n`,
      expected: "orinoco.yaml is invalid",
      label: "multiple YAML documents",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "contract_version: 2",
        "contract_version: 1",
      ),
      expected: "contract is unsupported",
      label: "an unsupported contract",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "paths:\n  records: site-specific/metadata/records",
        "paths:\n  records: ../escape",
      ),
      expected: "paths.records is unsafe",
      label: "an escaping metadata root",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "paths:\n  records: site-specific/metadata/records",
        "paths: []",
      ),
      expected: "paths is not a mapping",
      label: "a non-mapping path configuration",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "https://site.example/",
        "http://site.example/",
      ),
      expected: "site.base_url is unsafe",
      label: "an unsafe site URL",
    },
    {
      config: ORINOCO_CONFIG.replace("https://site.example/", "/project/"),
      expected: "site.base_url is unsafe",
      label: "a relative site URL",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "base_url: https://site.example/",
        'base_url: "https://site.exa\\tmple/"',
      ),
      expected: "site.base_url is unsafe",
      label: "a control character in the site URL",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "https://review.example/",
        "https://review.example/api/",
      ),
      expected: "site.curation_service is not an origin",
      label: "a non-origin curation service",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "https://review.example/",
        "https://review.example/./",
      ),
      expected: "site.curation_service is not an origin",
      label: "a normalized curation-service path",
    },
    {
      config: ORINOCO_CONFIG.replace(
        "https://review.example/",
        "http://review.example/",
      ),
      expected: "site.curation_service is not an origin",
      label: "an unsafe curation service",
    },
  ])("rejects $label at the metadata base", async ({ config, expected }) => {
    await expect(
      loadReviewProposal(
        client({ siteConfig: config }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow(expected);
  });

  it("appends the review route to a normalized site base path", async () => {
    const result = await loadReviewProposal(
      client({
        siteConfig: ORINOCO_CONFIG.replace(
          "https://site.example/",
          "https://site.example/project",
        ).replace("https://review.example/", "https://review.example"),
      }),
      "example/site",
      42,
      ARTIFACT_ID,
    );

    expect(result.review_site_url).toBe("https://site.example/project/review/");
    expect(result.review_service_origin).toBe("https://review.example");
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

  it("rejects proposal writes outside the metadata roots before loading record blobs", async () => {
    for (const file of [
      { filename: ".github/workflows/pwn.yml", status: "added" },
      { filename: "orinoco.yaml", status: "modified" },
    ]) {
      const contentRequests: ContentRequest[][] = [];
      await expect(
        loadReviewProposal(
          client({ contentRequests, files: [file] }),
          "example/site",
          42,
          ARTIFACT_ID,
        ),
      ).rejects.toThrow("outside the metadata roots");
      expectOnlySiteConfig(contentRequests);
    }
  });

  it("rejects oversized proposal paths before loading record blobs", async () => {
    const contentRequests: ContentRequest[][] = [];
    const files = Array.from({ length: MAX_REVIEW_CANDIDATES }, (_, index) => [
      {
        filename: `site-specific/metadata/records/example/extra-${index}.yaml`,
        status: "added",
      },
      {
        filename: `site-specific/metadata/overlays/annotations/example/extra-${index}.yaml`,
        status: "added",
      },
    ]).flat();
    files.push({
      filename:
        "site-specific/metadata/overlays/annotations/example/overflow.yaml",
      status: "added",
    });
    expect(files).toHaveLength(MAX_REVIEW_PATHS + 1);

    await expect(
      loadReviewProposal(
        client({ contentRequests, files }),
        "example/site",
        42,
        ARTIFACT_ID,
      ),
    ).rejects.toThrow("unsupported number of candidate records");
    expectOnlySiteConfig(contentRequests);
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
    deletedAddition.delete(
      `site-specific/metadata/records/example/second.yaml@${HEAD_SHA}`,
    );
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
      `site-specific/metadata/records/example/first.yaml@${HEAD_SHA}`,
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
        `site-specific/metadata/records/example/second.yaml@${BASE_SHA}`,
        "pid: example:second\ntitle: Initial second\n",
      ],
      [
        `site-specific/metadata/records/example/second.yaml@${HEAD_SHA}`,
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

  it.each(["yml", "YAML"])(
    "accepts .%s paths using the same candidate path policy",
    async (suffix) => {
      const bundle = reviewBundle();
      bundle.candidates = bundle.candidates.slice(0, 1);
      const first = bundle.candidates[0];
      if (first === undefined) throw new Error("missing fixture candidate");
      first.record_path = `site-specific/metadata/records/example/first.${suffix}`;
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
    },
  );
});
