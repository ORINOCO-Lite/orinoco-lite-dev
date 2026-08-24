import { strToU8, zipSync } from "fflate";
import { describe, expect, it, vi } from "vitest";
import {
  EDITOR_INPUT_PATHS,
  loadExactHeadEditorInput,
  MAX_EDITOR_INPUT_BYTES,
  parseEditorInputArchive,
  type EditorInputGitHub,
} from "../functions/lib/editor-input";

const HEAD = "a".repeat(40);
const NOW = Date.parse("2026-08-24T18:00:00Z");
const ARTIFACT_ID = 123;
const RUN_ID = 456;
const TRUSTED_SHA = "b".repeat(40);

function archive(sourceCommit: string = HEAD): Uint8Array {
  return zipSync({
    "edit/config.json": strToU8('{"app_name":"Example"}\n'),
    "edit/data/record-sources.json": strToU8(
      JSON.stringify({
        format: "orinoco-static-record-sources",
        records: [],
        source_commit: sourceCommit,
        version: 2,
      }),
    ),
    "edit/records.ttl": strToU8("<urn:example> a <urn:Thing> .\n"),
  });
}

function artifact(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    created_at: "2026-08-24T17:00:00Z",
    expired: false,
    expires_at: "2026-09-07T17:00:00Z",
    id: ARTIFACT_ID,
    name: `orinoco-shacl-vue-input-${HEAD}`,
    size_in_bytes: archive().byteLength,
    workflow_run: { head_sha: TRUSTED_SHA, id: RUN_ID },
    ...overrides,
  };
}

function run(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    conclusion: "success",
    event: "workflow_dispatch",
    head_branch: "main",
    head_sha: TRUSTED_SHA,
    id: RUN_ID,
    name: "Materialize SHACL Vue proposal",
    path: ".github/workflows/shacl-vue-proposal.yml",
    repository: { full_name: "example/site" },
    run_attempt: 1,
    status: "completed",
    ...overrides,
  };
}

function client(
  options: {
    artifacts?: unknown[];
    archive?: Uint8Array;
    run?: Record<string, unknown>;
  } = {},
): EditorInputGitHub & {
  artifactArchive: ReturnType<typeof vi.fn>;
  json: ReturnType<typeof vi.fn>;
} {
  const artifacts = options.artifacts ?? [artifact()];
  return {
    artifactArchive: vi.fn(async () => options.archive ?? archive()),
    json: vi.fn(async (path: string) =>
      path.includes("/actions/artifacts?")
        ? { artifacts, total_count: artifacts.length }
        : (options.run ?? run()),
    ),
    repository: vi.fn(async () => ({
      defaultBranch: "main",
      fullName: "example/site",
    })),
  };
}

function centralDirectory(archiveBytes: Uint8Array): number {
  const data = new DataView(
    archiveBytes.buffer,
    archiveBytes.byteOffset,
    archiveBytes.byteLength,
  );
  let offset = archiveBytes.length - 22;
  while (data.getUint32(offset, true) !== 0x06054b50) offset -= 1;
  return data.getUint32(offset + 16, true);
}

describe("exact-head SHACL Vue input", () => {
  it("locates the named artifact, verifies its successful run, and loads exact files", async () => {
    const github = client();

    const result = await loadExactHeadEditorInput(
      github,
      "example/site",
      HEAD,
      NOW,
    );

    expect(result.artifactId).toBe(ARTIFACT_ID);
    expect(result.workflowRunId).toBe(RUN_ID);
    expect(result.sourceCommit).toBe(HEAD);
    expect(Object.keys(result.files).sort()).toEqual(
      [...EDITOR_INPUT_PATHS].sort(),
    );
    expect(github.json).toHaveBeenNthCalledWith(
      1,
      `/repos/example/site/actions/artifacts?name=orinoco-shacl-vue-input-${HEAD}&per_page=100&page=1`,
    );
    expect(github.json).toHaveBeenNthCalledWith(
      2,
      `/repos/example/site/actions/runs/${RUN_ID}`,
    );
    expect(github.artifactArchive).toHaveBeenCalledWith(
      "example/site",
      ARTIFACT_ID,
    );
  });

  it("selects the newest unexpired exact-name artifact deterministically", async () => {
    const older = artifact({
      created_at: "2026-08-23T17:00:00Z",
      id: 100,
      workflow_run: { head_sha: TRUSTED_SHA, id: 200 },
    });
    const github = client({ artifacts: [older, artifact()] });

    await expect(
      loadExactHeadEditorInput(github, "example/site", HEAD, NOW),
    ).resolves.toMatchObject({ artifactId: ARTIFACT_ID });
  });

  it("rejects expired, mismatched-producer, and unsuccessful artifacts", async () => {
    await expect(
      loadExactHeadEditorInput(
        client({ artifacts: [artifact({ expired: true })] }),
        "example/site",
        HEAD,
        NOW,
      ),
    ).rejects.toThrow("No unexpired exact-head");

    await expect(
      loadExactHeadEditorInput(
        client({
          artifacts: [
            artifact({
              workflow_run: { head_sha: "c".repeat(40), id: RUN_ID },
            }),
          ],
        }),
        "example/site",
        HEAD,
        NOW,
      ),
    ).rejects.toThrow("successful exact-head run");

    await expect(
      loadExactHeadEditorInput(
        client({ run: run({ conclusion: "failure" }) }),
        "example/site",
        HEAD,
        NOW,
      ),
    ).rejects.toThrow("successful exact-head run");
  });

  it("accepts only the reviewed default-branch workflow and trusted events", async () => {
    for (const untrustedRun of [
      run({ path: ".github/workflows/untrusted.yml" }),
      run({ head_branch: "feature" }),
      run({ event: "pull_request" }),
    ]) {
      await expect(
        loadExactHeadEditorInput(
          client({ run: untrustedRun }),
          "example/site",
          HEAD,
          NOW,
        ),
      ).rejects.toThrow("successful exact-head run");
    }

    await expect(
      loadExactHeadEditorInput(
        client({
          artifacts: [
            artifact({ workflow_run: { head_sha: HEAD, id: RUN_ID } }),
          ],
          run: run({ event: "push", head_sha: HEAD }),
        }),
        "example/site",
        HEAD,
        NOW,
      ),
    ).resolves.toMatchObject({ headSha: HEAD });

    await expect(
      loadExactHeadEditorInput(
        client({ run: run({ event: "push" }) }),
        "example/site",
        HEAD,
        NOW,
      ),
    ).rejects.toThrow("successful exact-head run");
  });

  it("accepts exactly the three editor binding files", () => {
    expect(parseEditorInputArchive(archive(), HEAD).sourceCommit).toBe(HEAD);

    const missing = zipSync({
      "edit/config.json": strToU8("{}"),
      "edit/records.ttl": strToU8(""),
    });
    expect(() => parseEditorInputArchive(missing, HEAD)).toThrow(
      "exactly three ordinary files",
    );

    const extra = zipSync({
      "edit/config.json": strToU8("{}"),
      "edit/data/record-sources.json": strToU8("{}"),
      "edit/index.html": strToU8("untrusted shell"),
      "edit/records.ttl": strToU8(""),
    });
    expect(() => parseEditorInputArchive(extra, HEAD)).toThrow(
      "exactly three ordinary files",
    );
  });

  it("rejects non-regular entries and declared uncompressed overflow", () => {
    const symlink = archive();
    const directory = centralDirectory(symlink);
    const data = new DataView(
      symlink.buffer,
      symlink.byteOffset,
      symlink.byteLength,
    );
    data.setUint16(directory + 4, (3 << 8) | 20, true);
    data.setUint32(directory + 38, (0o120777 << 16) >>> 0, true);
    expect(() => parseEditorInputArchive(symlink, HEAD)).toThrow(
      "regular files",
    );

    const oversized = archive();
    const oversizedDirectory = centralDirectory(oversized);
    new DataView(
      oversized.buffer,
      oversized.byteOffset,
      oversized.byteLength,
    ).setUint32(oversizedDirectory + 24, MAX_EDITOR_INPUT_BYTES + 1, true);
    expect(() => parseEditorInputArchive(oversized, HEAD)).toThrow(
      "unsupported entry",
    );
  });

  it("requires the generated catalog to bind the exact source commit", () => {
    expect(() =>
      parseEditorInputArchive(archive("b".repeat(40)), HEAD),
    ).toThrow("exact source commit");
  });
});
