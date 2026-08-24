import { afterEach, describe, expect, it, vi } from "vitest";
import { onRequest as authorizationStart } from "../functions/api/auth/start";
import { onRequest as authorizationCallback } from "../functions/api/auth/callback";
import { onRequest as loadProposal } from "../functions/api/proposal";
import { onRequest as submitDecisions } from "../functions/api/submit";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env, EventContext } from "../functions/lib/pages";
import {
  createSessionCookie,
  OAUTH_COOKIE,
  readOAuthCookie,
  readSessionCookie,
  SESSION_COOKIE,
} from "../functions/lib/session";
import {
  ARTIFACT_ID,
  BASE_SHA,
  HEAD_SHA,
  PROPOSAL_SHA,
  WORKFLOW_RUN_ID,
  proposalCommitMessage,
  reviewBundleArchive,
  submission,
} from "./fixtures";

const ORIGIN = "https://review.example";
const ARTIFACT_STORAGE =
  "https://pipelines.actions.githubusercontent.com/results/archive.zip?sig=short-lived";
const artifactArchive = reviewBundleArchive();
const env: Env = {
  GITHUB_CLIENT_ID: "Iv1.example",
  GITHUB_CLIENT_SECRET: "client-secret",
  PUBLIC_ORIGIN: ORIGIN,
  SESSION_SEAL_KEY: base64urlEncode(new Uint8Array(32).fill(7)),
};

function context(request: Request): EventContext {
  return {
    data: {},
    env,
    functionPath: "",
    next: async () => new Response(null, { status: 204 }),
    params: {},
    passThroughOnException: () => undefined,
    request,
    waitUntil: () => undefined,
  };
}

function cookiePair(header: string, name: string): string {
  const match = header.match(new RegExp(`(?:^|, )(${name}=[^;,]+)`));
  if (match?.[1] === undefined) throw new Error(`Missing ${name} cookie.`);
  return match[1];
}

async function sessionCookie(): Promise<string> {
  return (
    await createSessionCookie(
      env,
      {
        access_token: "ghu_short_lived",
        csrf_token: "csrf-token",
        login: "octocat",
      },
      28_800,
    )
  ).split(";", 1)[0] as string;
}

function blob(text: string): Record<string, unknown> {
  return {
    __typename: "Blob",
    byteSize: new TextEncoder().encode(text).byteLength,
    isBinary: false,
    isTruncated: false,
    text,
  };
}

function proposalApi(
  url: string,
  init: RequestInit | undefined,
): Response | null {
  if (url.endsWith("/collaborators/octocat/permission")) {
    return Response.json({ permission: "write" });
  }
  if (url.endsWith("/pulls/42")) {
    return Response.json({
      base: { repo: { full_name: "example/site" } },
      body: "Accessible fallback text may be edited freely.",
      head: { sha: HEAD_SHA },
      html_url: "https://github.com/example/site/pull/42",
      number: 42,
      state: "open",
    });
  }
  if (url.includes("/pulls/42/commits?")) {
    return Response.json([
      {
        commit: { message: proposalCommitMessage() },
        parents: [{ sha: BASE_SHA }],
        sha: PROPOSAL_SHA,
      },
    ]);
  }
  if (url.endsWith(`/actions/artifacts/${ARTIFACT_ID}`)) {
    return Response.json({
      expired: false,
      id: ARTIFACT_ID,
      name: `orinoco-curation-review-${PROPOSAL_SHA}`,
      size_in_bytes: artifactArchive.byteLength,
      workflow_run: { head_sha: BASE_SHA, id: WORKFLOW_RUN_ID },
    });
  }
  if (url.endsWith(`/actions/runs/${WORKFLOW_RUN_ID}`)) {
    return Response.json({
      conclusion: "success",
      event: "workflow_dispatch",
      head_sha: BASE_SHA,
      id: WORKFLOW_RUN_ID,
      repository: { full_name: "example/site" },
      run_attempt: 1,
      status: "completed",
    });
  }
  if (url.endsWith(`/actions/artifacts/${ARTIFACT_ID}/zip`)) {
    return new Response(null, {
      headers: { Location: ARTIFACT_STORAGE },
      status: 302,
    });
  }
  if (url === ARTIFACT_STORAGE) {
    return new Response(new Uint8Array(artifactArchive).buffer, {
      headers: { "Content-Length": String(artifactArchive.byteLength) },
    });
  }
  if (url.includes(`/commits/${PROPOSAL_SHA}?`)) {
    return Response.json({
      files: [
        {
          filename: "metadata/records/example/first.yaml",
          status: "modified",
        },
        {
          filename: "metadata/overlays/annotations/example/first.yaml",
          status: "modified",
        },
        { filename: "metadata/records/example/second.yaml", status: "added" },
        {
          filename: "metadata/overlays/annotations/example/second.yaml",
          status: "added",
        },
      ],
      sha: PROPOSAL_SHA,
    });
  }
  if (url === "https://api.github.com/graphql") {
    const request = JSON.parse(String(init?.body)) as {
      variables: Record<string, string>;
    };
    const repository: Record<string, unknown> = {};
    Object.entries(request.variables)
      .filter(([key]) => key.startsWith("expression"))
      .forEach(([key, expression]) => {
        const index = key.slice("expression".length);
        if (expression === `${BASE_SHA}:metadata/records/example/first.yaml`) {
          repository[`blob${index}`] = blob(
            "pid: example:first\ntitle: Original first\n",
          );
        } else if (
          expression === `${PROPOSAL_SHA}:metadata/records/example/first.yaml`
        ) {
          repository[`blob${index}`] = blob(
            "pid: example:first\ntitle: Proposed first\n",
          );
        } else if (
          expression === `${PROPOSAL_SHA}:metadata/records/example/second.yaml`
        ) {
          repository[`blob${index}`] = blob(
            "pid: example:second\ntitle: Proposed second\n",
          );
        } else if (
          expression === `${HEAD_SHA}:metadata/records/example/first.yaml`
        ) {
          repository[`blob${index}`] = blob(
            "pid: example:first\ntitle: Current first\n",
          );
        } else if (
          expression === `${HEAD_SHA}:metadata/records/example/second.yaml`
        ) {
          repository[`blob${index}`] = blob(
            "pid: example:second\ntitle: Second\n",
          );
        } else {
          repository[`blob${index}`] = null;
        }
      });
    return Response.json({ data: { repository } });
  }
  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("GitHub App user-to-server handlers", () => {
  it("round-trips sealed OAuth state and creates a short-lived user session", async () => {
    const start = await authorizationStart(
      context(
        new Request(
          `${ORIGIN}/api/auth/start?artifact_id=${ARTIFACT_ID}&repository=example%2Fsite&pull_request=42`,
        ),
      ),
    );
    expect(start.status).toBe(302);
    const authorization = new URL(start.headers.get("location") as string);
    expect(authorization.origin).toBe("https://github.com");
    expect(authorization.searchParams.get("client_id")).toBe("Iv1.example");
    expect(authorization.searchParams.has("scope")).toBe(false);
    expect(authorization.searchParams.get("code_challenge_method")).toBe(
      "S256",
    );
    const oauthCookie = cookiePair(
      start.headers.get("set-cookie") as string,
      OAUTH_COOKIE,
    );
    const oauth = await readOAuthCookie(
      new Request(ORIGIN, { headers: { Cookie: oauthCookie } }),
      env,
    );
    expect(oauth).toMatchObject({
      artifact_id: ARTIFACT_ID,
      origin: ORIGIN,
      pull_request: 42,
      repository: "example/site",
      state: authorization.searchParams.get("state"),
    });

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "https://github.com/login/oauth/access_token") {
          const body = init?.body as URLSearchParams;
          expect(body.get("code_verifier")).toBe(oauth.code_verifier);
          return Response.json({
            access_token: "ghu_short_lived",
            expires_in: 28_800,
            refresh_token: "must-not-be-retained",
            scope: "",
            token_type: "bearer",
          });
        }
        if (url === "https://api.github.com/user") {
          return Response.json({ id: 1, login: "octocat" });
        }
        throw new Error(`Unexpected GitHub request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const callback = await authorizationCallback(
      context(
        new Request(
          `${ORIGIN}/api/auth/callback?code=temporary-code&state=${oauth.state}`,
          { headers: { Cookie: oauthCookie } },
        ),
      ),
    );
    expect(callback.status).toBe(302);
    expect(callback.headers.get("location")).toBe(
      `${ORIGIN}/?artifact_id=${ARTIFACT_ID}&repository=example%2Fsite&pull_request=42`,
    );
    const setCookie = callback.headers.get("set-cookie") as string;
    expect(setCookie).toContain(`${OAUTH_COOKIE}=;`);
    const authenticated = await readSessionCookie(
      new Request(ORIGIN, {
        headers: { Cookie: cookiePair(setCookie, SESSION_COOKIE) },
      }),
      env,
    );
    expect(authenticated).toMatchObject({
      access_token: "ghu_short_lived",
      csrf_token: expect.any(String),
      login: "octocat",
    });
    expect(setCookie).not.toContain("must-not-be-retained");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("rejects an OAuth callback whose state does not match the sealed state", async () => {
    const start = await authorizationStart(
      context(
        new Request(
          `${ORIGIN}/api/auth/start?artifact_id=${ARTIFACT_ID}&repository=example%2Fsite&pull_request=42`,
        ),
      ),
    );
    const oauthCookie = cookiePair(
      start.headers.get("set-cookie") as string,
      OAUTH_COOKIE,
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      authorizationCallback(
        context(
          new Request(
            `${ORIGIN}/api/auth/callback?code=temporary-code&state=wrong-state`,
            { headers: { Cookie: oauthCookie } },
          ),
        ),
      ),
    ).rejects.toMatchObject({ code: "invalid_oauth_state", status: 401 });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("curator authorization and exact-head submission handlers", () => {
  it("rejects a signed-in repository reader before loading proposal data", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
      Response.json({ permission: "read" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      loadProposal(
        context(
          new Request(
            `${ORIGIN}/api/proposal?artifact_id=${ARTIFACT_ID}&repository=example%2Fsite&pull_request=42`,
            { headers: { Cookie: await sessionCookie() } },
          ),
        ),
      ),
    ).rejects.toMatchObject({
      code: "curator_permission_required",
      status: 403,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/collaborators/octocat/permission",
    );
  });

  it("reloads and verifies the proposal before posting the authenticated comment", async () => {
    const requests: string[] = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        requests.push(url);
        const response = proposalApi(url, init);
        if (response !== null) return response;
        if (url.endsWith("/issues/42/comments")) {
          expect(init?.method).toBe("POST");
          return Response.json({
            html_url:
              "https://github.com/example/site/pull/42#issuecomment-123",
          });
        }
        throw new Error(`Unexpected GitHub request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const response = await submitDecisions(
      context(
        new Request(`${ORIGIN}/api/submit?artifact_id=${ARTIFACT_ID}`, {
          body: JSON.stringify(submission()),
          headers: {
            "Content-Type": "application/json",
            Cookie: await sessionCookie(),
            Origin: ORIGIN,
            "X-CSRF-Token": "csrf-token",
          },
          method: "POST",
        }),
      ),
    );
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({
      comment_url: "https://github.com/example/site/pull/42#issuecomment-123",
    });
    const commentIndex = requests.findIndex((url) =>
      url.endsWith("/issues/42/comments"),
    );
    expect(commentIndex).toBe(requests.length - 1);
    expect(
      requests.findIndex((url) => url.endsWith("/pulls/42")),
    ).toBeGreaterThanOrEqual(0);
    expect(requests.findIndex((url) => url.endsWith("/pulls/42"))).toBeLessThan(
      commentIndex,
    );
  });

  it("reloads the proposal but rejects a stale head without posting", async () => {
    const requests: string[] = [];
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        requests.push(url);
        const response = proposalApi(url, init);
        if (response !== null) return response;
        throw new Error(`Unexpected GitHub request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      submitDecisions(
        context(
          new Request(`${ORIGIN}/api/submit?artifact_id=${ARTIFACT_ID}`, {
            body: JSON.stringify({
              ...submission(),
              head_sha: "d".repeat(40),
            }),
            headers: {
              "Content-Type": "application/json",
              Cookie: await sessionCookie(),
              Origin: ORIGIN,
              "X-CSRF-Token": "csrf-token",
            },
            method: "POST",
          }),
        ),
      ),
    ).rejects.toMatchObject({ code: "stale_submission", status: 409 });
    expect(requests.some((url) => url.endsWith("/pulls/42"))).toBe(true);
    expect(requests.some((url) => url.endsWith("/issues/42/comments"))).toBe(
      false,
    );
  });
});
