import { HttpError } from "./http";
import { splitRepository } from "./input";

const GITHUB_API = "https://api.github.com";
const API_VERSION = "2022-11-28";
const MAX_RECORD_BYTES = 1_048_576;
const MAX_REVIEW_BYTES = 16_777_216;
const BLOBS_PER_QUERY = 20;

export interface ContentRequest {
  key: string;
  path: string;
  ref: string;
}

export type FetchImplementation = typeof fetch;

function endpoint(repository: string, suffix: string): string {
  const [owner, name] = splitRepository(repository);
  return `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}${suffix}`;
}

function apiUrl(path: string): string {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new Error("GitHub API paths must be absolute paths");
  }
  return `${GITHUB_API}${path}`;
}

function githubError(status: number): HttpError {
  if (status === 401) {
    return new HttpError(
      401,
      "authentication_required",
      "Sign in with GitHub to continue.",
    );
  }
  if (status === 403) {
    return new HttpError(
      403,
      "github_forbidden",
      "GitHub did not authorize this request.",
    );
  }
  if (status === 404) {
    return new HttpError(
      404,
      "github_not_found",
      "The requested GitHub resource was not found.",
    );
  }
  if (status === 422) {
    return new HttpError(
      422,
      "github_rejected",
      "GitHub rejected the request.",
    );
  }
  return new HttpError(
    502,
    "github_error",
    "GitHub could not complete the request.",
  );
}

export class GitHubClient {
  readonly #fetch: FetchImplementation;
  readonly #token: string;

  constructor(token: string, fetchImplementation: FetchImplementation = fetch) {
    this.#token = token;
    this.#fetch = fetchImplementation;
  }

  async #request(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/vnd.github+json");
    headers.set("Authorization", `Bearer ${this.#token}`);
    headers.set("X-GitHub-Api-Version", API_VERSION);
    const response = await this.#fetch(apiUrl(path), {
      ...init,
      headers,
      redirect: "error",
    });
    if (!response.ok) throw githubError(response.status);
    return response;
  }

  async json(path: string, init: RequestInit = {}): Promise<unknown> {
    const response = await this.#request(path, init);
    try {
      return (await response.json()) as unknown;
    } catch {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned malformed JSON.",
      );
    }
  }

  async currentUser(): Promise<{ id: number; login: string }> {
    const value = await this.json("/user");
    if (
      value === null ||
      typeof value !== "object" ||
      Array.isArray(value) ||
      typeof (value as Record<string, unknown>).login !== "string" ||
      !Number.isSafeInteger((value as Record<string, unknown>).id)
    ) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned an invalid user.",
      );
    }
    return {
      id: Number((value as Record<string, unknown>).id),
      login: String((value as Record<string, unknown>).login),
    };
  }

  async requireCurator(repository: string, login: string): Promise<void> {
    const value = await this.json(
      endpoint(
        repository,
        `/collaborators/${encodeURIComponent(login)}/permission`,
      ),
    );
    const permission =
      value !== null && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>).permission
        : null;
    if (permission !== "write" && permission !== "admin") {
      throw new HttpError(
        403,
        "curator_permission_required",
        "Repository write or admin permission is required.",
      );
    }
  }

  async pullRequest(repository: string, number: number): Promise<unknown> {
    return this.json(endpoint(repository, `/pulls/${number}`));
  }

  async firstPullRequestCommit(
    repository: string,
    number: number,
  ): Promise<unknown> {
    const value = await this.json(
      endpoint(repository, `/pulls/${number}/commits?per_page=1&page=1`),
    );
    if (!Array.isArray(value) || value.length !== 1) {
      throw new HttpError(
        422,
        "invalid_proposal",
        "The pull request commit list is invalid.",
      );
    }
    return value[0];
  }

  async commit(
    repository: string,
    sha: string,
    maximumFiles: number,
  ): Promise<Record<string, unknown>> {
    if (
      !Number.isSafeInteger(maximumFiles) ||
      maximumFiles < 1 ||
      maximumFiles > 700
    ) {
      throw new HttpError(
        500,
        "invalid_commit_limit",
        "The proposal file limit is invalid.",
      );
    }
    let first: Record<string, unknown> | null = null;
    const files: unknown[] = [];
    const pages = Math.floor(maximumFiles / 100) + 1;
    for (let page = 1; page <= pages; page += 1) {
      const value = await this.json(
        endpoint(repository, `/commits/${sha}?per_page=100&page=${page}`),
      );
      if (value === null || typeof value !== "object" || Array.isArray(value)) {
        throw new HttpError(
          502,
          "github_error",
          "GitHub returned an invalid commit.",
        );
      }
      const record = value as Record<string, unknown>;
      const pageFiles = record.files;
      if (!Array.isArray(pageFiles)) {
        throw new HttpError(
          502,
          "github_error",
          "GitHub omitted the proposal files.",
        );
      }
      if (first === null) first = record;
      files.push(...pageFiles);
      if (files.length > maximumFiles) {
        throw new HttpError(
          422,
          "proposal_too_large",
          "The proposal changes too many files.",
        );
      }
      if (pageFiles.length < 100) break;
      if (page === pages) {
        throw new HttpError(
          422,
          "proposal_too_large",
          "The proposal changes too many files.",
        );
      }
    }
    if (first === null) throw new Error("commit pagination did not execute");
    return { ...first, files };
  }

  async contents(
    repository: string,
    requests: readonly ContentRequest[],
  ): Promise<Map<string, string | null>> {
    const [owner, name] = splitRepository(repository);
    const result = new Map<string, string | null>();
    let totalBytes = 0;
    for (let offset = 0; offset < requests.length; offset += BLOBS_PER_QUERY) {
      const batch = requests.slice(offset, offset + BLOBS_PER_QUERY);
      const variables: Record<string, string> = { name, owner };
      const declarations = ["$owner: String!", "$name: String!"];
      const fields: string[] = [];
      batch.forEach((request, index) => {
        if (
          !request.key ||
          result.has(request.key) ||
          batch.slice(0, index).some((item) => item.key === request.key)
        ) {
          throw new HttpError(
            500,
            "invalid_content_request",
            "Record-content request keys must be unique.",
          );
        }
        const variable = `expression${index}`;
        variables[variable] = `${request.ref}:${request.path}`;
        declarations.push(`$${variable}: String!`);
        fields.push(
          `blob${index}: object(expression: $${variable}) { __typename ... on Blob { byteSize isBinary isTruncated text } }`,
        );
      });
      const value = await this.json("/graphql", {
        body: JSON.stringify({
          query: `query ReviewRecords(${declarations.join(", ")}) { repository(owner: $owner, name: $name) { ${fields.join(" ")} } }`,
          variables,
        }),
        headers: { "Content-Type": "application/json; charset=utf-8" },
        method: "POST",
      });
      if (value === null || typeof value !== "object" || Array.isArray(value)) {
        throw new HttpError(
          502,
          "github_error",
          "GitHub returned invalid GraphQL data.",
        );
      }
      const envelope = value as Record<string, unknown>;
      if (Array.isArray(envelope.errors) && envelope.errors.length > 0) {
        throw new HttpError(
          502,
          "github_error",
          "GitHub could not load the proposal records.",
        );
      }
      const data = envelope.data;
      const repositoryData =
        data !== null && typeof data === "object" && !Array.isArray(data)
          ? (data as Record<string, unknown>).repository
          : null;
      if (
        repositoryData === null ||
        typeof repositoryData !== "object" ||
        Array.isArray(repositoryData)
      ) {
        throw new HttpError(
          502,
          "github_error",
          "GitHub returned an invalid repository response.",
        );
      }
      const blobs = repositoryData as Record<string, unknown>;
      batch.forEach((request, index) => {
        const raw = blobs[`blob${index}`];
        if (raw === null) {
          result.set(request.key, null);
          return;
        }
        if (
          raw === undefined ||
          typeof raw !== "object" ||
          Array.isArray(raw)
        ) {
          throw new HttpError(
            502,
            "github_error",
            "GitHub returned invalid record content.",
          );
        }
        const blob = raw as Record<string, unknown>;
        if (
          blob.__typename !== "Blob" ||
          !Number.isSafeInteger(blob.byteSize) ||
          Number(blob.byteSize) < 0 ||
          Number(blob.byteSize) > MAX_RECORD_BYTES ||
          blob.isBinary !== false ||
          blob.isTruncated !== false ||
          typeof blob.text !== "string"
        ) {
          throw new HttpError(
            422,
            "record_too_large",
            "A metadata record is binary, truncated, or too large to review.",
          );
        }
        const observedBytes = new TextEncoder().encode(blob.text).byteLength;
        if (observedBytes !== Number(blob.byteSize)) {
          throw new HttpError(
            502,
            "github_error",
            "GitHub returned inconsistent record content.",
          );
        }
        totalBytes += observedBytes;
        if (totalBytes > MAX_REVIEW_BYTES) {
          throw new HttpError(
            422,
            "proposal_too_large",
            "The proposal contains too much record content to review safely.",
          );
        }
        result.set(request.key, blob.text);
      });
    }
    return result;
  }

  async postComment(
    repository: string,
    number: number,
    body: string,
  ): Promise<string> {
    const value = await this.json(
      endpoint(repository, `/issues/${number}/comments`),
      {
        body: JSON.stringify({ body }),
        headers: { "Content-Type": "application/json; charset=utf-8" },
        method: "POST",
      },
    );
    const url =
      value !== null && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>).html_url
        : null;
    let parsed: URL | null = null;
    try {
      if (typeof url === "string") parsed = new URL(url);
    } catch {
      parsed = null;
    }
    const [owner, name] = splitRepository(repository);
    const parts = parsed?.pathname.split("/").filter(Boolean) ?? [];
    if (
      typeof url !== "string" ||
      parsed === null ||
      parsed.protocol !== "https:" ||
      parsed.hostname !== "github.com" ||
      parsed.username !== "" ||
      parsed.password !== "" ||
      parsed.port !== "" ||
      parsed.search !== "" ||
      parts.length !== 4 ||
      parts[0]?.toLowerCase() !== owner.toLowerCase() ||
      parts[1]?.toLowerCase() !== name.toLowerCase() ||
      (parts[2] !== "pull" && parts[2] !== "issues") ||
      parts[3] !== String(number) ||
      !/^#issuecomment-[1-9][0-9]*$/.test(parsed.hash)
    ) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned an invalid comment.",
      );
    }
    return url;
  }
}
