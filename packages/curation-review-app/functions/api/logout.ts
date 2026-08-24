import { equalTokens } from "../lib/encoding";
import {
  HttpError,
  jsonResponse,
  requireMethod,
  requireSameOrigin,
} from "../lib/http";
import type { EventContext } from "../lib/pages";
import {
  OAUTH_COOKIE,
  SESSION_COOKIE,
  clearCookie,
  configuredOrigin,
  readSessionCookie,
} from "../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireSameOrigin(context.request, configuredOrigin(context.env));
  const session = await readSessionCookie(context.request, context.env);
  const supplied = context.request.headers.get("x-csrf-token") ?? "";
  if (!equalTokens(supplied, session.csrf_token)) {
    throw new HttpError(403, "invalid_csrf", "The request token is invalid.");
  }
  const headers = new Headers();
  headers.append("Set-Cookie", clearCookie(OAUTH_COOKIE));
  headers.append("Set-Cookie", clearCookie(SESSION_COOKIE));
  return jsonResponse({ ok: true }, { headers });
}
