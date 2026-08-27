export type JsonPrimitive = boolean | number | string | null;
export type JsonValue =
  JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

export const MAX_SHACL_BUNDLE_BYTES = 10 * 1024 * 1024;
export const DEFAULT_CURATION_SERVICE_ORIGIN =
  "https://orinoco-curation-review.pages.dev";
export const SHACL_HANDOFF_NONCE = /^[0-9a-f]{64}$/;
export const REVIEW_HANDOFF_NONCE = SHACL_HANDOFF_NONCE;

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

export const isSafeReviewOrigin = isSafeEditorOrigin;

export function isReviewHandoffNonce(value: unknown): value is string {
  return typeof value === "string" && REVIEW_HANDOFF_NONCE.test(value);
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
  review_service_origin: string;
  review_site_url: string;
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

export interface ReviewGrant {
  artifact_id: number;
  handoff_nonce: string;
  pull_request: number;
  repository: string;
  review_origin: string;
}

export interface AuthenticatedSession {
  authenticated: true;
  csrf_token: string;
  login: string;
  review_grant: ReviewGrant | null;
  shacl_grant: ShaclGrant | null;
}

export interface AnonymousSession {
  authenticated: false;
}

export type SessionStatus = AnonymousSession | AuthenticatedSession;

export interface SubmitResult {
  comment_url: string;
}

export interface ReviewCoordinates {
  artifact_id: number;
  handoff_nonce: string;
  pull_request: number;
  repository: string;
}

export interface ReviewTransportReadyMessage extends ReviewCoordinates {
  format: "orinoco-lite-review-transport-ready-v1";
}

export interface ReviewProposalRequestMessage extends ReviewCoordinates {
  format: "orinoco-lite-review-proposal-request-v1";
}

export interface ReviewProposalMessage extends ReviewCoordinates {
  format: "orinoco-lite-review-proposal-message-v1";
  login: string;
  proposal: ReviewProposal;
}

export interface ReviewSubmissionMessage extends ReviewCoordinates {
  format: "orinoco-lite-review-submission-message-v1";
  submission: CurationSubmission;
}

export interface ReviewPostStartedMessage extends ReviewCoordinates {
  format: "orinoco-lite-review-post-started-v1";
}

export interface ReviewSubmissionSuccessMessage extends ReviewCoordinates {
  comment_url: string;
  error: null;
  format: "orinoco-lite-review-submission-result-v1";
  retry_safe: false;
}

export interface ReviewSubmissionFailureMessage extends ReviewCoordinates {
  comment_url: null;
  error: string;
  format: "orinoco-lite-review-submission-result-v1";
  retry_safe: boolean;
}

export type ReviewSubmissionResultMessage =
  ReviewSubmissionFailureMessage | ReviewSubmissionSuccessMessage;

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

export interface ShaclGrant {
  editor_origin: string;
  expected_head_sha: string | null;
  handoff_nonce: string;
  pull_request: number | null;
  repository: string;
}

export interface ShaclProposalMessage {
  format: "orinoco-lite-shacl-proposal-message-v1";
  handoff_nonce: string;
  proposal: ShaclProposalRequest;
  repository: string;
}

export interface ShaclProposalStartedMessage {
  format: "orinoco-lite-shacl-proposal-started-v1";
  handoff_nonce: string;
  repository: string;
}

export interface ShaclProposalSuccessMessage {
  error: null;
  format: "orinoco-lite-shacl-proposal-result-v1";
  handoff_nonce: string;
  repository: string;
  result: ShaclProposalResult;
  retry_safe: false;
}

export interface ShaclProposalFailureMessage {
  error: string;
  format: "orinoco-lite-shacl-proposal-result-v1";
  handoff_nonce: string;
  repository: string;
  result: null;
  retry_safe: boolean;
}

export type ShaclProposalResultMessage =
  ShaclProposalFailureMessage | ShaclProposalSuccessMessage;

export interface ShaclProposalReadyMessage {
  format: "orinoco-lite-shacl-proposal-ready-v1";
  handoff_nonce: string;
  repository: string;
}
