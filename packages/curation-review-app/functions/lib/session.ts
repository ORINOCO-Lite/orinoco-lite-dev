import {
  arrayBuffer,
  base64urlDecode,
  base64urlEncode,
  decodeUtf8,
  utf8,
} from "./encoding";
import { HttpError, requireExactKeys } from "./http";
import type { Env } from "./pages";
import {
  isSafeEditorOrigin,
  isSafeReviewOrigin,
  isReviewHandoffNonce,
  isShaclHandoffNonce,
  type ReviewGrant,
  type ShaclGrant,
} from "../../shared/contracts";

export const OAUTH_COOKIE = "__Host-orinoco_oauth";
export const SESSION_COOKIE = "__Host-orinoco_session";

const VERSION = "v1";
const OAUTH_TTL_SECONDS = 600;
const MAX_SESSION_TTL_SECONDS = 3_600;

interface OAuthCookieCommon {
  code_verifier: string;
  expires_at: number;
  issued_at: number;
  origin: string;
  repository: string;
  state: string;
}

export interface ReviewOAuthCookieState extends OAuthCookieCommon {
  artifact_id: number;
  handoff_nonce: string;
  kind: "review";
  pull_request: number;
  review_origin: string;
}

export interface ShaclOAuthCookieState extends OAuthCookieCommon {
  editor_origin: string;
  expected_head_sha: string | null;
  handoff_nonce: string;
  kind: "shacl";
  pull_request: number | null;
}

export type OAuthCookieState = ReviewOAuthCookieState | ShaclOAuthCookieState;

type OAuthCookieInput =
  | Omit<ReviewOAuthCookieState, "expires_at" | "issued_at">
  | Omit<ShaclOAuthCookieState, "expires_at" | "issued_at">;

export interface SessionCookieState {
  access_token: string;
  csrf_token: string;
  expires_at: number;
  issued_at: number;
  login: string;
  review_grant: ReviewGrant | null;
  shacl_grant: ShaclGrant | null;
}

function nowSeconds(): number {
  return Math.floor(Date.now() / 1_000);
}

function validOneLine(value: unknown, maximum: number): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= maximum &&
    !/[\r\n\0]/.test(value)
  );
}

function requireTimestamp(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) {
    throw new HttpError(401, "invalid_session", `${label} is invalid.`);
  }
  return Number(value);
}

function parseReviewGrant(value: unknown): ReviewGrant | null {
  if (value === null) return null;
  if (
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.keys(value).sort().join("\0") !==
      [
        "artifact_id",
        "handoff_nonce",
        "pull_request",
        "repository",
        "review_origin",
      ]
        .sort()
        .join("\0")
  ) {
    throw new HttpError(401, "invalid_session", "The session is invalid.");
  }
  const grant = value as Record<string, unknown>;
  if (
    !Number.isSafeInteger(grant.artifact_id) ||
    Number(grant.artifact_id) < 1 ||
    !Number.isSafeInteger(grant.pull_request) ||
    Number(grant.pull_request) < 1 ||
    !validOneLine(grant.repository, 200) ||
    !/^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/.test(
      grant.repository,
    ) ||
    grant.repository.includes("..") ||
    !isSafeReviewOrigin(grant.review_origin) ||
    !isReviewHandoffNonce(grant.handoff_nonce)
  ) {
    throw new HttpError(401, "invalid_session", "The session is invalid.");
  }
  return {
    artifact_id: Number(grant.artifact_id),
    handoff_nonce: grant.handoff_nonce,
    pull_request: Number(grant.pull_request),
    repository: grant.repository,
    review_origin: grant.review_origin,
  };
}

function parseShaclGrant(value: unknown): ShaclGrant | null {
  if (value === null) return null;
  requireExactKeys(
    value,
    [
      "editor_origin",
      "expected_head_sha",
      "handoff_nonce",
      "pull_request",
      "repository",
    ],
    "SHACL grant",
  );
  const standalone =
    value.expected_head_sha === null && value.pull_request === null;
  const existing =
    typeof value.expected_head_sha === "string" &&
    /^[0-9a-f]{40}$/.test(value.expected_head_sha) &&
    Number.isSafeInteger(value.pull_request) &&
    Number(value.pull_request) > 0;
  if (
    !isSafeEditorOrigin(value.editor_origin) ||
    !isShaclHandoffNonce(value.handoff_nonce) ||
    !validOneLine(value.repository, 200) ||
    !/^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/.test(
      value.repository,
    ) ||
    value.repository.includes("..") ||
    (!standalone && !existing)
  ) {
    throw new HttpError(401, "invalid_session", "The session is invalid.");
  }
  return {
    editor_origin: value.editor_origin,
    expected_head_sha: existing ? String(value.expected_head_sha) : null,
    handoff_nonce: value.handoff_nonce,
    pull_request: existing ? Number(value.pull_request) : null,
    repository: value.repository,
  };
}

function cookieValue(request: Request, name: string): string | null {
  const header = request.headers.get("cookie");
  if (header === null) return null;
  for (const item of header.split(";")) {
    const separator = item.indexOf("=");
    if (separator < 0) continue;
    if (item.slice(0, separator).trim() === name) {
      return item.slice(separator + 1).trim();
    }
  }
  return null;
}

function cookie(name: string, value: string, maxAge: number): string {
  return `${name}=${value}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`;
}

export function clearCookie(name: string): string {
  return cookie(name, "", 0);
}

function publicOrigin(value: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new HttpError(
      500,
      "configuration_error",
      "PUBLIC_ORIGIN is invalid.",
    );
  }
  const local =
    url.protocol === "http:" &&
    (url.hostname === "127.0.0.1" || url.hostname === "localhost");
  if (
    (!local && url.protocol !== "https:") ||
    url.origin !== value ||
    url.pathname !== "/"
  ) {
    throw new HttpError(
      500,
      "configuration_error",
      "PUBLIC_ORIGIN must be an HTTPS origin (or a loopback development origin).",
    );
  }
  return url.origin;
}

export function configuredOrigin(env: Env): string {
  return publicOrigin(env.PUBLIC_ORIGIN);
}

async function key(env: Env): Promise<CryptoKey> {
  const raw = base64urlDecode(env.SESSION_SEAL_KEY);
  if (raw.byteLength !== 32) {
    throw new HttpError(
      500,
      "configuration_error",
      "SESSION_SEAL_KEY must encode exactly 32 bytes.",
    );
  }
  return crypto.subtle.importKey("raw", arrayBuffer(raw), "AES-GCM", false, [
    "encrypt",
    "decrypt",
  ]);
}

async function seal(env: Env, purpose: string, value: object): Promise<string> {
  const iv = new Uint8Array(12);
  crypto.getRandomValues(iv);
  const encrypted = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv,
      additionalData: arrayBuffer(utf8(`orinoco:${purpose}:${VERSION}`)),
    },
    await key(env),
    arrayBuffer(utf8(JSON.stringify(value))),
  );
  return `${VERSION}.${base64urlEncode(iv)}.${base64urlEncode(new Uint8Array(encrypted))}`;
}

async function unseal(
  env: Env,
  purpose: string,
  value: string,
): Promise<unknown> {
  const fields = value.split(".");
  if (
    fields.length !== 3 ||
    fields[0] !== VERSION ||
    !fields[1] ||
    !fields[2]
  ) {
    throw new HttpError(401, "invalid_session", "The session is invalid.");
  }
  try {
    const decrypted = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: arrayBuffer(base64urlDecode(fields[1])),
        additionalData: arrayBuffer(utf8(`orinoco:${purpose}:${VERSION}`)),
      },
      await key(env),
      arrayBuffer(base64urlDecode(fields[2])),
    );
    return JSON.parse(decodeUtf8(new Uint8Array(decrypted))) as unknown;
  } catch (error) {
    if (error instanceof HttpError && error.status === 500) throw error;
    throw new HttpError(401, "invalid_session", "The session is invalid.");
  }
}

export async function createOAuthCookie(
  env: Env,
  state: OAuthCookieInput,
): Promise<string> {
  const issuedAt = nowSeconds();
  return cookie(
    OAUTH_COOKIE,
    await seal(env, "oauth", {
      ...state,
      expires_at: issuedAt + OAUTH_TTL_SECONDS,
      issued_at: issuedAt,
    }),
    OAUTH_TTL_SECONDS,
  );
}

export async function readOAuthCookie(
  request: Request,
  env: Env,
): Promise<OAuthCookieState> {
  const encoded = cookieValue(request, OAUTH_COOKIE);
  if (encoded === null) {
    throw new HttpError(
      401,
      "missing_oauth_state",
      "The OAuth state cookie is missing.",
    );
  }
  const value = await unseal(env, "oauth", encoded);
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(
      401,
      "invalid_oauth_state",
      "The OAuth state is invalid or expired.",
    );
  }
  const kind = (value as Record<string, unknown>).kind;
  requireExactKeys(
    value,
    kind === "review"
      ? [
          "artifact_id",
          "code_verifier",
          "expires_at",
          "handoff_nonce",
          "issued_at",
          "kind",
          "origin",
          "pull_request",
          "repository",
          "review_origin",
          "state",
        ]
      : [
          "code_verifier",
          "editor_origin",
          "expected_head_sha",
          "expires_at",
          "handoff_nonce",
          "issued_at",
          "kind",
          "origin",
          "pull_request",
          "repository",
          "state",
        ],
    "OAuth state",
  );
  const issuedAt = requireTimestamp(value.issued_at, "OAuth issued_at");
  const expiresAt = requireTimestamp(value.expires_at, "OAuth expires_at");
  if (
    expiresAt <= nowSeconds() ||
    expiresAt - issuedAt !== OAUTH_TTL_SECONDS ||
    !validOneLine(value.code_verifier, 128) ||
    !validOneLine(value.origin, 256) ||
    !validOneLine(value.repository, 200) ||
    !validOneLine(value.state, 128) ||
    (value.kind !== "review" && value.kind !== "shacl")
  ) {
    throw new HttpError(
      401,
      "invalid_oauth_state",
      "The OAuth state is invalid or expired.",
    );
  }
  const common = {
    code_verifier: value.code_verifier,
    expires_at: expiresAt,
    issued_at: issuedAt,
    origin: value.origin,
    repository: value.repository,
    state: value.state,
  };
  if (value.kind === "shacl") {
    const editorOrigin = isSafeEditorOrigin(value.editor_origin)
      ? value.editor_origin
      : null;
    const handoffNonce = isShaclHandoffNonce(value.handoff_nonce)
      ? value.handoff_nonce
      : null;
    const liveHandoff = editorOrigin !== null && handoffNonce !== null;
    const standalone =
      value.expected_head_sha === null && value.pull_request === null;
    const existing =
      typeof value.expected_head_sha === "string" &&
      /^[0-9a-f]{40}$/.test(value.expected_head_sha) &&
      Number.isSafeInteger(value.pull_request) &&
      Number(value.pull_request) > 0;
    if ((!standalone && !existing) || !liveHandoff) {
      throw new HttpError(
        401,
        "invalid_oauth_state",
        "The OAuth state is invalid or expired.",
      );
    }
    return {
      ...common,
      editor_origin: editorOrigin,
      expected_head_sha: existing ? String(value.expected_head_sha) : null,
      handoff_nonce: handoffNonce,
      kind: "shacl",
      pull_request: existing ? Number(value.pull_request) : null,
    };
  }
  if (
    !Number.isSafeInteger(value.artifact_id) ||
    Number(value.artifact_id) < 1 ||
    !Number.isSafeInteger(value.pull_request) ||
    Number(value.pull_request) < 1 ||
    !isSafeReviewOrigin(value.review_origin) ||
    !isReviewHandoffNonce(value.handoff_nonce)
  ) {
    throw new HttpError(
      401,
      "invalid_oauth_state",
      "The OAuth state is invalid or expired.",
    );
  }
  return {
    ...common,
    artifact_id: Number(value.artifact_id),
    handoff_nonce: value.handoff_nonce,
    kind: "review",
    pull_request: Number(value.pull_request),
    review_origin: value.review_origin,
  };
}

export async function createSessionCookie(
  env: Env,
  state: Omit<
    SessionCookieState,
    "expires_at" | "issued_at" | "review_grant" | "shacl_grant"
  > & {
    review_grant?: ReviewGrant | null;
    shacl_grant?: ShaclGrant | null;
  },
  expiresIn: number,
): Promise<string> {
  if (!Number.isSafeInteger(expiresIn) || expiresIn < 60) {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub returned an invalid token expiry.",
    );
  }
  const lifetime = Math.min(expiresIn, MAX_SESSION_TTL_SECONDS);
  const issuedAt = nowSeconds();
  return cookie(
    SESSION_COOKIE,
    await seal(env, "session", {
      ...state,
      expires_at: issuedAt + lifetime,
      issued_at: issuedAt,
      review_grant: state.review_grant ?? null,
      shacl_grant: state.shacl_grant ?? null,
    }),
    lifetime,
  );
}

export async function consumeSessionGrantCookie(
  env: Env,
  session: SessionCookieState,
  kind: "review" | "shacl",
): Promise<string> {
  const remaining = session.expires_at - nowSeconds();
  if (remaining < 60) return clearCookie(SESSION_COOKIE);
  return createSessionCookie(
    env,
    {
      access_token: session.access_token,
      csrf_token: session.csrf_token,
      login: session.login,
      review_grant: kind === "review" ? null : session.review_grant,
      shacl_grant: kind === "shacl" ? null : session.shacl_grant,
    },
    remaining,
  );
}

export async function readSessionCookie(
  request: Request,
  env: Env,
): Promise<SessionCookieState> {
  const encoded = cookieValue(request, SESSION_COOKIE);
  if (encoded === null) {
    throw new HttpError(
      401,
      "authentication_required",
      "Sign in with GitHub to continue.",
    );
  }
  const value = await unseal(env, "session", encoded);
  requireExactKeys(
    value,
    [
      "access_token",
      "csrf_token",
      "expires_at",
      "issued_at",
      "login",
      "review_grant",
      "shacl_grant",
    ],
    "session",
  );
  const issuedAt = requireTimestamp(value.issued_at, "session issued_at");
  const expiresAt = requireTimestamp(value.expires_at, "session expires_at");
  const reviewGrant = parseReviewGrant(value.review_grant);
  const shaclGrant = parseShaclGrant(value.shacl_grant);
  if (
    expiresAt <= nowSeconds() ||
    expiresAt - issuedAt > MAX_SESSION_TTL_SECONDS ||
    !validOneLine(value.access_token, 1_024) ||
    !validOneLine(value.csrf_token, 128) ||
    !validOneLine(value.login, 128)
  ) {
    throw new HttpError(
      401,
      "invalid_session",
      "The session is invalid or expired.",
    );
  }
  return {
    access_token: value.access_token,
    csrf_token: value.csrf_token,
    expires_at: expiresAt,
    issued_at: issuedAt,
    login: value.login,
    review_grant: reviewGrant,
    shacl_grant: shaclGrant,
  };
}
