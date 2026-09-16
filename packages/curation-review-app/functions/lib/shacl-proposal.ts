import type {
  ShaclGrant,
  ShaclProposalRequest,
  ShaclProposalResult,
} from "../../shared/contracts";
import { GitHubClient } from "./github";
import { HttpError } from "./http";
import { loadSiteCoordinates, type SiteCoordinates } from "./proposal";
import {
  SHACL_BUNDLE_PATH,
  serializeShaclReviewBundle,
  validateShaclRecordPaths,
} from "./shacl";

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

async function prepareHandoff(
  github: GitHubClient,
  proposal: ShaclProposalRequest,
  grant: ShaclGrant,
  login: string,
): Promise<{ bytes: Uint8Array; metadataPull: string | null }> {
  const source = proposal.bundle.source_commit;
  const submodule = await github.siteSubmodule(proposal.repository, source);
  const bytes = serializeShaclReviewBundle(proposal.bundle);
  if (submodule === null) return { bytes, metadataPull: null };
  if (
    proposal.bundle.records.some(
      (record) =>
        !record.source_path.startsWith("site-specific/metadata/records/"),
    )
  ) {
    throw new HttpError(
      422,
      "invalid_site_submodule",
      "A submodule proposal may edit only site-specific metadata records.",
    );
  }
  await github.requireInstallationAccess(proposal.repository);
  await github.requireInstallationAccess(submodule.repository);
  let repository;
  try {
    await github.requireCurator(submodule.repository, login);
    repository = await github.repository(submodule.repository);
  } catch {
    throw new HttpError(
      403,
      "metadata_access_required",
      `Install the GitHub App on ${submodule.repository} and give the signed-in curator write access before retrying.`,
    );
  }
  const base = await github.branchHead(
    submodule.repository,
    repository.defaultBranch,
  );
  if (base.sha !== submodule.sha) {
    throw new HttpError(
      409,
      "stale_metadata_submodule",
      `The deployed site-specific commit is not the current ${submodule.repository} default-branch head. Update the website gitlink and rebuild its editor before proposing.`,
    );
  }
  await requireEmptyHandoffPath(github, submodule.repository, submodule.sha);
  const branch = `curation/shacl-vue-${source.slice(0, 12)}-${grant.handoff_nonce.slice(0, 16)}`;
  // A nonce-derived ref is also the replay gate. Never delete it after an
  // uncertain write: another repository may already refer to its proposal.
  await github.createBranch(submodule.repository, branch, submodule.sha);
  try {
    const head = await github.commitFileAtHead(
      submodule.repository,
      branch,
      submodule.sha,
      SHACL_BUNDLE_PATH,
      bytes,
      COMMIT_HEADLINE,
      commitBody(source),
    );
    const pull = await github.openDraftPullRequest(
      submodule.repository,
      branch,
      repository.defaultBranch,
      head.sha,
      PULL_REQUEST_TITLE,
      `Metadata proposal for https://github.com/${proposal.repository}/commit/${source}. The website's trusted workflow validates the composed result before replacing this temporary bundle.`,
    );
    return {
      metadataPull: pull.url,
      bytes: new TextEncoder().encode(
        JSON.stringify({
          format: "orinoco-shacl-submodule-handoff",
          version: 1,
          bundle: proposal.bundle,
          metadata: {
            repository: submodule.repository,
            source_commit: submodule.sha,
            branch,
            head_sha: head.sha,
            pull_request: pull.number,
          },
        }) + "\n",
      ),
    };
  } catch (error) {
    throw new HttpError(
      502,
      "metadata_handoff_incomplete",
      `Metadata proposal in ${submodule.repository} on refs/heads/${branch} may be incomplete (${failureDiagnostic(error)}). Inspect that branch and its draft pull request before starting another submission.`,
    );
  }
}

async function requireTrustedEditorDeployment(
  github: GitHubClient,
  repository: string,
  baseSha: string,
  grant: ShaclGrant,
  serviceOrigin: string,
  pull: PullRequestCoordinates | null = null,
): Promise<SiteCoordinates> {
  const { coordinates: site } = await loadSiteCoordinates(
    github,
    repository,
    baseSha,
  );
  if (site.reviewServiceOrigin !== serviceOrigin) {
    throw new HttpError(
      403,
      "shacl_transport_mismatch",
      "This repository does not trust the selected review service.",
    );
  }
  if (new URL(site.editorSiteUrl).origin === grant.editor_origin) return site;
  if (pull !== null) {
    const value = await github.commitStatus(repository, pull.headSha);
    if (
      value !== null &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      Array.isArray((value as Record<string, unknown>).statuses)
    ) {
      const statuses = (value as { statuses: unknown[] }).statuses;
      const trusted = statuses.some((item: unknown) => {
        if (item === null || typeof item !== "object" || Array.isArray(item)) {
          return false;
        }
        const status = item as Record<string, unknown>;
        if (
          status.state !== "success" ||
          typeof status.context !== "string" ||
          !/^netlify\/[A-Za-z0-9_.-]+\/deploy-preview$/.test(status.context) ||
          typeof status.target_url !== "string"
        ) {
          return false;
        }
        let target: URL;
        try {
          target = new URL(status.target_url);
        } catch {
          return false;
        }
        const match = /^deploy-preview-(\d+)--[a-z0-9-]+\.netlify\.app$/.exec(
          target.hostname,
        );
        return (
          target.protocol === "https:" &&
          target.origin === grant.editor_origin &&
          target.pathname === "/" &&
          target.search === "" &&
          target.hash === "" &&
          target.username === "" &&
          target.password === "" &&
          target.port === "" &&
          match !== null &&
          Number(match[1]) === pull.number
        );
      });
      if (trusted) return site;
    }
  }
  throw new HttpError(
    403,
    "shacl_transport_mismatch",
    pull === null
      ? "Open the editor from the repository's configured site before proposing."
      : "GitHub does not show a successful Netlify deploy preview for this exact pull-request commit and editor origin.",
  );
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
    const site = await requireTrustedEditorDeployment(
      github,
      proposal.repository,
      pull.baseSha,
      grant,
      serviceOrigin,
      pull,
    );
    validateShaclRecordPaths(proposal.bundle, site.metadataRoots);
    await requireEmptyHandoffPath(github, proposal.repository, pull.headSha);
    const { bytes, metadataPull } = await prepareHandoff(
      github,
      proposal,
      grant,
      user.login,
    );
    let commit;
    try {
      commit = await github.commitFileAtHead(
        proposal.repository,
        pull.branch,
        pull.headSha,
        SHACL_BUNDLE_PATH,
        bytes,
        COMMIT_HEADLINE,
        commitBody(pull.headSha),
      );
    } catch (error) {
      throw new HttpError(
        502,
        "website_handoff_incomplete",
        `Website handoff failed (${failureDiagnostic(error)}). Inspect ${pull.url}${metadataPull ? ` and ${metadataPull}` : ""} before retrying.`,
      );
    }
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
  const site = await requireTrustedEditorDeployment(
    github,
    proposal.repository,
    base.sha,
    grant,
    serviceOrigin,
  );
  validateShaclRecordPaths(proposal.bundle, site.metadataRoots);
  await requireEmptyHandoffPath(github, proposal.repository, base.sha);
  const { bytes, metadataPull } = await prepareHandoff(
    github,
    proposal,
    grant,
    user.login,
  );
  const branch = `curation/shacl-vue-${base.sha.slice(0, 12)}-${grant.handoff_nonce.slice(0, 16)}`;
  try {
    await github.createBranch(proposal.repository, branch, base.sha);
  } catch (error) {
    if (metadataPull !== null)
      throw new HttpError(
        502,
        "website_handoff_incomplete",
        `Metadata draft ${metadataPull} exists, but the website branch could not be created (${failureDiagnostic(error)}). Inspect both repositories before retrying.`,
      );
    throw error;
  }
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
      metadataPull === null
        ? ""
        : `Companion metadata proposal: ${metadataPull}. Merge the metadata proposal before advancing the website gitlink.`,
    );
    return {
      commit_sha: commit.sha,
      commit_url: commit.url,
      pull_request: pull.number,
      pull_request_url: pull.url,
    };
  } catch (error) {
    if (metadataPull !== null)
      throw new HttpError(
        502,
        "website_handoff_incomplete",
        `Metadata draft ${metadataPull} exists, but website proposal refs/heads/${branch} may be incomplete (${failureDiagnostic(error)}). Inspect both repositories before retrying; neither branch was deleted.`,
      );
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
