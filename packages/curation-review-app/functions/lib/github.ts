import { HttpError } from "./http";
import { parseRepository, splitRepository } from "./input";
import { MAX_ARTIFACT_ARCHIVE_BYTES, MAX_REVIEW_PATHS } from "./bundle";
import { base64Encode } from "./encoding";
import type {
  DiscoveryArtifact,
  DiscoveryPullRequest,
} from "../../shared/contracts";

const GITHUB_API = "https://api.github.com";
const API_VERSION = "2022-11-28";
const MAX_RECORD_BYTES = 1_048_576;
const MAX_REVIEW_BYTES = 16_777_216;
const BLOBS_PER_QUERY = 20;
const MAX_DISCOVERY_PULL_REQUESTS = 20;
const MAX_DISCOVERY_ARTIFACTS = 100;
const CURATION_REVIEW_LABEL = "curation-review";
const COMMIT_SHA = /^[0-9a-f]{40}$/;
const GITHUB_TIMESTAMP =
  /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$/;

export interface ContentRequest {
  key: string;
  path: string;
  ref: string;
}

export interface ExactCommitResult {
  sha: string;
  url: string;
}

export interface RepositoryCoordinates {
  defaultBranch: string;
  fullName: string;
}

export interface BranchCoordinates {
  name: string;
  sha: string;
}

export interface DraftPullRequestResult {
  number: number;
  url: string;
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

function validBranchName(value: string): boolean {
  if (
    !value ||
    value.length > 255 ||
    value === "@" ||
    value.startsWith("refs/") ||
    /[~^:?*\[\\\s\0]/.test(value) ||
    value.includes("..") ||
    value.includes("@{") ||
    value.endsWith(".")
  ) {
    return false;
  }
  return value
    .split("/")
    .every(
      (part) =>
        part.length > 0 && !part.startsWith(".") && !part.endsWith(".lock"),
    );
}

function validCommitPath(value: string): boolean {
  return (
    value.length > 0 &&
    value.length <= 4_096 &&
    !value.startsWith("/") &&
    !/[\\\r\n\0]/.test(value) &&
    value
      .split("/")
      .every((part) => part.length > 0 && part !== "." && part !== "..")
  );
}

function objectRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function nestedRepositoryName(value: unknown): string | null {
  const container = objectRecord(value);
  const repository = objectRecord(container?.repo);
  return typeof repository?.full_name === "string"
    ? repository.full_name
    : null;
}

function githubTimestamp(value: unknown): string | null {
  if (typeof value !== "string" || !GITHUB_TIMESTAMP.test(value)) return null;
  return Number.isFinite(Date.parse(value)) ? value : null;
}

function invalidDiscoveryResponse(message: string): never {
  throw new HttpError(502, "github_error", message);
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

function artifactStorageUrl(value: string | null): URL {
  let result: URL;
  try {
    result = new URL(value ?? "");
  } catch {
    throw new HttpError(
      502,
      "github_error",
      "GitHub returned an invalid artifact download URL.",
    );
  }
  const allowedHost =
    result.hostname.endsWith(".actions.githubusercontent.com") ||
    result.hostname.endsWith(".blob.core.windows.net") ||
    result.hostname.endsWith(".githubusercontent.com");
  if (
    result.protocol !== "https:" ||
    !allowedHost ||
    result.username !== "" ||
    result.password !== "" ||
    result.port !== "" ||
    result.hash !== ""
  ) {
    throw new HttpError(
      502,
      "github_error",
      "GitHub returned an invalid artifact download URL.",
    );
  }
  return result;
}

export class GitHubClient {
  readonly #fetch: FetchImplementation;
  readonly #token: string;

  constructor(token: string, fetchImplementation: FetchImplementation = fetch) {
    this.#token = token;
    this.#fetch = (input, init) => fetchImplementation(input, init);
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

  async discoverReviewPullRequests(
    repository: string,
  ): Promise<DiscoveryPullRequest[]> {
    parseRepository(repository);
    const requestedRepository = repository.toLowerCase();
    const value = await this.json(
      endpoint(
        repository,
        "/pulls?state=open&sort=updated&direction=desc&per_page=100&page=1",
      ),
    );
    if (!Array.isArray(value)) {
      return invalidDiscoveryResponse(
        "GitHub returned an invalid pull-request listing.",
      );
    }

    const relevant = value
      .filter((item): item is Record<string, unknown> => {
        const pullRequest = objectRecord(item);
        if (pullRequest === null) {
          return invalidDiscoveryResponse(
            "GitHub returned an invalid pull request.",
          );
        }
        if (pullRequest.state !== "open") return false;
        const baseRepository = nestedRepositoryName(pullRequest.base);
        const headRepository = nestedRepositoryName(pullRequest.head);
        if (
          baseRepository?.toLowerCase() !== requestedRepository ||
          headRepository?.toLowerCase() !== requestedRepository
        ) {
          return false;
        }
        if (!Array.isArray(pullRequest.labels)) {
          return invalidDiscoveryResponse(
            "GitHub returned invalid pull-request labels.",
          );
        }
        return pullRequest.labels.some(
          (label) => objectRecord(label)?.name === CURATION_REVIEW_LABEL,
        );
      })
      .sort((left, right) => Number(right.number) - Number(left.number))
      .slice(0, MAX_DISCOVERY_PULL_REQUESTS);

    return Promise.all(
      relevant.map(async (pullRequest): Promise<DiscoveryPullRequest> => {
        const head = objectRecord(pullRequest.head);
        if (
          !Number.isSafeInteger(pullRequest.number) ||
          Number(pullRequest.number) < 1 ||
          typeof pullRequest.draft !== "boolean" ||
          typeof pullRequest.title !== "string" ||
          pullRequest.title.length < 1 ||
          pullRequest.title.length > 256 ||
          /[\r\n\0]/.test(pullRequest.title) ||
          typeof head?.sha !== "string" ||
          !COMMIT_SHA.test(head.sha)
        ) {
          return invalidDiscoveryResponse(
            "GitHub returned invalid pull-request coordinates.",
          );
        }
        const number = Number(pullRequest.number);
        const firstCommit = objectRecord(
          await this.firstPullRequestCommit(repository, number),
        );
        if (
          firstCommit === null ||
          typeof firstCommit.sha !== "string" ||
          !COMMIT_SHA.test(firstCommit.sha)
        ) {
          return invalidDiscoveryResponse(
            "GitHub returned an invalid proposal commit.",
          );
        }
        const proposalSha = firstCommit.sha;
        const artifactName = `orinoco-curation-review-${proposalSha}`;
        const artifactListing = objectRecord(
          await this.json(
            endpoint(
              repository,
              `/actions/artifacts?name=${encodeURIComponent(artifactName)}&per_page=${MAX_DISCOVERY_ARTIFACTS}&page=1`,
            ),
          ),
        );
        if (
          artifactListing === null ||
          !Number.isSafeInteger(artifactListing.total_count) ||
          Number(artifactListing.total_count) < 0 ||
          Number(artifactListing.total_count) > MAX_DISCOVERY_ARTIFACTS ||
          !Array.isArray(artifactListing.artifacts) ||
          artifactListing.artifacts.length > MAX_DISCOVERY_ARTIFACTS ||
          artifactListing.artifacts.length !==
            Number(artifactListing.total_count)
        ) {
          return invalidDiscoveryResponse(
            "GitHub returned an invalid artifact listing.",
          );
        }
        const artifacts: DiscoveryArtifact[] = [];
        for (const item of artifactListing.artifacts) {
          const artifact = objectRecord(item);
          if (artifact?.name !== artifactName) continue;
          const createdAt = githubTimestamp(artifact.created_at);
          const expiresAt = githubTimestamp(artifact.expires_at);
          if (
            !Number.isSafeInteger(artifact.id) ||
            Number(artifact.id) < 1 ||
            typeof artifact.expired !== "boolean" ||
            createdAt === null ||
            expiresAt === null ||
            Date.parse(createdAt) > Date.parse(expiresAt)
          ) {
            return invalidDiscoveryResponse(
              "GitHub returned invalid artifact coordinates.",
            );
          }
          if (artifact.expired || Date.parse(expiresAt) <= Date.now()) continue;
          artifacts.push({
            created_at: createdAt,
            expires_at: expiresAt,
            id: Number(artifact.id),
            name: artifactName,
          });
        }
        artifacts.sort(
          (left, right) =>
            Date.parse(right.created_at) - Date.parse(left.created_at) ||
            right.id - left.id,
        );
        return {
          artifacts,
          draft: pullRequest.draft,
          head_sha: head.sha,
          number,
          proposal_sha: proposalSha,
          title: pullRequest.title,
        };
      }),
    );
  }

  async repository(repository: string): Promise<RepositoryCoordinates> {
    parseRepository(repository);
    const value = await this.json(endpoint(repository, ""));
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned an invalid repository.",
      );
    }
    const record = value as Record<string, unknown>;
    if (
      typeof record.full_name !== "string" ||
      record.full_name.toLowerCase() !== repository.toLowerCase() ||
      typeof record.default_branch !== "string" ||
      !validBranchName(record.default_branch)
    ) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid repository coordinates.",
      );
    }
    return {
      defaultBranch: record.default_branch,
      fullName: record.full_name,
    };
  }

  async branchHead(
    repository: string,
    branch: string,
  ): Promise<BranchCoordinates> {
    if (!validBranchName(branch)) {
      throw new HttpError(
        422,
        "invalid_branch",
        "The GitHub branch is invalid.",
      );
    }
    const value = await this.json(
      endpoint(repository, `/branches/${encodeURIComponent(branch)}`),
    );
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned an invalid branch.",
      );
    }
    const record = value as Record<string, unknown>;
    const commit =
      record.commit !== null &&
      typeof record.commit === "object" &&
      !Array.isArray(record.commit)
        ? (record.commit as Record<string, unknown>)
        : null;
    if (
      record.name !== branch ||
      typeof commit?.sha !== "string" ||
      !/^[0-9a-f]{40}$/.test(commit.sha)
    ) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid branch coordinates.",
      );
    }
    return { name: branch, sha: commit.sha };
  }

  async pathExists(
    repository: string,
    ref: string,
    path: string,
  ): Promise<boolean> {
    parseRepository(repository);
    if (!/^[0-9a-f]{40}$/.test(ref) || !validCommitPath(path)) {
      throw new HttpError(
        422,
        "invalid_content_request",
        "The GitHub content coordinates are invalid.",
      );
    }
    const [owner, name] = splitRepository(repository);
    const value = await this.json("/graphql", {
      body: JSON.stringify({
        query:
          "query ExactPath($owner: String!, $name: String!, $expression: String!) { repository(owner: $owner, name: $name) { object(expression: $expression) { __typename } } }",
        variables: { expression: `${ref}:${path}`, name, owner },
      }),
      headers: { "Content-Type": "application/json; charset=utf-8" },
      method: "POST",
    });
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid path data.",
      );
    }
    const envelope = value as Record<string, unknown>;
    if (Array.isArray(envelope.errors) && envelope.errors.length > 0) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub could not inspect the exact bundle path.",
      );
    }
    const data =
      envelope.data !== null &&
      typeof envelope.data === "object" &&
      !Array.isArray(envelope.data)
        ? (envelope.data as Record<string, unknown>)
        : null;
    const repositoryData =
      data?.repository !== null &&
      typeof data?.repository === "object" &&
      !Array.isArray(data.repository)
        ? (data.repository as Record<string, unknown>)
        : null;
    if (repositoryData === null || !("object" in repositoryData)) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid path data.",
      );
    }
    const object = repositoryData.object;
    if (object === null) return false;
    if (
      typeof object !== "object" ||
      Array.isArray(object) ||
      typeof (object as Record<string, unknown>).__typename !== "string"
    ) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid path data.",
      );
    }
    return true;
  }

  async createBranch(
    repository: string,
    branch: string,
    sha: string,
  ): Promise<BranchCoordinates> {
    parseRepository(repository);
    if (!validBranchName(branch) || !/^[0-9a-f]{40}$/.test(sha)) {
      throw new HttpError(
        422,
        "invalid_branch",
        "The GitHub branch coordinates are invalid.",
      );
    }
    const value = await this.json(endpoint(repository, "/git/refs"), {
      body: JSON.stringify({ ref: `refs/heads/${branch}`, sha }),
      headers: { "Content-Type": "application/json; charset=utf-8" },
      method: "POST",
    });
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid branch data.",
      );
    }
    const record = value as Record<string, unknown>;
    const object =
      record.object !== null &&
      typeof record.object === "object" &&
      !Array.isArray(record.object)
        ? (record.object as Record<string, unknown>)
        : null;
    if (
      record.ref !== `refs/heads/${branch}` ||
      object?.type !== "commit" ||
      object.sha !== sha
    ) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid branch data.",
      );
    }
    return { name: branch, sha };
  }

  async deleteBranch(repository: string, branch: string): Promise<void> {
    parseRepository(repository);
    if (!validBranchName(branch)) {
      throw new HttpError(
        422,
        "invalid_branch",
        "The GitHub branch is invalid.",
      );
    }
    const encoded = branch
      .split("/")
      .map((part) => encodeURIComponent(part))
      .join("/");
    await this.#request(endpoint(repository, `/git/refs/heads/${encoded}`), {
      method: "DELETE",
    });
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

  async artifactMetadata(
    repository: string,
    artifactId: number,
  ): Promise<unknown> {
    return this.json(endpoint(repository, `/actions/artifacts/${artifactId}`));
  }

  async workflowRun(repository: string, runId: number): Promise<unknown> {
    return this.json(endpoint(repository, `/actions/runs/${runId}`));
  }

  async artifactArchive(
    repository: string,
    artifactId: number,
  ): Promise<Uint8Array> {
    const headers = new Headers({
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${this.#token}`,
      "X-GitHub-Api-Version": API_VERSION,
    });
    const redirect = await this.#fetch(
      apiUrl(endpoint(repository, `/actions/artifacts/${artifactId}/zip`)),
      { headers, redirect: "manual" },
    );
    if (redirect.status !== 302) {
      if (!redirect.ok) throw githubError(redirect.status);
      throw new HttpError(
        502,
        "github_error",
        "GitHub did not return an artifact download redirect.",
      );
    }
    const download = await this.#fetch(
      artifactStorageUrl(redirect.headers.get("location")),
      { redirect: "error" },
    );
    if (!download.ok) throw githubError(download.status);
    const contentLength = download.headers.get("content-length");
    if (
      contentLength !== null &&
      (!/^(?:0|[1-9][0-9]*)$/.test(contentLength) ||
        Number(contentLength) > MAX_ARTIFACT_ARCHIVE_BYTES)
    ) {
      throw new HttpError(
        422,
        "artifact_too_large",
        "The review artifact ZIP exceeds the compressed size limit.",
      );
    }
    if (download.body === null) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned an empty artifact response.",
      );
    }
    const reader = download.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_ARTIFACT_ARCHIVE_BYTES) {
        await reader.cancel();
        throw new HttpError(
          422,
          "artifact_too_large",
          "The review artifact ZIP exceeds the compressed size limit.",
        );
      }
      chunks.push(value);
    }
    const result = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return result;
  }

  async commit(
    repository: string,
    sha: string,
    maximumFiles: number = MAX_REVIEW_PATHS,
  ): Promise<Record<string, unknown>> {
    if (
      !Number.isSafeInteger(maximumFiles) ||
      maximumFiles < 1 ||
      maximumFiles > MAX_REVIEW_PATHS
    ) {
      throw new HttpError(
        500,
        "invalid_commit_limit",
        "The proposal path limit is invalid.",
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
      if (!Array.isArray(record.files)) {
        throw new HttpError(
          502,
          "github_error",
          "GitHub omitted the proposal files.",
        );
      }
      if (first === null) first = record;
      files.push(...record.files);
      if (files.length > maximumFiles) {
        throw new HttpError(
          422,
          "proposal_too_large",
          "The proposal changes too many metadata paths for this service.",
        );
      }
      if (record.files.length < 100) break;
      if (page === pages) {
        throw new HttpError(
          422,
          "proposal_too_large",
          "The proposal changes too many metadata paths for this service.",
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

  async commitFileAtHead(
    repository: string,
    branch: string,
    expectedHeadSha: string,
    path: string,
    content: Uint8Array,
    headline: string,
    body?: string,
  ): Promise<ExactCommitResult> {
    parseRepository(repository);
    if (
      !/^[0-9a-f]{40}$/.test(expectedHeadSha) ||
      !validBranchName(branch) ||
      !validCommitPath(path) ||
      !(
        ArrayBuffer.isView(content) &&
        Object.prototype.toString.call(content) === "[object Uint8Array]"
      ) ||
      content.byteLength === 0 ||
      content.byteLength > 10 * 1024 * 1024 ||
      !headline ||
      headline.length > 256 ||
      /[\r\n\0]/.test(headline) ||
      (body !== undefined && (body.length > 65_536 || /[\r\0]/.test(body)))
    ) {
      throw new HttpError(
        422,
        "invalid_commit_request",
        "The exact-head file commit request is invalid.",
      );
    }
    const message: { body?: string; headline: string } = { headline };
    if (body !== undefined && body !== "") message.body = body;
    const value = await this.json("/graphql", {
      body: JSON.stringify({
        query: `mutation CreateExactFileCommit($input: CreateCommitOnBranchInput!) { createCommitOnBranch(input: $input) { commit { oid url } ref { name prefix target { oid } } } }`,
        variables: {
          input: {
            branch: {
              branchName: branch,
              repositoryNameWithOwner: repository,
            },
            expectedHeadOid: expectedHeadSha,
            fileChanges: {
              additions: [{ contents: base64Encode(content), path }],
            },
            message,
          },
        },
      }),
      headers: { "Content-Type": "application/json; charset=utf-8" },
      method: "POST",
    });
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid commit data.",
      );
    }
    const envelope = value as Record<string, unknown>;
    if (Array.isArray(envelope.errors) && envelope.errors.length > 0) {
      throw new HttpError(
        409,
        "commit_rejected",
        "GitHub did not create the commit at the expected branch head.",
      );
    }
    const data =
      envelope.data !== null &&
      typeof envelope.data === "object" &&
      !Array.isArray(envelope.data)
        ? (envelope.data as Record<string, unknown>)
        : null;
    const payload =
      data?.createCommitOnBranch !== null &&
      typeof data?.createCommitOnBranch === "object" &&
      !Array.isArray(data.createCommitOnBranch)
        ? (data.createCommitOnBranch as Record<string, unknown>)
        : null;
    const commit =
      payload?.commit !== null &&
      typeof payload?.commit === "object" &&
      !Array.isArray(payload.commit)
        ? (payload.commit as Record<string, unknown>)
        : null;
    const ref =
      payload?.ref !== null &&
      typeof payload?.ref === "object" &&
      !Array.isArray(payload.ref)
        ? (payload.ref as Record<string, unknown>)
        : null;
    const target =
      ref?.target !== null &&
      typeof ref?.target === "object" &&
      !Array.isArray(ref.target)
        ? (ref.target as Record<string, unknown>)
        : null;
    const sha = commit?.oid;
    const url = commit?.url;
    if (
      typeof sha !== "string" ||
      !/^[0-9a-f]{40}$/.test(sha) ||
      target?.oid !== sha ||
      ref?.name !== branch ||
      ref?.prefix !== "refs/heads/" ||
      typeof url !== "string" ||
      url !== `https://github.com/${repository}/commit/${sha}`
    ) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid commit data.",
      );
    }
    return { sha, url };
  }

  async openDraftPullRequest(
    repository: string,
    head: string,
    base: string,
    expectedHeadSha: string,
    title: string,
    body: string,
  ): Promise<DraftPullRequestResult> {
    parseRepository(repository);
    if (
      !validBranchName(head) ||
      !validBranchName(base) ||
      !/^[0-9a-f]{40}$/.test(expectedHeadSha) ||
      !title ||
      title.length > 256 ||
      /[\r\n\0]/.test(title) ||
      body.length > 65_536 ||
      /[\r\0]/.test(body)
    ) {
      throw new HttpError(
        422,
        "invalid_pull_request",
        "The draft pull-request request is invalid.",
      );
    }
    const value = await this.json(endpoint(repository, "/pulls"), {
      body: JSON.stringify({ base, body, draft: true, head, title }),
      headers: { "Content-Type": "application/json; charset=utf-8" },
      method: "POST",
    });
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid pull-request data.",
      );
    }
    const record = value as Record<string, unknown>;
    const baseValue =
      record.base !== null &&
      typeof record.base === "object" &&
      !Array.isArray(record.base)
        ? (record.base as Record<string, unknown>)
        : null;
    const headValue =
      record.head !== null &&
      typeof record.head === "object" &&
      !Array.isArray(record.head)
        ? (record.head as Record<string, unknown>)
        : null;
    const baseRepository =
      baseValue?.repo !== null &&
      typeof baseValue?.repo === "object" &&
      !Array.isArray(baseValue.repo)
        ? (baseValue.repo as Record<string, unknown>)
        : null;
    const headRepository =
      headValue?.repo !== null &&
      typeof headValue?.repo === "object" &&
      !Array.isArray(headValue.repo)
        ? (headValue.repo as Record<string, unknown>)
        : null;
    if (
      !Number.isSafeInteger(record.number) ||
      Number(record.number) < 1 ||
      record.state !== "open" ||
      record.draft !== true ||
      baseValue?.ref !== base ||
      headValue?.ref !== head ||
      headValue.sha !== expectedHeadSha ||
      typeof baseRepository?.full_name !== "string" ||
      baseRepository.full_name.toLowerCase() !== repository.toLowerCase() ||
      typeof headRepository?.full_name !== "string" ||
      headRepository.full_name.toLowerCase() !== repository.toLowerCase() ||
      typeof record.html_url !== "string" ||
      record.html_url.toLowerCase() !==
        `https://github.com/${repository}/pull/${String(record.number)}`.toLowerCase()
    ) {
      throw new HttpError(
        502,
        "github_error",
        "GitHub returned invalid pull-request coordinates.",
      );
    }
    return { number: Number(record.number), url: record.html_url };
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
