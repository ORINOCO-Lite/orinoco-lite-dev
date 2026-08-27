import { GitHubClient } from "../lib/github";
import { HttpError, jsonResponse, requireMethod } from "../lib/http";
import { reviewTarget } from "../lib/input";
import type { EventContext } from "../lib/pages";
import { loadReviewProposal, requireReviewTransport } from "../lib/proposal";
import { configuredOrigin, readSessionCookie } from "../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const target = reviewTarget(new URL(context.request.url));
  const session = await readSessionCookie(context.request, context.env);
  const grant = session.review_grant;
  if (
    grant === null ||
    grant.artifact_id !== target.artifactId ||
    grant.pull_request !== target.pullRequest ||
    grant.repository.toLowerCase() !== target.repository.toLowerCase()
  ) {
    throw new HttpError(
      403,
      "review_grant_required",
      "Sign in from this downstream review before loading its proposal.",
    );
  }
  const github = new GitHubClient(session.access_token);
  await github.requireCurator(target.repository, session.login);
  const proposal = await loadReviewProposal(
    github,
    target.repository,
    target.pullRequest,
    target.artifactId,
  );
  requireReviewTransport(proposal, grant, configuredOrigin(context.env));
  return jsonResponse(proposal);
}
