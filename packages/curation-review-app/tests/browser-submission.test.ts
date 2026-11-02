// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import {
  AUTHORIZATION_PATH,
  SUBMISSION_PATH,
  uploadSubmission,
  type SubmissionAccess,
} from "../shared/submission";

const base = "a".repeat(40);
const input = {
  operation: "shacl",
  bundle: { source_commit: base, private_record: "fixture-only" },
};
const access: SubmissionAccess = {
  scope_proof: "scope-proof",
  scope: {
    repositories: ["owner/website", "owner/metadata"].map((name, index) => ({
      name,
      id: index + 1,
      ownerId: 3,
      defaultBranch: "main",
      baseCommit: base,
      worker: `owner/package/.github/workflows/orinoco.yml@${base}`,
    })),
    source: { repository: "owner/website", commit: base },
    metadata: { repository: "owner/metadata", commit: base },
  },
  credentials: Object.fromEntries(
    ["owner/website", "owner/metadata"].map((name) => [
      name,
      {
        token: `test-token-${name}`,
        expires_at: "2999-01-01T00:00:00Z",
      },
    ]),
  ),
};

/** A small Git data API fixture: commits are immutable, refs select commits. */
function github() {
  let sequence = 0;
  const files = new Map<string, Record<string, string>>([[base, {}]]);
  const refs = new Map<string, string>();
  let lostDispatch = false;
  const calls: Array<{
    repository: string;
    path: string;
    method: string;
    body: any;
  }> = [];
  const fetcher = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const parsed = new URL(String(url));
    expect(parsed.origin).toBe("https://api.github.com");
    const match = /^\/repos\/([^/]+\/[^/]+)(\/.*)$/.exec(parsed.pathname)!;
    const repository = match[1]!;
    const path = decodeURIComponent(match[2]!);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ repository, path, method, body });
    expect(new Headers(init?.headers).get("Authorization")).toBe(
      `Bearer test-token-${repository}`,
    );
    const next = () => (++sequence).toString(16).padStart(40, "0");
    if (path.startsWith("/git/ref/heads/")) {
      const sha = refs.get(
        `${repository}/${path.slice("/git/ref/heads/".length)}`,
      );
      return sha
        ? Response.json({ object: { sha } })
        : new Response(null, { status: 404 });
    }
    if (path.startsWith("/contents/")) {
      expect(new Headers(init?.headers).get("Accept")).toBe(
        "application/vnd.github.raw+json",
      );
      const ref = parsed.searchParams.get("ref")!;
      const sha = refs.get(`${repository}/${ref}`) ?? ref;
      const content = files.get(sha)?.[path.slice("/contents/".length)];
      return content === undefined
        ? new Response(null, { status: 404 })
        : new Response(content);
    }
    if (path.startsWith("/git/commits/"))
      return Response.json({
        tree: { sha: path.slice("/git/commits/".length) },
      });
    if (path === "/git/trees") {
      const sha = next();
      files.set(sha, {
        ...files.get(body.base_tree),
        ...Object.fromEntries(
          body.tree.map((entry: any) => [entry.path, entry.content]),
        ),
      });
      return Response.json({ sha });
    }
    if (path === "/git/commits") {
      const sha = next();
      files.set(sha, files.get(body.tree)!);
      return Response.json({ sha });
    }
    if (path === "/git/refs") {
      refs.set(
        `${repository}/${body.ref.slice("refs/heads/".length)}`,
        body.sha,
      );
      return Response.json({});
    }
    if (path.startsWith("/git/refs/heads/")) {
      expect(body.force).toBe(false);
      refs.set(
        `${repository}/${path.slice("/git/refs/heads/".length)}`,
        body.sha,
      );
      return Response.json({});
    }
    if (path === "/dispatches") {
      if (lostDispatch) {
        lostDispatch = false;
        throw new TypeError("Lost response after GitHub accepted dispatch");
      }
      return new Response(null, { status: 204 });
    }
    throw new Error(`Unexpected fixture request: ${method} ${path}`);
  });
  return {
    fetcher,
    calls,
    files,
    refs,
    loseDispatch: () => {
      lostDispatch = true;
    },
  };
}

describe("downstream submission", () => {
  it("uploads private input to metadata and sends only coordinates to authentication", async () => {
    const api = github();
    const authorize = vi.fn(async () => ({
      authorization: "signed-submission",
    }));
    const result = await uploadSubmission(
      input,
      access,
      { authorize },
      api.fetcher,
    );
    expect(result.repository).toBe("owner/metadata");
    expect(authorize).toHaveBeenCalledWith({
      scope_proof: "scope-proof",
      input_repository: "owner/metadata",
      input_commit: result.input_commit,
    });
    const websiteWrites = api.calls.filter(
      (call) =>
        call.repository === "owner/website" && call.path === "/git/trees",
    );
    expect(websiteWrites).toHaveLength(1);
    expect(websiteWrites[0]!.body.tree[0].path).toBe(AUTHORIZATION_PATH);
    expect(JSON.stringify(websiteWrites)).not.toContain("fixture-only");
    expect(api.files.get(result.input_commit)?.[SUBMISSION_PATH]).toContain(
      "fixture-only",
    );
    expect(api.calls.at(-1)).toMatchObject({
      repository: "owner/metadata",
      path: "/dispatches",
      body: { client_payload: { submission: result.branch } },
    });
  });

  it("resumes the same input after a lost response and advancing default branch", async () => {
    const api = github();
    const authorize = vi.fn(async () => ({
      authorization: "signed-submission",
    }));
    api.loseDispatch();
    await expect(
      uploadSubmission(input, access, { authorize }, api.fetcher),
    ).rejects.toThrow("Lost response");
    const refsBefore = new Map(api.refs);
    const advanced = structuredClone(access);
    advanced.scope.repositories.forEach((repo) => {
      repo.baseCommit = "b".repeat(40);
    });
    await uploadSubmission(input, advanced, { authorize }, api.fetcher);
    expect(api.refs).toEqual(refsBefore);
    expect(authorize).toHaveBeenCalledTimes(1);
    expect(api.calls.filter((call) => call.path === "/git/refs")).toHaveLength(
      2,
    );
  });

  it("does not upload anything if a required repository credential is absent", async () => {
    const api = github();
    const incomplete = {
      ...access,
      credentials: { "owner/metadata": access.credentials["owner/metadata"]! },
    };
    await expect(
      uploadSubmission(input, incomplete, { authorize: vi.fn() }, api.fetcher),
    ).rejects.toThrow("Sign in again");
    expect(api.fetcher).not.toHaveBeenCalled();
  });

  it("round-trips input above GitHub's 1 MiB JSON-content limit", async () => {
    const api = github();
    const large = {
      ...input,
      bundle: { ...input.bundle, private_record: "x".repeat(1024 * 1024 + 1) },
    };
    const result = await uploadSubmission(
      large,
      access,
      {
        authorize: vi.fn(async () => ({ authorization: "signed-submission" })),
      },
      api.fetcher,
    );
    expect(
      api.files.get(result.input_commit)?.[SUBMISSION_PATH]?.length,
    ).toBeGreaterThan(1024 * 1024);
  });
});
