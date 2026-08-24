export type JsonPrimitive = boolean | number | string | null;
export type JsonValue =
  JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
export type JsonObject = { [key: string]: JsonValue };

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
