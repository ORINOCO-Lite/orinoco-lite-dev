import type { JWTPayload } from "jose";
import { GitHubClient } from "./github";
import { HttpError, requireExactKeys } from "./http";
import { parseRepository } from "./input";
import type { Env } from "./pages";
import { AppAuthentication, object } from "./workflow-access";
import { parseSubmission } from "./submission";

const WORKFLOW = ".github/workflows/curation-review.yml";
const SHA = /^[0-9a-f]{40}$/;
function deny(message: string): never {
  throw new HttpError(403, "curation_workflow_denied", message);
}

// Authorization comes from GitHub's current default-branch workflow and its
// authenticated dispatch/comment actor, never from a proposal artifact.
export async function curationWorkflowAccess(
  env: Env,
  identity: JWTPayload,
  request: Record<string, unknown>,
  auth = new AppAuthentication(env),
) {
  requireExactKeys(
    request,
    ["repository", "head", "write", "comment_id"],
    "curation workflow request",
  );
  const repository = parseRepository(
    typeof request.repository === "string" ? request.repository : null,
  );
  if (
    typeof request.head !== "string" ||
    !SHA.test(request.head) ||
    typeof request.write !== "boolean" ||
    !(
      request.comment_id === null ||
      (Number.isSafeInteger(request.comment_id) &&
        Number(request.comment_id) > 0)
    ) ||
    identity.repository !== repository ||
    identity.run_attempt !== "1" ||
    typeof identity.actor !== "string" ||
    !/^[1-9][0-9]*$/.test(String(identity.actor_id)) ||
    !/^[1-9][0-9]*$/.test(String(identity.run_id)) ||
    !/^[1-9][0-9]*$/.test(String(identity.check_run_id))
  )
    deny("Invalid curation workflow coordinates.");
  const token = await auth.token(repository, false, true);
  let metadataToken: { token: string; expires_at: string } | undefined;
  try {
    const website = new GitHubClient(token.token, auth.fetcher);
    const repo = object(await website.json(`/repos/${repository}`));
    const trusted = (await website.branchHead(repository, repo.default_branch))
      .sha;
    if (
      String(repo.id) !== identity.repository_id ||
      identity.ref !== `refs/heads/${repo.default_branch}` ||
      identity.workflow_sha !== trusted ||
      identity.workflow_ref !== `${repository}/${WORKFLOW}@${identity.ref}` ||
      identity.event_name !==
        (request.comment_id === null ? "workflow_dispatch" : "issue_comment")
    ) {
      deny(
        "The curation workflow must run the current trusted default branch.",
      );
    }
    const run = object(
      await website.workflowRun(repository, Number(identity.run_id)),
    );
    if (
      run.path !== WORKFLOW ||
      run.head_sha !== trusted ||
      run.status !== "in_progress" ||
      run.run_attempt !== 1 ||
      run.event !== identity.event_name ||
      String(run.repository?.id) !== identity.repository_id ||
      String(run.actor?.id) !== identity.actor_id ||
      run.actor?.login !== identity.actor
    ) {
      deny("The Actions run does not match the authenticated curation actor.");
    }
    await website.requireCurator(
      repository,
      identity.actor,
      Number(identity.actor_id),
    );
    let source = trusted;
    let submission;
    if (request.comment_id !== null) {
      const comment = object(
        await website.json(
          `/repos/${repository}/issues/comments/${request.comment_id}`,
        ),
      );
      if (
        String(comment.user?.id) !== identity.actor_id ||
        comment.user?.login !== identity.actor ||
        comment.created_at !== comment.updated_at ||
        typeof comment.body !== "string"
      ) {
        deny(
          "The authenticated decision comment was edited or belongs to another curator.",
        );
      }
      const matches = [...comment.body.matchAll(/```json\n([\s\S]*?)\n```/g)];
      if (matches.length !== 1 || !comment.body.includes("/curation submit"))
        deny("The comment has no complete curation submission.");
      try {
        submission = parseSubmission(JSON.parse(matches[0]![1]!));
      } catch {
        deny("The comment has no valid curation submission.");
      }
      if (
        submission.repository !== repository ||
        submission.head_sha !== request.head ||
        !submission.metadata ||
        comment.issue_url !==
          `https://api.github.com/repos/${repository}/issues/${submission.pull_request}`
      )
        deny("The comment does not authorize this proposal.");
      const pull = object(
        await website.pullRequest(repository, submission.pull_request),
      );
      if (
        pull.state !== "open" ||
        pull.draft !== true ||
        pull.head?.repo?.full_name !== repository ||
        pull.head?.sha !== request.head ||
        pull.base?.sha !== trusted ||
        pull.base?.ref !== repo.default_branch
      )
        deny("The website draft head or reviewed base changed.");
      source = submission.proposal_sha;
    } else if (request.head !== trusted)
      deny("The proposal base is no longer current.");
    const pinned = await website.siteSubmodule(repository, source);
    const current = await website.siteSubmodule(repository, request.head);
    if (
      !pinned ||
      !current ||
      pinned.repository !== current.repository ||
      (submission &&
        (submission.metadata!.repository !== pinned.repository ||
          submission.metadata!.proposal_sha !== pinned.sha ||
          submission.metadata!.head_sha !== current.sha))
    ) {
      deny("The submission does not match the website's metadata gitlinks.");
    }
    metadataToken = await auth.token(pinned.repository);
    const metadata = new GitHubClient(metadataToken.token, auth.fetcher);
    await metadata.requireCurator(
      pinned.repository,
      identity.actor,
      Number(identity.actor_id),
    );
    const metaRepo = object(await metadata.json(`/repos/${pinned.repository}`));
    if (submission) {
      const pull = object(
        await metadata.pullRequest(
          pinned.repository,
          submission.metadata!.pull_request,
        ),
      );
      const baseLink = await website.siteSubmodule(repository, trusted);
      if (
        pull.state !== "open" ||
        pull.draft !== true ||
        pull.head?.repo?.full_name !== pinned.repository ||
        pull.head?.sha !== current.sha ||
        pull.base?.sha !== baseLink?.sha ||
        pull.base?.ref !== metaRepo.default_branch
      )
        deny("The metadata draft head or reviewed base changed.");
    } else if (
      (await metadata.branchHead(pinned.repository, metaRepo.default_branch))
        .sha !== pinned.sha
    ) {
      deny("The metadata default branch differs from the website gitlink.");
    }
    if (request.write) {
      const jobs = object(
        await website.json(
          `/repos/${repository}/actions/runs/${identity.run_id}/attempts/1/jobs?per_page=100`,
        ),
      );
      const job = jobs.jobs?.find(
        (item: any) =>
          item.check_run_url ===
          `https://api.github.com/repos/${repository}/check-runs/${identity.check_run_id}`,
      );
      if (
        !job?.steps?.some(
          (step: any) =>
            step.name === "Validate and record the composed adapter result" &&
            step.status === "completed" &&
            step.conclusion === "success",
        )
      ) {
        deny(
          "Composed validation and DataLad recording must succeed before write access.",
        );
      }
      const writableMetadata = await auth.token(
        pinned.repository,
        true,
        false,
        request.comment_id === null,
      );
      try {
        const writableWebsite = await auth.token(repository, true, false, true);
        return {
          ...writableMetadata,
          website_token: writableWebsite.token,
          repository: pinned.repository,
          head: current.sha,
        };
      } catch (error) {
        await auth.revoke(writableMetadata.token);
        throw error;
      }
    }
    const result = metadataToken;
    metadataToken = undefined;
    return { ...result, repository: pinned.repository, head: current.sha };
  } finally {
    await auth.revoke(token.token);
    if (metadataToken) await auth.revoke(metadataToken.token);
  }
}
