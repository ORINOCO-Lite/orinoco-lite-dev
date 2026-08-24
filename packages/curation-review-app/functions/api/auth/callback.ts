import { equalTokens, randomToken } from "../../lib/encoding";
import { GitHubClient } from "../../lib/github";
import { HttpError, requireMethod } from "../../lib/http";
import { exchangeCode } from "../../lib/oauth";
import type { EventContext } from "../../lib/pages";
import {
  OAUTH_COOKIE,
  clearCookie,
  configuredOrigin,
  createSessionCookie,
  readOAuthCookie,
} from "../../lib/session";

function oneParameter(url: URL, name: string): string {
  const values = url.searchParams.getAll(name);
  if (values.length !== 1 || !values[0] || /[\r\n\0]/.test(values[0])) {
    throw new HttpError(
      400,
      "invalid_oauth_callback",
      `OAuth ${name} is invalid.`,
    );
  }
  return values[0];
}

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const url = new URL(context.request.url);
  const origin = configuredOrigin(context.env);
  if (
    url.origin !== origin ||
    [...url.searchParams.keys()].some(
      (key) => key !== "code" && key !== "state",
    )
  ) {
    throw new HttpError(
      400,
      "invalid_oauth_callback",
      "The OAuth callback is invalid.",
    );
  }
  const code = oneParameter(url, "code");
  const returnedState = oneParameter(url, "state");
  const oauth = await readOAuthCookie(context.request, context.env);
  if (oauth.origin !== origin || !equalTokens(returnedState, oauth.state)) {
    throw new HttpError(
      401,
      "invalid_oauth_state",
      "The OAuth state does not match.",
    );
  }
  const token = await exchangeCode(
    context.env,
    code,
    oauth.code_verifier,
    `${origin}/api/auth/callback`,
  );
  const user = await new GitHubClient(token.accessToken).currentUser();
  const destination = new URL("/", origin);
  if (oauth.kind === "review") {
    destination.searchParams.set("artifact_id", String(oauth.artifact_id));
    destination.searchParams.set("repository", oauth.repository);
    destination.searchParams.set("pull_request", String(oauth.pull_request));
  } else {
    destination.pathname = "/edit";
    destination.searchParams.set("repository", oauth.repository);
    if (oauth.pull_request !== null && oauth.expected_head_sha !== null) {
      destination.searchParams.set(
        "expected_head_sha",
        oauth.expected_head_sha,
      );
      destination.searchParams.set("pull_request", String(oauth.pull_request));
    }
  }
  const headers = new Headers({
    "Cache-Control": "no-store",
    Location: destination.toString(),
  });
  headers.append("Set-Cookie", clearCookie(OAUTH_COOKIE));
  headers.append(
    "Set-Cookie",
    await createSessionCookie(
      context.env,
      {
        access_token: token.accessToken,
        csrf_token: randomToken(),
        login: user.login,
      },
      token.expiresIn,
    ),
  );
  return new Response(null, { headers, status: 302 });
}
