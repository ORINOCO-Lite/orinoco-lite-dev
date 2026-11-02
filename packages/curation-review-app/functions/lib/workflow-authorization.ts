import { SignJWT, jwtVerify, type JWTPayload } from "jose";
import { utf8 } from "./encoding";
import { GitHubClient } from "./github";
import { HttpError } from "./http";
import type { Env } from "./pages";
import { AppAuthentication } from "./workflow-access";
import { writableUserRepository } from "./user-credentials";
import type { BrowserCredentialScope } from "./browser-access";

const AUDIENCE = "orinoco-repository-workflow";
const SHA = /^[0-9a-f]{40}$/;
const WORKER =
  /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/\.github\/workflows\/[A-Za-z0-9_.-]+\.ya?ml@[0-9a-f]{40}$/;

export interface WorkflowAuthorizationRequest {
  input_repository: string;
  input_commit: string;
  scope: BrowserCredentialScope;
}

export interface WorkflowAuthorization extends WorkflowAuthorizationRequest {
  submitter: { id: number; login: string };
}

function deny(message: string): never {
  throw new HttpError(403, "workflow_authorization_required", message);
}

function signingKey(env: Env): Uint8Array {
  return utf8(`orinoco-repository-workflow-v1:${env.SESSION_SEAL_KEY}`);
}

function validateRequest(value: WorkflowAuthorizationRequest): void {
  const repositories = value?.scope?.repositories;
  if (
    !Array.isArray(repositories) ||
    repositories.length < 1 ||
    repositories.length > 2 ||
    repositories.some(
      (repository) =>
        !repository ||
        typeof repository.name !== "string" ||
        !Number.isSafeInteger(repository.id) ||
        repository.id <= 0 ||
        !SHA.test(repository.baseCommit) ||
        !WORKER.test(repository.worker),
    ) ||
    new Set(repositories.map((repository) => repository.name.toLowerCase()))
      .size !== repositories.length ||
    !repositories.some(
      (repository) => repository.name === value.input_repository,
    ) ||
    !SHA.test(value.input_commit) ||
    !SHA.test(value.scope.source?.commit) ||
    value.scope.source?.repository !== repositories[0]?.name ||
    (value.scope.metadata !== null &&
      (!SHA.test(value.scope.metadata?.commit) ||
        !repositories.some(
          (repository) => repository.name === value.scope.metadata?.repository,
        )))
  )
    deny(
      "The workflow authorization needs its repositories, immutable input commit, and pinned reusable workflow.",
    );
}

/** Record the signed-in user's consent to process this immutable submission. */
export async function authorizeSubmission(
  env: Env,
  github: GitHubClient,
  request: WorkflowAuthorizationRequest,
): Promise<string> {
  validateRequest(request);
  const submitter = await github.currentUser();
  const repositories = await Promise.all(
    request.scope.repositories.map(({ name }) =>
      writableUserRepository(github, name),
    ),
  );
  if (
    repositories.some(
      (repository, index) =>
        repository.id !== request.scope.repositories[index]!.id ||
        repository.name !== request.scope.repositories[index]!.name,
    )
  )
    deny("The repository identity changed during submission. Sign in again.");
  const authorization: WorkflowAuthorization = {
    ...request,
    submitter,
  };
  // This is a record of consent, not a GitHub credential. It survives review
  // and merge delays; use requires the pinned worker's GitHub-signed identity.
  return new SignJWT({ authorization })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuer(env.PUBLIC_ORIGIN)
    .setAudience(AUDIENCE)
    .setIssuedAt()
    .sign(signingKey(env));
}

export async function verifySubmissionAuthorization(
  env: Env,
  signed: string,
  identity: JWTPayload,
): Promise<WorkflowAuthorization> {
  let authorization: WorkflowAuthorization;
  try {
    const { payload } = await jwtVerify(signed, signingKey(env), {
      issuer: env.PUBLIC_ORIGIN,
      audience: AUDIENCE,
      algorithms: ["HS256"],
      requiredClaims: ["iat", "authorization"],
    });
    authorization = payload.authorization as WorkflowAuthorization;
    validateRequest(authorization);
    if (
      !Number.isSafeInteger(authorization.submitter?.id) ||
      authorization.submitter.id <= 0 ||
      typeof authorization.submitter.login !== "string"
    )
      throw new Error("Invalid authorization identity");
  } catch {
    return deny("The submission authorization is missing or invalid.");
  }
  const repository = authorization.scope.repositories.find(
    (repository) => repository.name === identity.repository,
  );
  if (
    !repository ||
    identity.repository_id !== String(repository.id) ||
    identity.job_workflow_ref !== repository.worker ||
    identity.job_workflow_sha !== repository.worker.slice(-40)
  )
    deny(
      "This GitHub Actions job is not the workflow authorized for the submission.",
    );
  // The merger need not be the submitter. The worker may only process the
  // authenticated input returned below, never substitute caller-supplied data.
  return authorization;
}

export async function submissionCredentials(
  env: Env,
  signed: string,
  identity: JWTPayload,
  auth = new AppAuthentication(env),
): Promise<{
  authorization: WorkflowAuthorization;
  credentials: Record<string, { token: string; expires_at: string }>;
}> {
  const authorization = await verifySubmissionAuthorization(
    env,
    signed,
    identity,
  );
  const credentials: Record<string, { token: string; expires_at: string }> = {};
  try {
    for (const repository of authorization.scope.repositories) {
      const credential = await auth.token(repository.name, true, false, true);
      credentials[repository.name] = credential;
      const current = (await new GitHubClient(
        credential.token,
        auth.fetcher,
      ).json(`/repos/${repository.name}`)) as any;
      if (current?.id !== repository.id)
        deny("The authorized repository identity changed.");
    }
    return { authorization, credentials };
  } catch (error) {
    await Promise.allSettled(
      Object.values(credentials).map((credential) =>
        auth.revoke(credential.token),
      ),
    );
    throw error;
  }
}
