import { randomToken, sha256Base64url } from "../../lib/encoding";
import { HttpError, requireMethod } from "../../lib/http";
import { parsePullRequest, parseRepository } from "../../lib/input";
import type { EventContext } from "../../lib/pages";
import { configuredOrigin, createOAuthCookie } from "../../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const requestUrl = new URL(context.request.url);
  const origin = configuredOrigin(context.env);
  if (
    requestUrl.origin !== origin ||
    [...requestUrl.searchParams.keys()].some(
      (key) =>
        key !== "repository" &&
        key !== "pull_request" &&
        key !== "expected_head_sha",
    ) ||
    requestUrl.searchParams.getAll("repository").length !== 1
  ) {
    throw new HttpError(
      400,
      "invalid_shacl_auth_target",
      "The SHACL authentication target is invalid.",
    );
  }
  const repository = parseRepository(requestUrl.searchParams.get("repository"));
  const pullValues = requestUrl.searchParams.getAll("pull_request");
  const headValues = requestUrl.searchParams.getAll("expected_head_sha");
  if (
    pullValues.length > 1 ||
    headValues.length > 1 ||
    (pullValues.length === 0) !== (headValues.length === 0)
  ) {
    throw new HttpError(
      400,
      "invalid_shacl_auth_target",
      "The SHACL pull-request coordinates must be supplied together once.",
    );
  }
  const pullRequest =
    pullValues.length === 1 ? parsePullRequest(pullValues[0] ?? null) : null;
  const expectedHeadSha = headValues[0] ?? null;
  if (expectedHeadSha !== null && !/^[0-9a-f]{40}$/.test(expectedHeadSha)) {
    throw new HttpError(
      400,
      "invalid_shacl_auth_target",
      "The SHACL expected head is invalid.",
    );
  }
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
        expected_head_sha: expectedHeadSha,
        kind: "shacl",
        origin,
        pull_request: pullRequest,
        repository,
        state,
      }),
    },
    status: 302,
  });
}
