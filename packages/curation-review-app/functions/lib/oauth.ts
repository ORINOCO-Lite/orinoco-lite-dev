import { HttpError } from "./http";
import type { Env } from "./pages";

const TOKEN_ENDPOINT = "https://github.com/login/oauth/access_token";

export interface GitHubToken {
  accessToken: string;
  expiresIn: number;
}

export async function exchangeCode(
  env: Env,
  code: string,
  codeVerifier: string,
  redirectUri: string,
  fetchImplementation: typeof fetch = fetch,
): Promise<GitHubToken> {
  const response = await fetchImplementation(TOKEN_ENDPOINT, {
    body: new URLSearchParams({
      client_id: env.GITHUB_CLIENT_ID,
      client_secret: env.GITHUB_CLIENT_SECRET,
      code,
      code_verifier: codeVerifier,
      redirect_uri: redirectUri,
    }),
    headers: {
      Accept: "application/json",
      "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    },
    method: "POST",
    redirect: "manual",
  });
  if (!response.ok) {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub rejected the authorization exchange.",
    );
  }
  let value: unknown;
  try {
    value = (await response.json()) as unknown;
  } catch {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub returned malformed authorization data.",
    );
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub returned invalid authorization data.",
    );
  }
  const fields = value as Record<string, unknown>;
  if (typeof fields.error === "string") {
    const message =
      fields.error === "bad_verification_code"
        ? "GitHub rejected an expired or already-used authorization code."
        : fields.error === "incorrect_client_credentials"
          ? "GitHub rejected the configured OAuth client credentials."
          : "GitHub rejected the authorization exchange.";
    throw new HttpError(502, "github_oauth_error", message);
  }
  const token = fields.access_token;
  const expires = fields.expires_in;
  const tokenType = fields.token_type;
  const scope = fields.scope;
  if (
    typeof token !== "string" ||
    !token ||
    token.length > 1_024 ||
    /\s/.test(token)
  ) {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub returned an invalid user access token.",
    );
  }
  if (!Number.isSafeInteger(expires) || Number(expires) < 60) {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub did not return a valid user token expiration.",
    );
  }
  if (tokenType !== "bearer") {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub returned an unexpected user token type.",
    );
  }
  if (scope !== "") {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub returned unexpected user-token scopes.",
    );
  }
  return { accessToken: token, expiresIn: Number(expires) };
}
