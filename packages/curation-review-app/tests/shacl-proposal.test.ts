import { describe, expect, it, vi } from "vitest";
import type {
  ShaclProposalRequest,
  ShaclReviewBundle,
} from "../shared/contracts";
import { GitHubClient } from "../functions/lib/github";
import { createShaclProposal } from "../functions/lib/shacl-proposal";
import {
  SHACL_BUNDLE_PATH,
  serializeShaclReviewBundle,
} from "../functions/lib/shacl";

const HEAD = "a".repeat(40);
const COMMIT = "b".repeat(40);

function bundle(): ShaclReviewBundle {
  return {
    format: "orinoco-shacl-review-bundle",
    records: [
      {
        pid: "example:one",
        rdf_turtle:
          '<https://example.test/one> <https://example.test/p> "é" .\n',
        schema_type: "example:Thing",
        source_path: "metadata/records/Thing/one.yaml",
        source_sha256: "c".repeat(64),
      },
    ],
    source_commit: HEAD,
    version: 2,
  };
}

function request(target: ShaclProposalRequest["target"]): ShaclProposalRequest {
  return {
    bundle: bundle(),
    format: "orinoco-lite-shacl-proposal-v1",
    repository: "example/site",
    target,
  };
}

function pathResponse(): Response {
  return Response.json({ data: { repository: { object: null } } });
}

function commitResponse(branch: string): Response {
  return Response.json({
    data: {
      createCommitOnBranch: {
        commit: {
          oid: COMMIT,
          url: `https://github.com/example/site/commit/${COMMIT}`,
        },
        ref: {
          name: branch,
          prefix: "refs/heads/",
          target: { oid: COMMIT },
        },
      },
    },
  });
}

function commonResponse(url: string): Response | null {
  if (url.endsWith("/user")) {
    return Response.json({ id: 1, login: "octocat" });
  }
  if (url.endsWith("/collaborators/octocat/permission")) {
    return Response.json({ permission: "write" });
  }
  return null;
}

describe("attributed existing-PR SHACL handoff", () => {
  it("appends one exact normal bundle file at the current same-repo draft head", async () => {
    const fetchMock = vi.fn(
      async (input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        const common = commonResponse(url);
        if (common !== null) return common;
        if (url.endsWith("/pulls/42")) {
          return Response.json({
            base: { ref: "main", repo: { full_name: "example/site" } },
            draft: true,
            head: {
              ref: "curation/edit",
              repo: { full_name: "example/site" },
              sha: HEAD,
            },
            html_url: "https://github.com/example/site/pull/42",
            number: 42,
            state: "open",
          });
        }
        if (url === "https://api.github.com/graphql") {
          const graphql = JSON.parse(String(init?.body)) as {
            query: string;
            variables: Record<string, unknown>;
          };
          if (graphql.query.includes("query ExactPath")) {
            expect(graphql.variables).toMatchObject({
              expression: `${HEAD}:${SHACL_BUNDLE_PATH}`,
            });
            return pathResponse();
          }
          expect(graphql.query).toContain("CreateExactFileCommit");
          const commit = graphql.variables.input as Record<string, unknown>;
          expect(commit).not.toHaveProperty("author");
          expect(commit).not.toHaveProperty("committer");
          expect(commit).toMatchObject({
            branch: {
              branchName: "curation/edit",
              repositoryNameWithOwner: "example/site",
            },
            expectedHeadOid: HEAD,
          });
          const changes = commit.fileChanges as {
            additions: Array<{ contents: string; path: string }>;
          };
          expect(changes.additions).toHaveLength(1);
          expect(changes.additions[0]?.path).toBe(SHACL_BUNDLE_PATH);
          expect(
            Array.from(atob(changes.additions[0]?.contents ?? ""), (item) =>
              item.charCodeAt(0),
            ),
          ).toEqual(Array.from(serializeShaclReviewBundle(bundle())));
          return commitResponse("curation/edit");
        }
        throw new Error(`Unexpected request: ${url}`);
      },
    );

    await expect(
      createShaclProposal(
        new GitHubClient("ghu_curator", fetchMock),
        request({
          expected_head_sha: HEAD,
          kind: "pull_request",
          pull_request: 42,
        }),
      ),
    ).resolves.toEqual({
      commit_sha: COMMIT,
      commit_url: `https://github.com/example/site/commit/${COMMIT}`,
      pull_request: 42,
      pull_request_url: "https://github.com/example/site/pull/42",
    });
    for (const call of fetchMock.mock.calls) {
      expect(new Headers(call[1]?.headers).get("authorization")).toBe(
        "Bearer ghu_curator",
      );
    }
  });

  it("rejects a changed PR head before creating a commit", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      const common = commonResponse(url);
      if (common !== null) return common;
      return Response.json({
        base: { ref: "main", repo: { full_name: "example/site" } },
        draft: true,
        head: {
          ref: "curation/edit",
          repo: { full_name: "example/site" },
          sha: "d".repeat(40),
        },
        html_url: "https://github.com/example/site/pull/42",
        number: 42,
        state: "open",
      });
    });
    await expect(
      createShaclProposal(
        new GitHubClient("ghu_curator", fetchMock),
        request({
          expected_head_sha: HEAD,
          kind: "pull_request",
          pull_request: 42,
        }),
      ),
    ).rejects.toMatchObject({ code: "stale_shacl_proposal", status: 409 });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("never replaces an already-pending fixed-path handoff", async () => {
    const fetchMock = vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      const common = commonResponse(url);
      if (common !== null) return common;
      if (url.endsWith("/pulls/42")) {
        return Response.json({
          base: { ref: "main", repo: { full_name: "example/site" } },
          draft: true,
          head: {
            ref: "curation/edit",
            repo: { full_name: "example/site" },
            sha: HEAD,
          },
          html_url: "https://github.com/example/site/pull/42",
          number: 42,
          state: "open",
        });
      }
      return Response.json({
        data: { repository: { object: { __typename: "Blob" } } },
      });
    });
    await expect(
      createShaclProposal(
        new GitHubClient("ghu_curator", fetchMock),
        request({
          expected_head_sha: HEAD,
          kind: "pull_request",
          pull_request: 42,
        }),
      ),
    ).rejects.toMatchObject({ code: "shacl_handoff_pending", status: 409 });
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });
});

interface StandaloneOptions {
  cleanupFails?: boolean;
  commitFails?: boolean;
  pullFails?: boolean;
}

function standaloneFetch(options: StandaloneOptions = {}): {
  branch: () => string;
  fetchMock: (
    input: string | URL | Request,
    init?: RequestInit,
  ) => Promise<Response>;
  requests: Array<{ body: unknown; method: string; url: string }>;
} {
  let branch = "";
  const requests: Array<{ body: unknown; method: string; url: string }> = [];
  const fetchMock = vi.fn(
    async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      let body: unknown = null;
      if (typeof init?.body === "string") body = JSON.parse(init.body);
      requests.push({ body, method: init?.method ?? "GET", url });
      const common = commonResponse(url);
      if (common !== null) return common;
      if (url === "https://api.github.com/repos/example/site") {
        return Response.json({
          default_branch: "main",
          full_name: "example/site",
        });
      }
      if (url.endsWith("/branches/main")) {
        return Response.json({ commit: { sha: HEAD }, name: "main" });
      }
      if (url === "https://api.github.com/graphql") {
        const graphql = body as {
          query: string;
          variables: Record<string, unknown>;
        };
        if (graphql.query.includes("query ExactPath")) return pathResponse();
        if (options.commitFails) {
          return Response.json({ errors: [{ type: "UNPROCESSABLE" }] });
        }
        return commitResponse(branch);
      }
      if (url.endsWith("/git/refs") && init?.method === "POST") {
        const reference = body as { ref: string; sha: string };
        branch = reference.ref.slice("refs/heads/".length);
        return Response.json({
          object: { sha: reference.sha, type: "commit" },
          ref: reference.ref,
        });
      }
      if (url.endsWith("/pulls") && init?.method === "POST") {
        if (options.pullFails) return Response.json({}, { status: 422 });
        const pull = body as Record<string, unknown>;
        expect(String(pull.body)).toContain(
          "Do not merge this pull request while the temporary path exists",
        );
        expect(String(pull.body)).toContain("may remain");
        return Response.json({
          base: { ref: "main", repo: { full_name: "example/site" } },
          draft: true,
          head: {
            ref: branch,
            repo: { full_name: "example/site" },
            sha: COMMIT,
          },
          html_url: "https://github.com/example/site/pull/43",
          number: 43,
          state: "open",
        });
      }
      if (url.includes("/git/refs/heads/") && init?.method === "DELETE") {
        return options.cleanupFails
          ? Response.json({}, { status: 500 })
          : new Response(null, { status: 204 });
      }
      throw new Error(`Unexpected request: ${url}`);
    },
  );
  return { branch: () => branch, fetchMock, requests };
}

describe("standalone SHACL proposal", () => {
  it("branches only from the freshly read default head and opens a draft PR", async () => {
    const mock = standaloneFetch();
    const result = await createShaclProposal(
      new GitHubClient("ghu_curator", mock.fetchMock),
      request({ kind: "standalone" }),
    );
    expect(mock.branch()).toMatch(
      /^curation\/shacl-vue-a{12}-[A-Za-z0-9_-]{12}$/,
    );
    expect(result).toMatchObject({
      commit_sha: COMMIT,
      pull_request: 43,
      pull_request_url: "https://github.com/example/site/pull/43",
    });
    const reference = mock.requests.find(
      (item) => item.url.endsWith("/git/refs") && item.method === "POST",
    );
    expect(reference?.body).toMatchObject({ sha: HEAD });
    expect(mock.requests.some((item) => item.method === "DELETE")).toBe(false);
  });

  it("rejects a stale default head before creating a branch", async () => {
    const mock = standaloneFetch();
    const stale = request({ kind: "standalone" });
    stale.bundle.source_commit = "d".repeat(40);
    await expect(
      createShaclProposal(
        new GitHubClient("ghu_curator", mock.fetchMock),
        stale,
      ),
    ).rejects.toMatchObject({ code: "stale_shacl_proposal", status: 409 });
    expect(mock.requests.some((item) => item.url.endsWith("/git/refs"))).toBe(
      false,
    );
  });

  it.each([
    ["handoff commit", { commitFails: true }],
    ["draft PR", { pullFails: true }],
  ])(
    "deletes the new branch when %s creation fails",
    async (_label, options) => {
      const mock = standaloneFetch(options);
      await expect(
        createShaclProposal(
          new GitHubClient("ghu_curator", mock.fetchMock),
          request({ kind: "standalone" }),
        ),
      ).rejects.toBeInstanceOf(Error);
      expect(
        mock.requests.some(
          (item) =>
            item.method === "DELETE" &&
            item.url.includes("/git/refs/heads/curation/shacl-vue-"),
        ),
      ).toBe(true);
    },
  );

  it("returns the stranded ref diagnostic when bounded cleanup also fails", async () => {
    const mock = standaloneFetch({ cleanupFails: true, pullFails: true });
    await expect(
      createShaclProposal(
        new GitHubClient("ghu_curator", mock.fetchMock),
        request({ kind: "standalone" }),
      ),
    ).rejects.toMatchObject({
      code: "shacl_cleanup_failed",
      message: expect.stringContaining("Remove that branch before retrying"),
      status: 502,
    });
  });
});
