import { requireOperation } from "./operation-policy";
import type { JWTPayload } from "jose";
import { GitHubClient } from "./github";
import { HttpError, requireExactKeys } from "./http";
import { parseRepository } from "./input";
import type { Env } from "./pages";
import { AppAuthentication, object } from "./workflow-access";

const WORKFLOW = ".github/workflows/template-update.yml";
function deny(message: string): never {
  throw new HttpError(403, "template_workflow_denied", message);
}

export async function templateWorkflowAccess(
  env: Env,
  identity: JWTPayload,
  request: Record<string, unknown>,
  auth = new AppAuthentication(env),
) {
  requireExactKeys(
    request,
    "site_specific" in request
      ? ["repository", "head", "site_specific"]
      : ["repository", "head"],
    "template workflow request",
  );
  const repository = parseRepository(
    typeof request.repository === "string" ? request.repository : null,
  );
  if (
    ("site_specific" in request && request.site_specific !== true) ||
    identity.repository !== repository ||
    typeof request.head !== "string" ||
    !/^[0-9a-f]{40}$/.test(request.head) ||
    identity.workflow_sha !== request.head ||
    identity.event_name !== "workflow_dispatch" ||
    identity.run_attempt !== "1" ||
    typeof identity.ref !== "string" ||
    !identity.ref.startsWith("refs/heads/") ||
    identity.workflow_ref !== `${repository}/${WORKFLOW}@${identity.ref}` ||
    typeof identity.actor !== "string" ||
    ![identity.actor_id, identity.run_id, identity.check_run_id].every(
      (value) => /^[1-9][0-9]*$/.test(String(value)),
    )
  )
    deny("Invalid template workflow coordinates.");
  const read = await auth.token(repository, false, true);
  try {
    const github = new GitHubClient(read.token, auth.fetcher);
    await requireOperation(github, repository, "template_updates");
    const repo = object(await github.json(`/repos/${repository}`));
    const current = await github.branchHead(
      repository,
      identity.ref.slice("refs/heads/".length),
    );
    if (
      String(repo.id) !== identity.repository_id ||
      current.sha !== request.head
    )
      deny("The repository or update base changed. Start a new update.");
    // A recovery branch may run only the workflow trusted on the default branch.
    const files = await github.contents(repository, [
      { key: "trusted", path: WORKFLOW, ref: repo.default_branch },
      { key: "running", path: WORKFLOW, ref: request.head },
    ]);
    if (!files.get("trusted") || files.get("trusted") !== files.get("running"))
      deny(
        "The update must use the current default branch's trusted workflow.",
      );
    await github.requireCurator(
      repository,
      identity.actor,
      Number(identity.actor_id),
    );
    const run = object(
      await github.workflowRun(repository, Number(identity.run_id)),
    );
    if (
      run.path !== WORKFLOW ||
      run.head_sha !== request.head ||
      run.status !== "in_progress" ||
      run.run_attempt !== 1 ||
      run.event !== identity.event_name ||
      String(run.repository?.id) !== identity.repository_id ||
      String(run.actor?.id) !== identity.actor_id ||
      run.actor?.login !== identity.actor
    )
      deny("The Actions run does not match the authenticated update actor.");
    const jobs = object(
      await github.json(
        `/repos/${repository}/actions/runs/${identity.run_id}/attempts/1/jobs?per_page=100`,
      ),
    );
    const publisher = jobs.jobs?.find(
      (job: any) =>
        job.check_run_url ===
        `https://api.github.com/repos/${repository}/check-runs/${identity.check_run_id}`,
    );
    if (
      publisher?.name !== "Publish template update" ||
      publisher.status !== "in_progress" ||
      !jobs.jobs?.some(
        (job: any) =>
          job.name === "Prepare template update" &&
          job.conclusion === "success",
      )
    )
      deny(
        "Only the separate publishing job may obtain update access after preparation.",
      );
    if (!request.site_specific)
      return await auth.token(repository, true, false, true, true);
    // The original gitlink authorizes the child repository, never candidate output.
    const pinned = await github.siteSubmodule(repository, request.head);
    if (!pinned) deny("The update base has no site-specific submodule.");
    const childRead = await auth.token(pinned.repository);
    try {
      const child = new GitHubClient(childRead.token, auth.fetcher);
      await child.requireCurator(
        pinned.repository,
        identity.actor,
        Number(identity.actor_id),
      );
      const childRepo = object(await child.json(`/repos/${pinned.repository}`));
      const branch = childRepo.default_branch;
      if (
        (await child.branchHead(pinned.repository, branch)).sha !== pinned.sha
      )
        deny(
          "The site-specific default branch changed; update the parent gitlink first.",
        );
      const childWrite = await auth.token(pinned.repository, true, false, true);
      try {
        return {
          ...(await auth.token(repository, true, false, true, true)),
          site_token: childWrite.token,
          site_repository: pinned.repository,
          site_head: pinned.sha,
          site_branch: branch,
        };
      } catch (error) {
        await auth.revoke(childWrite.token);
        throw error;
      }
    } finally {
      await auth.revoke(childRead.token);
    }
  } finally {
    await auth.revoke(read.token);
  }
}
