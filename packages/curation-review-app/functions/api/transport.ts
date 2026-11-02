import { randomToken } from "../lib/encoding";
import { HttpError, requireMethod } from "../lib/http";
import { reviewTransportTarget, shaclTransportTarget } from "../lib/input";
import type { EventContext } from "../lib/pages";
import { configuredOrigin } from "../lib/session";

interface BrowserReviewTarget {
  artifact_id: number;
  client_origin: string;
  handoff_nonce: string;
  kind: "review";
  pull_request: number;
  repository: string;
}

interface BrowserShaclTarget {
  client_origin: string;
  expected_head_sha: string | null;
  handoff_nonce: string;
  kind: "shacl";
  pull_request: number | null;
  repository: string;
}

type BrowserTarget = BrowserReviewTarget | BrowserShaclTarget;

function browserTarget(url: URL): BrowserTarget {
  const kinds = url.searchParams.getAll("kind");
  if (kinds.length !== 1 || (kinds[0] !== "review" && kinds[0] !== "shacl")) {
    throw new HttpError(
      400,
      "invalid_transport",
      "The downstream transport kind is invalid.",
    );
  }
  const coordinates = new URL(url);
  coordinates.searchParams.delete("kind");
  if (kinds[0] === "review") {
    const target = reviewTransportTarget(coordinates);
    return {
      artifact_id: target.artifactId,
      client_origin: target.reviewOrigin,
      handoff_nonce: target.handoffNonce,
      kind: "review",
      pull_request: target.pullRequest,
      repository: target.repository,
    };
  }
  const target = shaclTransportTarget(coordinates);
  return {
    client_origin: target.editorOrigin,
    expected_head_sha: target.expectedHeadSha,
    handoff_nonce: target.handoffNonce,
    kind: "shacl",
    pull_request: target.pullRequest,
    repository: target.repository,
  };
}

function embeddedJson(value: unknown): string {
  return JSON.stringify(value)
    .replaceAll("<", "\\u003c")
    .replaceAll(">", "\\u003e")
    .replaceAll("&", "\\u0026")
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029");
}

function transportScript(target: BrowserTarget): string {
  return `"use strict";
const target = Object.freeze(${embeddedJson(target)});
const status = document.getElementById("status");
const source = window.opener;
let finished = false;
const issuedTokens = new Set();
const acceptedRequests = new Set();

function setStatus(value) {
  status.textContent = value;
}

function exactKeys(value, expected) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const observed = Object.keys(value).sort();
  const required = [...expected].sort();
  return observed.length === required.length && observed.every((key, index) => key === required[index]);
}

function coordinatesMatch(value) {
  if (
    value.handoff_nonce !== target.handoff_nonce ||
    typeof value.repository !== "string" ||
    value.repository.toLowerCase() !== target.repository.toLowerCase()
  ) return false;
  return target.kind !== "review" ||
    (value.artifact_id === target.artifact_id && value.pull_request === target.pull_request);
}

function post(value) {
  if (source !== null && !source.closed) source.postMessage(value, target.client_origin);
}

function errorDetails(error) {
  return {
    code: typeof error?.code === "string" && error.code.length > 0 ? error.code : null,
    status: Number.isSafeInteger(error?.status) ? error.status : null,
  };
}

function transportError(error) {
  const message = error instanceof Error ? error.message : "The GitHub transport failed.";
  const details = errorDetails(error);
  post({
    ...details,
    format: "orinoco-lite-transport-error-v1",
    handoff_nonce: target.handoff_nonce,
    kind: target.kind,
    message,
    repository: target.repository,
  });
  setStatus(message);
}

async function requestJson(path, init = {}) {
  const response = await fetch(path, {
    ...init,
    cache: "no-store",
    credentials: "same-origin",
    headers: { Accept: "application/json", ...(init.headers || {}) },
    redirect: "error",
  });
  let value;
  try {
    value = await response.json();
  } catch {
    throw new Error("The authentication service returned an invalid response.");
  }
  if (!response.ok) {
    const detail = value && typeof value === "object" && value.error && typeof value.error === "object"
      ? value.error : {};
    const error = new Error(typeof detail.message === "string" ? detail.message : "The authentication request failed.");
    error.code = typeof detail.code === "string" ? detail.code : null;
    error.status = response.status;
    throw error;
  }
  return value;
}

function authUrl() {
  const path = target.kind === "review" ? "/api/auth/start" : "/api/auth/shacl-start";
  const url = new URL(path, window.location.origin);
  url.searchParams.set("repository", target.repository);
  url.searchParams.set(target.kind === "review" ? "review_origin" : "editor_origin", target.client_origin);
  url.searchParams.set("handoff_nonce", target.handoff_nonce);
  if (target.kind === "review") {
    url.searchParams.set("artifact_id", String(target.artifact_id));
    url.searchParams.set("pull_request", String(target.pull_request));
  } else if (target.pull_request !== null && target.expected_head_sha !== null) {
    url.searchParams.set("pull_request", String(target.pull_request));
    url.searchParams.set("expected_head_sha", target.expected_head_sha);
  }
  return url.toString();
}

function matchingGrant(session) {
  if (!session || session.authenticated !== true) return false;
  const grant = target.kind === "review" ? session.review_grant : session.shacl_grant;
  if (
    !grant || grant.handoff_nonce !== target.handoff_nonce ||
    typeof grant.repository !== "string" ||
    grant.repository.toLowerCase() !== target.repository.toLowerCase()
  ) return false;
  if (target.kind === "review") {
    return grant.artifact_id === target.artifact_id &&
      grant.pull_request === target.pull_request &&
      grant.review_origin === target.client_origin;
  }
  return grant.editor_origin === target.client_origin &&
    grant.pull_request === target.pull_request &&
    grant.expected_head_sha === target.expected_head_sha;
}

async function startAuthentication(session) {
  async function authenticatedPost(path, input) {
    return requestJson(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf_token },
      body: JSON.stringify(input),
    });
  }
  async function revokeIssuedTokens() {
    await Promise.allSettled([...issuedTokens].map(async (token) => {
      await authenticatedPost("/api/auth/revoke", { token });
      issuedTokens.delete(token);
    }));
  }
  window.addEventListener("message", async (event) => {
    if (finished || event.source !== source || event.origin !== target.client_origin) return;
    const value = event.data;
    if (!exactKeys(value, ["format", "handoff_nonce", "repository", "id", "method", "input"]) ||
        value.format !== "orinoco-authentication-request-v1" ||
        value.handoff_nonce !== target.handoff_nonce || value.repository !== target.repository ||
        typeof value.id !== "string" || !/^[0-9a-f]{32}$/.test(value.id) ||
        acceptedRequests.has(value.id)) return;
    if (!["credentials", "authorize", "release"].includes(value.method)) return;
    acceptedRequests.add(value.id);
    let result = null;
    let error = null;
    try {
      if (value.method === "credentials") {
        if (!exactKeys(value.input, ["source_commit"])) throw new Error("Invalid credential request.");
        result = await authenticatedPost("/api/auth/credentials", { ...value.input, kind: target.kind });
        Object.values(result.credentials).forEach((credential) => issuedTokens.add(credential.token));
      } else if (value.method === "authorize") {
        if (!exactKeys(value.input, ["scope_proof", "input_repository", "input_commit"])) throw new Error("Invalid authorization request.");
        result = await authenticatedPost("/api/auth/authorize-submission", value.input);
      } else {
        await revokeIssuedTokens();
        result = { released: true };
        finished = true;
      }
    } catch (failure) {
      error = { ...errorDetails(failure), message: failure instanceof Error ? failure.message : "GitHub authentication failed." };
    }
    post({ format: "orinoco-authentication-response-v1", handoff_nonce: target.handoff_nonce,
      repository: target.repository, id: value.id, result, error });
  });
  window.addEventListener("pagehide", () => {
    for (const token of issuedTokens) {
      void fetch("/api/auth/revoke", {
        method: "POST", credentials: "same-origin", keepalive: true, redirect: "error",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf_token },
        body: JSON.stringify({ token }),
      }).catch(() => {});
    }
  });
  post({ format: "orinoco-authentication-ready-v1", handoff_nonce: target.handoff_nonce,
    repository: target.repository, login: session.login });
  setStatus("Connected. Continue in the website; its repository workflows will process your submission.");
}

async function main() {
  if (source === null || source.closed) throw new Error("Open this transport from the downstream site.");
  const session = await requestJson("/api/session");
  if (!matchingGrant(session)) {
    setStatus("Continuing to GitHub sign-in…");
    window.location.replace(authUrl());
    return;
  }
  await startAuthentication(session);
}

void main().catch(transportError);`;
}

function htmlResponse(target: BrowserTarget): Response {
  const nonce = randomToken();
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orinoco GitHub sign-in</title>
</head>
<body>
<p id="status" role="status">Connecting to GitHub. Continue in the website after sign-in.</p>
<script nonce="${nonce}">${transportScript(target)}</script>
</body>
</html>`;
  return new Response(html, {
    headers: {
      "Cache-Control": "no-store",
      "Content-Security-Policy":
        `default-src 'none'; base-uri 'none'; connect-src 'self'; ` +
        `form-action 'none'; frame-ancestors 'none'; object-src 'none'; ` +
        `script-src 'nonce-${nonce}'; style-src 'none'`,
      "Content-Type": "text/html; charset=utf-8",
      "Cross-Origin-Opener-Policy": "unsafe-none",
      "Cross-Origin-Resource-Policy": "same-origin",
      "Permissions-Policy":
        "camera=(), geolocation=(), microphone=(), payment=(), usb=()",
      Pragma: "no-cache",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
    },
  });
}

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const url = new URL(context.request.url);
  const origin = configuredOrigin(context.env);
  if (url.origin !== origin || url.pathname !== "/api/transport") {
    throw new HttpError(
      400,
      "invalid_transport",
      "The downstream transport URL is invalid.",
    );
  }
  return htmlResponse(browserTarget(url));
}
