import { equalTokens } from "../lib/encoding";
import { GitHubClient } from "../lib/github";
import {
  HttpError,
  jsonResponse,
  readJsonBody,
  requireJsonContentType,
  requireMethod,
  requireSameOrigin,
} from "../lib/http";
import type { EventContext } from "../lib/pages";
import { loadReviewProposal } from "../lib/proposal";
import { configuredOrigin, readSessionCookie } from "../lib/session";
import {
  parseSubmission,
  submissionComment,
  verifySubmission,
} from "../lib/submission";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  requireSameOrigin(context.request, configuredOrigin(context.env));
  if (new URL(context.request.url).search) {
    throw new HttpError(
      400,
      "unexpected_query",
      "The submission endpoint accepts no query fields.",
    );
  }
  const session = await readSessionCookie(context.request, context.env);
  const supplied = context.request.headers.get("x-csrf-token") ?? "";
  if (!equalTokens(supplied, session.csrf_token)) {
    throw new HttpError(403, "invalid_csrf", "The request token is invalid.");
  }
  const submitted = parseSubmission(await readJsonBody(context.request));
  const github = new GitHubClient(session.access_token);
  await github.requireCurator(submitted.repository, session.login);
  const proposal = await loadReviewProposal(
    github,
    submitted.repository,
    submitted.pull_request,
  );
  const verified = verifySubmission(submitted, proposal);
  const commentUrl = await github.postComment(
    proposal.repository,
    proposal.pull_request,
    submissionComment(verified),
  );
  return jsonResponse({ comment_url: commentUrl }, { status: 201 });
}
