import type { ReviewDiscovery } from "../../shared/contracts";
import { GitHubClient } from "../lib/github";
import { HttpError, jsonResponse, requireMethod } from "../lib/http";
import { parseRepository } from "../lib/input";
import type { EventContext } from "../lib/pages";
import { readSessionCookie } from "../lib/session";

function discoveryRepository(url: URL): string {
  for (const key of url.searchParams.keys()) {
    if (key !== "repository") {
      throw new HttpError(
        400,
        "unexpected_query",
        "The request has an unexpected query field.",
      );
    }
  }
  if (url.searchParams.getAll("repository").length !== 1) {
    throw new HttpError(400, "invalid_query", "Repository is required once.");
  }
  return parseRepository(url.searchParams.get("repository"));
}

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const repository = discoveryRepository(new URL(context.request.url));
  const session = await readSessionCookie(context.request, context.env);
  const github = new GitHubClient(session.access_token);
  await github.requireCurator(repository, session.login);
  const result: ReviewDiscovery = {
    pull_requests: await github.discoverReviewPullRequests(repository),
    repository,
  };
  return jsonResponse(result);
}
