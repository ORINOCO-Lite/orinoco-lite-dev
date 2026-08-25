import { randomToken, sha256Base64url } from "../../lib/encoding";
import { HttpError, requireMethod } from "../../lib/http";
import { parseRepository } from "../../lib/input";
import type { EventContext } from "../../lib/pages";
import { configuredOrigin, createOAuthCookie } from "../../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const requestUrl = new URL(context.request.url);
  const origin = configuredOrigin(context.env);
  if (
    requestUrl.origin !== origin ||
    [...requestUrl.searchParams.keys()].some((key) => key !== "repository") ||
    requestUrl.searchParams.getAll("repository").length !== 1
  ) {
    throw new HttpError(
      400,
      "invalid_discovery_auth_target",
      "The repository discovery target is invalid.",
    );
  }
  const repository = parseRepository(requestUrl.searchParams.get("repository"));
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
      Location: authorize.toString(),
      "Set-Cookie": await createOAuthCookie(context.env, {
        code_verifier: codeVerifier,
        kind: "discovery",
        origin,
        repository,
        state,
      }),
    },
    status: 302,
  });
}
