import {
  arrayBuffer,
  base64urlDecode,
  base64urlEncode,
  decodeUtf8,
  utf8,
} from "./encoding";
import { HttpError, requireExactKeys } from "./http";
import type { Env } from "./pages";

export const OAUTH_COOKIE = "__Host-orinoco_oauth";
export const SESSION_COOKIE = "__Host-orinoco_session";

const VERSION = "v1";
const OAUTH_TTL_SECONDS = 600;
const MAX_SESSION_TTL_SECONDS = 28_800;

export interface OAuthCookieState {
  artifact_id: number;
  code_verifier: string;
  expires_at: number;
  issued_at: number;
  origin: string;
  pull_request: number;
  repository: string;
  state: string;
}

export interface SessionCookieState {
  access_token: string;
  csrf_token: string;
  expires_at: number;
  issued_at: number;
  login: string;
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
  state: Omit<OAuthCookieState, "expires_at" | "issued_at">,
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
  requireExactKeys(
    value,
    [
      "artifact_id",
      "code_verifier",
      "expires_at",
      "issued_at",
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
    !Number.isSafeInteger(value.artifact_id) ||
    Number(value.artifact_id) < 1 ||
    !Number.isSafeInteger(value.pull_request) ||
    Number(value.pull_request) < 1
  ) {
    throw new HttpError(
      401,
      "invalid_oauth_state",
      "The OAuth state is invalid or expired.",
    );
  }
  return {
    artifact_id: Number(value.artifact_id),
    code_verifier: value.code_verifier,
    expires_at: expiresAt,
    issued_at: issuedAt,
    origin: value.origin,
    pull_request: Number(value.pull_request),
    repository: value.repository,
    state: value.state,
  };
}

export async function createSessionCookie(
  env: Env,
  state: Omit<SessionCookieState, "expires_at" | "issued_at">,
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
    }),
    lifetime,
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
    ["access_token", "csrf_token", "expires_at", "issued_at", "login"],
    "session",
  );
  const issuedAt = requireTimestamp(value.issued_at, "session issued_at");
  const expiresAt = requireTimestamp(value.expires_at, "session expires_at");
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
  };
}
