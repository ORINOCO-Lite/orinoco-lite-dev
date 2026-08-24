import { afterEach, describe, expect, it, vi } from "vitest";
import { onRequest as submitDecisions } from "../functions/api/submit";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env, EventContext } from "../functions/lib/pages";
import { MAX_REVIEW_CANDIDATES } from "../functions/lib/proposal";
import { createSessionCookie } from "../functions/lib/session";
import type { CurationSubmission } from "../shared/contracts";
import { BASE_SHA, generatedSummary, HEAD_SHA, PROPOSAL_SHA } from "./fixtures";

const CLOUDFLARE_FREE_SUBREQUEST_LIMIT = 50;
const ORIGIN = "https://review.example";
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

function recordPath(index: number): string {
  return `metadata/records/example/record-${String(index + 1).padStart(4, "0")}.yaml`;
}

function annotationPath(index: number): string {
  return recordPath(index).replace(
    "metadata/records/",
    "metadata/overlays/annotations/",
  );
}

function submission(): CurationSubmission {
  return {
    adapter: "zotero",
    decisions: Array.from({ length: MAX_REVIEW_CANDIDATES }, (_, index) => ({
      disposition: "defer",
      operation: "add",
      pid: `example:record-${String(index + 1).padStart(4, "0")}`,
      record_path: recordPath(index),
    })),
    format: "orinoco-lite-curation-submission-v1",
    head_sha: HEAD_SHA,
    proposal_sha: PROPOSAL_SHA,
    pull_request: 42,
    repository: "example/site",
    source_coordinate: { group: 6197458, library_version: 451 },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Cloudflare Free support envelope", () => {
  it("submits the maximum candidate set within 50 outbound subrequests", async () => {
    const files = Array.from({ length: MAX_REVIEW_CANDIDATES }, (_, index) => [
      { filename: recordPath(index), status: "added" },
      { filename: annotationPath(index), status: "added" },
    ]).flat();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/collaborators/octocat/permission")) {
          return Response.json({ permission: "write" });
        }
        if (url.endsWith("/pulls/42")) {
          return Response.json({
            base: { repo: { full_name: "example/site" } },
            body: generatedSummary(MAX_REVIEW_CANDIDATES),
            head: { sha: HEAD_SHA },
            html_url: "https://github.com/example/site/pull/42",
            number: 42,
            state: "open",
          });
        }
        if (url.includes("/pulls/42/commits?")) {
          return Response.json([
            { parents: [{ sha: BASE_SHA }], sha: PROPOSAL_SHA },
          ]);
        }
        if (url.includes(`/commits/${PROPOSAL_SHA}?`)) {
          const page = Number(new URL(url).searchParams.get("page"));
          const start = (page - 1) * 100;
          return Response.json({
            files: files.slice(start, start + 100),
            sha: PROPOSAL_SHA,
          });
        }
        if (url === "https://api.github.com/graphql") {
          const body = JSON.parse(String(init?.body)) as {
            variables: Record<string, string>;
          };
          const repository: Record<string, unknown> = {};
          Object.entries(body.variables)
            .filter(([key]) => key.startsWith("expression"))
            .forEach(([key, expression]) => {
              const alias = `blob${key.slice("expression".length)}`;
              if (expression.startsWith(`${BASE_SHA}:`)) {
                repository[alias] = null;
              } else {
                const text = `pid: ${expression.slice(expression.lastIndexOf("/") + 1, -5)}\n`;
                repository[alias] = {
                  __typename: "Blob",
                  byteSize: new TextEncoder().encode(text).byteLength,
                  isBinary: false,
                  isTruncated: false,
                  text,
                };
              }
            });
          return Response.json({ data: { repository } });
        }
        if (url.endsWith("/issues/42/comments")) {
          return Response.json({
            html_url:
              "https://github.com/example/site/pull/42#issuecomment-123",
          });
        }
        throw new Error(`Unexpected GitHub request: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const sealed = await createSessionCookie(
      env,
      {
        access_token: "ghu_short_lived",
        csrf_token: "csrf-token",
        login: "octocat",
      },
      28_800,
    );
    const response = await submitDecisions(
      context(
        new Request(`${ORIGIN}/api/submit`, {
          body: JSON.stringify(submission()),
          headers: {
            "Content-Type": "application/json",
            Cookie: sealed.split(";", 1)[0] as string,
            Origin: ORIGIN,
            "X-CSRF-Token": "csrf-token",
          },
          method: "POST",
        }),
      ),
    );
    expect(response.status).toBe(201);
    expect(fetchMock).toHaveBeenCalledTimes(47);
    const urls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(
      urls.filter((url) => url.includes(`/commits/${PROPOSAL_SHA}?`)),
    ).toHaveLength(8);
    expect(
      urls.filter((url) => url === "https://api.github.com/graphql"),
    ).toHaveLength(35);
    expect(fetchMock.mock.calls.length).toBeLessThanOrEqual(
      CLOUDFLARE_FREE_SUBREQUEST_LIMIT,
    );
  });
});
