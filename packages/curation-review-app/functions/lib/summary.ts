import type {
  CandidateOperation,
  JsonObject,
  ReviewCandidate,
} from "../../shared/contracts";
import { HttpError } from "./http";

const COMMIT = /^[0-9a-f]{40}$/;
const CLAIM = /^sha256:[0-9a-f]{64}$/;
const RECORD_ROOT = "metadata/records/";
const RECORD_PATH = /^metadata\/records\/[^\\\r\n]+\.ya?ml$/;
export const MAX_REVIEW_CANDIDATES = 350;

export interface ProposalSummary {
  adapter: string;
  candidates: Omit<ReviewCandidate, "after" | "before">[];
  proposal_sha: string;
  source_coordinate: JsonObject;
}

function invalid(message: string): never {
  throw new HttpError(422, "invalid_proposal_summary", message);
}

function oneLine(value: string, label: string): string {
  if (!value || value !== value.trim() || /[\r\n\0]/.test(value)) {
    invalid(`${label} is invalid.`);
  }
  return value;
}

function headingOffsets(body: string, heading: string): number[] {
  const marker = `${heading}\n`;
  const offsets: number[] = [];
  if (body.startsWith(marker)) offsets.push(0);
  let offset = body.indexOf(`\n${marker}`);
  while (offset >= 0) {
    offsets.push(offset + 1);
    offset = body.indexOf(`\n${marker}`, offset + marker.length + 1);
  }
  return offsets;
}

function section(body: string, heading: string, nextHeading?: string): string {
  const marker = `${heading}\n`;
  const offsets = headingOffsets(body, heading);
  if (offsets.length !== 1) {
    invalid(`The pull request must contain exactly one ${heading} section.`);
  }
  const start = offsets[0] as number;
  const contentStart = start + marker.length;
  let end: number;
  if (nextHeading === undefined) {
    const nextSection = body.indexOf("\n## ", contentStart);
    end = nextSection < 0 ? body.length : nextSection;
  } else {
    const nextOffsets = headingOffsets(body, nextHeading);
    if (nextOffsets.length !== 1 || (nextOffsets[0] as number) <= start) {
      invalid(`The pull request is missing the ${nextHeading} section.`);
    }
    end = nextOffsets[0] as number;
  }
  return body.slice(contentStart, end).trim();
}

function validRecordPath(value: string): boolean {
  if (!RECORD_PATH.test(value)) return false;
  const parts = value.slice(RECORD_ROOT.length).split("/");
  return parts.every(
    (part) =>
      part.length > 0 && part !== "." && part !== ".." && !part.startsWith("."),
  );
}

function inlineField(content: string, label: string): string {
  const escapedLabel = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const expression = new RegExp(
    "^- " + escapedLabel + ": `([^`\\r\\n]+)`$",
    "gm",
  );
  const matches = [...content.matchAll(expression)];
  if (matches.length !== 1 || matches[0]?.[1] === undefined) {
    invalid(`The summary must contain exactly one ${label} field.`);
  }
  return oneLine(matches[0][1], label);
}

function sourceCoordinate(content: string): JsonObject {
  const expression = /^- Source coordinate:\s*\n```json\n([^\r\n]+)\n```$/gm;
  const matches = [...content.matchAll(expression)];
  if (matches.length !== 1 || matches[0]?.[1] === undefined) {
    invalid("The summary must contain one fenced Source coordinate object.");
  }
  let value: unknown;
  try {
    value = JSON.parse(matches[0][1]) as unknown;
  } catch {
    invalid("The Source coordinate is not valid JSON.");
  }
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.keys(value).length === 0
  ) {
    invalid("The Source coordinate must be a non-empty JSON object.");
  }
  return value as JsonObject;
}

function blockers(content: string): string[] {
  if (content === "- Blockers: None") return [];
  if (!content.startsWith("- Blockers:\n"))
    invalid("Candidate blockers are invalid.");
  const values = content.slice("- Blockers:\n".length).split("\n");
  if (values.length === 0 || values.some((line) => !line.startsWith("  - "))) {
    invalid("Candidate blockers must be a visible indented list.");
  }
  const result = values.map((line) =>
    oneLine(line.slice(4), "Candidate blocker"),
  );
  if (new Set(result).size !== result.length)
    invalid("Candidate blockers must be unique.");
  return result;
}

function candidate(block: string): Omit<ReviewCandidate, "after" | "before"> {
  const firstBreak = block.indexOf("\n");
  if (firstBreak < 0) invalid("A candidate section has no detail fields.");
  const heading = block.slice(0, firstBreak);
  const separator = heading.indexOf(" — ");
  if (separator < 1 || separator === heading.length - 3) {
    invalid("Candidate headings must contain a friendly ID and label.");
  }
  const friendlyId = oneLine(
    heading.slice(0, separator),
    "Candidate friendly ID",
  );
  const label = oneLine(heading.slice(separator + 3), "Candidate label");
  const details = block.slice(firstBreak + 1);
  const blockerStart = details.indexOf("- Blockers:");
  if (
    blockerStart < 0 ||
    details.indexOf("- Blockers:", blockerStart + 1) >= 0
  ) {
    invalid("Each candidate must contain one Blockers field.");
  }
  const prefix = details.slice(0, blockerStart).trimEnd();
  const blockerValues = blockers(details.slice(blockerStart).trim());
  const pid = inlineField(prefix, "PID");
  const sourceRecordId = inlineField(prefix, "Source record");
  const recordPath = inlineField(prefix, "Record path");
  const operation = inlineField(prefix, "Operation");
  const claim = inlineField(prefix, "Claim SHA-256");
  const expectedLines = 5;
  if (
    prefix.split("\n").filter((line) => line.trim()).length !== expectedLines
  ) {
    invalid("A candidate contains unexpected detail fields.");
  }
  if (!validRecordPath(recordPath))
    invalid("Candidate Record path is invalid.");
  if (operation !== "add" && operation !== "modify" && operation !== "delete") {
    invalid("Candidate Operation is invalid.");
  }
  if (!CLAIM.test(claim)) invalid("Candidate Claim SHA-256 is invalid.");
  return {
    blockers: blockerValues,
    claim_sha256: claim,
    friendly_id: friendlyId,
    label,
    operation: operation as CandidateOperation,
    pid,
    record_path: recordPath,
    source_record_id: sourceRecordId,
  };
}

export function parseProposalSummary(body: string): ProposalSummary {
  if (typeof body !== "string" || body.length > 1_048_576) {
    invalid("The pull-request summary is missing or too large.");
  }
  const proposal = section(body, "## Curation proposal", "## Candidate review");
  const review = section(body, "## Candidate review");
  const adapter = inlineField(proposal, "Adapter");
  const proposalSha = inlineField(proposal, "Proposal commit");
  if (!COMMIT.test(proposalSha)) invalid("Proposal commit is invalid.");
  const coordinate = sourceCoordinate(proposal);
  const parts = review.split(/^### /m);
  if (parts[0]?.trim())
    invalid("Candidate review contains unexpected introductory text.");
  const candidates = parts.slice(1).map((item) => candidate(item.trim()));
  if (candidates.length === 0) invalid("Candidate review must not be empty.");
  if (candidates.length > MAX_REVIEW_CANDIDATES) {
    invalid(
      `Candidate review must contain at most ${MAX_REVIEW_CANDIDATES} candidates.`,
    );
  }
  const pids = candidates.map((item) => item.pid);
  const paths = candidates.map((item) => item.record_path);
  const sourceIds = candidates.map((item) => item.source_record_id);
  const friendlyIds = candidates.map((item) => item.friendly_id);
  if (
    new Set(pids).size !== pids.length ||
    new Set(paths).size !== paths.length ||
    new Set(sourceIds).size !== sourceIds.length ||
    new Set(friendlyIds).size !== friendlyIds.length
  ) {
    invalid(
      "Candidate friendly ID, PID, path, and source-record identities must be unique.",
    );
  }
  return {
    adapter,
    candidates,
    proposal_sha: proposalSha,
    source_coordinate: coordinate,
  };
}
