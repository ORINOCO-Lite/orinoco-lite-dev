import type {
  CurationSubmission,
  ReviewProposal,
  SessionStatus,
  ShaclProposalRequest,
  ShaclProposalResult,
  SubmitResult,
} from "../shared/contracts";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function responseJson<T>(response: Response): Promise<T> {
  let value: unknown;
  try {
    value = (await response.json()) as unknown;
  } catch {
    throw new ApiError(
      response.status,
      "invalid_response",
      "The review service returned an invalid response.",
    );
  }
  if (!response.ok) {
    const record =
      value !== null && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>).error
        : null;
    const error =
      record !== null && typeof record === "object" && !Array.isArray(record)
        ? (record as Record<string, unknown>)
        : {};
    throw new ApiError(
      response.status,
      typeof error.code === "string" ? error.code : "request_failed",
      typeof error.message === "string"
        ? error.message
        : "The review request failed.",
    );
  }
  return value as T;
}

function targetQuery(
  repository: string,
  pullRequest: number,
  artifactId: number,
): string {
  const query = new URLSearchParams({
    artifact_id: String(artifactId),
    pull_request: String(pullRequest),
    repository,
  });
  return query.toString();
}

export function authenticationUrl(
  repository: string,
  pullRequest: number,
  artifactId: number,
  reviewOrigin?: string,
  handoffNonce?: string,
): string {
  const query = new URLSearchParams(
    targetQuery(repository, pullRequest, artifactId),
  );
  if (reviewOrigin !== undefined && handoffNonce !== undefined) {
    query.set("review_origin", reviewOrigin);
    query.set("handoff_nonce", handoffNonce);
  }
  return `/api/auth/start?${query.toString()}`;
}

export function shaclAuthenticationUrl(
  repository: string,
  pullRequest?: number,
  expectedHeadSha?: string,
  editorOrigin?: string,
  handoffNonce?: string,
): string {
  const query = new URLSearchParams({ repository });
  if (editorOrigin !== undefined && handoffNonce !== undefined) {
    query.set("editor_origin", editorOrigin);
    query.set("handoff_nonce", handoffNonce);
  }
  if (pullRequest !== undefined && expectedHeadSha !== undefined) {
    query.set("expected_head_sha", expectedHeadSha);
    query.set("pull_request", String(pullRequest));
  }
  return `/api/auth/shacl-start?${query.toString()}`;
}

export async function loadSession(): Promise<SessionStatus> {
  return responseJson<SessionStatus>(
    await fetch("/api/session", { headers: { Accept: "application/json" } }),
  );
}

export async function loadProposal(
  repository: string,
  pullRequest: number,
  artifactId: number,
): Promise<ReviewProposal> {
  return responseJson<ReviewProposal>(
    await fetch(
      `/api/proposal?${targetQuery(repository, pullRequest, artifactId)}`,
      {
        headers: { Accept: "application/json" },
      },
    ),
  );
}

export async function submitDecisions(
  submission: CurationSubmission,
  csrfToken: string,
  artifactId: number,
): Promise<SubmitResult> {
  return responseJson<SubmitResult>(
    await fetch(
      `/api/submit?artifact_id=${encodeURIComponent(String(artifactId))}`,
      {
        body: JSON.stringify(submission),
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        method: "POST",
      },
    ),
  );
}

export async function proposeShaclEdit(
  proposal: ShaclProposalRequest,
  csrfToken: string,
): Promise<ShaclProposalResult> {
  return responseJson<ShaclProposalResult>(
    await fetch("/api/shacl/propose", {
      body: JSON.stringify(proposal),
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    }),
  );
}

export async function logout(csrfToken: string): Promise<void> {
  await responseJson(
    await fetch("/api/logout", {
      headers: { Accept: "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    }),
  );
}
