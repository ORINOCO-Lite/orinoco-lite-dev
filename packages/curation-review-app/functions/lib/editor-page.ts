import { base64Encode, randomToken } from "./encoding";
import type { ExactHeadEditorInput } from "./editor-input";
import { HttpError } from "./http";
import type { Env } from "./pages";

const DIGEST = /^[0-9a-f]{64}$/;
const MAX_RUNTIME_INDEX_BYTES = 262_144;
const RUNTIME_INDEX = "index.html";
const SCHEMA_FILES = [
  "config_default_xyzri.yaml",
  "dlschemas_owl.ttl",
  "dlschemas_shacl.ttl",
] as const;

function configurationError(message: string): never {
  throw new HttpError(500, "configuration_error", message);
}

function runtimeBase(digest: string): string {
  return `/editor-runtime/${digest}/`;
}

function contentLength(response: Response): number | null {
  const value = response.headers.get("content-length");
  if (value === null) return null;
  if (!/^(?:0|[1-9][0-9]*)$/.test(value)) {
    configurationError("The staged editor runtime returned an invalid size.");
  }
  return Number(value);
}

async function boundedRuntimeIndex(response: Response): Promise<string> {
  if (
    response.status !== 200 ||
    !response.headers.get("content-type")?.toLowerCase().startsWith("text/html")
  ) {
    configurationError("The staged editor runtime index is unavailable.");
  }
  const declared = contentLength(response);
  if (declared !== null && declared > MAX_RUNTIME_INDEX_BYTES) {
    configurationError("The staged editor runtime index is too large.");
  }
  if (response.body === null) {
    configurationError("The staged editor runtime index is empty.");
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_RUNTIME_INDEX_BYTES) {
      await reader.cancel();
      configurationError("The staged editor runtime index is too large.");
    }
    chunks.push(value);
  }
  if (size === 0 || (declared !== null && declared !== size)) {
    configurationError("The staged editor runtime returned an invalid size.");
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    configurationError("The staged editor runtime index is not valid UTF-8.");
  }
}

function oneMatch(
  value: string,
  pattern: RegExp,
  label: string,
): RegExpMatchArray {
  const matches = [...value.matchAll(pattern)];
  if (matches.length !== 1 || matches[0] === undefined) {
    configurationError(`The staged editor runtime has an invalid ${label}.`);
  }
  return matches[0];
}

function insertionOffset(index: string): number {
  if (
    !/^\s*<!doctype\s+html(?:\s[^>]*)?>/i.test(index) ||
    index.includes("\0")
  ) {
    configurationError("The staged editor runtime index has an invalid shape.");
  }
  const head = oneMatch(index, /<head\b[^>]*>/gi, "head");
  const closeHead = oneMatch(index, /<\/head\s*>/gi, "head");
  const body = oneMatch(index, /<body\b[^>]*>/gi, "body");
  const closeBody = oneMatch(index, /<\/body\s*>/gi, "body");
  const headEnd = (head.index ?? -1) + head[0].length;
  if (
    headEnd <= 0 ||
    (closeHead.index ?? -1) <= headEnd ||
    (body.index ?? -1) <= (closeHead.index ?? -1) ||
    (closeBody.index ?? -1) <= (body.index ?? -1) ||
    /<base\b/i.test(index) ||
    /<meta\b[^>]*http-equiv\s*=\s*["']?content-security-policy/i.test(index)
  ) {
    configurationError("The staged editor runtime index has an invalid shape.");
  }
  const scripts = [...index.matchAll(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi)];
  if (
    scripts.length !== 1 ||
    !/\btype\s*=\s*["']module["']/i.test(scripts[0]?.[0] ?? "") ||
    !/\bsrc\s*=\s*["']\.\/assets\/[A-Za-z0-9_.-]+\.js["']/i.test(
      scripts[0]?.[0] ?? "",
    ) ||
    !/<link\b[^>]*\bhref\s*=\s*["']\.\/assets\/[A-Za-z0-9_.-]+\.css["'][^>]*>/i.test(
      index,
    )
  ) {
    configurationError("The staged editor runtime assets are invalid.");
  }
  return headEnd;
}

function bootstrap(
  repository: string,
  input: ExactHeadEditorInput,
  base: string,
): string {
  const resources = {
    "config.json": {
      body: base64Encode(input.files["edit/config.json"]),
      type: "application/json; charset=utf-8",
    },
    "data/record-sources.json": {
      body: base64Encode(input.files["edit/data/record-sources.json"]),
      type: "application/json; charset=utf-8",
    },
    "records.ttl": {
      body: base64Encode(input.files["edit/records.ttl"]),
      type: "text/turtle; charset=utf-8",
    },
  };
  return `(() => {
  "use strict";
  const base = new URL(${JSON.stringify(base)}, window.location.origin);
  const encoded = Object.freeze(${JSON.stringify(resources)});
  const schemas = new Set(${JSON.stringify(SCHEMA_FILES)});
  const originalFetch = window.fetch.bind(window);
  const requestUrl = (input) => new URL(
    input instanceof Request ? input.url : input instanceof URL ? input.href : String(input),
    document.baseURI,
  );
  const method = (input, init) => String(
    init && init.method ? init.method : input instanceof Request ? input.method : "GET",
  ).toUpperCase();
  const bytes = (value) => Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
  window.fetch = (input, init) => {
    const url = requestUrl(input);
    if (url.origin === window.location.origin && url.search === "" && url.hash === "") {
      const relative = url.pathname.startsWith(base.pathname)
        ? url.pathname.slice(base.pathname.length)
        : null;
      const resource = relative !== null && Object.hasOwn(encoded, relative)
        ? encoded[relative]
        : undefined;
      if (resource !== undefined) {
        const verb = method(input, init);
        if (verb !== "GET" && verb !== "HEAD") {
          return Promise.resolve(new Response(null, { status: 405 }));
        }
        return Promise.resolve(new Response(verb === "HEAD" ? null : bytes(resource.body), {
          headers: {
            "Cache-Control": "no-store",
            "Content-Type": resource.type,
            "X-Content-Type-Options": "nosniff",
          },
        }));
      }
      if (relative !== null && schemas.has(relative)) {
        const target = new URL(relative, base);
        const redirected = input instanceof Request ? new Request(target, input) : target;
        return originalFetch(redirected, init);
      }
    }
    return originalFetch(input, init);
  };
  window.addEventListener("orinoco:review-bundle", (event) => {
    if (window.parent === window || !(event instanceof CustomEvent)) return;
    window.parent.postMessage({
      bundle: event.detail,
      format: "orinoco-lite-shacl-bundle-message-v1",
      repository: ${JSON.stringify(repository)},
    }, window.location.origin);
  });
})();`;
}

function responseHeaders(nonce: string): Headers {
  return new Headers({
    "Cache-Control": "no-store",
    "Content-Security-Policy": [
      "default-src 'none'",
      "base-uri 'self'",
      "connect-src 'self'",
      "font-src 'self' data:",
      "form-action 'none'",
      "frame-ancestors 'self'",
      "img-src 'self' data: blob:",
      "object-src 'none'",
      `script-src 'self' 'nonce-${nonce}'`,
      "style-src 'self' 'unsafe-inline'",
    ].join("; "),
    "Content-Type": "text/html; charset=utf-8",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy":
      "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
    Pragma: "no-cache",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
  });
}

export async function renderEditorPage(
  env: Env,
  requestUrl: string,
  repository: string,
  input: ExactHeadEditorInput,
): Promise<Response> {
  const digest = env.EDITOR_RUNTIME_MANIFEST_SHA256;
  if (typeof digest !== "string" || !DIGEST.test(digest)) {
    configurationError(
      "EDITOR_RUNTIME_MANIFEST_SHA256 must be a lowercase SHA-256 digest.",
    );
  }
  if (env.ASSETS === undefined || typeof env.ASSETS.fetch !== "function") {
    configurationError("The staged editor runtime asset binding is missing.");
  }
  const base = runtimeBase(digest);
  const indexUrl = new URL(`${base}${RUNTIME_INDEX}`, requestUrl);
  const indexResponse = await env.ASSETS.fetch(
    new Request(indexUrl, {
      headers: { Accept: "text/html" },
      method: "GET",
      redirect: "manual",
    }),
  );
  const index = await boundedRuntimeIndex(indexResponse);
  const offset = insertionOffset(index);
  const nonce = randomToken(24);
  const injected = [
    `\n<base href="${base}">`,
    `<script nonce="${nonce}">\n${bootstrap(repository, input, base)}\n</script>\n`,
  ].join("\n");
  return new Response(
    `${index.slice(0, offset)}${injected}${index.slice(offset)}`,
    {
      headers: responseHeaders(nonce),
    },
  );
}
