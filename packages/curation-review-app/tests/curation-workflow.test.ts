import { describe, expect, it, vi } from "vitest";
import { curationWorkflowAccess } from "../functions/lib/curation-workflow";
import { AppAuthentication } from "../functions/lib/workflow-access";
import { submission } from "./fixtures";
import type { Env } from "../functions/lib/pages";

const base = "a".repeat(40);
const meta = "b".repeat(40);
const identity = {
  repository: "owner/site",
  repository_id: "1",
  ref: "refs/heads/main",
  workflow_sha: base,
  workflow_ref:
    "owner/site/.github/workflows/curation-review.yml@refs/heads/main",
  event_name: "workflow_dispatch",
  actor: "curator",
  actor_id: "2",
  run_id: "3",
  run_attempt: "1",
  check_run_id: "4",
};
function authentication(
  options: {
    stale?: boolean;
    permission?: string;
    validated?: boolean;
    finalize?: boolean;
    edited?: boolean;
  } = {},
) {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    const path = url.pathname;
    const pin = (ref: string | null) =>
      ref === "c".repeat(40)
        ? "d".repeat(40)
        : ref === "e".repeat(40)
          ? "f".repeat(40)
          : meta;
    let result: unknown;
    if (path.endsWith("/permission"))
      result = {
        permission: options.permission ?? "write",
        user: { id: 2, login: "curator" },
      };
    else if (path.endsWith("/branches/main"))
      result = {
        name: "main",
        commit: {
          sha: path.includes("/metadata/")
            ? options.stale
              ? "c".repeat(40)
              : meta
            : base,
        },
      };
    else if (path.includes("/git/trees/"))
      result = {
        truncated: false,
        tree: [
          {
            path: "site-specific",
            mode: "160000",
            type: "commit",
            sha: pin(path.split("/").at(-1)!),
          },
        ],
      };
    else if (path.endsWith("/contents/site-specific"))
      result = {
        path: "site-specific",
        sha: pin(url.searchParams.get("ref")),
        submodule_git_url: "https://github.com/owner/metadata.git",
      };
    else if (path.endsWith("/actions/runs/3"))
      result = {
        path: ".github/workflows/curation-review.yml",
        head_sha: base,
        status: "in_progress",
        run_attempt: 1,
        event: options.finalize ? "issue_comment" : "workflow_dispatch",
        repository: { id: 1 },
        actor: { id: 2, login: "curator" },
      };
    else if (path.endsWith("/jobs"))
      result = {
        jobs: [
          {
            check_run_url:
              "https://api.github.com/repos/owner/site/check-runs/4",
            steps: options.validated
              ? [
                  {
                    name: "Validate and record the composed adapter result",
                    status: "completed",
                    conclusion: "success",
                  },
                ]
              : [],
          },
        ],
      };
    else if (path.endsWith("/issues/comments/9")) {
      const body = {
        ...submission(),
        repository: "owner/site",
        pull_request: 7,
        proposal_sha: "c".repeat(40),
        head_sha: "e".repeat(40),
        metadata: {
          repository: "owner/metadata",
          pull_request: 8,
          proposal_sha: "d".repeat(40),
          head_sha: "f".repeat(40),
        },
      };
      result = {
        user: { id: 2, login: "curator" },
        created_at: "now",
        updated_at: options.edited ? "later" : "now",
        issue_url: "https://api.github.com/repos/owner/site/issues/7",
        body: "/curation submit\n```json\n" + JSON.stringify(body) + "\n```",
      };
    } else if (path.endsWith("/pulls/7"))
      result = {
        state: "open",
        draft: true,
        head: { repo: { full_name: "owner/site" }, sha: "e".repeat(40) },
        base: { sha: base, ref: "main" },
      };
    else if (path.endsWith("/pulls/8"))
      result = {
        state: "open",
        draft: true,
        head: {
          repo: { full_name: "owner/metadata" },
          sha: options.stale ? "0".repeat(40) : "f".repeat(40),
        },
        base: { sha: meta, ref: "main" },
      };
    else if (path === "/repos/owner/site")
      result = { id: 1, default_branch: "main" };
    else if (path === "/repos/owner/metadata")
      result = { id: 5, default_branch: "main" };
    else throw new Error(`Unexpected GitHub read: ${path}`);
    return new Response(JSON.stringify(result), { status: 200 });
  });
  const auth = new AppAuthentication({} as Env, fetcher);
  auth.token = vi.fn(async () => ({
    token: "test-token",
    expires_at: "later",
  }));
  auth.revoke = vi.fn(async () => {});
  return auth;
}
const request = {
  repository: "owner/site",
  head: base,
  write: false,
  comment_id: null,
};
describe("source-adapter workflow access", () => {
  it("derives metadata access from the trusted website gitlink", async () => {
    const auth = authentication();
    expect(
      await curationWorkflowAccess({} as Env, identity, request, auth),
    ).toMatchObject({ repository: "owner/metadata", head: meta });
    expect(auth.token).toHaveBeenCalledWith("owner/metadata");
    expect(auth.token).not.toHaveBeenCalledWith(
      "owner/metadata",
      true,
      false,
      true,
    );
  });
  it("grants proposal writes only after composed validation and recording", async () => {
    const auth = authentication({ validated: true });
    await curationWorkflowAccess(
      {} as Env,
      identity,
      { ...request, write: true },
      auth,
    );
    expect(auth.token).toHaveBeenCalledWith("owner/site", true, false, true);
    expect(auth.token).toHaveBeenCalledWith(
      "owner/metadata",
      true,
      false,
      true,
    );
  });
  it.each([
    [{ stale: true }, "default branch differs"],
    [{ permission: "read" }, "permission is required"],
    [{}, "Composed validation"],
  ] as const)(
    "rejects stale state, lost permission, and unvalidated writes",
    async (options, message) => {
      const auth = authentication(options);
      await expect(
        curationWorkflowAccess(
          {} as Env,
          identity,
          { ...request, write: true },
          auth,
        ),
      ).rejects.toThrow(message);
      expect(auth.token).not.toHaveBeenCalledWith(
        "owner/metadata",
        true,
        false,
        true,
      );
    },
  );
  it("rejects a different trusted workflow revision", async () => {
    await expect(
      curationWorkflowAccess(
        {} as Env,
        { ...identity, workflow_sha: meta },
        request,
        authentication(),
      ),
    ).rejects.toThrow("current trusted default branch");
  });
});

describe("authenticated finalization without a presentation artifact", () => {
  const finalIdentity = { ...identity, event_name: "issue_comment" };
  const finalRequest = {
    ...request,
    head: "e".repeat(40),
    comment_id: 9,
    write: true,
  };
  it("uses the unchanged curator comment and exact paired heads", async () => {
    const auth = authentication({ finalize: true, validated: true });
    await curationWorkflowAccess({} as Env, finalIdentity, finalRequest, auth);
    expect(auth.token).toHaveBeenCalledWith(
      "owner/metadata",
      true,
      false,
      false,
    );
  });
  it.each([
    [{ stale: true }, "metadata draft head"],
    [{ edited: true }, "comment was edited"],
    [{ permission: "read" }, "permission is required"],
  ] as const)(
    "refuses changed authority before issuing a write token",
    async (options, message) => {
      const auth = authentication({
        finalize: true,
        validated: true,
        ...options,
      });
      await expect(
        curationWorkflowAccess({} as Env, finalIdentity, finalRequest, auth),
      ).rejects.toThrow(message);
      expect(auth.token).not.toHaveBeenCalledWith(
        "owner/metadata",
        true,
        false,
        false,
      );
    },
  );
});
