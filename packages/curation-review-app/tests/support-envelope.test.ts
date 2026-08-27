import { afterEach, describe, expect, it, vi } from "vitest";
import { onRequest as submitDecisions } from "../functions/api/submit";
import type { ReviewBundle } from "../functions/lib/bundle";
import {
  MAX_REVIEW_CANDIDATES,
  MAX_REVIEW_PATHS,
} from "../functions/lib/bundle";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env, EventContext } from "../functions/lib/pages";
import { createSessionCookie } from "../functions/lib/session";
import type { CurationSubmission, ReviewGrant } from "../shared/contracts";
import { MAX_GITHUB_TEXT_LENGTH } from "../shared/contracts";
import {
  ARTIFACT_ID,
  BASE_SHA,
  CLAIM_ONE,
  HEAD_SHA,
  ORINOCO_CONFIG,
  PROPOSAL_SHA,
  WORKFLOW_RUN_ID,
  proposalCommitMessage,
  reviewBundleArchive,
} from "./fixtures";

const CLOUDFLARE_FREE_SUBREQUEST_LIMIT = 50;
const FILES_PER_COMMIT_PAGE = 100;
const BLOBS_PER_GRAPHQL_REQUEST = 20;
const ORIGIN = "https://review.example";
const REVIEW_ORIGIN = "https://site.example";
const REVIEW_NONCE = "e".repeat(64);
const env: Env = {
  GITHUB_CLIENT_ID: "Iv1.example",
  GITHUB_CLIENT_SECRET: "client-secret",
  PUBLIC_ORIGIN: ORIGIN,
  SESSION_SEAL_KEY: base64urlEncode(new Uint8Array(32).fill(7)),
};
const REVIEW_GRANT: ReviewGrant = {
  artifact_id: ARTIFACT_ID,
  handoff_nonce: REVIEW_NONCE,
  pull_request: 42,
  repository: "example/site",
  review_origin: REVIEW_ORIGIN,
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

function identity(index: number): string {
  return String(index + 1).padStart(4, "0");
}

function recordPath(index: number): string {
  return `metadata/records/example/record-${identity(index)}.yaml`;
}

function annotationPath(index: number): string {
  return recordPath(index).replace(
    "metadata/records/",
    "metadata/overlays/annotations/",
  );
}

function bundle(): ReviewBundle {
  return {
    adapter: "zotero",
    candidates: Array.from({ length: MAX_REVIEW_CANDIDATES }, (_, index) => ({
      blockers: [],
      claim_sha256: CLAIM_ONE,
      friendly_id: `DRI-${identity(index)}`,
      label: `Record ${identity(index)}`,
      operation: "modify",
      paths: [recordPath(index), annotationPath(index)],
      pid: `example:record-${identity(index)}`,
      record_path: recordPath(index),
      source_namespace: "zotero:group:6197458",
      source_record_id: `item:${identity(index)}`,
    })),
    format: "orinoco-lite-curation-review-bundle-v1",
    metadata_base_sha: BASE_SHA,
    proposal_sha: PROPOSAL_SHA,
    pull_request: 42,
    repository: "example/site",
    source_coordinate: { group: 6197458, library_version: 451 },
    workflow_run_id: WORKFLOW_RUN_ID,
  };
}

function submission(): CurationSubmission {
  return {
    adapter: "zotero",
    decisions: Array.from({ length: MAX_REVIEW_CANDIDATES }, (_, index) => ({
      disposition: "defer",
      operation: "modify",
      pid: `example:record-${identity(index)}`,
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

describe("hosted service-resource envelope", () => {
  it("submits 225 records and 450 metadata paths within 50 subrequests", async () => {
    const reviewBundle = bundle();
    const archive = reviewBundleArchive(reviewBundle);
    const files = reviewBundle.candidates.flatMap((candidate) =>
      candidate.paths.map((filename) => ({ filename, status: "modified" })),
    );
    const storage =
      "https://pipelines.actions.githubusercontent.com/results/archive.zip?sig=short-lived";
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
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
            size_in_bytes: archive.byteLength,
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
            headers: { Location: storage },
            status: 302,
          });
        }
        if (url === storage) {
          return new Response(new Uint8Array(archive).buffer, {
            headers: { "Content-Length": String(archive.byteLength) },
          });
        }
        if (url.includes(`/commits/${PROPOSAL_SHA}?`)) {
          const page = Number(new URL(url).searchParams.get("page"));
          const start = (page - 1) * FILES_PER_COMMIT_PAGE;
          return Response.json({
            files: files.slice(start, start + FILES_PER_COMMIT_PAGE),
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
              if (expression === `${BASE_SHA}:orinoco.yaml`) {
                const text = ORINOCO_CONFIG;
                repository[alias] = {
                  __typename: "Blob",
                  byteSize: new TextEncoder().encode(text).byteLength,
                  isBinary: false,
                  isTruncated: false,
                  text,
                };
                return;
              }
              const filename = expression.slice(
                expression.lastIndexOf("/") + 1,
              );
              const pid = filename.replace(/\.ya?ml$/, "");
              const text = `pid: example:${pid}\ntitle: ${pid}\n`;
              repository[alias] = {
                __typename: "Blob",
                byteSize: new TextEncoder().encode(text).byteLength,
                isBinary: false,
                isTruncated: false,
                text,
              };
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
        review_grant: REVIEW_GRANT,
      },
      28_800,
    );
    const response = await submitDecisions(
      context(
        new Request(`${ORIGIN}/api/submit?artifact_id=${ARTIFACT_ID}`, {
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
    expect(files).toHaveLength(MAX_REVIEW_PATHS);
    const commitPages = Math.ceil(MAX_REVIEW_PATHS / FILES_PER_COMMIT_PAGE);
    const graphRequests = Math.ceil(
      (MAX_REVIEW_CANDIDATES * 3) / BLOBS_PER_GRAPHQL_REQUEST,
    );
    const expectedRequests = 8 + commitPages + graphRequests;
    expect(expectedRequests).toBe(47);
    expect(fetchMock).toHaveBeenCalledTimes(expectedRequests);
    expect(fetchMock.mock.calls.length).toBeLessThanOrEqual(
      CLOUDFLARE_FREE_SUBREQUEST_LIMIT,
    );
    const commentCall = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith("/issues/42/comments"),
    );
    const commentRequest = JSON.parse(String(commentCall?.[1]?.body)) as {
      body: string;
    };
    expect(commentRequest.body.length).toBeLessThanOrEqual(
      MAX_GITHUB_TEXT_LENGTH,
    );
  });
});
