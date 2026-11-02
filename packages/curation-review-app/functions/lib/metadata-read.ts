import type { JWTPayload } from "jose";
import { GitHubClient } from "./github";
import { HttpError } from "./http";
import type { Env } from "./pages";
import { AppAuthentication, object } from "./workflow-access";

const SHA = /^[0-9a-f]{40}$/;
const REPO = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const WORKFLOW = ".github/workflows/shacl-vue-proposal.yml";
function deny(): never {
  throw new HttpError(
    403,
    "metadata_read_denied",
    "GitHub could not verify the linked metadata proposal.",
  );
}

export async function metadataReadAccess(
  env: Env,
  identity: JWTPayload,
  request: Record<string, any>,
  auth = new AppAuthentication(env),
) {
  if (
    Object.keys(request).sort().join() !== "head,pull_request,repository" ||
    typeof request.repository !== "string" ||
    !REPO.test(request.repository) ||
    !SHA.test(request.head) ||
    !Number.isSafeInteger(request.pull_request) ||
    request.pull_request < 1 ||
    identity.repository !== request.repository ||
    !["pull_request_target", "workflow_dispatch"].includes(
      String(identity.event_name),
    ) ||
    !/^[1-9][0-9]*$/.test(String(identity.run_attempt)) ||
    !/^[1-9][0-9]*$/.test(String(identity.run_id)) ||
    !SHA.test(String(identity.workflow_sha))
  )
    deny();
  const websiteToken = await auth.token(request.repository, false, true);
  let metadataToken: { token: string; expires_at: string } | undefined;
  try {
    const website = new GitHubClient(websiteToken.token, auth.fetcher);
    const repo = object(await website.json(`/repos/${request.repository}`));
    if (
      String(repo.id) !== identity.repository_id ||
      identity.ref !== `refs/heads/${repo.default_branch}` ||
      identity.workflow_ref !==
        `${request.repository}/${WORKFLOW}@${identity.ref}`
    )
      deny();
    const pull = object(
      await website.pullRequest(request.repository, request.pull_request),
    );
    if (
      pull.state !== "open" ||
      pull.head?.repo?.full_name !== request.repository ||
      pull.base?.repo?.full_name !== request.repository ||
      pull.base?.ref !== repo.default_branch ||
      pull.head?.sha !== request.head ||
      typeof pull.head?.ref !== "string"
    )
      deny();
    const run = object(
      await website.json(
        `/repos/${request.repository}/actions/runs/${identity.run_id}`,
      ),
    );
    if (
      String(run.id) !== identity.run_id ||
      String(run.repository?.id) !== identity.repository_id ||
      run.path !== WORKFLOW ||
      run.event !== identity.event_name ||
      String(run.run_attempt) !== identity.run_attempt ||
      run.status !== "in_progress" ||
      run.head_sha !==
        (identity.event_name === "workflow_dispatch"
          ? identity.workflow_sha
          : request.head)
    )
      deny();
    const link = await website.siteSubmodule(request.repository, request.head);
    if (
      !link ||
      !REPO.test(link.repository) ||
      !SHA.test(link.sha) ||
      link.repository === request.repository
    )
      deny();
    metadataToken = await auth.token(link.repository);
    const metadata = new GitHubClient(metadataToken.token, auth.fetcher);
    const pulls = await metadata.json(
      `/repos/${link.repository}/commits/${link.sha}/pulls?per_page=100`,
    );
    const marker = `Website branch: https://github.com/${request.repository}/tree/${encodeURIComponent(pull.head.ref)}`;
    if (!Array.isArray(pulls)) deny();
    const matches = pulls.filter(
      (item) =>
        item.merged_at &&
        item.merge_commit_sha === link.sha &&
        typeof item.body === "string" &&
        item.body.split("\n").includes(marker),
    );
    if (
      matches.length !== 1 ||
      !Number.isSafeInteger(matches[0].user?.id) ||
      typeof matches[0].user?.login !== "string"
    )
      deny();
    const author = matches[0].user;
    await website.requireCurator(request.repository, author.login, author.id);
    await metadata.requireCurator(link.repository, author.login, author.id);
    const result = metadataToken;
    metadataToken = undefined;
    return result;
  } finally {
    await auth.revoke(websiteToken.token);
    if (metadataToken) await auth.revoke(metadataToken.token);
  }
}
