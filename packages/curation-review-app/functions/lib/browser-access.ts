import { SignJWT, jwtVerify } from "jose";
import { parse as parseToml } from "smol-toml";
import { parse as parseYaml } from "yaml";
import { DEFAULT_CURATION_SERVICE_ORIGIN } from "../../shared/contracts";
import { sha256Base64url, utf8 } from "./encoding";
import { GitHubClient } from "./github";
import { HttpError } from "./http";
import type { Env } from "./pages";
import {
  revokeUserCredential,
  scopedUserCredential,
  writableUserRepository,
  type ScopedUserCredential,
  type UserRepository,
} from "./user-credentials";

export const REPOSITORY_WORKFLOW_PATH = ".github/workflows/orinoco.yml";
const WORKER =
  /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/\.github\/workflows\/[A-Za-z0-9_.-]+\.ya?ml@[0-9a-f]{40}$/;
const SHA = /^[0-9a-f]{40}$/;
const SCOPE_AUDIENCE = "orinoco-browser-credential-scope";

export interface BrowserRepository extends UserRepository {
  baseCommit: string;
  worker: string;
}

export interface BrowserCredentialScope {
  repositories: BrowserRepository[];
  source: { repository: string; commit: string };
  metadata: { repository: string; commit: string } | null;
}

function deny(message: string): never {
  throw new HttpError(403, "authentication_scope_required", message);
}

function key(env: Env): Uint8Array {
  return utf8(`orinoco-browser-credential-scope-v1:${env.SESSION_SEAL_KEY}`);
}

async function configuredWorker(
  github: GitHubClient,
  repository: UserRepository,
): Promise<BrowserRepository> {
  const head = await github.branchHead(
    repository.name,
    repository.defaultBranch,
  );
  const files = await github.contents(repository.name, [
    { key: "workflow", path: REPOSITORY_WORKFLOW_PATH, ref: head.sha },
  ]);
  let workflow: any;
  try {
    workflow = parseYaml(files.get("workflow") ?? "");
  } catch {
    /* Report configuration without echoing file contents. */
  }
  const workers = [
    ...new Set(
      Object.values(workflow?.jobs ?? {})
        .map((job: any) => job?.uses)
        .filter(
          (uses): uses is string =>
            typeof uses === "string" && WORKER.test(uses),
        ),
    ),
  ];
  if (workers.length !== 1) {
    throw new HttpError(
      409,
      "workflow_setup_required",
      `${repository.name} needs the repository workflow from the current template.`,
    );
  }
  return { ...repository, baseCommit: head.sha, worker: workers[0]! };
}

async function requireBrowserOrigin(
  env: Env,
  github: GitHubClient,
  repository: BrowserRepository,
  clientOrigin: string,
  sourceCommit: string,
): Promise<void> {
  const files = await github.contents(repository.name, [
    {
      key: "configuration",
      path: "pyproject.toml",
      ref: repository.baseCommit,
    },
  ]);
  let config: any;
  try {
    config = (parseToml(files.get("configuration") ?? "") as any).tool?.orinoco;
  } catch {
    /* Avoid echoing repository contents. */
  }
  let configuredOrigin: string;
  try {
    configuredOrigin = new URL(config.site.identity.base_url).origin;
  } catch {
    return deny(
      "The website repository needs its public site URL in pyproject.toml.",
    );
  }
  if (
    (config.service?.url ?? DEFAULT_CURATION_SERVICE_ORIGIN).replace(
      /\/$/,
      "",
    ) !== env.PUBLIC_ORIGIN
  )
    deny(
      "The website is configured to use a different authentication service.",
    );
  if (configuredOrigin === clientOrigin) return;
  const statuses = (await github.commitStatus(
    repository.name,
    sourceCommit,
  )) as any;
  const preview = statuses?.statuses?.some((status: any) => {
    if (
      status.state !== "success" ||
      !/^netlify\/.+\/deploy-preview$/.test(status.context)
    )
      return false;
    try {
      return (
        new URL(status.target_url).origin === clientOrigin &&
        new URL(clientOrigin).protocol === "https:"
      );
    } catch {
      return false;
    }
  });
  if (!preview)
    deny(
      "Sign in from the configured website or its GitHub-verified deployment preview.",
    );
}

/** Resolve credential resources without deciding whether the edit can merge. */
export async function browserCredentialScope(
  env: Env,
  github: GitHubClient,
  repository: string,
  clientOrigin: string,
  sourceCommit: string,
): Promise<BrowserCredentialScope> {
  if (!SHA.test(sourceCommit)) deny("The website source commit is invalid.");
  // Check website access first, before issuing credentials or uploading private metadata.
  const website = await configuredWorker(
    github,
    await writableUserRepository(github, repository),
  );
  await requireBrowserOrigin(env, github, website, clientOrigin, sourceCommit);
  const metadata = await github.siteSubmodule(website.name, sourceCommit);
  const repositories = [website];
  if (
    metadata !== null &&
    metadata.repository.toLowerCase() !== website.name.toLowerCase()
  ) {
    repositories.push(
      await configuredWorker(
        github,
        await writableUserRepository(github, metadata.repository),
      ),
    );
  }
  return {
    repositories,
    source: { repository: website.name, commit: sourceCommit },
    metadata:
      metadata === null
        ? null
        : {
            repository: repositories.find(
              (item) =>
                item.name.toLowerCase() === metadata.repository.toLowerCase(),
            )!.name,
            commit: metadata.sha,
          },
  };
}

export async function issueBrowserCredentials(
  env: Env,
  accessToken: string,
  scope: BrowserCredentialScope,
  sessionExpiresAt: number,
  fetcher: typeof fetch = fetch,
): Promise<{
  scope: BrowserCredentialScope;
  scope_proof: string;
  credentials: Record<string, ScopedUserCredential>;
}> {
  const credentials: Record<string, ScopedUserCredential> = {};
  try {
    for (const repository of scope.repositories)
      credentials[repository.name] = await scopedUserCredential(
        env,
        accessToken,
        repository,
        fetcher,
      );
    const proof = await new SignJWT({
      scope,
      session: await sha256Base64url(accessToken),
    })
      .setProtectedHeader({ alg: "HS256", typ: "JWT" })
      .setIssuer(env.PUBLIC_ORIGIN)
      .setAudience(SCOPE_AUDIENCE)
      .setIssuedAt()
      .setExpirationTime(sessionExpiresAt)
      .sign(key(env));
    return { scope, scope_proof: proof, credentials };
  } catch (error) {
    await Promise.allSettled(
      Object.values(credentials).map((credential) =>
        revokeUserCredential(env, credential.token, fetcher),
      ),
    );
    throw error;
  }
}

/** Freeze the selected worker versions across uploads and default-branch advances. */
export async function verifyBrowserCredentialScope(
  env: Env,
  accessToken: string,
  proof: string,
): Promise<BrowserCredentialScope> {
  try {
    const { payload } = await jwtVerify(proof, key(env), {
      issuer: env.PUBLIC_ORIGIN,
      audience: SCOPE_AUDIENCE,
      algorithms: ["HS256"],
      requiredClaims: ["exp", "iat", "scope", "session"],
    });
    if (payload.session !== (await sha256Base64url(accessToken)))
      throw new Error("Wrong session");
    return payload.scope as BrowserCredentialScope;
  } catch {
    return deny("Sign in again to authorize this submission.");
  }
}
