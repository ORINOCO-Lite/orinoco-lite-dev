import { afterEach, describe, expect, it, vi } from "vitest";
import { onRequest as discoverReviews } from "../functions/api/discovery";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env, EventContext } from "../functions/lib/pages";
import { createSessionCookie } from "../functions/lib/session";

const ORIGIN = "https://review.example";
const REPOSITORY = "example/site";
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

function pullRequest(
  number: number,
  options: {
    baseRepository?: string;
    draft?: boolean;
    headRepository?: string;
    labels?: string[];
    state?: string;
  } = {},
): Record<string, unknown> {
  return {
    base: {
      repo: { full_name: options.baseRepository ?? REPOSITORY },
    },
    body: "Not a machine protocol: []{}<> punctuation is ordinary text.",
    draft: options.draft ?? true,
    head: {
      repo: { full_name: options.headRepository ?? REPOSITORY },
      sha: number.toString(16).padStart(40, "0"),
    },
    labels: (options.labels ?? ["curation-review"]).map((name) => ({ name })),
    number,
    state: options.state ?? "open",
    title: `Curation proposal ${number}`,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("review discovery", () => {
  it("returns only same-repository labeled proposals and exact unexpired artifacts", async () => {
    const proposalSeven = "a".repeat(40);
    const proposalEight = "b".repeat(40);
    const artifactName = `orinoco-curation-review-${proposalSeven}`;
    const requests: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      requests.push(url);
      if (url.endsWith("/collaborators/octocat/permission")) {
        return Response.json({ permission: "write" });
      }
      if (url.includes("/pulls?state=open")) {
        return Response.json([
          pullRequest(7),
          pullRequest(8, { draft: false }),
          pullRequest(9, { labels: ["not-curation-review"] }),
          pullRequest(10, { headRepository: "someone/fork" }),
          pullRequest(11, { state: "closed" }),
          pullRequest(12, { baseRepository: "example/other" }),
          pullRequest(13, { labels: ["Curation-Review"] }),
        ]);
      }
      if (url.includes("/pulls/7/commits?")) {
        return Response.json([{ sha: proposalSeven }]);
      }
      if (url.includes("/pulls/8/commits?")) {
        return Response.json([{ sha: proposalEight }]);
      }
      if (url.includes(`name=orinoco-curation-review-${proposalSeven}`)) {
        return Response.json({
          artifacts: [
            {
              created_at: "2030-01-01T00:00:00Z",
              expired: false,
              expires_at: "2099-01-01T00:00:00Z",
              id: 701,
              name: artifactName,
            },
            {
              created_at: "2029-01-01T00:00:00Z",
              expired: true,
              expires_at: "2099-01-01T00:00:00Z",
              id: 702,
              name: artifactName,
            },
            {
              created_at: "2019-01-01T00:00:00Z",
              expired: false,
              expires_at: "2020-01-01T00:00:00Z",
              id: 703,
              name: artifactName,
            },
            {
              created_at: "2031-01-01T00:00:00Z",
              expired: false,
              expires_at: "2099-01-01T00:00:00Z",
              id: 704,
              name: "orinoco-curation-review-not-the-proposal",
            },
          ],
          total_count: 4,
        });
      }
      if (url.includes(`name=orinoco-curation-review-${proposalEight}`)) {
        return Response.json({ artifacts: [], total_count: 0 });
      }
      throw new Error(`Unexpected GitHub request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await discoverReviews(
      context(
        new Request(`${ORIGIN}/api/discovery?repository=example%2Fsite`, {
          headers: { Cookie: await sessionCookie() },
        }),
      ),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      pull_requests: [
        {
          artifacts: [],
          draft: false,
          head_sha: "8".padStart(40, "0"),
          number: 8,
          proposal_sha: proposalEight,
          title: "Curation proposal 8",
        },
        {
          artifacts: [
            {
              created_at: "2030-01-01T00:00:00Z",
              expires_at: "2099-01-01T00:00:00Z",
              id: 701,
              name: artifactName,
            },
          ],
          draft: true,
          head_sha: "7".padStart(40, "0"),
          number: 7,
          proposal_sha: proposalSeven,
          title: "Curation proposal 7",
        },
      ],
      repository: REPOSITORY,
    });
    expect(requests[0]).toContain("/collaborators/octocat/permission");
    expect(requests[1]).toContain("/pulls?state=open");
    expect(requests.some((url) => url.includes("/pulls/9/commits"))).toBe(
      false,
    );
    expect(requests.some((url) => url.includes("/pulls/10/commits"))).toBe(
      false,
    );
    expect(requests.some((url) => url.includes("/pulls/11/commits"))).toBe(
      false,
    );
    expect(requests.some((url) => url.includes("/pulls/12/commits"))).toBe(
      false,
    );
    expect(requests.some((url) => url.includes("/pulls/13/commits"))).toBe(
      false,
    );
  });

  it("does not contact GitHub for an anonymous request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      discoverReviews(
        context(
          new Request(`${ORIGIN}/api/discovery?repository=example%2Fsite`),
        ),
      ),
    ).rejects.toMatchObject({ code: "authentication_required", status: 401 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("checks write authority before enumerating pull requests", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) =>
      Response.json({ permission: "read" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      discoverReviews(
        context(
          new Request(`${ORIGIN}/api/discovery?repository=example%2Fsite`, {
            headers: { Cookie: await sessionCookie() },
          }),
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

  it("bounds discovery before loading proposal and artifact coordinates", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/collaborators/octocat/permission")) {
        return Response.json({ permission: "admin" });
      }
      if (url.includes("/pulls?state=open")) {
        return Response.json(
          Array.from({ length: 25 }, (_, index) => pullRequest(index + 1)),
        );
      }
      const commit = url.match(/\/pulls\/(\d+)\/commits\?/);
      if (commit?.[1] !== undefined) {
        return Response.json([
          { sha: Number(commit[1]).toString(16).padStart(40, "a") },
        ]);
      }
      if (url.includes("/actions/artifacts?name=")) {
        return Response.json({ artifacts: [], total_count: 0 });
      }
      throw new Error(`Unexpected GitHub request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await discoverReviews(
      context(
        new Request(`${ORIGIN}/api/discovery?repository=example%2Fsite`, {
          headers: { Cookie: await sessionCookie() },
        }),
      ),
    );
    const result = (await response.json()) as {
      pull_requests: Array<{ number: number }>;
    };
    expect(result.pull_requests).toHaveLength(20);
    expect(result.pull_requests.map(({ number }) => number)).toEqual(
      Array.from({ length: 20 }, (_, index) => 25 - index),
    );
    expect(
      fetchMock.mock.calls.some(([url]) =>
        String(url).includes("/pulls/5/commits"),
      ),
    ).toBe(false);
    expect(fetchMock).toHaveBeenCalledTimes(42);
  });

  it("rejects duplicate or unexpected repository query fields", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const cookie = await sessionCookie();

    await expect(
      discoverReviews(
        context(
          new Request(
            `${ORIGIN}/api/discovery?repository=example%2Fsite&repository=example%2Fother`,
            { headers: { Cookie: cookie } },
          ),
        ),
      ),
    ).rejects.toMatchObject({ code: "invalid_query", status: 400 });
    await expect(
      discoverReviews(
        context(
          new Request(
            `${ORIGIN}/api/discovery?repository=example%2Fsite&pull_request=7`,
            { headers: { Cookie: cookie } },
          ),
        ),
      ),
    ).rejects.toMatchObject({ code: "unexpected_query", status: 400 });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
