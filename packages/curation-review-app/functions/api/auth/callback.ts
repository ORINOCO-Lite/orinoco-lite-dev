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

const GITHUB_OAUTH_ISSUER = "https://github.com/login/oauth";

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
  if (url.origin !== origin || url.pathname !== "/api/auth/callback") {
    throw new HttpError(
      400,
      "invalid_oauth_callback",
      "The OAuth callback is invalid.",
    );
  }
  const keys = [...url.searchParams.keys()];
  if (keys.some((key) => key.startsWith("error"))) {
    throw new HttpError(
      400,
      "github_oauth_not_authorized",
      "GitHub did not authorize this sign-in. Return to the review link and try again.",
    );
  }
  if (keys.some((key) => key === "installation_id" || key === "setup_action")) {
    throw new HttpError(
      400,
      "github_app_setup_misdirected",
      "GitHub App installation was sent to the OAuth callback. Configure a separate setup URL and start sign-in from the review link.",
    );
  }
  if (keys.some((key) => key !== "code" && key !== "state" && key !== "iss")) {
    throw new HttpError(
      400,
      "invalid_oauth_callback",
      "The OAuth callback is invalid.",
    );
  }
  if (
    url.searchParams.has("iss") &&
    oneParameter(url, "iss") !== GITHUB_OAUTH_ISSUER
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
    destination.pathname = "/review-auth-complete/";
  } else {
    destination.pathname = "/edit/";
    destination.searchParams.set("repository", oauth.repository);
    if (oauth.editor_origin !== null && oauth.handoff_nonce !== null) {
      destination.searchParams.set("editor_origin", oauth.editor_origin);
      destination.searchParams.set("handoff_nonce", oauth.handoff_nonce);
    }
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
        review_grant:
          oauth.kind === "review"
            ? {
                artifact_id: oauth.artifact_id,
                handoff_nonce: oauth.handoff_nonce,
                pull_request: oauth.pull_request,
                repository: oauth.repository,
                review_origin: oauth.review_origin,
              }
            : null,
      },
      token.expiresIn,
    ),
  );
  return new Response(null, { headers, status: 302 });
}
