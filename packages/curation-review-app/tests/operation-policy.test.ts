import { afterEach, describe, expect, it, vi } from "vitest";
import { GitHubClient } from "../functions/lib/github";
import {
  OPERATIONS,
  parseOperations,
  requireOperation,
} from "../functions/lib/operation-policy";
const base = "a".repeat(40);
function client(policy: string) {
  const github = new GitHubClient("read-token");
  vi.spyOn(github, "json").mockResolvedValue({ default_branch: "main" });
  vi.spyOn(github, "branchHead").mockResolvedValue({ name: "main", sha: base });
  vi.spyOn(github, "contents").mockImplementation(async (_repo, requests) => {
    expect(requests).toEqual([
      { key: "operation-policy", path: "pyproject.toml", ref: base },
    ]);
    return new Map([["operation-policy", policy]]);
  });
  return github;
}
afterEach(() => vi.restoreAllMocks());
describe("downstream operation policy", () => {
  it.each(OPERATIONS)(
    "requires explicit default-branch opt-in for %s",
    async (operation) => {
      const github = client(`[tool.orinoco.operations]\n${operation} = true\n`);
      await expect(
        requireOperation(github, "owner/site", operation),
      ).resolves.toBeUndefined();
      expect(github.branchHead).toHaveBeenCalledWith("owner/site", "main");
    },
  );
  it.each([
    "[tool.orinoco]",
    "[tool.orinoco.operations]\ntemplate_updates = false",
    "[tool.orinoco.operations]\nautomated_curation = true",
  ])("denies absent or disabled choices: %s", async (policy) => {
    await expect(
      requireOperation(client(policy), "owner/site", "template_updates"),
    ).rejects.toMatchObject({ code: "operation_disabled" });
  });
  it("ignores an enabled policy available only on a proposal branch", async () => {
    const github = client("[tool.orinoco]");
    vi.mocked(github.contents).mockImplementation(
      async (_repo, requests) =>
        new Map([
          [
            "operation-policy",
            requests[0]?.ref === base
              ? "[tool.orinoco]"
              : "[tool.orinoco.operations]\ntemplate_updates = true",
          ],
        ]),
    );
    await expect(
      requireOperation(github, "owner/site", "template_updates"),
    ).rejects.toMatchObject({ code: "operation_disabled" });
  });
  it.each([
    null,
    [],
    { unknown: true },
    { template_updates: "true" },
    { template_updates: 1 },
  ])("rejects malformed policy %j", (policy) =>
    expect(() => parseOperations(policy)).toThrow(),
  );
  it("refuses duplicate TOML keys", async () => {
    await expect(
      requireOperation(
        client(
          "[tool.orinoco.operations]\ntemplate_updates = false\ntemplate_updates = true",
        ),
        "owner/site",
        "template_updates",
      ),
    ).rejects.toMatchObject({ code: "invalid_operation_policy" });
  });
});
