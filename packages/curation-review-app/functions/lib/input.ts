import { HttpError } from "./http";

const REPOSITORY =
  /^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/;

export interface ReviewTarget {
  pullRequest: number;
  repository: string;
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
  const allowed = new Set(["repository", "pull_request"]);
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
    url.searchParams.getAll("repository").length !== 1 ||
    url.searchParams.getAll("pull_request").length !== 1
  ) {
    throw new HttpError(
      400,
      "invalid_query",
      "Repository and pull request are required once.",
    );
  }
  return {
    repository: parseRepository(url.searchParams.get("repository")),
    pullRequest: parsePullRequest(url.searchParams.get("pull_request")),
  };
}

export function splitRepository(repository: string): [string, string] {
  const separator = repository.indexOf("/");
  return [repository.slice(0, separator), repository.slice(separator + 1)];
}
