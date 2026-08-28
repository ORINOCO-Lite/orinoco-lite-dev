import { Unzip, UnzipInflate } from "fflate";
import type {
  CandidateOperation,
  JsonObject,
  JsonValue,
} from "../../shared/contracts";
import {
  annotationPathForRecord,
  CURRENT_METADATA_ROOTS,
  type MetadataRoots,
  validRepositoryYamlPath,
  validYamlPathBelow,
} from "../../shared/metadata";
import { HttpError } from "./http";

export const MAX_ARTIFACT_ARCHIVE_BYTES = 8_388_608;
export const MAX_REVIEW_BUNDLE_BYTES = 16_777_216;
export const MAX_REVIEW_CANDIDATES = 225;
export const MAX_REVIEW_PATHS = MAX_REVIEW_CANDIDATES * 2;

const BUNDLE_ENTRY = "review-bundle.json";
const COMMIT = /^[0-9a-f]{40}$/;
const CLAIM = /^sha256:[0-9a-f]{64}$/;
const SUPPORTED_ADAPTERS = new Set(["dump-research-info", "zotero"]);
const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_SIGNATURE = 0x02014b50;
const LOCAL_SIGNATURE = 0x04034b50;

export interface ReviewBundleCandidate {
  blockers: string[];
  claim_sha256: string;
  friendly_id: string;
  label: string;
  operation: CandidateOperation;
  paths: string[];
  pid: string;
  record_path: string;
  source_namespace: string;
  source_record_id: string;
}

export interface ReviewBundle {
  adapter: string;
  candidates: ReviewBundleCandidate[];
  format: "orinoco-lite-curation-review-bundle-v1";
  metadata_base_sha: string;
  proposal_sha: string;
  pull_request: number;
  repository: string;
  source_coordinate: JsonObject;
  workflow_run_id: number;
}

function invalid(message: string): never {
  throw new HttpError(422, "invalid_review_artifact", message);
}

function exactKeys(
  value: unknown,
  expected: readonly string[],
  label: string,
): asserts value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalid(`${label} must be an object.`);
  }
  const observed = Object.keys(value).sort();
  const required = [...expected].sort();
  if (
    observed.length !== required.length ||
    observed.some((key, index) => key !== required[index])
  ) {
    invalid(`${label} has missing or unexpected fields.`);
  }
}

function line(value: unknown, label: string): string {
  if (
    typeof value !== "string" ||
    !value ||
    value !== value.trim() ||
    /[\r\n\0]/.test(value)
  ) {
    invalid(`${label} is invalid.`);
  }
  return value;
}

function commit(value: unknown, label: string): string {
  const result = line(value, label);
  if (!COMMIT.test(result)) invalid(`${label} must be a full Git commit.`);
  return result;
}

function positiveInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 1) {
    invalid(`${label} must be a positive integer.`);
  }
  return Number(value);
}

function jsonValue(value: unknown, label: string): JsonValue {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) invalid(`${label} is not JSON.`);
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => jsonValue(item, label));
  }
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, jsonValue(item, label)]),
    );
  }
  invalid(`${label} is not JSON.`);
}

function sourceCoordinate(value: unknown): JsonObject {
  const result = jsonValue(value, "source_coordinate");
  if (
    result === null ||
    typeof result !== "object" ||
    Array.isArray(result) ||
    Object.keys(result).length === 0
  ) {
    invalid("source_coordinate must be a non-empty JSON object.");
  }
  return result;
}

function recordPath(value: unknown, roots: MetadataRoots | null): string {
  const result = line(value, "Candidate record_path");
  if (
    roots === null
      ? !validRepositoryYamlPath(result)
      : !validYamlPathBelow(result, roots.records)
  ) {
    invalid("Candidate record_path is invalid.");
  }
  return result;
}

function operation(value: unknown): CandidateOperation {
  if (value !== "add" && value !== "modify" && value !== "delete") {
    invalid("Candidate operation is invalid.");
  }
  return value;
}

function stringArray(value: unknown, label: string): string[] {
  if (!Array.isArray(value)) invalid(`${label} must be an array.`);
  const result = value.map((item) => line(item, label));
  if (new Set(result).size !== result.length) {
    invalid(`${label} values must be unique.`);
  }
  return result;
}

function candidate(
  value: unknown,
  roots: MetadataRoots | null,
): ReviewBundleCandidate {
  exactKeys(
    value,
    [
      "blockers",
      "claim_sha256",
      "friendly_id",
      "label",
      "operation",
      "paths",
      "pid",
      "record_path",
      "source_namespace",
      "source_record_id",
    ],
    "Review candidate",
  );
  const path = recordPath(value.record_path, roots);
  const paths = stringArray(value.paths, "Candidate path");
  const companion =
    roots === null ? null : annotationPathForRecord(path, roots);
  if (
    paths.length < 1 ||
    paths.length > 2 ||
    !paths.includes(path) ||
    paths.some(
      (item) =>
        !validRepositoryYamlPath(item) ||
        (companion !== null && item !== path && item !== companion),
    )
  ) {
    invalid("Candidate paths must contain its record and optional companion.");
  }
  const claim = line(value.claim_sha256, "Candidate claim_sha256");
  if (!CLAIM.test(claim)) invalid("Candidate claim_sha256 is invalid.");
  return {
    blockers: stringArray(value.blockers, "Candidate blocker"),
    claim_sha256: claim,
    friendly_id: line(value.friendly_id, "Candidate friendly_id"),
    label: line(value.label, "Candidate label"),
    operation: operation(value.operation),
    paths,
    pid: line(value.pid, "Candidate pid"),
    record_path: path,
    source_namespace: line(
      value.source_namespace,
      "Candidate source_namespace",
    ),
    source_record_id: line(
      value.source_record_id,
      "Candidate source_record_id",
    ),
  };
}

function view(bytes: Uint8Array): DataView {
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
}

function zipName(bytes: Uint8Array): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    invalid("The artifact ZIP contains an invalid entry name.");
  }
}

function findEndOfCentralDirectory(bytes: Uint8Array): number {
  if (bytes.length < 22) invalid("The artifact is not a complete ZIP archive.");
  const data = view(bytes);
  const lower = Math.max(0, bytes.length - 65_557);
  for (let offset = bytes.length - 22; offset >= lower; offset -= 1) {
    if (data.getUint32(offset, true) !== EOCD_SIGNATURE) continue;
    const commentLength = data.getUint16(offset + 20, true);
    if (offset + 22 + commentLength === bytes.length) return offset;
  }
  invalid("The artifact has no valid ZIP directory.");
}

function validateZipDirectory(bytes: Uint8Array): void {
  if (bytes.byteLength > MAX_ARTIFACT_ARCHIVE_BYTES) {
    invalid("The artifact ZIP exceeds the compressed size limit.");
  }
  const data = view(bytes);
  const eocd = findEndOfCentralDirectory(bytes);
  const disk = data.getUint16(eocd + 4, true);
  const directoryDisk = data.getUint16(eocd + 6, true);
  const diskEntries = data.getUint16(eocd + 8, true);
  const totalEntries = data.getUint16(eocd + 10, true);
  const directorySize = data.getUint32(eocd + 12, true);
  const directoryOffset = data.getUint32(eocd + 16, true);
  if (
    disk !== 0 ||
    directoryDisk !== 0 ||
    diskEntries !== 1 ||
    totalEntries !== 1 ||
    directoryOffset + directorySize !== eocd ||
    directoryOffset + 46 > eocd ||
    data.getUint32(directoryOffset, true) !== CENTRAL_SIGNATURE
  ) {
    invalid("The artifact ZIP must contain exactly one ordinary entry.");
  }
  const flags = data.getUint16(directoryOffset + 8, true);
  const compression = data.getUint16(directoryOffset + 10, true);
  const compressedSize = data.getUint32(directoryOffset + 20, true);
  const originalSize = data.getUint32(directoryOffset + 24, true);
  const nameLength = data.getUint16(directoryOffset + 28, true);
  const extraLength = data.getUint16(directoryOffset + 30, true);
  const commentLength = data.getUint16(directoryOffset + 32, true);
  const externalAttributes = data.getUint32(directoryOffset + 38, true);
  const localOffset = data.getUint32(directoryOffset + 42, true);
  const centralEnd =
    directoryOffset + 46 + nameLength + extraLength + commentLength;
  if (
    centralEnd !== eocd ||
    compressedSize > MAX_ARTIFACT_ARCHIVE_BYTES ||
    originalSize > MAX_REVIEW_BUNDLE_BYTES ||
    (flags & 1) !== 0 ||
    (compression !== 0 && compression !== 8) ||
    localOffset !== 0 ||
    data.getUint32(localOffset, true) !== LOCAL_SIGNATURE
  ) {
    invalid("The artifact ZIP entry is unsupported or too large.");
  }
  const nameStart = directoryOffset + 46;
  const name = zipName(bytes.subarray(nameStart, nameStart + nameLength));
  const madeBy = data.getUint16(directoryOffset + 4, true) >> 8;
  const unixMode = externalAttributes >>> 16;
  const unixRegular = (unixMode & 0o170000) === 0o100000;
  const dosDirectory = (externalAttributes & 0x10) !== 0;
  if (
    name !== BUNDLE_ENTRY ||
    name.includes("/") ||
    (madeBy === 3 ? !unixRegular : dosDirectory)
  ) {
    invalid(
      "The artifact must contain one regular top-level review-bundle.json.",
    );
  }
  const localFlags = data.getUint16(localOffset + 6, true);
  const localCompression = data.getUint16(localOffset + 8, true);
  const localNameLength = data.getUint16(localOffset + 26, true);
  const localExtraLength = data.getUint16(localOffset + 28, true);
  const localNameStart = localOffset + 30;
  const localDataStart = localNameStart + localNameLength + localExtraLength;
  if (
    localFlags !== flags ||
    localCompression !== compression ||
    localDataStart + compressedSize > directoryOffset ||
    localNameLength !== nameLength ||
    zipName(
      bytes.subarray(localNameStart, localNameStart + localNameLength),
    ) !== BUNDLE_ENTRY
  ) {
    invalid("The artifact ZIP local entry is inconsistent.");
  }
}

function extractReviewBundle(bytes: Uint8Array): Uint8Array {
  validateZipDirectory(bytes);
  const chunks: Uint8Array[] = [];
  let complete = false;
  let entries = 0;
  let failure: Error | null = null;
  let total = 0;
  const archive = new Unzip((file) => {
    entries += 1;
    if (entries !== 1 || file.name !== BUNDLE_ENTRY) {
      failure = new Error("unexpected ZIP entry");
      file.terminate();
      return;
    }
    file.ondata = (error, chunk, final) => {
      if (error !== null) {
        failure = error;
        return;
      }
      total += chunk.byteLength;
      if (total > MAX_REVIEW_BUNDLE_BYTES) {
        failure = new Error("uncompressed artifact is too large");
        file.terminate();
        return;
      }
      chunks.push(chunk);
      if (final) complete = true;
    };
    file.start();
  });
  archive.register(UnzipInflate);
  try {
    archive.push(bytes, true);
  } catch {
    invalid("The artifact ZIP could not be decompressed.");
  }
  if (failure !== null || entries !== 1 || !complete) {
    invalid("The artifact ZIP could not be decompressed safely.");
  }
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

export function parseReviewBundle(
  archive: Uint8Array,
  roots: MetadataRoots | null = CURRENT_METADATA_ROOTS,
): ReviewBundle {
  const bytes = extractReviewBundle(archive);
  let raw: unknown;
  try {
    raw = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(bytes),
    ) as unknown;
  } catch {
    invalid("review-bundle.json is not valid UTF-8 JSON.");
  }
  exactKeys(
    raw,
    [
      "adapter",
      "candidates",
      "format",
      "metadata_base_sha",
      "proposal_sha",
      "pull_request",
      "repository",
      "source_coordinate",
      "workflow_run_id",
    ],
    "Review bundle",
  );
  if (raw.format !== "orinoco-lite-curation-review-bundle-v1") {
    invalid("The review-bundle format is unsupported.");
  }
  const adapter = line(raw.adapter, "adapter");
  if (!SUPPORTED_ADAPTERS.has(adapter)) invalid("Adapter is unsupported.");
  if (
    !Array.isArray(raw.candidates) ||
    raw.candidates.length < 1 ||
    raw.candidates.length > MAX_REVIEW_CANDIDATES
  ) {
    invalid(
      `Review bundle candidates must contain 1 to ${MAX_REVIEW_CANDIDATES} records.`,
    );
  }
  const candidates = raw.candidates.map((value) => candidate(value, roots));
  const pids = candidates.map((item) => item.pid);
  const paths = candidates.map((item) => item.record_path);
  const friendlyIds = candidates.map((item) => item.friendly_id);
  const sourceIds = candidates.map(
    (item) => `${item.source_namespace}\0${item.source_record_id}`,
  );
  const changedPaths = candidates.flatMap((item) => item.paths);
  if (
    new Set(pids).size !== pids.length ||
    new Set(paths).size !== paths.length ||
    new Set(friendlyIds).size !== friendlyIds.length ||
    new Set(sourceIds).size !== sourceIds.length ||
    new Set(changedPaths).size !== changedPaths.length ||
    changedPaths.length > MAX_REVIEW_PATHS
  ) {
    invalid("Review bundle candidate identities and paths must be unique.");
  }
  return {
    adapter,
    candidates,
    format: "orinoco-lite-curation-review-bundle-v1",
    metadata_base_sha: commit(raw.metadata_base_sha, "metadata_base_sha"),
    proposal_sha: commit(raw.proposal_sha, "proposal_sha"),
    pull_request: positiveInteger(raw.pull_request, "pull_request"),
    repository: line(raw.repository, "repository"),
    source_coordinate: sourceCoordinate(raw.source_coordinate),
    workflow_run_id: positiveInteger(raw.workflow_run_id, "workflow_run_id"),
  };
}

export function validateReviewBundleMetadataRoots(
  bundle: ReviewBundle,
  roots: MetadataRoots,
): void {
  for (const candidate of bundle.candidates) {
    const record = candidate.record_path;
    const companion = annotationPathForRecord(record, roots);
    if (
      !validYamlPathBelow(record, roots.records) ||
      candidate.paths.some((path) => path !== record && path !== companion)
    ) {
      invalid("Review bundle metadata paths do not match configured roots.");
    }
  }
}

export function canonicalJson(value: JsonValue): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map(
        (key) =>
          `${JSON.stringify(key)}:${canonicalJson(value[key] as JsonValue)}`,
      )
      .join(",")}}`;
  }
  return JSON.stringify(value);
}
