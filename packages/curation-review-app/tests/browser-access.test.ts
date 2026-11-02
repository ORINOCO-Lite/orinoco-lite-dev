// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import {
  browserCredentialScope,
  issueBrowserCredentials,
  verifyBrowserCredentialScope,
} from "../functions/lib/browser-access";
import { GitHubClient } from "../functions/lib/github";
import type { Env } from "../functions/lib/pages";

const source = "a".repeat(40);
const current = "b".repeat(40);
const metadata = "c".repeat(40);
const worker = `owner/package/.github/workflows/orinoco.yml@${source}`;
const env: Env = {
  PUBLIC_ORIGIN: "https://auth.example",
  GITHUB_CLIENT_ID: "client",
  GITHUB_CLIENT_SECRET: "secret",
  SESSION_SEAL_KEY: "test-key",
};

function fixture({ websiteWrite = true, metadataWrite = true } = {}) {
  const github = new GitHubClient("user-token");
  vi.spyOn(github, "json").mockImplementation(async (path) => {
    const name = String(path).slice("/repos/".length);
    const site = name === "owner/website";
    return {
      full_name: name,
      id: site ? 1 : 2,
      owner: { id: 3 },
      default_branch: "main",
      permissions: { push: site ? websiteWrite : metadataWrite },
    };
  });
  vi.spyOn(github, "branchHead").mockResolvedValue({
    name: "main",
    sha: current,
  });
  vi.spyOn(github, "contents").mockImplementation(
    async (_repository, files) =>
      new Map(
        files.map(({ key }) => [
          key,
          key === "workflow"
            ? `jobs:\n  process:\n    uses: ${worker}\n`
            : '[tool.orinoco.site.identity]\nbase_url="https://website.example/"\n[tool.orinoco.service]\nurl="https://auth.example"\n',
        ]),
      ),
  );
  vi.spyOn(github, "siteSubmodule").mockResolvedValue({
    repository: "owner/metadata",
    sha: metadata,
  });
  vi.spyOn(github, "commitStatus").mockResolvedValue({
    statuses: [
      {
        state: "success",
        context: "netlify/website/deploy-preview",
        target_url: "https://deploy-preview-42--website.netlify.app/",
      },
    ],
  });
  return github;
}

describe("browser repository access", () => {
  it("accepts a deployed snapshot after defaults have advanced", async () => {
    const github = fixture();
    const scope = await browserCredentialScope(
      env,
      github,
      "owner/website",
      "https://website.example",
      source,
    );
    expect(scope.source.commit).toBe(source);
    expect(scope.repositories.map((repo) => repo.baseCommit)).toEqual([
      current,
      current,
    ]);
    expect(scope.metadata).toEqual({
      repository: "owner/metadata",
      commit: metadata,
    });
    expect(github.siteSubmodule).toHaveBeenCalledWith("owner/website", source);
  });

  it("refuses metadata-only access before looking up private inputs", async () => {
    const github = fixture({ websiteWrite: false });
    await expect(
      browserCredentialScope(
        env,
        github,
        "owner/website",
        "https://website.example",
        source,
      ),
    ).rejects.toMatchObject({ code: "curator_permission_required" });
    expect(github.siteSubmodule).not.toHaveBeenCalled();
    expect(github.contents).not.toHaveBeenCalled();
  });

  it("requires the submitter's access to the separate metadata repository", async () => {
    await expect(
      browserCredentialScope(
        env,
        fixture({ metadataWrite: false }),
        "owner/website",
        "https://website.example",
        source,
      ),
    ).rejects.toMatchObject({ code: "curator_permission_required" });
  });

  it("accepts GitHub's successful deployment preview for the source snapshot", async () => {
    const github = fixture();
    await expect(
      browserCredentialScope(
        env,
        github,
        "owner/website",
        "https://deploy-preview-42--website.netlify.app",
        source,
      ),
    ).resolves.toBeDefined();
    expect(github.commitStatus).toHaveBeenCalledWith("owner/website", source);
  });

  it("does not deliver credentials to an unrelated origin", async () => {
    await expect(
      browserCredentialScope(
        env,
        fixture(),
        "owner/website",
        "https://unrelated.example",
        source,
      ),
    ).rejects.toMatchObject({ code: "authentication_scope_required" });
  });

  it("binds captured workflow versions to the signed-in session", async () => {
    const scope = await browserCredentialScope(
      env,
      fixture(),
      "owner/website",
      "https://website.example",
      source,
    );
    const api = vi.fn(async () =>
      Response.json({
        token: "scoped-user-token",
        expires_at: new Date(Date.now() + 3600000).toISOString(),
      }),
    );
    const { scope_proof } = await issueBrowserCredentials(
      env,
      "alice-session",
      scope,
      Math.floor(Date.now() / 1000) + 60,
      api,
    );
    await expect(
      verifyBrowserCredentialScope(env, "alice-session", scope_proof),
    ).resolves.toEqual(scope);
    await expect(
      verifyBrowserCredentialScope(env, "bob-session", scope_proof),
    ).rejects.toMatchObject({ code: "authentication_scope_required" });
  });

  it("revokes the first repository credential when issuing the second fails", async () => {
    const scope = await browserCredentialScope(
      env,
      fixture(),
      "owner/website",
      "https://website.example",
      source,
    );
    const api = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          token: "first-token",
          expires_at: new Date(Date.now() + 3600000).toISOString(),
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 403 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(
      issueBrowserCredentials(
        env,
        "alice-session",
        scope,
        Math.floor(Date.now() / 1000) + 60,
        api,
      ),
    ).rejects.toMatchObject({ code: "github_credential_error" });
    expect(api.mock.calls[2]?.[1]).toMatchObject({
      method: "DELETE",
      body: JSON.stringify({ access_token: "first-token" }),
    });
  });
});
