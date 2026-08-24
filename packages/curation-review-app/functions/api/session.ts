import { HttpError, jsonResponse, requireMethod } from "../lib/http";
import type { EventContext } from "../lib/pages";
import { SESSION_COOKIE, clearCookie, readSessionCookie } from "../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  try {
    const session = await readSessionCookie(context.request, context.env);
    return jsonResponse({
      authenticated: true,
      csrf_token: session.csrf_token,
      login: session.login,
    });
  } catch (error) {
    if (!(error instanceof HttpError) || error.status !== 401) throw error;
    return jsonResponse(
      { authenticated: false },
      { headers: { "Set-Cookie": clearCookie(SESSION_COOKIE) } },
    );
  }
}
