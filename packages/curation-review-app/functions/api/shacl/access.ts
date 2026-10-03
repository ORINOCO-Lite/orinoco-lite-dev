import { equalTokens } from "../../lib/encoding";
import { GitHubClient } from "../../lib/github";
import {
  HttpError,
  jsonResponse,
  requireMethod,
  requireSameOrigin,
} from "../../lib/http";
import type { EventContext } from "../../lib/pages";
import { configuredOrigin, readSessionCookie } from "../../lib/session";
import { checkShaclAccess } from "../../lib/shacl-proposal";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  const origin = configuredOrigin(context.env);
  requireSameOrigin(context.request, origin);
  const session = await readSessionCookie(context.request, context.env);
  if (
    !equalTokens(
      context.request.headers.get("x-csrf-token") ?? "",
      session.csrf_token,
    )
  ) {
    throw new HttpError(
      403,
      "invalid_csrf",
      "The request token is invalid. Sign in again from the editor.",
    );
  }
  if (session.shacl_grant === null) {
    throw new HttpError(
      403,
      "shacl_grant_required",
      "Sign in from this editor to check GitHub access.",
    );
  }
  await checkShaclAccess(
    new GitHubClient(session.access_token),
    session.shacl_grant,
    origin,
    () => {
      if (!context.env.GITHUB_APP_PRIVATE_KEY)
        throw new HttpError(
          503,
          "automation_unavailable",
          "The service operator must configure the curation App signing key.",
        );
    },
  );
  return jsonResponse({ ready: true });
}
