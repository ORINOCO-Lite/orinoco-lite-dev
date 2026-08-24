import { GitHubClient } from "../lib/github";
import { jsonResponse, requireMethod } from "../lib/http";
import { reviewTarget } from "../lib/input";
import type { EventContext } from "../lib/pages";
import { loadReviewProposal } from "../lib/proposal";
import { readSessionCookie } from "../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const target = reviewTarget(new URL(context.request.url));
  const session = await readSessionCookie(context.request, context.env);
  const github = new GitHubClient(session.access_token);
  await github.requireCurator(target.repository, session.login);
  return jsonResponse(
    await loadReviewProposal(github, target.repository, target.pullRequest),
  );
}
