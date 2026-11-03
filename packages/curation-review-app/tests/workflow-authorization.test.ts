// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { GitHubClient } from "../functions/lib/github";
import type { Env } from "../functions/lib/pages";
import {
  authorizeSubmission,
  verifySubmissionAuthorization,
} from "../functions/lib/workflow-authorization";

const sha = "a".repeat(40);
const env: Env = {
  GITHUB_CLIENT_ID: "test-client",
  GITHUB_CLIENT_SECRET: "test-secret",
  PUBLIC_ORIGIN: "https://auth.example",
  SESSION_SEAL_KEY: "test-key",
};
const worker = `owner/template/.github/workflows/editor.yml@${sha}`;
const request = {
  input_repository: "owner/metadata",
  input_commit: sha,
  scope: {
    repositories: ["owner/site", "owner/metadata"].map((name, index) => ({
      id: index + 1,
      name,
      ownerId: 3,
      defaultBranch: "main",
      baseCommit: sha,
      worker,
    })),
    source: { repository: "owner/site", commit: sha },
    metadata: { repository: "owner/metadata", commit: sha },
  },
};
const identity = {
  repository: "owner/metadata",
  repository_id: "2",
  actor: "bob",
  actor_id: "11",
  job_workflow_ref: worker,
  job_workflow_sha: sha,
  workflow_sha: "b".repeat(40),
  run_attempt: "2",
};

function github(canWriteWebsite = true) {
  return new GitHubClient(
    "alice-test-token",
    vi.fn(async (url) => {
      if (String(url).endsWith("/user"))
        return Response.json({ id: 10, login: "alice" });
      const site = String(url).endsWith("/site");
      return Response.json({
        id: site ? 1 : 2,
        owner: { id: 3 },
        full_name: site ? "owner/site" : "owner/metadata",
        default_branch: "main",
        permissions: { push: site ? canWriteWebsite : true },
      });
    }),
  );
}

describe("authorization for one submission", () => {
  it("allows the pinned workflow to finish Alice's edit after Bob merges and defaults advance", async () => {
    const signed = await authorizeSubmission(env, github(), request);
    await expect(
      verifySubmissionAuthorization(env, signed, identity),
    ).resolves.toEqual({
      ...request,
      submitter: { id: 10, login: "alice" },
    });
  });

  it("does not authorize a metadata-only contributor to submit a website change", async () => {
    await expect(
      authorizeSubmission(env, github(false), request),
    ).rejects.toMatchObject({
      code: "curator_permission_required",
      status: 403,
    });
  });

  it.each([
    { repository: "stranger/site", repository_id: "9" },
    { repository_id: "99" },
    { job_workflow_ref: worker.replace(sha, "c".repeat(40)) },
    { job_workflow_sha: "c".repeat(40) },
    { job_workflow_ref: undefined, job_workflow_sha: undefined },
  ])("rejects an unrelated caller: %j", async (replacement) => {
    const signed = await authorizeSubmission(env, github(), request);
    await expect(
      verifySubmissionAuthorization(env, signed, {
        ...identity,
        ...replacement,
      }),
    ).rejects.toMatchObject({ code: "workflow_authorization_required" });
  });

  it("rejects changed authorized input", async () => {
    const signed = await authorizeSubmission(env, github(), request);
    const [header, payload, signature] = signed.split(".");
    const claims = JSON.parse(Buffer.from(payload!, "base64url").toString());
    claims.authorization.input_commit = "c".repeat(40);
    const changed = `${header}.${Buffer.from(JSON.stringify(claims)).toString("base64url")}.${signature}`;
    await expect(
      verifySubmissionAuthorization(env, changed, identity),
    ).rejects.toMatchObject({ code: "workflow_authorization_required" });
  });

  it("requires an immutable worker instead of the current default branch", async () => {
    await expect(
      authorizeSubmission(env, github(), {
        ...request,
        scope: {
          ...request.scope,
          repositories: request.scope.repositories.map((repository) => ({
            ...repository,
            worker: worker.replace(sha, "main"),
          })),
        },
      }),
    ).rejects.toMatchObject({ code: "workflow_authorization_required" });
  });
});
