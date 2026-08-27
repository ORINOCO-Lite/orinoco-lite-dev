import { randomToken, sha256Base64url } from "../../lib/encoding";
import { HttpError, requireMethod } from "../../lib/http";
import { reviewTransportTarget } from "../../lib/input";
import type { EventContext } from "../../lib/pages";
import { configuredOrigin, createOAuthCookie } from "../../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const requestUrl = new URL(context.request.url);
  const origin = configuredOrigin(context.env);
  if (requestUrl.origin !== origin) {
    throw new HttpError(
      400,
      "invalid_origin",
      "The request URL does not match PUBLIC_ORIGIN.",
    );
  }
  const target = reviewTransportTarget(requestUrl);
  const state = randomToken();
  const codeVerifier = randomToken();
  const redirectUri = `${origin}/api/auth/callback`;
  const authorize = new URL("https://github.com/login/oauth/authorize");
  authorize.searchParams.set("client_id", context.env.GITHUB_CLIENT_ID);
  authorize.searchParams.set("redirect_uri", redirectUri);
  authorize.searchParams.set("state", state);
  authorize.searchParams.set(
    "code_challenge",
    await sha256Base64url(codeVerifier),
  );
  authorize.searchParams.set("code_challenge_method", "S256");

  return new Response(null, {
    headers: {
      "Cache-Control": "no-store",
      "Cross-Origin-Opener-Policy": "unsafe-none",
      Location: authorize.toString(),
      "Set-Cookie": await createOAuthCookie(context.env, {
        artifact_id: target.artifactId,
        code_verifier: codeVerifier,
        handoff_nonce: target.handoffNonce,
        kind: "review",
        origin,
        pull_request: target.pullRequest,
        repository: target.repository,
        review_origin: target.reviewOrigin,
        state,
      }),
    },
    status: 302,
  });
}
