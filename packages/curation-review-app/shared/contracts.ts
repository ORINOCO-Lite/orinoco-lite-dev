export type JsonPrimitive = boolean | number | string | null;
export type JsonValue =
  JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export const MAX_SHACL_BUNDLE_BYTES = 10 * 1024 * 1024;
export const SHACL_HANDOFF_NONCE = /^[0-9a-f]{64}$/;

export function isSafeEditorOrigin(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 256) return false;
  let origin: URL;
  try {
    origin = new URL(value);
  } catch {
    return false;
  }
  const loopback =
    origin.protocol === "http:" &&
    (origin.hostname === "127.0.0.1" || origin.hostname === "localhost");
  return (
    (origin.protocol === "https:" || loopback) &&
    origin.origin === value &&
    origin.pathname === "/" &&
    origin.search === "" &&
    origin.hash === "" &&
    origin.username === "" &&
    origin.password === ""
  );
}

export function isShaclHandoffNonce(value: unknown): value is string {
  return typeof value === "string" && SHACL_HANDOFF_NONCE.test(value);
}

export type CandidateOperation = "add" | "delete" | "modify";
export type Disposition = "accept" | "defer" | "reject";

export const MAX_GITHUB_TEXT_LENGTH = 65_536;

export interface ReviewCandidate {
  after: string | null;
  before: string | null;
  blockers: string[];
  claim_sha256: string;
  friendly_id: string;
  label: string;
  operation: CandidateOperation;
  pid: string;
  record_path: string;
  source_namespace: string;
  source_record_id: string;
}

export interface ReviewProposal {
  adapter: string;
  candidates: ReviewCandidate[];
  head_sha: string;
  proposal_sha: string;
  pull_request: number;
  pull_request_url: string;
  repository: string;
  source_coordinate: JsonObject;
}

export interface SubmissionDecision {
  disposition: Disposition;
  operation: CandidateOperation;
  pid: string;
  record_path: string;
}

export interface CurationSubmission {
  adapter: string;
  decisions: SubmissionDecision[];
  format: "orinoco-lite-curation-submission-v1";
  head_sha: string;
  proposal_sha: string;
  pull_request: number;
  repository: string;
  source_coordinate: JsonObject;
}

export interface AuthenticatedSession {
  authenticated: true;
  csrf_token: string;
  login: string;
}

export interface AnonymousSession {
  authenticated: false;
}

export type SessionStatus = AnonymousSession | AuthenticatedSession;

export interface SubmitResult {
  comment_url: string;
}

export interface DiscoveryArtifact {
  created_at: string;
  expires_at: string;
  id: number;
  name: string;
}

export interface DiscoveryPullRequest {
  artifacts: DiscoveryArtifact[];
  draft: boolean;
  head_sha: string;
  number: number;
  proposal_sha: string;
  title: string;
}

export interface ReviewDiscovery {
  pull_requests: DiscoveryPullRequest[];
  repository: string;
}

export interface ShaclReviewRecord {
  pid: string;
  rdf_turtle: string;
  schema_type: string;
  source_path: string;
  source_sha256: string;
}

export interface ShaclReviewBundle {
  format: "orinoco-shacl-review-bundle";
  records: ShaclReviewRecord[];
  source_commit: string;
  version: 2;
}

export interface ShaclPullRequestTarget {
  expected_head_sha: string;
  kind: "pull_request";
  pull_request: number;
}

export interface ShaclStandaloneTarget {
  kind: "standalone";
}

export type ShaclProposalTarget =
  ShaclPullRequestTarget | ShaclStandaloneTarget;

export interface ShaclProposalRequest {
  acknowledge_public_data: true;
  bundle: ShaclReviewBundle;
  format: "orinoco-lite-shacl-proposal-v1";
  repository: string;
  target: ShaclProposalTarget;
}

export interface ShaclProposalResult {
  commit_sha: string;
  commit_url: string;
  pull_request: number;
  pull_request_url: string;
}

export interface ShaclBundleMessage {
  bundle: ShaclReviewBundle;
  format: "orinoco-lite-shacl-bundle-message-v1";
  handoff_nonce: string;
  repository: string;
}

export interface ShaclProposalReadyMessage {
  format: "orinoco-lite-shacl-proposal-ready-v1";
  handoff_nonce: string;
  repository: string;
}
