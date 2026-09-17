// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  SignJWT,
  createLocalJWKSet,
  exportJWK,
  generateKeyPair,
  exportPKCS8,
  jwtVerify,
} from "jose";
import {
  AppAuthentication,
  authorizeWorkflow,
  verifyAuthorization,
  verifyWorkflowIdentity,
  workflowAccess,
} from "../functions/lib/workflow-access";
import { GitHubClient } from "../functions/lib/github";
import type { Env } from "../functions/lib/pages";
import { utf8 } from "../functions/lib/encoding";
import { SHACL_BUNDLE_PATH } from "../functions/lib/shacl";

const source = "a".repeat(40),
  head = "b".repeat(40),
  metaSource = "c".repeat(40),
  metaHead = "d".repeat(40);
const env: Env = {
  PUBLIC_ORIGIN: "https://review.example",
  SESSION_SEAL_KEY: "test-only-seal-key",
  GITHUB_CLIENT_ID: "test",
  GITHUB_CLIENT_SECRET: "test",
  GITHUB_APP_PRIVATE_KEY: "configured",
};
const identity = {
  repository: "owner/site",
  repository_id: "1",
  workflow_sha: source,
  workflow_ref:
    "owner/site/.github/workflows/shacl-vue-proposal.yml@refs/heads/main",
  ref: "refs/heads/main",
  event_name: "pull_request_target",
  actor_id: "3",
  run_id: "4",
  run_attempt: "1",
  check_run_id: "5",
};
const bundle = {
  format: "orinoco-shacl-review-bundle",
  version: 2,
  source_commit: source,
  records: [
    {
      pid: "https://example.org/person",
      rdf_turtle:
        '<https://example.org/person> <https://example.org/name> "Fixture" .',
      schema_type: "example:Person",
      source_path: "site-specific/metadata/records/person.yaml",
      source_sha256: "f".repeat(64),
    },
  ],
};
const unsigned = {
  format: "orinoco-shacl-submodule-handoff",
  version: 1,
  bundle,
  metadata: {
    repository: "owner/data",
    source_commit: metaSource,
    head_sha: metaHead,
    branch: "curation/metadata",
    pull_request: 2,
  },
};
const user = { id: 3, login: "curator" };
function draft(repo: string, sha: string, branch: string, base: string) {
  return {
    state: "open",
    draft: true,
    head: { sha, ref: branch, repo: { full_name: repo } },
    base: {
      sha: base,
      ref: "main",
      repo: { full_name: repo, default_branch: "main" },
    },
  };
}
async function setup() {
  const github = new GitHubClient("user-token");
  const spy = vi
    .spyOn(github, "json")
    .mockResolvedValueOnce({ id: 1 })
    .mockResolvedValueOnce({ id: 2 });
  const authorization = await authorizeWorkflow(github, env, {
    repository: "owner/site",
    branch: "curation/site",
    trustedSha: source,
    curator: user,
    handoff: unsigned,
  });
  spy.mockRestore();
  const handoff = { ...unsigned, authorization };
  const token = vi.fn(async (_repo: string, _write = false) => ({
    token: "scoped-test-token",
    expires_at: "later",
  }));
  const auth = new AppAuthentication(env);
  auth.token = token;
  auth.revoke = vi.fn(async () => undefined);
  const contents = vi
    .spyOn(GitHubClient.prototype, "contents")
    .mockImplementation(
      async (repo) =>
        new Map(
          repo === "owner/site"
            ? [["handoff", JSON.stringify(handoff)]]
            : [["bundle", JSON.stringify(bundle)]],
        ),
    );
  const permission = vi
    .spyOn(GitHubClient.prototype, "requireCurator")
    .mockResolvedValue();
  const submodule = vi
    .spyOn(GitHubClient.prototype, "siteSubmodule")
    .mockResolvedValue({ repository: "owner/data", sha: metaSource });
  const pull = vi
    .spyOn(GitHubClient.prototype, "pullRequest")
    .mockImplementation(async (repo) =>
      repo === "owner/site"
        ? draft(repo, head, "curation/site", source)
        : draft(repo, metaHead, "curation/metadata", metaSource),
    );
  const commit = vi
    .spyOn(GitHubClient.prototype, "commit")
    .mockImplementation(async (repo, sha) => ({
      sha,
      author: user,
      parents: [{ sha: repo === "owner/site" ? source : metaSource }],
      files: [{ filename: SHACL_BUNDLE_PATH, status: "added" }],
    }));
  const json = vi
    .spyOn(GitHubClient.prototype, "json")
    .mockImplementation(async (path) => {
      if (path === "/repos/owner/site")
        return { id: 1, default_branch: "main" };
      if (path === "/repos/owner/data")
        return { id: 2, default_branch: "main" };
      if (path.endsWith("/actions/runs/4"))
        return {
          id: 4,
          repository: { id: 1 },
          event: "pull_request_target",
          path: ".github/workflows/shacl-vue-proposal.yml",
          head_sha: head,
          run_attempt: 1,
          actor: user,
          status: "in_progress",
        };
      if (path.endsWith("/jobs?per_page=100"))
        return {
          jobs: [
            {
              check_run_url:
                "https://api.github.com/repos/owner/site/check-runs/5",
              steps: [
                "Validate the materialized joined graph",
                "Create the equivalent attributed human metadata commit",
              ].map((name) => ({
                name,
                status: "completed",
                conclusion: "success",
              })),
            },
          ],
        };
      throw new Error(`Unexpected endpoint ${path}`);
    });
  return {
    handoff,
    auth,
    token,
    contents,
    permission,
    submodule,
    pull,
    commit,
    json,
  };
}
const request = {
  repository: "owner/site",
  pull_request: 1,
  head,
  write: true,
};
afterEach(() => vi.restoreAllMocks());

describe("proposal-bound workflow authority", () => {
  it("grants only metadata write access after validation and live authorization", async () => {
    const s = await setup();
    expect(await workflowAccess(env, identity, request, s.auth)).toMatchObject({
      token: "scoped-test-token",
    });
    expect(s.token.mock.calls).toEqual([
      ["owner/site", false, true],
      ["owner/data"],
      ["owner/data", true],
    ]);
    expect(s.permission.mock.calls).toEqual([
      ["owner/site", "curator", 3],
      ["owner/data", "curator", 3],
    ]);
    expect(s.auth.revoke).toHaveBeenCalledTimes(2);
  });
  it("uses read-only access before validation", async () => {
    const s = await setup();
    await workflowAccess(env, identity, { ...request, write: false }, s.auth);
    expect(s.token.mock.calls.every((call) => call[1] !== true)).toBe(true);
  });
  it.each([
    { repository_id: "9" },
    { repository: "attacker/site" },
    { workflow_sha: "e".repeat(40) },
    { workflow_ref: "owner/site/.github/workflows/other.yml@refs/heads/main" },
    { event_name: "pull_request" },
    { actor_id: "99" },
    { run_attempt: "2" },
    { ref: "refs/tags/main" },
  ])("rejects a different workflow identity %j", async (change) => {
    const s = await setup();
    await expect(
      verifyAuthorization(env, s.handoff, { ...identity, ...change }),
    ).rejects.toThrow();
  });
  it("rejects modified bundle coordinates and forged grants", async () => {
    const s = await setup();
    await expect(
      verifyAuthorization(
        env,
        {
          ...s.handoff,
          metadata: { ...unsigned.metadata, repository: "other/private" },
        },
        identity,
      ),
    ).rejects.toThrow();
    await expect(
      verifyAuthorization(
        env,
        { ...s.handoff, authorization: "forged" },
        identity,
      ),
    ).rejects.toThrow();
  });
  it("rejects expired signed authorization", async () => {
    const s = await setup();
    const claims = await verifyAuthorization(env, s.handoff, identity);
    const expired = await new SignJWT({ ...claims, iat: 1, exp: 2 })
      .setProtectedHeader({ alg: "HS256" })
      .sign(utf8(`orinoco-workflow-authorization-v1:${env.SESSION_SEAL_KEY}`));
    await expect(
      verifyAuthorization(
        env,
        { ...s.handoff, authorization: expired },
        identity,
      ),
    ).rejects.toThrow("expired");
  });
  it("rejects unsigned Actions identities", async () => {
    await expect(
      verifyWorkflowIdentity("fake", env.PUBLIC_ORIGIN),
    ).rejects.toThrow();
  });
  it.each([
    "website head",
    "metadata head",
    "permission",
    "gitlink",
    "validation",
    "changed paths",
    "bundle",
    "repository identity",
    "closed draft",
  ])("denies %s changes without issuing write access", async (boundary) => {
    const s = await setup();
    if (boundary === "website head")
      s.pull.mockResolvedValue(
        draft("owner/site", "e".repeat(40), "curation/site", source),
      );
    if (boundary === "metadata head")
      s.pull.mockImplementation(async (repo) =>
        repo === "owner/site"
          ? draft(repo, head, "curation/site", source)
          : draft(repo, "e".repeat(40), "curation/metadata", metaSource),
      );
    if (boundary === "permission")
      s.permission.mockRejectedValue(new Error("revoked"));
    if (boundary === "gitlink")
      s.submodule.mockResolvedValue({
        repository: "other/private",
        sha: metaSource,
      });
    if (boundary === "validation") {
      const original = s.json.getMockImplementation()!;
      s.json.mockImplementation(async (path, ...rest) =>
        path.includes("/jobs?") ? { jobs: [] } : original(path, ...rest),
      );
    }
    if (boundary === "changed paths")
      s.commit.mockResolvedValue({
        sha: head,
        author: user,
        parents: [{ sha: source }],
        files: [{ filename: ".github/workflows/evil.yml", status: "added" }],
      });
    if (boundary === "bundle")
      s.contents.mockImplementation(
        async (repo) =>
          new Map(
            repo === "owner/site"
              ? [["handoff", JSON.stringify(s.handoff)]]
              : [
                  [
                    "bundle",
                    JSON.stringify({ ...bundle, source_commit: metaSource }),
                  ],
                ],
          ),
      );
    if (boundary === "repository identity") {
      const original = s.json.getMockImplementation()!;
      s.json.mockImplementation(async (path, ...rest) =>
        path === "/repos/owner/data" ? { id: 99 } : original(path, ...rest),
      );
    }
    if (boundary === "closed draft")
      s.pull.mockResolvedValue({
        ...draft("owner/site", head, "curation/site", source),
        state: "closed",
      });
    await expect(
      workflowAccess(env, identity, request, s.auth),
    ).rejects.toThrow();
    expect(s.token.mock.calls.every((call) => call[1] !== true)).toBe(true);
    expect(s.auth.revoke).toHaveBeenCalled();
  });
});

describe("GitHub OIDC cryptographic verification", () => {
  it("accepts a signed identity only for the exact issuer and service audience", async () => {
    const pair = await generateKeyPair("RS256");
    const jwk = await exportJWK(pair.publicKey);
    const verifier = createLocalJWKSet({
      keys: [{ ...jwk, kid: "test", alg: "RS256" }],
    });
    const audience = `${env.PUBLIC_ORIGIN}/api/shacl/workflow-access`;
    const sign = (issuer: string, aud: string, expiration: string = "5m") =>
      new SignJWT(identity)
        .setProtectedHeader({ alg: "RS256", kid: "test" })
        .setIssuer(issuer)
        .setAudience(aud)
        .setIssuedAt()
        .setNotBefore("0s")
        .setExpirationTime(expiration)
        .sign(pair.privateKey);
    const issuer = "https://token.actions.githubusercontent.com";
    expect(
      (
        await verifyWorkflowIdentity(
          await sign(issuer, audience),
          env.PUBLIC_ORIGIN,
          verifier,
        )
      ).repository_id,
    ).toBe("1");
    for (const token of [
      await sign("https://attacker.example", audience),
      await sign(issuer, "other-service"),
      await sign(issuer, audience, "-1s"),
    ]) {
      await expect(
        verifyWorkflowIdentity(token, env.PUBLIC_ORIGIN, verifier),
      ).rejects.toThrow();
    }
    const other = await generateKeyPair("RS256");
    const forged = await new SignJWT(identity)
      .setProtectedHeader({ alg: "RS256", kid: "test" })
      .setIssuer(issuer)
      .setAudience(audience)
      .setIssuedAt()
      .setNotBefore("0s")
      .setExpirationTime("5m")
      .sign(other.privateKey);
    await expect(
      verifyWorkflowIdentity(forged, env.PUBLIC_ORIGIN, verifier),
    ).rejects.toThrow();
  });
});

describe("completed proposal validation", () => {
  it("permits only read access to the exact composed replacement", async () => {
    const s = await setup();
    const newHead = "e".repeat(40),
      newMetadata = "f".repeat(40);
    const dispatch = {
      ...identity,
      event_name: "workflow_dispatch",
      actor_id: "41898282",
    };
    s.pull.mockImplementation(async (repo) =>
      repo === "owner/site"
        ? draft(repo, newHead, "curation/site", source)
        : draft(repo, newMetadata, "curation/metadata", metaSource),
    );
    s.submodule.mockImplementation(async (_repo, sha) => ({
      repository: "owner/data",
      sha: sha === newHead ? newMetadata : metaSource,
    }));
    const oldCommit = s.commit.getMockImplementation()!;
    s.commit.mockImplementation(async (repo, sha, ...rest) =>
      sha === newHead || sha === newMetadata
        ? {
            sha,
            author: user,
            parents: [{ sha: repo === "owner/site" ? source : metaSource }],
            files: [
              {
                filename:
                  repo === "owner/site"
                    ? "site-specific"
                    : "metadata/records/person.yaml",
                status: "modified",
              },
            ],
          }
        : oldCommit(repo, sha, ...rest),
    );
    const oldJson = s.json.getMockImplementation()!;
    s.json.mockImplementation(async (path, ...rest) =>
      path.endsWith("/actions/runs/4")
        ? {
            id: 4,
            repository: { id: 1 },
            event: "workflow_dispatch",
            path: ".github/workflows/shacl-vue-proposal.yml",
            head_sha: source,
            run_attempt: 1,
            status: "in_progress",
          }
        : oldJson(path, ...rest),
    );
    await workflowAccess(
      env,
      dispatch,
      { ...request, head: newHead, handoff: head, write: false },
      s.auth,
    );
    expect(s.token.mock.calls.every((c) => c[1] !== true)).toBe(true);
    await expect(
      workflowAccess(
        env,
        dispatch,
        { ...request, head: newHead, handoff: head },
        s.auth,
      ),
    ).rejects.toThrow();
    await expect(
      workflowAccess(env, identity, request, s.auth),
    ).rejects.toThrow();
  });
});

describe("App installation token boundaries", () => {
  it("signs as the existing App and requests only one repository and required permissions", async () => {
    const pair = await generateKeyPair("RS256", { extractable: true });
    const privateKey = await exportPKCS8(pair.privateKey);
    const fetcher = vi.fn<typeof fetch>(async (_url, init) => {
      const bearer = new Headers(init?.headers).get("authorization")!.slice(7);
      expect((await jwtVerify(bearer, pair.publicKey)).payload.iss).toBe(
        env.GITHUB_CLIENT_ID,
      );
      return new Response(
        JSON.stringify(
          init?.method === "POST"
            ? { token: "scoped", expires_at: "later" }
            : { id: 8, suspended_at: null },
        ),
        { status: 200 },
      );
    });
    const app = new AppAuthentication(
      { ...env, GITHUB_APP_PRIVATE_KEY: privateKey },
      fetcher,
    );
    await app.token("owner/data", true);
    expect(JSON.parse(String(fetcher.mock.calls[1]?.[1]?.body))).toEqual({
      repositories: ["data"],
      permissions: { contents: "write", pull_requests: "read" },
    });
    await app.token("owner/site", false, true);
    expect(JSON.parse(String(fetcher.mock.calls[3]?.[1]?.body))).toEqual({
      repositories: ["site"],
      permissions: { contents: "read", pull_requests: "read", actions: "read" },
    });
    fetcher.mockImplementation(
      async () => new Response(JSON.stringify({ id: 8, suspended_at: "now" })),
    );
    await expect(app.token("owner/data", true)).rejects.toThrow("suspended");
  });
  it("rejects a reused curator login with another immutable user ID", async () => {
    const github = new GitHubClient(
      "token",
      async () =>
        new Response(
          JSON.stringify({
            permission: "write",
            user: { id: 99, login: "curator" },
          }),
        ),
    );
    await expect(
      github.requireCurator("owner/data", "curator", 3),
    ).rejects.toThrow();
  });
});
