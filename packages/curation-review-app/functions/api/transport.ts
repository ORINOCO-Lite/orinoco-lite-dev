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
let requestAccepted = false;

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

function transportError(error) {
  const message = error instanceof Error ? error.message : "The GitHub transport failed.";
  post({
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
    throw new Error("The curation service returned an invalid response.");
  }
  if (!response.ok) {
    const detail = value && typeof value === "object" && value.error && typeof value.error === "object"
      ? value.error : {};
    const error = new Error(typeof detail.message === "string" ? detail.message : "The curation request failed.");
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

function reviewCoordinates() {
  return {
    artifact_id: target.artifact_id,
    handoff_nonce: target.handoff_nonce,
    pull_request: target.pull_request,
    repository: target.repository,
  };
}

async function startReview(session) {
  const query = new URLSearchParams({
    artifact_id: String(target.artifact_id),
    pull_request: String(target.pull_request),
    repository: target.repository,
  });
  const proposal = await requestJson("/api/proposal?" + query.toString());
  const listener = async (event) => {
    if (
      finished || event.source !== source || event.origin !== target.client_origin ||
      event.data === null || typeof event.data !== "object" || Array.isArray(event.data)
    ) return;
    const value = event.data;
    if (value.format === "orinoco-lite-review-proposal-request-v1") {
      if (!exactKeys(value, ["artifact_id", "format", "handoff_nonce", "pull_request", "repository"]) || !coordinatesMatch(value)) return;
      post({
        ...reviewCoordinates(),
        format: "orinoco-lite-review-proposal-message-v1",
        login: session.login,
        proposal,
      });
      return;
    }
    if (
      value.format !== "orinoco-lite-review-submission-message-v1" || requestAccepted ||
      !exactKeys(value, ["artifact_id", "format", "handoff_nonce", "pull_request", "repository", "submission"]) ||
      !coordinatesMatch(value)
    ) return;
    requestAccepted = true;
    post({ ...reviewCoordinates(), format: "orinoco-lite-review-post-started-v1" });
    setStatus("Posting the confirmed downstream decisions to GitHub…");
    let result;
    try {
      const submitted = await requestJson("/api/submit?artifact_id=" + encodeURIComponent(String(target.artifact_id)), {
        body: JSON.stringify(value.submission),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf_token },
        method: "POST",
      });
      result = {
        ...reviewCoordinates(),
        comment_url: submitted.comment_url,
        error: null,
        format: "orinoco-lite-review-submission-result-v1",
        retry_safe: false,
      };
    } catch (error) {
      result = {
        ...reviewCoordinates(),
        comment_url: null,
        error: error instanceof Error ? error.message : "The decisions could not be posted.",
        format: "orinoco-lite-review-submission-result-v1",
        retry_safe: Number.isInteger(error && error.status) && error.status >= 400 && error.status < 500,
      };
    }
    finished = true;
    post(result);
    setStatus(result.error === null ? "GitHub received the confirmed decisions." : result.error);
    window.setTimeout(() => window.close(), 250);
  };
  window.addEventListener("message", listener);
  post({ ...reviewCoordinates(), format: "orinoco-lite-review-transport-ready-v1" });
  setStatus("Connected. Complete and confirm the review in the downstream site.");
}

function shaclCoordinates() {
  return {
    handoff_nonce: target.handoff_nonce,
    repository: target.repository,
  };
}

function proposalMatchesGrant(proposal) {
  if (!proposal || typeof proposal !== "object" || proposal.repository?.toLowerCase() !== target.repository.toLowerCase()) return false;
  if (target.pull_request === null) return proposal.target?.kind === "standalone";
  return proposal.target?.kind === "pull_request" &&
    proposal.target.pull_request === target.pull_request &&
    proposal.target.expected_head_sha === target.expected_head_sha;
}

async function startShacl(session) {
  const listener = async (event) => {
    if (
      finished || requestAccepted || event.source !== source || event.origin !== target.client_origin ||
      event.data === null || typeof event.data !== "object" || Array.isArray(event.data)
    ) return;
    const value = event.data;
    if (
      value.format !== "orinoco-lite-shacl-proposal-message-v1" ||
      !exactKeys(value, ["format", "handoff_nonce", "proposal", "repository"]) ||
      !coordinatesMatch(value) || !proposalMatchesGrant(value.proposal)
    ) return;
    requestAccepted = true;
    post({ ...shaclCoordinates(), format: "orinoco-lite-shacl-proposal-started-v1" });
    setStatus("Creating the downstream proposal on GitHub…");
    let result;
    try {
      const created = await requestJson("/api/shacl/propose", {
        body: JSON.stringify(value.proposal),
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrf_token },
        method: "POST",
      });
      result = {
        ...shaclCoordinates(),
        error: null,
        format: "orinoco-lite-shacl-proposal-result-v1",
        result: created,
        retry_safe: false,
      };
    } catch (error) {
      result = {
        ...shaclCoordinates(),
        error: error instanceof Error ? error.message : "The bundle could not be proposed.",
        format: "orinoco-lite-shacl-proposal-result-v1",
        result: null,
        retry_safe: Number.isInteger(error && error.status) && error.status >= 400 && error.status < 500,
      };
    }
    finished = true;
    post(result);
    setStatus(result.error === null ? "GitHub created the proposal." : result.error);
    window.setTimeout(() => window.close(), 250);
  };
  window.addEventListener("message", listener);
  post({ ...shaclCoordinates(), format: "orinoco-lite-shacl-proposal-ready-v1" });
  setStatus("Connected. Return to the downstream editor. This window closes automatically after GitHub responds.");
}

async function main() {
  if (source === null || source.closed) throw new Error("Open this transport from the downstream site.");
  const session = await requestJson("/api/session");
  if (!matchingGrant(session)) {
    setStatus("Continuing to GitHub sign-in…");
    window.location.replace(authUrl());
    return;
  }
  if (target.kind === "review") await startReview(session);
  else await startShacl(session);
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
<title>Orinoco GitHub transport</title>
</head>
<body>
<p id="status" role="status">Starting the secure GitHub transport. This window closes automatically after GitHub responds.</p>
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
