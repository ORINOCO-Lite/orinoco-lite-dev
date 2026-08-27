import { HttpError } from "./http";
import {
  isReviewHandoffNonce,
  isSafeEditorOrigin,
  isSafeReviewOrigin,
  isShaclHandoffNonce,
} from "../../shared/contracts";

const REPOSITORY =
  /^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/;

export interface ReviewTarget {
  artifactId: number;
  pullRequest: number;
  repository: string;
}

export interface ReviewTransportTarget extends ReviewTarget {
  handoffNonce: string;
  reviewOrigin: string;
}

export interface ShaclTransportTarget {
  editorOrigin: string;
  expectedHeadSha: string | null;
  handoffNonce: string;
  pullRequest: number | null;
  repository: string;
}

export function parseArtifactId(value: string | null): number {
  if (value === null || !/^[1-9][0-9]{0,15}$/.test(value)) {
    throw new HttpError(
      400,
      "invalid_artifact_id",
      "Artifact ID must be a positive integer.",
    );
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) {
    throw new HttpError(
      400,
      "invalid_artifact_id",
      "Artifact ID must be a positive integer.",
    );
  }
  return parsed;
}

export function parseRepository(value: string | null): string {
  if (value === null || !REPOSITORY.test(value) || value.includes("..")) {
    throw new HttpError(
      400,
      "invalid_repository",
      "Repository must use the owner/name form.",
    );
  }
  return value;
}

export function parsePullRequest(value: string | null): number {
  if (value === null || !/^[1-9][0-9]{0,9}$/.test(value)) {
    throw new HttpError(
      400,
      "invalid_pull_request",
      "Pull request must be a positive integer.",
    );
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) {
    throw new HttpError(
      400,
      "invalid_pull_request",
      "Pull request must be a positive integer.",
    );
  }
  return parsed;
}

export function reviewTarget(url: URL): ReviewTarget {
  const allowed = new Set(["artifact_id", "repository", "pull_request"]);
  for (const key of url.searchParams.keys()) {
    if (!allowed.has(key)) {
      throw new HttpError(
        400,
        "unexpected_query",
        "The request has an unexpected query field.",
      );
    }
  }
  if (
    url.searchParams.getAll("artifact_id").length !== 1 ||
    url.searchParams.getAll("repository").length !== 1 ||
    url.searchParams.getAll("pull_request").length !== 1
  ) {
    throw new HttpError(
      400,
      "invalid_query",
      "Artifact ID, repository, and pull request are required once.",
    );
  }
  return {
    artifactId: parseArtifactId(url.searchParams.get("artifact_id")),
    repository: parseRepository(url.searchParams.get("repository")),
    pullRequest: parsePullRequest(url.searchParams.get("pull_request")),
  };
}

export function reviewTransportTarget(url: URL): ReviewTransportTarget {
  const allowed = new Set([
    "artifact_id",
    "handoff_nonce",
    "pull_request",
    "repository",
    "review_origin",
  ]);
  if ([...url.searchParams.keys()].some((key) => !allowed.has(key))) {
    throw new HttpError(
      400,
      "unexpected_query",
      "The review transport request has an unexpected query field.",
    );
  }
  if (
    [...allowed].some((key) => url.searchParams.getAll(key).length !== 1) ||
    !isSafeReviewOrigin(url.searchParams.get("review_origin")) ||
    !isReviewHandoffNonce(url.searchParams.get("handoff_nonce"))
  ) {
    throw new HttpError(
      400,
      "invalid_review_transport",
      "The downstream review transport coordinates are invalid.",
    );
  }
  const reviewUrl = new URL(url);
  reviewUrl.searchParams.delete("review_origin");
  reviewUrl.searchParams.delete("handoff_nonce");
  const target = reviewTarget(reviewUrl);
  return {
    ...target,
    handoffNonce: url.searchParams.get("handoff_nonce") as string,
    reviewOrigin: url.searchParams.get("review_origin") as string,
  };
}

export function shaclTransportTarget(url: URL): ShaclTransportTarget {
  const allowed = new Set([
    "editor_origin",
    "expected_head_sha",
    "handoff_nonce",
    "pull_request",
    "repository",
  ]);
  if ([...url.searchParams.keys()].some((key) => !allowed.has(key))) {
    throw new HttpError(
      400,
      "unexpected_query",
      "The SHACL transport request has an unexpected query field.",
    );
  }
  if (
    url.searchParams.getAll("editor_origin").length !== 1 ||
    url.searchParams.getAll("handoff_nonce").length !== 1 ||
    url.searchParams.getAll("repository").length !== 1 ||
    !isSafeEditorOrigin(url.searchParams.get("editor_origin")) ||
    !isShaclHandoffNonce(url.searchParams.get("handoff_nonce"))
  ) {
    throw new HttpError(
      400,
      "invalid_shacl_transport",
      "The downstream SHACL transport coordinates are invalid.",
    );
  }
  const pulls = url.searchParams.getAll("pull_request");
  const heads = url.searchParams.getAll("expected_head_sha");
  if (
    pulls.length > 1 ||
    heads.length > 1 ||
    (pulls.length === 0) !== (heads.length === 0) ||
    (heads.length === 1 && !/^[0-9a-f]{40}$/.test(heads[0] ?? ""))
  ) {
    throw new HttpError(
      400,
      "invalid_shacl_transport",
      "The SHACL pull-request coordinates are invalid.",
    );
  }
  return {
    editorOrigin: url.searchParams.get("editor_origin") as string,
    expectedHeadSha: heads[0] ?? null,
    handoffNonce: url.searchParams.get("handoff_nonce") as string,
    pullRequest: pulls.length === 1 ? parsePullRequest(pulls[0] ?? null) : null,
    repository: parseRepository(url.searchParams.get("repository")),
  };
}

export function splitRepository(repository: string): [string, string] {
  const separator = repository.indexOf("/");
  return [repository.slice(0, separator), repository.slice(separator + 1)];
}
