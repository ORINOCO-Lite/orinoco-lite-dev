import { afterEach, describe, expect, it, vi } from "vitest";
import { templateWorkflowAccess } from "../functions/lib/template-workflow";
import { AppAuthentication } from "../functions/lib/workflow-access";
import { GitHubClient } from "../functions/lib/github";
import type { Env } from "../functions/lib/pages";

const head = "a".repeat(40);
const identity = {
  repository: "owner/site",
  repository_id: "1",
  ref: "refs/heads/main",
  workflow_sha: head,
  workflow_ref:
    "owner/site/.github/workflows/template-update.yml@refs/heads/main",
  event_name: "workflow_dispatch",
  actor: "curator",
  actor_id: "2",
  run_id: "3",
  run_attempt: "1",
  check_run_id: "4",
};
function fixture(
  options: {
    stale?: boolean;
    changedWorkflow?: boolean;
    prepared?: boolean;
    publisher?: boolean;
    permission?: boolean;
    enabled?: boolean;
  } = {},
) {
  const auth = new AppAuthentication({} as Env);
  vi.spyOn(auth, "token").mockResolvedValue({
    token: "bounded",
    expires_at: "later",
  });
  vi.spyOn(auth, "revoke").mockResolvedValue();
  vi.spyOn(GitHubClient.prototype, "branchHead").mockResolvedValue({
    sha: options.stale ? "b".repeat(40) : head,
  } as any);
  vi.spyOn(GitHubClient.prototype, "contents").mockResolvedValue(
    new Map([
      [
        "operation-policy",
        `[tool.orinoco.operations]\ntemplate_updates = ${options.enabled !== false}`,
      ],
      ["trusted", "trusted workflow"],
      ["running", options.changedWorkflow ? "changed" : "trusted workflow"],
    ]),
  );
  vi.spyOn(GitHubClient.prototype, "requireCurator").mockImplementation(
    async () => {
      if (options.permission === false) throw new Error("No write permission");
    },
  );
  vi.spyOn(GitHubClient.prototype, "workflowRun").mockResolvedValue({
    path: ".github/workflows/template-update.yml",
    head_sha: head,
    status: "in_progress",
    run_attempt: 1,
    event: "workflow_dispatch",
    repository: { id: 1 },
    actor: { id: 2, login: "curator" },
  });
  vi.spyOn(GitHubClient.prototype, "json").mockImplementation(async (path) => {
    if (path === "/repos/owner/site") return { id: 1, default_branch: "main" };
    if (path.endsWith("/jobs?per_page=100"))
      return {
        jobs: [
          {
            name: "Prepare template update",
            conclusion: options.prepared === false ? "failure" : "success",
          },
          {
            name:
              options.publisher === false
                ? "Prepare template update"
                : "Publish template update",
            status: "in_progress",
            check_run_url:
              "https://api.github.com/repos/owner/site/check-runs/4",
          },
        ],
      };
    throw new Error(`Unexpected request: ${path}`);
  });
  return auth;
}
afterEach(() => vi.restoreAllMocks());
describe("template update App access", () => {
  it("grants repository-scoped bot transport after preparation", async () => {
    const auth = fixture();
    await expect(
      templateWorkflowAccess(
        {} as Env,
        identity,
        { repository: "owner/site", head },
        auth,
      ),
    ).resolves.toEqual({ token: "bounded", expires_at: "later" });
    expect(auth.token).toHaveBeenLastCalledWith(
      "owner/site",
      true,
      false,
      true,
      true,
    );
    expect(auth.revoke).toHaveBeenCalledWith("bounded");
  });
  it.each([
    { enabled: false },
    { stale: true },
    { changedWorkflow: true },
    { prepared: false },
    { publisher: false },
    { permission: false },
  ])("refuses unauthorized transport %j", async (options) => {
    const auth = fixture(options);
    await expect(
      templateWorkflowAccess(
        {} as Env,
        identity,
        { repository: "owner/site", head },
        auth,
      ),
    ).rejects.toThrow();
    expect(auth.token).toHaveBeenCalledTimes(1);
    expect(auth.revoke).toHaveBeenCalled();
  });
  it.each([
    { repository: "other/site" },
    { event_name: "pull_request" },
    { run_attempt: "2" },
    { workflow_sha: "b".repeat(40) },
  ])("rejects mismatched identity %j", async (override) => {
    const auth = fixture();
    await expect(
      templateWorkflowAccess(
        {} as Env,
        { ...identity, ...override },
        { repository: "owner/site", head },
        auth,
      ),
    ).rejects.toThrow();
    expect(auth.token).not.toHaveBeenCalled();
  });
});
