import type {
  CandidateOperation,
  ReviewProposal,
} from "../../shared/contracts";
import { GitHubClient } from "./github";
import { HttpError } from "./http";
import { parseProposalSummary } from "./summary";

const RECORD_ROOT = "metadata/records/";
const ANNOTATION_ROOT = "metadata/overlays/annotations/";
const COMMIT = /^[0-9a-f]{40}$/;

export { MAX_REVIEW_CANDIDATES } from "./summary";

function object(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(
      502,
      "github_error",
      `GitHub returned an invalid ${label}.`,
    );
  }
  return value as Record<string, unknown>;
}

function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value || /[\r\n\0]/.test(value)) {
    throw new HttpError(
      502,
      "github_error",
      `GitHub returned an invalid ${label}.`,
    );
  }
  return value;
}

function commit(value: unknown, label: string): string {
  const result = text(value, label);
  if (!COMMIT.test(result)) {
    throw new HttpError(
      502,
      "github_error",
      `GitHub returned an invalid ${label}.`,
    );
  }
  return result;
}

function operation(status: unknown): CandidateOperation {
  if (status === "added") return "add";
  if (status === "modified") return "modify";
  if (status === "removed") return "delete";
  throw new HttpError(
    422,
    "invalid_proposal",
    "Proposal record files must be added, modified, or removed.",
  );
}

interface PullCoordinates {
  body: string;
  headSha: string;
  repository: string;
  url: string;
}

function pullCoordinates(
  value: unknown,
  requestedRepository: string,
  requestedNumber: number,
): PullCoordinates {
  const pull = object(value, "pull request");
  if (pull.number !== requestedNumber || pull.state !== "open") {
    throw new HttpError(
      422,
      "invalid_proposal",
      "The requested pull request is not an open review.",
    );
  }
  const base = object(pull.base, "pull-request base");
  const head = object(pull.head, "pull-request head");
  const baseRepo = object(base.repo, "base repository");
  const repository = text(baseRepo.full_name, "base repository name");
  if (repository.toLowerCase() !== requestedRepository.toLowerCase()) {
    throw new HttpError(
      422,
      "invalid_proposal",
      "The pull request belongs to a different repository.",
    );
  }
  if (typeof pull.body !== "string") {
    throw new HttpError(
      422,
      "invalid_proposal",
      "The pull request has no curation summary.",
    );
  }
  return {
    body: pull.body,
    headSha: commit(head.sha, "head SHA"),
    repository,
    url: text(pull.html_url, "pull-request URL"),
  };
}

interface ProposalCommitCoordinates {
  baseSha: string;
  proposalSha: string;
}

function proposalCommit(value: unknown): ProposalCommitCoordinates {
  const item = object(value, "proposal commit");
  const proposalSha = commit(item.sha, "proposal SHA");
  if (!Array.isArray(item.parents) || item.parents.length !== 1) {
    throw new HttpError(
      422,
      "invalid_proposal",
      "The proposal commit must have exactly one parent.",
    );
  }
  const parent = object(item.parents[0], "proposal parent");
  return {
    baseSha: commit(parent.sha, "proposal parent SHA"),
    proposalSha,
  };
}

interface ProposalFiles {
  changedPaths: Set<string>;
  records: Map<string, CandidateOperation>;
}

function proposalFiles(value: Record<string, unknown>): ProposalFiles {
  if (!Array.isArray(value.files)) {
    throw new HttpError(
      502,
      "github_error",
      "GitHub omitted the proposal files.",
    );
  }
  const records = new Map<string, CandidateOperation>();
  const changedPaths = new Set<string>();
  for (const fileValue of value.files) {
    const file = object(fileValue, "proposal file");
    const filename = text(file.filename, "proposal filename");
    if (
      !filename.startsWith(RECORD_ROOT) &&
      !filename.startsWith(ANNOTATION_ROOT)
    ) {
      throw new HttpError(
        422,
        "invalid_proposal",
        "The proposal commit changes a path outside the metadata roots.",
      );
    }
    if (file.previous_filename !== undefined || changedPaths.has(filename)) {
      throw new HttpError(
        422,
        "invalid_proposal",
        "Metadata renames and repeated paths are not supported.",
      );
    }
    const fileOperation = operation(file.status);
    changedPaths.add(filename);
    if (filename.startsWith(RECORD_ROOT)) {
      records.set(filename, fileOperation);
    }
  }
  if (records.size === 0) {
    throw new HttpError(
      422,
      "invalid_proposal",
      "The proposal commit changes no metadata records.",
    );
  }
  return { changedPaths, records };
}

export async function loadReviewProposal(
  github: GitHubClient,
  repository: string,
  pullRequest: number,
): Promise<ReviewProposal> {
  const pull = pullCoordinates(
    await github.pullRequest(repository, pullRequest),
    repository,
    pullRequest,
  );
  const first = await github.firstPullRequestCommit(repository, pullRequest);
  const proposalCoordinates = proposalCommit(first);
  const proposalSha = proposalCoordinates.proposalSha;
  const summary = parseProposalSummary(pull.body);
  if (summary.proposal_sha !== proposalSha) {
    throw new HttpError(
      422,
      "invalid_proposal",
      "The visible summary names a different proposal commit.",
    );
  }
  const proposal = await github.commit(
    repository,
    proposalSha,
    summary.candidates.length * 2,
  );
  const files = proposalFiles(proposal);
  if (files.records.size !== summary.candidates.length) {
    throw new HttpError(
      422,
      "invalid_proposal",
      "The visible summary does not cover every changed record.",
    );
  }

  const allowedPaths = new Set(
    summary.candidates.flatMap((candidate) => [
      candidate.record_path,
      `${ANNOTATION_ROOT}${candidate.record_path.slice(RECORD_ROOT.length)}`,
    ]),
  );
  if ([...files.changedPaths].some((path) => !allowedPaths.has(path))) {
    throw new HttpError(
      422,
      "invalid_proposal",
      "The proposal changes metadata outside the candidate record companions.",
    );
  }

  const requests = summary.candidates.flatMap((candidate, index) => {
    const actualOperation = files.records.get(candidate.record_path);
    if (
      actualOperation === undefined ||
      actualOperation !== candidate.operation
    ) {
      throw new HttpError(
        422,
        "invalid_proposal",
        "A summary candidate does not match the proposal diff.",
      );
    }
    return [
      {
        key: `before:${index}`,
        path: candidate.record_path,
        ref: proposalCoordinates.baseSha,
      },
      { key: `after:${index}`, path: candidate.record_path, ref: pull.headSha },
    ];
  });
  const contents = await github.contents(repository, requests);
  const candidates = summary.candidates.map((candidate, index) => {
    const before = contents.get(`before:${index}`) ?? null;
    const current = contents.get(`after:${index}`) ?? null;
    if (
      (candidate.operation === "add" && before !== null) ||
      ((candidate.operation === "modify" || candidate.operation === "delete") &&
        before === null)
    ) {
      throw new HttpError(
        422,
        "invalid_proposal",
        "A candidate's baseline content does not match its operation.",
      );
    }
    return { ...candidate, after: current, before };
  });

  return {
    adapter: summary.adapter,
    candidates,
    head_sha: pull.headSha,
    proposal_sha: proposalSha,
    pull_request: pullRequest,
    pull_request_url: pull.url,
    repository: pull.repository,
    source_coordinate: summary.source_coordinate,
  };
}
