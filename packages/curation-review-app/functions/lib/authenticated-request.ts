import { equalTokens } from "./encoding";
import {
  HttpError,
  requireJsonContentType,
  requireMethod,
  requireSameOrigin,
} from "./http";
import type { EventContext } from "./pages";
import { configuredOrigin, readSessionCookie } from "./session";

export async function authenticatedRequest(context: EventContext) {
  requireMethod(context.request, "POST");
  requireSameOrigin(context.request, configuredOrigin(context.env));
  requireJsonContentType(context.request);
  const session = await readSessionCookie(context.request, context.env);
  if (
    !equalTokens(
      context.request.headers.get("x-csrf-token") ?? "",
      session.csrf_token,
    )
  )
    throw new HttpError(
      403,
      "invalid_csrf",
      "The request token is invalid. Sign in again.",
    );
  return session;
}
