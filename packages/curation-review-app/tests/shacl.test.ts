import { afterEach, describe, expect, it, vi } from "vitest";
import { onRequest as proposeShacl } from "../functions/api/shacl/propose";
import { base64urlEncode } from "../functions/lib/encoding";
import type { Env, EventContext } from "../functions/lib/pages";
import { createSessionCookie } from "../functions/lib/session";
import type { ShaclGrant, ShaclReviewBundle } from "../shared/contracts";
import {
  MAX_SHACL_BUNDLE_BYTES,
  SHACL_BUNDLE_PATH,
  parseShaclProposalRequest,
  parseShaclReviewBundle,
  serializeShaclReviewBundle,
  validateShaclRecordPaths,
} from "../functions/lib/shacl";
import { metadataRoots } from "../shared/metadata";

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

const SHACL_GRANT: ShaclGrant = {
  editor_origin: "https://site.example",
  expected_head_sha: null,
  handoff_nonce: "d".repeat(64),
  pull_request: null,
  repository: "example/site",
};

async function sessionCookie(
  shaclGrant: ShaclGrant | null = null,
): Promise<string> {
  return (
    await createSessionCookie(
      env,
      {
        access_token: "ghu_curator",
        csrf_token: "csrf-token",
        login: "octocat",
        shacl_grant: shaclGrant,
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
        source_path: "site-specific/metadata/records/Thing/one.yaml",
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

  it("rejects extra fields, duplicate coordinates, and unsafe paths", () => {
    expect(() =>
      parseShaclReviewBundle({ ...bundle(), retained_copy: true }),
    ).toThrow("missing or unexpected fields");

    const duplicate = bundle();
    duplicate.records.push({ ...duplicate.records[0]! });
    expect(() => parseShaclReviewBundle(duplicate)).toThrow(
      "duplicate record coordinates",
    );

    const unsafe = bundle();
    unsafe.records[0]!.source_path = "../metadata/records/Thing/one.yaml";
    expect(() => parseShaclReviewBundle(unsafe)).toThrow("source path");
  });

  it.each([
    ["current", "site-specific/metadata/records"],
    ["legacy", "metadata/records"],
    ["custom", ".site-data/catalog/records"],
  ])("binds %s SHACL paths to configured records", (_label, recordRoot) => {
    const value = bundle();
    value.records[0]!.source_path = `${recordRoot}/Thing/one.yaml`;
    const parsed = parseShaclReviewBundle(value);

    expect(() =>
      validateShaclRecordPaths(parsed, metadataRoots(recordRoot)),
    ).not.toThrow();
    expect(() =>
      validateShaclRecordPaths(parsed, metadataRoots("other/metadata/records")),
    ).toThrow("outside configured metadata records");
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

  it("rejects the removed acknowledgement field before contacting GitHub", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      proposeShacl(
        context(
          new Request(`${ORIGIN}/api/shacl/propose`, {
            body: JSON.stringify({
              acknowledge_public_data: true,
              bundle: bundle(),
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
    ).rejects.toMatchObject({ status: 400 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    { grant: null, label: "missing" },
    {
      grant: { ...SHACL_GRANT, repository: "example/other" },
      label: "repository-mismatched",
    },
    {
      grant: {
        ...SHACL_GRANT,
        expected_head_sha: SOURCE,
        pull_request: 42,
      },
      label: "target-mismatched",
    },
  ])(
    "rejects a $label OAuth grant before contacting GitHub",
    async ({ grant }) => {
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
                Cookie: await sessionCookie(grant),
                Origin: ORIGIN,
                "X-CSRF-Token": "csrf-token",
              },
              method: "POST",
            }),
          ),
        ),
      ).rejects.toMatchObject({ code: "shacl_grant_required", status: 403 });
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );
});
