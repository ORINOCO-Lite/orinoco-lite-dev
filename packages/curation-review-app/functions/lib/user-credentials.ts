import { base64Encode, utf8 } from "./encoding";
import { GitHubClient } from "./github";
import { HttpError } from "./http";
import { parseRepository } from "./input";
import type { Env } from "./pages";

export interface UserRepository {
  id: number;
  name: string;
  ownerId: number;
  defaultBranch: string;
}

export interface ScopedUserCredential {
  token: string;
  expires_at: string;
}

/** Ask GitHub for the signed-in user's effective access, including custom roles. */
export async function writableUserRepository(
  github: GitHubClient,
  repository: string,
): Promise<UserRepository> {
  parseRepository(repository);
  const value = (await github.json(`/repos/${repository}`)) as any;
  if (
    !value ||
    !Number.isSafeInteger(value.id) ||
    !Number.isSafeInteger(value.owner?.id) ||
    typeof value.full_name !== "string" ||
    value.full_name.toLowerCase() !== repository.toLowerCase() ||
    typeof value.default_branch !== "string"
  ) {
    throw new HttpError(
      502,
      "github_error",
      "GitHub returned an invalid repository identity.",
    );
  }
  if (value.permissions?.push !== true) {
    throw new HttpError(
      403,
      "curator_permission_required",
      `Your GitHub account needs write access to ${value.full_name} to submit this edit.`,
    );
  }
  return {
    id: value.id,
    name: value.full_name,
    ownerId: value.owner.id,
    defaultBranch: value.default_branch,
  };
}

async function applicationRequest(
  env: Env,
  path: "token/scoped" | "token",
  method: "POST" | "DELETE",
  body: Record<string, unknown>,
  fetcher: typeof fetch,
): Promise<Response> {
  const response = await fetcher(
    `https://api.github.com/applications/${encodeURIComponent(env.GITHUB_CLIENT_ID)}/${path}`,
    {
      method,
      redirect: "manual",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Basic ${base64Encode(utf8(`${env.GITHUB_CLIENT_ID}:${env.GITHUB_CLIENT_SECRET}`))}`,
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "orinoco-lite-authentication",
      },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    // A token API error can contain credentials. Never include its body.
    throw new HttpError(
      response.status === 403 || response.status === 404 ? 403 : 502,
      "github_credential_error",
      `GitHub could not ${method === "DELETE" ? "revoke" : "issue"} the repository credential (HTTP ${response.status}).`,
    );
  }
  return response;
}

/** GitHub enforces the intersection of this scope, App access, and user access. */
export async function scopedUserCredential(
  env: Env,
  accessToken: string,
  repository: UserRepository,
  fetcher: typeof fetch = fetch,
): Promise<ScopedUserCredential> {
  const response = await applicationRequest(
    env,
    "token/scoped",
    "POST",
    {
      access_token: accessToken,
      target_id: repository.ownerId,
      repository_ids: [repository.id],
      permissions: {
        contents: "write",
        pull_requests: "read",
        actions: "read",
      },
    },
    fetcher,
  );
  let value: any;
  try {
    value = await response.json();
  } catch {
    throw new HttpError(
      502,
      "github_credential_error",
      "GitHub returned an invalid credential response.",
    );
  }
  if (
    typeof value?.token !== "string" ||
    !value.token ||
    /\s/.test(value.token) ||
    typeof value.expires_at !== "string" ||
    !Number.isFinite(Date.parse(value.expires_at)) ||
    Date.parse(value.expires_at) <= Date.now()
  ) {
    if (
      typeof value?.token === "string" &&
      value.token &&
      !/\s/.test(value.token)
    )
      await revokeUserCredential(env, value.token, fetcher).catch(
        () => undefined,
      );
    throw new HttpError(
      502,
      "github_credential_error",
      "GitHub did not return an expiring repository credential.",
    );
  }
  return { token: value.token, expires_at: value.expires_at };
}

export async function revokeUserCredential(
  env: Env,
  token: string,
  fetcher: typeof fetch = fetch,
): Promise<void> {
  await applicationRequest(
    env,
    "token",
    "DELETE",
    { access_token: token },
    fetcher,
  );
}
