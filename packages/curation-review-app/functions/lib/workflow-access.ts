import {
  createRemoteJWKSet,
  importPKCS8,
  jwtVerify,
  SignJWT,
  type JWTPayload,
  type JWTVerifyGetKey,
} from "jose";
import { GitHubClient } from "./github";
import { HttpError } from "./http";
import type { Env } from "./pages";
import { sha256Base64url, utf8 } from "./encoding";
import { SHACL_BUNDLE_PATH, parseShaclReviewBundle } from "./shacl";

const ISSUER = "https://token.actions.githubusercontent.com";
const WORKFLOW = ".github/workflows/shacl-vue-proposal.yml";
const keys = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const SHA = /^[0-9a-f]{40}$/;
const REPO = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const MAX_AGE = 3600;

function deny(message: string): never {
  // Callers supply fixed diagnostic text, never tokens or proposal contents.
  console.warn("Workflow access denied:", message);
  throw new HttpError(403, "workflow_access_denied", message);
}
export function object(value: unknown): Record<string, any> {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    deny("Invalid workflow authorization data.");
  return value as Record<string, any>;
}
function parseOperationalJson(value: string | null | undefined): unknown {
  try {
    return JSON.parse(value ?? "null");
  } catch {
    return deny("The proposal handoff is not valid JSON.");
  }
}
function grantKey(env: Env): Uint8Array {
  if (!env.SESSION_SEAL_KEY) deny("Service signing is not configured.");
  return utf8(`orinoco-workflow-authorization-v1:${env.SESSION_SEAL_KEY}`);
}
export interface AuthorizationInput {
  repository: string;
  branch: string;
  trustedSha: string;
  curator: { id: number; login: string };
  handoff: Record<string, unknown>;
}
export async function authorizeWorkflow(
  github: GitHubClient,
  env: Env,
  input: AuthorizationInput,
): Promise<string> {
  if (!env.GITHUB_APP_PRIVATE_KEY)
    throw new HttpError(
      503,
      "automation_unavailable",
      "The curation service operator must configure this App's signing key for submodule materialization. No downstream App or secret is required.",
    );
  const repo = object(await github.json(`/repos/${input.repository}`));
  const metadata = object(input.handoff.metadata);
  const meta = object(await github.json(`/repos/${metadata.repository}`));
  if (!Number.isSafeInteger(repo.id) || !Number.isSafeInteger(meta.id))
    deny("GitHub omitted repository identities.");
  return new SignJWT({
    repository: input.repository,
    repository_id: String(repo.id),
    metadata_repository_id: String(meta.id),
    branch: input.branch,
    trusted_sha: input.trustedSha,
    curator_id: input.curator.id,
    curator_login: input.curator.login,
    digest: await sha256Base64url(JSON.stringify(input.handoff)),
  })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuer(env.PUBLIC_ORIGIN)
    .setAudience("orinoco-submodule-materialization")
    .setIssuedAt()
    .setExpirationTime(`${MAX_AGE}s`)
    .sign(grantKey(env));
}
export async function verifyWorkflowIdentity(
  token: string,
  origin: string,
  verificationKeys: JWTVerifyGetKey = keys,
): Promise<JWTPayload> {
  try {
    return (
      await jwtVerify(token, verificationKeys, {
        issuer: ISSUER,
        audience: `${origin}/api/shacl/workflow-access`,
        algorithms: ["RS256"],
        maxTokenAge: "10m",
        requiredClaims: [
          "exp",
          "iat",
          "nbf",
          "repository_id",
          "repository",
          "workflow_sha",
          "workflow_ref",
          "run_id",
          "run_attempt",
          "check_run_id",
        ],
      })
    ).payload;
  } catch {
    return deny(
      "A valid GitHub Actions identity for this service is required.",
    );
  }
}
export async function verifyAuthorization(
  env: Env,
  handoff: Record<string, any>,
  identity: JWTPayload,
  canonicalRead = false,
): Promise<JWTPayload> {
  const { authorization, ...unsigned } = handoff;
  let grant: JWTPayload;
  try {
    grant = (
      await jwtVerify(authorization, grantKey(env), {
        issuer: env.PUBLIC_ORIGIN,
        audience: "orinoco-submodule-materialization",
        algorithms: ["HS256"],
        maxTokenAge: `${MAX_AGE}s`,
        requiredClaims: ["exp", "iat"],
      })
    ).payload;
  } catch {
    return deny(
      "The proposal's service authorization is missing, invalid, or expired. Start a new authenticated proposal.",
    );
  }
  if (
    grant.digest !== (await sha256Base64url(JSON.stringify(unsigned))) ||
    identity.repository !== grant.repository ||
    identity.repository_id !== grant.repository_id ||
    identity.workflow_sha !== grant.trusted_sha ||
    (canonicalRead
      ? identity.event_name !== "workflow_dispatch"
      : identity.event_name !== "pull_request_target" ||
        identity.actor_id !== String(grant.curator_id)) ||
    identity.workflow_ref !==
      `${grant.repository}/${WORKFLOW}@${identity.ref}` ||
    typeof identity.ref !== "string" ||
    !identity.ref.startsWith("refs/heads/") ||
    identity.run_attempt !== "1"
  )
    deny(
      "The workflow does not match the authorized proposal and trusted code.",
    );
  return grant;
}

// Tokens never leave this service except for the one repository explicitly
// authorized for this trusted job. The App private key is operator-only.
export class AppAuthentication {
  readonly fetcher: typeof fetch;
  constructor(
    readonly env: Env,
    fetcher: typeof fetch = fetch,
  ) {
    this.fetcher = async (input, init) => {
      const response = await fetcher(input, init);
      if (!response.ok) {
        const path = new URL(
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.href
              : input.url,
        ).pathname;
        const operation = path.includes("/collaborators/")
          ? "curator-permission"
          : path.endsWith("/access_tokens")
            ? "issue-installation-token"
            : path.endsWith("/installation")
              ? "resolve-installation"
              : path === "/graphql"
                ? "read-repository-content"
                : "verify-repository-state";
        console.warn(
          "Workflow GitHub request rejected:",
          operation,
          response.status,
        );
      }
      return response;
    };
  }
  async token(
    repository: string,
    write = false,
    actions = false,
  ): Promise<{ token: string; expires_at: string }> {
    if (!REPO.test(repository)) deny("Invalid repository.");
    if (!this.env.GITHUB_APP_PRIVATE_KEY)
      throw new HttpError(
        503,
        "automation_unavailable",
        "The service operator has not configured the curation App signing key.",
      );
    const key = await importPKCS8(this.env.GITHUB_APP_PRIVATE_KEY, "RS256");
    const jwt = await new SignJWT({})
      .setProtectedHeader({ alg: "RS256" })
      .setIssuer(this.env.GITHUB_CLIENT_ID)
      .setIssuedAt(Math.floor(Date.now() / 1000) - 60)
      .setExpirationTime("5m")
      .sign(key);
    const app = new GitHubClient(jwt, this.fetcher);
    const installation = object(
      await app.json(`/repos/${repository}/installation`),
    );
    if (
      !Number.isSafeInteger(installation.id) ||
      installation.suspended_at !== null
    )
      deny("The App installation is unavailable or suspended.");
    const result = object(
      await app.json(`/app/installations/${installation.id}/access_tokens`, {
        method: "POST",
        body: JSON.stringify({
          repositories: [repository.split("/")[1]],
          permissions: {
            contents: write ? "write" : "read",
            pull_requests: "read",
            ...(actions ? { actions: "read" } : {}),
          },
        }),
      }),
    );
    if (
      typeof result.token !== "string" ||
      typeof result.expires_at !== "string"
    )
      deny("GitHub did not issue bounded installation access.");
    return { token: result.token, expires_at: result.expires_at };
  }
  async revoke(token: string): Promise<void> {
    await new GitHubClient(token, this.fetcher)
      .json("/installation/token", { method: "DELETE" })
      .catch(() => undefined);
  }
}

function requireDraft(
  pull: Record<string, any>,
  repo: string,
  head: string,
  branch: string,
): void {
  if (
    pull.state !== "open" ||
    pull.draft !== true ||
    pull.head?.repo?.full_name !== repo ||
    pull.base?.repo?.full_name !== repo ||
    pull.head?.sha !== head ||
    pull.head?.ref !== branch ||
    pull.base?.ref !== pull.base?.repo?.default_branch
  )
    deny("The proposal is no longer an open draft at its authorized head.");
}
async function handoffCommit(
  github: GitHubClient,
  repository: string,
  sha: string,
  source: string,
  curator: JWTPayload,
): Promise<void> {
  const commit = await github.commit(repository, sha, 1);
  const files = commit.files as any[];
  const parents = commit.parents as any[];
  if (
    commit.sha !== sha ||
    parents?.length !== 1 ||
    parents[0]?.sha !== source ||
    files.length !== 1 ||
    files[0]?.filename !== SHACL_BUNDLE_PATH ||
    files[0]?.status !== "added" ||
    object(commit.author).id !== curator.curator_id ||
    object(commit.author).login !== curator.curator_login
  )
    deny("The authenticated handoff commit changed.");
}
async function canonicalCommit(
  github: GitHubClient,
  repo: string,
  head: string,
  source: string,
  grant: JWTPayload,
  website: boolean,
): Promise<void> {
  const commit = await github.commit(repo, head);
  const parents = commit.parents as any[];
  const files = commit.files as any[];
  if (
    parents?.length !== 1 ||
    parents[0]?.sha !== source ||
    object(commit.author).id !== grant.curator_id ||
    !files.length ||
    (website
      ? files.length !== 1 || files[0]?.filename !== "site-specific"
      : files.some(
          (f) =>
            typeof f.filename !== "string" ||
            !/^metadata\/(records|overlays\/annotations)\/.+\.ya?ml$/.test(
              f.filename,
            ) ||
            f.previous_filename,
        ))
  )
    deny(
      "The canonical replacement is outside the authorized metadata operation.",
    );
}

export async function workflowAccess(
  env: Env,
  identity: JWTPayload,
  request: Record<string, any>,
  auth = new AppAuthentication(env),
): Promise<{ token: string; expires_at: string }> {
  if (
    ![
      "head,pull_request,repository,write",
      "handoff,head,pull_request,repository,write",
    ].includes(Object.keys(request).sort().join()) ||
    typeof request.repository !== "string" ||
    !REPO.test(request.repository) ||
    !SHA.test(request.head) ||
    !Number.isSafeInteger(request.pull_request) ||
    request.pull_request < 1 ||
    typeof request.write !== "boolean" ||
    identity.repository !== request.repository
  )
    deny("Invalid workflow access request.");
  const handoffSha = request.handoff ?? request.head;
  const canonicalRead = handoffSha !== request.head;
  if (!SHA.test(handoffSha) || (canonicalRead && request.write))
    deny("Canonical validation cannot obtain write access.");
  const websiteToken = await auth.token(request.repository, false, true);
  let metadataToken: { token: string; expires_at: string } | undefined;
  try {
    const website = new GitHubClient(websiteToken.token, auth.fetcher);
    const values = await website.contents(request.repository, [
      { key: "handoff", path: SHACL_BUNDLE_PATH, ref: handoffSha },
    ]);
    const handoff = object(parseOperationalJson(values.get("handoff")));
    const grant = await verifyAuthorization(
      env,
      handoff,
      identity,
      canonicalRead,
    );
    const bundle = parseShaclReviewBundle(handoff.bundle);
    const metadata = object(handoff.metadata);
    if (
      handoff.format !== "orinoco-shacl-submodule-handoff" ||
      handoff.version !== 1 ||
      !REPO.test(metadata.repository) ||
      !SHA.test(metadata.head_sha) ||
      !SHA.test(metadata.source_commit) ||
      typeof metadata.branch !== "string" ||
      !Number.isSafeInteger(metadata.pull_request) ||
      metadata.repository === request.repository ||
      bundle.records.some(
        (r) => !r.source_path.startsWith("site-specific/metadata/records/"),
      )
    )
      deny("Invalid coordinated proposal.");
    const repo = object(await website.json(`/repos/${request.repository}`));
    if (
      String(repo.id) !== grant.repository_id ||
      identity.ref !== `refs/heads/${repo.default_branch}`
    )
      deny("Repository identity or trusted default branch changed.");
    const pull = object(
      await website.pullRequest(request.repository, request.pull_request),
    );
    requireDraft(pull, request.repository, request.head, String(grant.branch));
    if (pull.base.sha !== grant.trusted_sha)
      deny(
        "The trusted default branch changed; submit again from the current deployment.",
      );
    await handoffCommit(
      website,
      request.repository,
      handoffSha,
      bundle.source_commit,
      grant,
    );
    if (canonicalRead)
      await canonicalCommit(
        website,
        request.repository,
        request.head,
        bundle.source_commit,
        grant,
        true,
      );
    await website.requireCurator(
      request.repository,
      String(grant.curator_login),
      Number(grant.curator_id),
    );
    const pinned = await website.siteSubmodule(
      request.repository,
      bundle.source_commit,
    );
    if (
      pinned?.repository !== metadata.repository ||
      pinned?.sha !== metadata.source_commit
    )
      deny("The source gitlink does not authorize this metadata repository.");
    const run = object(
      await website.json(
        `/repos/${request.repository}/actions/runs/${identity.run_id}`,
      ),
    );
    if (
      String(run.id) !== identity.run_id ||
      String(run.repository?.id) !== grant.repository_id ||
      run.event !==
        (canonicalRead ? "workflow_dispatch" : "pull_request_target") ||
      run.path !== WORKFLOW ||
      run.head_sha !== (canonicalRead ? grant.trusted_sha : request.head) ||
      run.run_attempt !== 1 ||
      (!canonicalRead && run.actor?.id !== grant.curator_id) ||
      run.status !== "in_progress"
    )
      deny("The GitHub run does not match this active proposal.");
    if (request.write) {
      const jobs = object(
        await website.json(
          `/repos/${request.repository}/actions/runs/${identity.run_id}/attempts/1/jobs?per_page=100`,
        ),
      );
      const job = jobs.jobs?.find(
        (j: any) =>
          j.check_run_url ===
          `https://api.github.com/repos/${request.repository}/check-runs/${identity.check_run_id}`,
      );
      for (const name of [
        "Validate the materialized joined graph",
        "Create the equivalent attributed human metadata commit",
      ]) {
        if (
          !job?.steps?.some(
            (s: any) =>
              s.name === name &&
              s.status === "completed" &&
              s.conclusion === "success",
          )
        )
          deny(
            "Trusted materialization and validation must succeed before write access.",
          );
      }
    }
    metadataToken = await auth.token(metadata.repository);
    const github = new GitHubClient(metadataToken.token, auth.fetcher);
    const metaRepo = object(await github.json(`/repos/${metadata.repository}`));
    if (String(metaRepo.id) !== grant.metadata_repository_id)
      deny("The metadata repository identity changed.");
    const metaPull = object(
      await github.pullRequest(metadata.repository, metadata.pull_request),
    );
    const currentMetadata = canonicalRead
      ? await website.siteSubmodule(request.repository, request.head)
      : pinned;
    if (
      currentMetadata === null ||
      currentMetadata.repository !== metadata.repository
    )
      deny("The replacement changed the metadata repository.");
    const metadataHead = canonicalRead
      ? currentMetadata.sha
      : metadata.head_sha;
    requireDraft(metaPull, metadata.repository, metadataHead, metadata.branch);
    if (canonicalRead)
      await canonicalCommit(
        github,
        metadata.repository,
        metadataHead,
        metadata.source_commit,
        grant,
        false,
      );
    if (metaPull.base.sha !== metadata.source_commit)
      deny("The metadata default branch changed.");
    await github.requireCurator(
      metadata.repository,
      String(grant.curator_login),
      Number(grant.curator_id),
    );
    await handoffCommit(
      github,
      metadata.repository,
      metadata.head_sha,
      metadata.source_commit,
      grant,
    );
    const metaValues = await github.contents(metadata.repository, [
      { key: "bundle", path: SHACL_BUNDLE_PATH, ref: metadata.head_sha },
    ]);
    if (
      JSON.stringify(
        parseShaclReviewBundle(parseOperationalJson(metaValues.get("bundle"))),
      ) !== JSON.stringify(bundle)
    )
      deny("The two handoffs do not contain the same authorized bundle.");
    // A separate write token is minted only after all current authority checks.
    if (request.write) return await auth.token(metadata.repository, true);
    const result = metadataToken;
    metadataToken = undefined;
    return result;
  } finally {
    await auth.revoke(websiteToken.token);
    if (metadataToken) await auth.revoke(metadataToken.token);
  }
}
