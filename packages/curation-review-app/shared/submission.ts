/** Runs in the downstream browser. The authentication service never sees input. */
import type { BrowserCredentialScope } from "../functions/lib/browser-access";

export const SUBMISSION_PATH = ".orinoco-lite/submission.json";
export const AUTHORIZATION_PATH = ".orinoco-lite/submission-authorization.json";
const SHA = /^[a-f0-9]{40}$/;

export interface SubmissionAccess {
  scope: BrowserCredentialScope;
  scope_proof: string;
  credentials: Record<string, { token: string; expires_at: string }>;
}

export interface AuthenticationChannel {
  authorize(input: {
    scope_proof: string;
    input_repository: string;
    input_commit: string;
  }): Promise<{ authorization: string }>;
}

export class GitHubSubmissionError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

class Repository {
  constructor(
    readonly name: string,
    private readonly token: string,
    private readonly fetcher: typeof fetch,
  ) {}

  async request(
    path: string,
    method = "GET",
    body?: unknown,
    raw = false,
  ): Promise<any> {
    const response = await this.fetcher(
      `https://api.github.com/repos/${this.name}${path}`,
      {
        method,
        redirect: raw ? "follow" : "error",
        credentials: "omit",
        cache: "no-store",
        headers: {
          Accept: raw
            ? "application/vnd.github.raw+json"
            : "application/vnd.github+json",
          Authorization: `Bearer ${this.token}`,
          "X-GitHub-Api-Version": "2022-11-28",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      },
    );
    if (!response.ok)
      throw new GitHubSubmissionError(
        `GitHub could not ${method === "GET" ? "read" : "save"} the submission in ${this.name} (HTTP ${response.status}).`,
        response.status,
      );
    return response.status === 204
      ? null
      : raw
        ? response.text()
        : response.json();
  }

  async file(ref: string, path: string): Promise<string | null> {
    try {
      // Raw media supports the editor's full 10 MiB limit; GitHub omits
      // base64 content from the JSON representation above 1 MiB.
      return await this.request(
        `/contents/${path}?ref=${encodeURIComponent(ref)}`,
        "GET",
        undefined,
        true,
      );
    } catch (error) {
      if (error instanceof GitHubSubmissionError && error.status === 404)
        return null;
      throw error;
    }
  }

  async head(branch: string): Promise<string | null> {
    try {
      return (
        await this.request(`/git/ref/heads/${encodeURIComponent(branch)}`)
      ).object.sha;
    } catch (error) {
      if (error instanceof GitHubSubmissionError && error.status === 404)
        return null;
      throw error;
    }
  }

  async commit(parent: string, path: string, content: string): Promise<string> {
    const base = await this.request(`/git/commits/${parent}`);
    const tree = await this.request("/git/trees", "POST", {
      base_tree: base.tree.sha,
      tree: [{ path, mode: "100644", type: "blob", content }],
    });
    return (
      await this.request("/git/commits", "POST", {
        message: "chore: submit website edit for repository processing",
        parents: [parent],
        tree: tree.sha,
      })
    ).sha;
  }

  async create(branch: string, sha: string): Promise<void> {
    await this.request("/git/refs", "POST", {
      ref: `refs/heads/${branch}`,
      sha,
    });
  }

  async advance(branch: string, sha: string): Promise<void> {
    await this.request(
      `/git/refs/heads/${encodeURIComponent(branch)}`,
      "PATCH",
      { sha, force: false },
    );
  }
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object")
    return `{${Object.entries(value)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
      .join(",")}}`;
  const serialized = JSON.stringify(value);
  if (serialized === undefined)
    throw new Error("The submission contains an unsupported value.");
  return serialized;
}

/** Content determines the submission ref, so a lost response does not duplicate work. */
export async function uploadSubmission(
  input: unknown,
  access: SubmissionAccess,
  authentication: AuthenticationChannel,
  fetcher: typeof fetch = fetch,
): Promise<{
  repository: string;
  branch: string;
  input_commit: string;
  workflow_url: string;
}> {
  const bytes = canonicalJson(input) + "\n";
  if (new TextEncoder().encode(bytes).length > 10 * 1024 * 1024 + 64 * 1024)
    throw new Error("The submission exceeds the 10 MiB bundle limit.");
  const fingerprint = new Uint8Array(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(bytes)),
  );
  const id = Array.from(fingerprint, (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  const branch = `orinoco/submissions/${id}`;
  const inputRepository =
    access.scope.metadata?.repository ?? access.scope.source.repository;
  const repositories = new Map(
    access.scope.repositories.map((repository) => {
      const credential = access.credentials[repository.name];
      if (!credential?.token || Date.parse(credential.expires_at) <= Date.now())
        throw new Error("Sign in again to submit the edit.");
      return [
        repository.name,
        new Repository(repository.name, credential.token, fetcher),
      ] as const;
    }),
  );
  const storage = repositories.get(inputRepository);
  const base = access.scope.repositories.find(
    (repository) => repository.name === inputRepository,
  );
  if (!storage || !base)
    throw new Error(
      "The submission repository is outside the authenticated scope.",
    );

  let head = await storage.head(branch);
  if (head === null) {
    const commit = await storage.commit(
      base.baseCommit,
      SUBMISSION_PATH,
      bytes,
    );
    try {
      await storage.create(branch, commit);
    } catch (error) {
      // Another tab or a retry may have completed the same create. Verify it below.
      if (!(error instanceof GitHubSubmissionError && error.status === 422))
        throw error;
    }
    head = await storage.head(branch);
  }
  if (!head || (await storage.file(head, SUBMISSION_PATH)) !== bytes)
    throw new Error(
      "The existing submission contains different input. Your edit has been retained; inspect its branch before retrying.",
    );

  let receiptBytes = await storage.file(head, AUTHORIZATION_PATH);
  let inputCommit: string;
  if (receiptBytes === null) {
    inputCommit = head;
    const { authorization } = await authentication.authorize({
      scope_proof: access.scope_proof,
      input_repository: inputRepository,
      input_commit: inputCommit,
    });
    receiptBytes =
      JSON.stringify({
        authorization,
        input_repository: inputRepository,
        input_commit: inputCommit,
      }) + "\n";
    const commit = await storage.commit(head, AUTHORIZATION_PATH, receiptBytes);
    await storage.advance(branch, commit);
  } else {
    const receipt = JSON.parse(receiptBytes);
    inputCommit = receipt.input_commit;
    if (
      receipt.input_repository !== inputRepository ||
      !SHA.test(inputCommit) ||
      typeof receipt.authorization !== "string" ||
      (await storage.file(inputCommit, SUBMISSION_PATH)) !== bytes
    )
      throw new Error(
        "The existing submission has an invalid authorization record.",
      );
  }

  // Website retains only coordinates and authorization, never the private bundle.
  for (const repository of access.scope.repositories) {
    if (repository.name === inputRepository) continue;
    const client = repositories.get(repository.name)!;
    const existing = await client.head(branch);
    if (existing === null) {
      const commit = await client.commit(
        repository.baseCommit,
        AUTHORIZATION_PATH,
        receiptBytes,
      );
      try {
        await client.create(branch, commit);
      } catch (error) {
        if (!(error instanceof GitHubSubmissionError && error.status === 422))
          throw error;
      }
    }
    if ((await client.file(branch, AUTHORIZATION_PATH)) !== receiptBytes)
      throw new Error(
        "The website has a different submission authorization. Inspect its submission branch before retrying.",
      );
  }
  await storage.request("/dispatches", "POST", {
    event_type: "orinoco-submission",
    client_payload: { submission: branch },
  });
  return {
    repository: inputRepository,
    branch,
    input_commit: inputCommit,
    workflow_url: `https://github.com/${inputRepository}/actions/workflows/orinoco.yml?query=${encodeURIComponent(`branch:${branch}`)}`,
  };
}
