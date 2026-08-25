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
  const token = (value as Record<string, unknown>).access_token;
  const expires = (value as Record<string, unknown>).expires_in;
  const tokenType = (value as Record<string, unknown>).token_type;
  const scope = (value as Record<string, unknown>).scope;
  if (
    typeof token !== "string" ||
    !token ||
    token.length > 1_024 ||
    /\s/.test(token) ||
    !Number.isSafeInteger(expires) ||
    Number(expires) < 60 ||
    tokenType !== "bearer" ||
    scope !== ""
  ) {
    throw new HttpError(
      502,
      "github_oauth_error",
      "GitHub returned an invalid expiring user token.",
    );
  }
  return { accessToken: token, expiresIn: Number(expires) };
}
