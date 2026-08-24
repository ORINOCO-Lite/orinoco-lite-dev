import { afterEach, describe, expect, it, vi } from "vitest";
import { onRequest as proposeShacl } from "../functions/api/shacl/propose";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env, EventContext } from "../functions/lib/pages";
import { createSessionCookie } from "../functions/lib/session";
import type { ShaclReviewBundle } from "../shared/contracts";
import {
  MAX_SHACL_BUNDLE_BYTES,
  SHACL_BUNDLE_PATH,
  parseShaclProposalRequest,
  parseShaclReviewBundle,
  serializeShaclReviewBundle,
} from "../functions/lib/shacl";

const SOURCE = "a".repeat(40);
const ORIGIN = "https://review.example";
const env: Env = {
  GITHUB_CLIENT_ID: "Iv1.example",
  GITHUB_CLIENT_SECRET: "secret",
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
        access_token: "ghu_curator",
        csrf_token: "csrf-token",
        login: "octocat",
      },
      28_800,
    )
  ).split(";", 1)[0] as string;
}

afterEach(() => vi.unstubAllGlobals());

function bundle(): ShaclReviewBundle {
  return {
    format: "orinoco-shacl-review-bundle",
    records: [
      {
        pid: "example:one",
        rdf_turtle:
          '<https://example.test/one> <https://example.test/p> "é" .\n',
        schema_type: "example:Thing",
        source_path: "metadata/records/Thing/one.yaml",
        source_sha256: "b".repeat(64),
      },
    ],
    source_commit: SOURCE,
    version: 2,
  };
}

describe("normal SHACL Vue v2 bundle handoff", () => {
  it("preserves the normal Download bundle JSON bytes at one fixed path", () => {
    const value = bundle();
    const parsed = parseShaclReviewBundle(value);
    expect(new TextDecoder().decode(serializeShaclReviewBundle(parsed))).toBe(
      `${JSON.stringify(value, null, 2)}\n`,
    );
    expect(SHACL_BUNDLE_PATH).toBe(
      ".orinoco-lite/shacl-vue-review-bundle.json",
    );
  });

  it("binds an existing-PR request to the same exact source and head", () => {
    expect(
      parseShaclProposalRequest({
        bundle: bundle(),
        format: "orinoco-lite-shacl-proposal-v1",
        repository: "example/site",
        target: {
          expected_head_sha: SOURCE,
          kind: "pull_request",
          pull_request: 42,
        },
      }),
    ).toMatchObject({
      repository: "example/site",
      target: { expected_head_sha: SOURCE, pull_request: 42 },
    });
    expect(() =>
      parseShaclProposalRequest({
        bundle: bundle(),
        format: "orinoco-lite-shacl-proposal-v1",
        repository: "example/site",
        target: {
          expected_head_sha: "c".repeat(40),
          kind: "pull_request",
          pull_request: 42,
        },
      }),
    ).toThrow("does not match the expected pull-request head");
    expect(() =>
      parseShaclProposalRequest({
        bundle: bundle(),
        format: "orinoco-lite-shacl-proposal-v1",
        repository: "example/site",
        target: {
          expected_head_sha: SOURCE,
          kind: "pull_request",
          pull_request: "42",
        },
      }),
    ).toThrow("pull-request target is invalid");
  });

  it("rejects extra fields, duplicate coordinates, and non-record paths", () => {
    expect(() =>
      parseShaclReviewBundle({ ...bundle(), retained_copy: true }),
    ).toThrow("missing or unexpected fields");

    const duplicate = bundle();
    duplicate.records.push({ ...duplicate.records[0]! });
    expect(() => parseShaclReviewBundle(duplicate)).toThrow(
      "duplicate record coordinates",
    );

    const annotation = bundle();
    annotation.records[0]!.source_path =
      "metadata/overlays/annotations/Thing/one.yaml";
    expect(() => parseShaclReviewBundle(annotation)).toThrow("source path");
  });

  it("rejects a serialized normal bundle beyond the released 10 MiB bound", () => {
    const oversized = bundle();
    oversized.records[0]!.rdf_turtle = "x".repeat(MAX_SHACL_BUNDLE_BYTES);
    expect(() => parseShaclReviewBundle(oversized)).toThrow("exceeds 10 MiB");
  });
});

describe("SHACL proposal API boundary", () => {
  it("requires the sealed session CSRF token before any GitHub write", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      proposeShacl(
        context(
          new Request(`${ORIGIN}/api/shacl/propose`, {
            body: JSON.stringify({
              bundle: bundle(),
              format: "orinoco-lite-shacl-proposal-v1",
              repository: "example/site",
              target: { kind: "standalone" },
            }),
            headers: {
              "Content-Type": "application/json",
              Cookie: await sessionCookie(),
              Origin: ORIGIN,
              "X-CSRF-Token": "wrong-token",
            },
            method: "POST",
          }),
        ),
      ),
    ).rejects.toMatchObject({ code: "invalid_csrf", status: 403 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an expanded transport envelope before contacting GitHub", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      proposeShacl(
        context(
          new Request(`${ORIGIN}/api/shacl/propose`, {
            body: JSON.stringify({
              bundle: bundle(),
              durable_copy: true,
              format: "orinoco-lite-shacl-proposal-v1",
              repository: "example/site",
              target: { kind: "standalone" },
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
    ).rejects.toThrow("missing or unexpected fields");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
