import { renderEditorPage } from "../../lib/editor-page";
import { loadExactHeadEditorInput } from "../../lib/editor-input";
import { GitHubClient } from "../../lib/github";
import { HttpError, requireMethod } from "../../lib/http";
import { parsePullRequest, parseRepository } from "../../lib/input";
import type { EventContext } from "../../lib/pages";
import { readSessionCookie } from "../../lib/session";

interface EditorTarget {
  expectedHeadSha: string | null;
  pullRequest: number | null;
  repository: string;
}

function editorTarget(url: URL): EditorTarget {
  const allowed = new Set(["expected_head_sha", "pull_request", "repository"]);
  if (
    [...url.searchParams.keys()].some((key) => !allowed.has(key)) ||
    url.searchParams.getAll("repository").length !== 1
  ) {
    throw new HttpError(
      400,
      "invalid_shacl_editor_target",
      "The SHACL editor target is invalid.",
    );
  }
  const pulls = url.searchParams.getAll("pull_request");
  const heads = url.searchParams.getAll("expected_head_sha");
  if (
    pulls.length > 1 ||
    heads.length > 1 ||
    (pulls.length === 0) !== (heads.length === 0)
  ) {
    throw new HttpError(
      400,
      "invalid_shacl_editor_target",
      "The SHACL editor pull-request coordinates must be supplied together once.",
    );
  }
  const expectedHeadSha = heads[0] ?? null;
  if (expectedHeadSha !== null && !/^[0-9a-f]{40}$/.test(expectedHeadSha)) {
    throw new HttpError(
      400,
      "invalid_shacl_editor_target",
      "The SHACL editor expected head is invalid.",
    );
  }
  return {
    expectedHeadSha,
    pullRequest: pulls.length === 1 ? parsePullRequest(pulls[0] ?? null) : null,
    repository: parseRepository(url.searchParams.get("repository")),
  };
}

function nested(
  value: Record<string, unknown>,
  key: string,
): Record<string, unknown> | null {
  const item = value[key];
  return item !== null && typeof item === "object" && !Array.isArray(item)
    ? (item as Record<string, unknown>)
    : null;
}

function exactPullHead(
  value: unknown,
  repository: string,
  number: number,
  expectedHeadSha: string,
): string {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(
      502,
      "github_error",
      "GitHub returned an invalid pull request.",
    );
  }
  const pull = value as Record<string, unknown>;
  const base = nested(pull, "base");
  const head = nested(pull, "head");
  const baseRepository = base === null ? null : nested(base, "repo");
  const headRepository = head === null ? null : nested(head, "repo");
  if (
    pull.number !== number ||
    pull.state !== "open" ||
    pull.draft !== true ||
    typeof base?.ref !== "string" ||
    typeof head?.ref !== "string" ||
    typeof head.sha !== "string" ||
    !/^[0-9a-f]{40}$/.test(head.sha) ||
    typeof baseRepository?.full_name !== "string" ||
    baseRepository.full_name.toLowerCase() !== repository.toLowerCase() ||
    typeof headRepository?.full_name !== "string" ||
    headRepository.full_name.toLowerCase() !== repository.toLowerCase()
  ) {
    throw new HttpError(
      422,
      "invalid_shacl_pull_request",
      "SHACL edits require an open same-repository draft pull request.",
    );
  }
  if (head.sha !== expectedHeadSha) {
    throw new HttpError(
      409,
      "stale_shacl_editor",
      "The draft pull-request head no longer matches the requested editor head.",
    );
  }
  return head.sha;
}

export async function onRequest(context: EventContext): Promise<Response> {
  requireMethod(context.request, "GET");
  const target = editorTarget(new URL(context.request.url));
  const session = await readSessionCookie(context.request, context.env);
  const github = new GitHubClient(session.access_token);
  const user = await github.currentUser();
  await github.requireCurator(target.repository, user.login);

  let headSha: string;
  if (target.pullRequest !== null && target.expectedHeadSha !== null) {
    headSha = exactPullHead(
      await github.pullRequest(target.repository, target.pullRequest),
      target.repository,
      target.pullRequest,
      target.expectedHeadSha,
    );
  } else {
    const repository = await github.repository(target.repository);
    headSha = (
      await github.branchHead(target.repository, repository.defaultBranch)
    ).sha;
  }
  const input = await loadExactHeadEditorInput(
    github,
    target.repository,
    headSha,
  );
  return renderEditorPage(
    context.env,
    context.request.url,
    target.repository,
    input,
  );
}
