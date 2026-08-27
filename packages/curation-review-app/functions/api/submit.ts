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
import { parseArtifactId } from "../lib/input";
import { loadReviewProposal, requireReviewTransport } from "../lib/proposal";
import {
  configuredOrigin,
  consumeSessionGrantCookie,
  readSessionCookie,
} from "../lib/session";
import {
  parseSubmission,
  submissionComment,
  verifySubmission,
} from "../lib/submission";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  const serviceOrigin = configuredOrigin(context.env);
  requireSameOrigin(context.request, serviceOrigin);
  const url = new URL(context.request.url);
  if (
    [...url.searchParams.keys()].some((key) => key !== "artifact_id") ||
    url.searchParams.getAll("artifact_id").length !== 1
  ) {
    throw new HttpError(
      400,
      "unexpected_query",
      "The submission endpoint requires one artifact_id query field.",
    );
  }
  const artifactId = parseArtifactId(url.searchParams.get("artifact_id"));
  const session = await readSessionCookie(context.request, context.env);
  const supplied = context.request.headers.get("x-csrf-token") ?? "";
  if (!equalTokens(supplied, session.csrf_token)) {
    throw new HttpError(403, "invalid_csrf", "The request token is invalid.");
  }
  const submitted = parseSubmission(await readJsonBody(context.request));
  const grant = session.review_grant;
  if (
    grant === null ||
    grant.artifact_id !== artifactId ||
    grant.pull_request !== submitted.pull_request ||
    grant.repository.toLowerCase() !== submitted.repository.toLowerCase()
  ) {
    throw new HttpError(
      403,
      "review_grant_required",
      "Sign in from this downstream review before posting its decisions.",
    );
  }
  const github = new GitHubClient(session.access_token);
  await github.requireCurator(submitted.repository, session.login);
  const proposal = await loadReviewProposal(
    github,
    submitted.repository,
    submitted.pull_request,
    artifactId,
  );
  requireReviewTransport(proposal, grant, serviceOrigin);
  const verified = verifySubmission(submitted, proposal);
  const commentUrl = await github.postComment(
    proposal.repository,
    proposal.pull_request,
    submissionComment(verified),
  );
  return jsonResponse(
    { comment_url: commentUrl },
    {
      headers: {
        "Set-Cookie": await consumeSessionGrantCookie(
          context.env,
          session,
          "review",
        ),
      },
      status: 201,
    },
  );
}
