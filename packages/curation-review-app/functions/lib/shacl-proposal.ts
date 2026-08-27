import type {
  ShaclGrant,
  ShaclProposalRequest,
  ShaclProposalResult,
} from "../../shared/contracts";
import { GitHubClient } from "./github";
import { HttpError } from "./http";
import { siteCoordinates } from "./proposal";
import { SHACL_BUNDLE_PATH, serializeShaclReviewBundle } from "./shacl";

const COMMIT_HEADLINE = "chore(metadata): hand off SHACL Vue edit";
const PULL_REQUEST_TITLE = "chore(metadata): propose SHACL Vue edit";

interface PullRequestCoordinates {
  baseSha: string;
  branch: string;
  headSha: string;
  number: number;
  url: string;
}

function nestedRecord(
  value: Record<string, unknown>,
  key: string,
): Record<string, unknown> | null {
  const item = value[key];
  return item !== null && typeof item === "object" && !Array.isArray(item)
    ? (item as Record<string, unknown>)
    : null;
}

function parsePullRequest(
  value: unknown,
  repository: string,
  number: number,
): PullRequestCoordinates {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(
      502,
      "github_error",
      "GitHub returned an invalid pull request.",
    );
  }
  const record = value as Record<string, unknown>;
  const base = nestedRecord(record, "base");
  const head = nestedRecord(record, "head");
  const baseRepository = base === null ? null : nestedRecord(base, "repo");
  const headRepository = head === null ? null : nestedRecord(head, "repo");
  if (
    record.number !== number ||
    record.state !== "open" ||
    record.draft !== true ||
    typeof base?.ref !== "string" ||
    typeof base.sha !== "string" ||
    !/^[0-9a-f]{40}$/.test(base.sha) ||
    typeof head?.ref !== "string" ||
    typeof head.sha !== "string" ||
    !/^[0-9a-f]{40}$/.test(head.sha) ||
    typeof baseRepository?.full_name !== "string" ||
    baseRepository.full_name.toLowerCase() !== repository.toLowerCase() ||
    typeof headRepository?.full_name !== "string" ||
    headRepository.full_name.toLowerCase() !== repository.toLowerCase() ||
    typeof record.html_url !== "string" ||
    record.html_url.toLowerCase() !==
      `https://github.com/${repository}/pull/${number}`.toLowerCase()
  ) {
    throw new HttpError(
      422,
      "invalid_shacl_pull_request",
      "SHACL edits require an open same-repository draft pull request.",
    );
  }
  return {
    baseSha: base.sha,
    branch: head.ref,
    headSha: head.sha,
    number,
    url: record.html_url,
  };
}

function commitBody(sourceCommit: string): string {
  return [
    "Hand off the exact SHACL Vue v2 bundle for the trusted workflow.",
    "",
    `Source commit: ${sourceCommit}`,
    `Temporary path: ${SHACL_BUNDLE_PATH}`,
  ].join("\n");
}

function pullRequestBody(sourceCommit: string): string {
  return [
    "This draft contains an explicit human-authored SHACL Vue proposal.",
    "The trusted default-branch workflow must validate the bundle and replace",
    "the temporary handoff commit with equivalent canonical YAML.",
    "",
    "Warning: the temporary bundle is public while referenced and may remain",
    "retrievable by commit ID after its branch becomes unreachable under GitHub",
    "retention. Do not merge this pull request while the temporary path exists.",
    "",
    `Source commit: ${sourceCommit}`,
    `Temporary path: ${SHACL_BUNDLE_PATH}`,
    "",
    "The service did not approve, merge, deploy, or write to a source system.",
  ].join("\n");
}

function failureDiagnostic(error: unknown): string {
  return error instanceof HttpError
    ? `${error.code}: ${error.message}`
    : "internal_error: GitHub did not complete the proposal operation.";
}

async function requireEmptyHandoffPath(
  github: GitHubClient,
  repository: string,
  sha: string,
): Promise<void> {
  if (await github.pathExists(repository, sha, SHACL_BUNDLE_PATH)) {
    throw new HttpError(
      409,
      "shacl_handoff_pending",
      "A SHACL Vue bundle handoff is already present at this head.",
    );
  }
}

async function requireTrustedEditorDeployment(
  github: GitHubClient,
  repository: string,
  baseSha: string,
  grant: ShaclGrant,
  serviceOrigin: string,
): Promise<void> {
  const contents = await github.contents(repository, [
    { key: "site-config", path: "orinoco.yaml", ref: baseSha },
  ]);
  const site = siteCoordinates(contents.get("site-config") ?? null);
  if (
    new URL(site.editorSiteUrl).origin !== grant.editor_origin ||
    site.reviewServiceOrigin !== serviceOrigin
  ) {
    throw new HttpError(
      403,
      "shacl_transport_mismatch",
      "This editor does not match the repository's trusted deployment.",
    );
  }
}

export async function createShaclProposal(
  github: GitHubClient,
  proposal: ShaclProposalRequest,
  grant: ShaclGrant,
  serviceOrigin: string,
): Promise<ShaclProposalResult> {
  const pullRequest =
    proposal.target.kind === "pull_request"
      ? proposal.target.pull_request
      : null;
  const expectedHeadSha =
    proposal.target.kind === "pull_request"
      ? proposal.target.expected_head_sha
      : null;
  if (
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
  const user = await github.currentUser();
  await github.requireCurator(proposal.repository, user.login);
  const bytes = serializeShaclReviewBundle(proposal.bundle);

  if (proposal.target.kind === "pull_request") {
    const pull = parsePullRequest(
      await github.pullRequest(
        proposal.repository,
        proposal.target.pull_request,
      ),
      proposal.repository,
      proposal.target.pull_request,
    );
    if (
      pull.headSha !== proposal.target.expected_head_sha ||
      pull.headSha !== proposal.bundle.source_commit
    ) {
      throw new HttpError(
        409,
        "stale_shacl_proposal",
        "The draft pull-request head no longer matches the SHACL bundle source commit.",
      );
    }
    await requireTrustedEditorDeployment(
      github,
      proposal.repository,
      pull.baseSha,
      grant,
      serviceOrigin,
    );
    await requireEmptyHandoffPath(github, proposal.repository, pull.headSha);
    const commit = await github.commitFileAtHead(
      proposal.repository,
      pull.branch,
      pull.headSha,
      SHACL_BUNDLE_PATH,
      bytes,
      COMMIT_HEADLINE,
      commitBody(pull.headSha),
    );
    return {
      commit_sha: commit.sha,
      commit_url: commit.url,
      pull_request: pull.number,
      pull_request_url: pull.url,
    };
  }

  const repository = await github.repository(proposal.repository);
  const base = await github.branchHead(
    proposal.repository,
    repository.defaultBranch,
  );
  if (base.sha !== proposal.bundle.source_commit) {
    throw new HttpError(
      409,
      "stale_shacl_proposal",
      "The repository default-branch head no longer matches the SHACL bundle source commit.",
    );
  }
  await requireTrustedEditorDeployment(
    github,
    proposal.repository,
    base.sha,
    grant,
    serviceOrigin,
  );
  await requireEmptyHandoffPath(github, proposal.repository, base.sha);
  const branch = `curation/shacl-vue-${base.sha.slice(0, 12)}-${grant.handoff_nonce.slice(0, 16)}`;
  await github.createBranch(proposal.repository, branch, base.sha);
  try {
    const commit = await github.commitFileAtHead(
      proposal.repository,
      branch,
      base.sha,
      SHACL_BUNDLE_PATH,
      bytes,
      COMMIT_HEADLINE,
      commitBody(base.sha),
    );
    const pull = await github.openDraftPullRequest(
      proposal.repository,
      branch,
      repository.defaultBranch,
      commit.sha,
      PULL_REQUEST_TITLE,
      pullRequestBody(base.sha),
    );
    return {
      commit_sha: commit.sha,
      commit_url: commit.url,
      pull_request: pull.number,
      pull_request_url: pull.url,
    };
  } catch (error) {
    try {
      await github.deleteBranch(proposal.repository, branch);
    } catch (cleanupError) {
      throw new HttpError(
        502,
        "shacl_cleanup_failed",
        `Standalone SHACL proposal failed (${failureDiagnostic(error)}); cleanup of refs/heads/${branch} also failed (${failureDiagnostic(cleanupError)}). Remove that branch before retrying.`,
      );
    }
    throw error;
  }
}
