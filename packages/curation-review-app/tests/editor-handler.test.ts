import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { base64urlEncode } from "../functions/lib/encoding";
import type { ExactHeadEditorInput } from "../functions/lib/editor-input";
import type { Env, EventContext } from "../functions/lib/pages";
import { createSessionCookie } from "../functions/lib/session";

const loadExactHeadEditorInput = vi.hoisted(() => vi.fn());
vi.mock("../functions/lib/editor-input", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../functions/lib/editor-input")>();
  return { ...actual, loadExactHeadEditorInput };
});

import { onRequest as loadEditor } from "../functions/api/shacl/editor";
import { onRequest as apiMiddleware } from "../functions/api/_middleware";

const ORIGIN = "https://review.example";
const HEAD = "a".repeat(40);
const DIGEST = "d".repeat(64);
const INDEX = `<!doctype html><html><head>
<script type="module" src="./assets/app.js"></script>
<link rel="stylesheet" href="./assets/app.css">
</head><body><div id="app"></div></body></html>`;

const editorInput: ExactHeadEditorInput = {
  artifactId: 123,
  files: {
    "edit/config.json": new TextEncoder().encode("{}\n"),
    "edit/data/record-sources.json": new TextEncoder().encode(
      JSON.stringify({
        format: "orinoco-static-record-sources",
        records: [],
        source_commit: HEAD,
        version: 2,
      }),
    ),
    "edit/records.ttl": new TextEncoder().encode(""),
  },
  headSha: HEAD,
  sourceCommit: HEAD,
  workflowRunId: 456,
};

const env: Env = {
  ASSETS: {
    fetch: vi.fn(
      async () =>
        new Response(INDEX, { headers: { "Content-Type": "text/html" } }),
    ),
  },
  EDITOR_RUNTIME_MANIFEST_SHA256: DIGEST,
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

async function cookie(login = "cached-user"): Promise<string> {
  return (
    await createSessionCookie(
      env,
      {
        access_token: "ghu_short_lived",
        csrf_token: "csrf-token",
        login,
      },
      28_800,
    )
  ).split(";", 1)[0] as string;
}

function request(query: string, session?: string): Request {
  return new Request(`${ORIGIN}/api/shacl/editor?${query}`, {
    headers: session === undefined ? {} : { Cookie: session },
  });
}

function common(url: string): Response | null {
  if (url.endsWith("/user")) {
    return Response.json({ id: 1, login: "fresh-user" });
  }
  if (url.endsWith("/collaborators/fresh-user/permission")) {
    return Response.json({ permission: "write" });
  }
  return null;
}

beforeEach(() => {
  loadExactHeadEditorInput.mockReset();
  loadExactHeadEditorInput.mockResolvedValue(editorInput);
  if (env.ASSETS === undefined) throw new Error("missing asset fixture");
  vi.mocked(env.ASSETS.fetch).mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("authenticated exact-head SHACL editor handler", () => {
  it("resolves a fresh default-branch head and loads its trusted artifact", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const shared = common(url);
      if (shared !== null) return shared;
      if (url === "https://api.github.com/repos/example/site") {
        return Response.json({
          default_branch: "main",
          full_name: "example/site",
        });
      }
      if (url.endsWith("/branches/main")) {
        return Response.json({ commit: { sha: HEAD }, name: "main" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await loadEditor(
      context(
        request("repository=example%2Fsite", await cookie("cached-user")),
      ),
    );

    expect(response.status).toBe(200);
    expect(loadExactHeadEditorInput).toHaveBeenCalledTimes(1);
    expect(loadExactHeadEditorInput.mock.calls[0]?.slice(1, 3)).toEqual([
      "example/site",
      HEAD,
    ]);
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain(
      "https://api.github.com/repos/example/site/collaborators/fresh-user/permission",
    );
    expect(await response.text()).toContain("orinoco:review-bundle");
  });

  it("requires the same-repository draft PR at the supplied exact head", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const shared = common(url);
      if (shared !== null) return shared;
      if (url.endsWith("/pulls/42")) {
        return Response.json({
          base: { ref: "main", repo: { full_name: "example/site" } },
          draft: true,
          head: {
            ref: "curation/edit",
            repo: { full_name: "example/site" },
            sha: HEAD,
          },
          number: 42,
          state: "open",
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const response = await loadEditor(
      context(
        request(
          `repository=example%2Fsite&pull_request=42&expected_head_sha=${HEAD}`,
          await cookie(),
        ),
      ),
    );
    expect(response.status).toBe(200);
    expect(loadExactHeadEditorInput.mock.calls[0]?.slice(1, 3)).toEqual([
      "example/site",
      HEAD,
    ]);
  });

  it("rejects a stale PR before looking for an artifact", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const shared = common(url);
      if (shared !== null) return shared;
      return Response.json({
        base: { ref: "main", repo: { full_name: "example/site" } },
        draft: true,
        head: {
          ref: "curation/edit",
          repo: { full_name: "example/site" },
          sha: "b".repeat(40),
        },
        number: 42,
        state: "open",
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      loadEditor(
        context(
          request(
            `repository=example%2Fsite&pull_request=42&expected_head_sha=${HEAD}`,
            await cookie(),
          ),
        ),
      ),
    ).rejects.toMatchObject({ code: "stale_shacl_editor", status: 409 });
    expect(loadExactHeadEditorInput).not.toHaveBeenCalled();
  });

  it("requires a sealed session, fresh user lookup, and write UAT", async () => {
    vi.stubGlobal("fetch", vi.fn());
    await expect(
      loadEditor(context(request("repository=example%2Fsite"))),
    ).rejects.toMatchObject({ code: "authentication_required", status: 401 });

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/user")) {
        return Response.json({ id: 1, login: "fresh-user" });
      }
      if (url.endsWith("/collaborators/fresh-user/permission")) {
        return Response.json({ permission: "read" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      loadEditor(context(request("repository=example%2Fsite", await cookie()))),
    ).rejects.toMatchObject({
      code: "curator_permission_required",
      status: 403,
    });
    expect(loadExactHeadEditorInput).not.toHaveBeenCalled();
  });

  it("accepts only the required repository and paired exact PR fields", async () => {
    const session = await cookie();
    for (const query of [
      "repository=example%2Fsite&unexpected=1",
      "repository=example%2Fsite&repository=example%2Fother",
      "repository=example%2Fsite&pull_request=42",
      `repository=example%2Fsite&expected_head_sha=${HEAD}`,
      `repository=example%2Fsite&pull_request=42&expected_head_sha=${HEAD}&expected_head_sha=${HEAD}`,
    ]) {
      await expect(
        loadEditor(context(request(query, session))),
      ).rejects.toMatchObject({
        code: "invalid_shacl_editor_target",
        status: 400,
      });
    }
    expect(loadExactHeadEditorInput).not.toHaveBeenCalled();
  });

  it("preserves only the editor HTML CSP through the API middleware", async () => {
    const editor = new Response("<!doctype html>", {
      headers: {
        "Content-Security-Policy":
          "default-src 'none'; script-src 'nonce-example'; frame-ancestors 'self'",
        "Content-Type": "text/html; charset=utf-8",
      },
    });
    const editorContext = context(
      new Request(`${ORIGIN}/api/shacl/editor?repository=example%2Fsite`),
    );
    editorContext.next = async () => editor;
    const preserved = await apiMiddleware(editorContext);
    expect(preserved.headers.get("content-security-policy")).toContain(
      "frame-ancestors 'self'",
    );

    const ordinaryContext = context(
      new Request(`${ORIGIN}/api/proposal?repository=example%2Fsite`),
    );
    ordinaryContext.next = async () =>
      new Response("{}", {
        headers: {
          "Content-Security-Policy": "default-src *",
          "Content-Type": "application/json",
        },
      });
    const ordinary = await apiMiddleware(ordinaryContext);
    expect(ordinary.headers.get("content-security-policy")).toContain(
      "frame-ancestors 'none'",
    );
    expect(ordinary.headers.get("content-security-policy")).not.toContain(
      "default-src *",
    );
  });
});
