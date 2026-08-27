import { equalTokens } from "../../lib/encoding";
import { GitHubClient } from "../../lib/github";
import {
  HttpError,
  jsonResponse,
  readJsonBody,
  requireJsonContentType,
  requireMethod,
  requireSameOrigin,
} from "../../lib/http";
import type { EventContext } from "../../lib/pages";
import {
  MAX_SHACL_PROPOSAL_BODY_BYTES,
  parseShaclProposalRequest,
} from "../../lib/shacl";
import { createShaclProposal } from "../../lib/shacl-proposal";
import {
  configuredOrigin,
  consumeSessionGrantCookie,
  readSessionCookie,
} from "../../lib/session";

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "POST");
  requireJsonContentType(context.request);
  requireSameOrigin(context.request, configuredOrigin(context.env));
  const url = new URL(context.request.url);
  if ([...url.searchParams.keys()].length > 0) {
    throw new HttpError(
      400,
      "unexpected_query",
      "The SHACL proposal endpoint does not accept query fields.",
    );
  }
  const session = await readSessionCookie(context.request, context.env);
  const supplied = context.request.headers.get("x-csrf-token") ?? "";
  if (!equalTokens(supplied, session.csrf_token)) {
    throw new HttpError(403, "invalid_csrf", "The request token is invalid.");
  }
  const proposal = parseShaclProposalRequest(
    await readJsonBody(context.request, MAX_SHACL_PROPOSAL_BODY_BYTES),
  );
  const grant = session.shacl_grant;
  const pullRequest =
    proposal.target.kind === "pull_request"
      ? proposal.target.pull_request
      : null;
  const expectedHeadSha =
    proposal.target.kind === "pull_request"
      ? proposal.target.expected_head_sha
      : null;
  if (
    grant === null ||
    grant.repository.toLowerCase() !== proposal.repository.toLowerCase() ||
    grant.pull_request !== pullRequest ||
    grant.expected_head_sha !== expectedHeadSha
  ) {
    throw new HttpError(
      403,
      "shacl_grant_required",
      "Sign in from this downstream editor before proposing its bundle.",
    );
  }
  const result = await createShaclProposal(
    new GitHubClient(session.access_token),
    proposal,
    grant,
    configuredOrigin(context.env),
  );
  return jsonResponse(result, {
    headers: {
      "Set-Cookie": await consumeSessionGrantCookie(
        context.env,
        session,
        "shacl",
      ),
    },
    status: 201,
  });
}
