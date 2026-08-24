import type {
  CandidateOperation,
  CurationSubmission,
  Disposition,
  JsonObject,
  JsonValue,
  ReviewProposal,
  SubmissionDecision,
} from "../../shared/contracts";
import { MAX_GITHUB_TEXT_LENGTH } from "../../shared/contracts";
import { HttpError, requireExactKeys } from "./http";
import { parseRepository } from "./input";

const COMMIT = /^[0-9a-f]{40}$/;

function line(value: unknown, label: string): string {
  if (
    typeof value !== "string" ||
    !value ||
    value !== value.trim() ||
    /[\r\n\0]/.test(value)
  ) {
    throw new HttpError(400, "invalid_payload", `${label} is invalid.`);
  }
  return value;
}

function sha(value: unknown, label: string): string {
  const result = line(value, label);
  if (!COMMIT.test(result)) {
    throw new HttpError(
      400,
      "invalid_payload",
      `${label} must be a full Git commit.`,
    );
  }
  return result;
}

function jsonValue(value: unknown, label: string): JsonValue {
  try {
    const encoded = JSON.stringify(value);
    if (encoded === undefined) throw new Error("not JSON");
    return JSON.parse(encoded) as JsonValue;
  } catch {
    throw new HttpError(
      400,
      "invalid_payload",
      `${label} is not deterministic JSON.`,
    );
  }
}

function coordinate(value: unknown): JsonObject {
  const copied = jsonValue(value, "source_coordinate");
  if (
    copied === null ||
    typeof copied !== "object" ||
    Array.isArray(copied) ||
    Object.keys(copied).length === 0
  ) {
    throw new HttpError(
      400,
      "invalid_payload",
      "source_coordinate must be a non-empty JSON object.",
    );
  }
  return copied as JsonObject;
}

function disposition(value: unknown): Disposition {
  if (value !== "accept" && value !== "reject" && value !== "defer") {
    throw new HttpError(
      400,
      "invalid_payload",
      "Decision disposition is invalid.",
    );
  }
  return value;
}

function operation(value: unknown): CandidateOperation {
  if (value !== "add" && value !== "modify" && value !== "delete") {
    throw new HttpError(
      400,
      "invalid_payload",
      "Decision operation is invalid.",
    );
  }
  return value;
}

function pullRequest(value: unknown): number {
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < 1 ||
    value > 9_999_999_999
  ) {
    throw new HttpError(
      400,
      "invalid_payload",
      "pull_request must be a positive integer.",
    );
  }
  return value;
}

function decision(value: unknown): SubmissionDecision {
  requireExactKeys(
    value,
    ["disposition", "operation", "pid", "record_path"],
    "decision",
  );
  return {
    disposition: disposition(value.disposition),
    operation: operation(value.operation),
    pid: line(value.pid, "Decision pid"),
    record_path: line(value.record_path, "Decision record_path"),
  };
}

export function parseSubmission(value: unknown): CurationSubmission {
  requireExactKeys(
    value,
    [
      "adapter",
      "decisions",
      "format",
      "head_sha",
      "proposal_sha",
      "pull_request",
      "repository",
      "source_coordinate",
    ],
    "submission",
  );
  if (value.format !== "orinoco-lite-curation-submission-v1") {
    throw new HttpError(
      400,
      "invalid_payload",
      "Submission format is unsupported.",
    );
  }
  if (!Array.isArray(value.decisions) || value.decisions.length === 0) {
    throw new HttpError(
      400,
      "invalid_payload",
      "Submission decisions must be a non-empty array.",
    );
  }
  return {
    adapter: line(value.adapter, "adapter"),
    decisions: value.decisions.map(decision),
    format: "orinoco-lite-curation-submission-v1",
    head_sha: sha(value.head_sha, "head_sha"),
    proposal_sha: sha(value.proposal_sha, "proposal_sha"),
    pull_request: pullRequest(value.pull_request),
    repository: parseRepository(
      typeof value.repository === "string" ? value.repository : null,
    ),
    source_coordinate: coordinate(value.source_coordinate),
  };
}

function canonical(value: JsonValue): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map(
        (key) => `${JSON.stringify(key)}:${canonical(value[key] as JsonValue)}`,
      )
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function verifySubmission(
  submitted: CurationSubmission,
  proposal: ReviewProposal,
): CurationSubmission {
  if (
    submitted.repository.toLowerCase() !== proposal.repository.toLowerCase() ||
    submitted.pull_request !== proposal.pull_request ||
    submitted.proposal_sha !== proposal.proposal_sha ||
    submitted.head_sha !== proposal.head_sha ||
    submitted.adapter !== proposal.adapter ||
    canonical(submitted.source_coordinate) !==
      canonical(proposal.source_coordinate) ||
    submitted.decisions.length !== proposal.candidates.length
  ) {
    throw new HttpError(
      409,
      "stale_submission",
      "The submission no longer matches the current proposal.",
    );
  }
  const byPath = new Map(
    submitted.decisions.map((item) => [item.record_path, item]),
  );
  if (byPath.size !== submitted.decisions.length) {
    throw new HttpError(
      409,
      "stale_submission",
      "The submission does not cover the complete candidate set.",
    );
  }
  const decisions = proposal.candidates.map((candidate) => {
    const item = byPath.get(candidate.record_path);
    if (
      item === undefined ||
      item.pid !== candidate.pid ||
      item.operation !== candidate.operation
    ) {
      throw new HttpError(
        409,
        "stale_submission",
        "The submission does not cover the complete candidate set.",
      );
    }
    return { ...item };
  });
  return {
    adapter: proposal.adapter,
    decisions,
    format: "orinoco-lite-curation-submission-v1",
    head_sha: proposal.head_sha,
    proposal_sha: proposal.proposal_sha,
    pull_request: proposal.pull_request,
    repository: proposal.repository,
    source_coordinate: proposal.source_coordinate,
  };
}

export function submissionComment(value: CurationSubmission): string {
  const body = `/curation submit\n\n\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``;
  if (body.length > MAX_GITHUB_TEXT_LENGTH) {
    throw new HttpError(
      422,
      "submission_too_large",
      "The complete decision comment exceeds GitHub's text limit.",
    );
  }
  return body;
}
