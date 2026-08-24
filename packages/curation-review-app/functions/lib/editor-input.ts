import { Unzip, UnzipInflate } from "fflate";
import type { GitHubClient } from "./github";
import { HttpError } from "./http";
import { parseRepository, splitRepository } from "./input";

export const MAX_EDITOR_INPUT_ARCHIVE_BYTES = 8_388_608;
export const MAX_EDITOR_INPUT_BYTES = 16_777_216;
export const EDITOR_INPUT_PATHS = [
  "edit/config.json",
  "edit/records.ttl",
  "edit/data/record-sources.json",
] as const;

const ARTIFACT_PAGE_SIZE = 100;
const COMMIT = /^[0-9a-f]{40}$/;
const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_SIGNATURE = 0x02014b50;
const LOCAL_SIGNATURE = 0x04034b50;
const EXPECTED_PATHS = new Set<string>(EDITOR_INPUT_PATHS);
const TRUSTED_WORKFLOW_NAME = "Materialize SHACL Vue proposal";
const TRUSTED_WORKFLOW_PATH = ".github/workflows/shacl-vue-proposal.yml";
const TRUSTED_WORKFLOW_EVENTS = new Set([
  "pull_request_target",
  "push",
  "workflow_dispatch",
]);

export type EditorInputPath = (typeof EDITOR_INPUT_PATHS)[number];

export interface EditorInputFiles {
  files: Record<EditorInputPath, Uint8Array>;
  sourceCommit: string;
}

export interface ExactHeadEditorInput extends EditorInputFiles {
  artifactId: number;
  headSha: string;
  workflowRunId: number;
}

export type EditorInputGitHub = Pick<
  GitHubClient,
  "artifactArchive" | "json" | "repository"
>;

interface ZipEntry {
  originalSize: number;
}

interface ArtifactCandidate {
  createdAt: number;
  id: number;
  runHeadSha: string;
  runId: number;
}

function invalid(message: string): never {
  throw new HttpError(422, "invalid_editor_input", message);
}

function object(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    invalid(`${label} must be an object.`);
  }
  return value as Record<string, unknown>;
}

function positiveInteger(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 1) {
    invalid(`${label} must be a positive integer.`);
  }
  return Number(value);
}

function timestamp(value: unknown, label: string): number {
  if (typeof value !== "string" || !value) {
    invalid(`${label} must be a timestamp.`);
  }
  const result = Date.parse(value);
  if (!Number.isFinite(result)) invalid(`${label} must be a timestamp.`);
  return result;
}

function view(bytes: Uint8Array): DataView {
  return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
}

function zipName(bytes: Uint8Array): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    invalid("The editor-input ZIP contains an invalid entry name.");
  }
}

function findEndOfCentralDirectory(bytes: Uint8Array): number {
  if (bytes.byteLength < 22) {
    invalid("The editor-input artifact is not a complete ZIP archive.");
  }
  const data = view(bytes);
  const lower = Math.max(0, bytes.byteLength - 65_557);
  for (let offset = bytes.byteLength - 22; offset >= lower; offset -= 1) {
    if (data.getUint32(offset, true) !== EOCD_SIGNATURE) continue;
    const commentLength = data.getUint16(offset + 20, true);
    if (offset + 22 + commentLength === bytes.byteLength) return offset;
  }
  invalid("The editor-input artifact has no valid ZIP directory.");
}

function validateZipDirectory(
  bytes: Uint8Array,
): Map<EditorInputPath, ZipEntry> {
  if (bytes.byteLength > MAX_EDITOR_INPUT_ARCHIVE_BYTES) {
    invalid("The editor-input ZIP exceeds the compressed size limit.");
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
    diskEntries !== EDITOR_INPUT_PATHS.length ||
    totalEntries !== EDITOR_INPUT_PATHS.length ||
    directoryOffset + directorySize !== eocd
  ) {
    invalid("The editor-input ZIP must contain exactly three ordinary files.");
  }

  const entries = new Map<EditorInputPath, ZipEntry>();
  let offset = directoryOffset;
  let totalSize = 0;
  for (let index = 0; index < totalEntries; index += 1) {
    if (
      offset + 46 > eocd ||
      data.getUint32(offset, true) !== CENTRAL_SIGNATURE
    ) {
      invalid("The editor-input ZIP directory is invalid.");
    }
    const flags = data.getUint16(offset + 8, true);
    const compression = data.getUint16(offset + 10, true);
    const compressedSize = data.getUint32(offset + 20, true);
    const originalSize = data.getUint32(offset + 24, true);
    const nameLength = data.getUint16(offset + 28, true);
    const extraLength = data.getUint16(offset + 30, true);
    const commentLength = data.getUint16(offset + 32, true);
    const diskStart = data.getUint16(offset + 34, true);
    const externalAttributes = data.getUint32(offset + 38, true);
    const localOffset = data.getUint32(offset + 42, true);
    const end = offset + 46 + nameLength + extraLength + commentLength;
    if (
      end > eocd ||
      diskStart !== 0 ||
      (flags & ~0x0808) !== 0 ||
      (compression !== 0 && compression !== 8) ||
      compressedSize > MAX_EDITOR_INPUT_ARCHIVE_BYTES ||
      originalSize > MAX_EDITOR_INPUT_BYTES ||
      localOffset + 30 > directoryOffset ||
      data.getUint32(localOffset, true) !== LOCAL_SIGNATURE
    ) {
      invalid("The editor-input ZIP contains an unsupported entry.");
    }
    const nameStart = offset + 46;
    const name = zipName(bytes.subarray(nameStart, nameStart + nameLength));
    if (!EXPECTED_PATHS.has(name) || entries.has(name as EditorInputPath)) {
      invalid("The editor-input ZIP contains an unexpected entry.");
    }
    const madeBy = data.getUint16(offset + 4, true) >> 8;
    const unixMode = externalAttributes >>> 16;
    const unixRegular = (unixMode & 0o170000) === 0o100000;
    const dosDirectory = (externalAttributes & 0x10) !== 0;
    if (madeBy === 3 ? !unixRegular : dosDirectory) {
      invalid("The editor-input ZIP entries must be regular files.");
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
      ) !== name
    ) {
      invalid("The editor-input ZIP local entry is inconsistent.");
    }
    totalSize += originalSize;
    if (totalSize > MAX_EDITOR_INPUT_BYTES) {
      invalid("The editor-input ZIP exceeds the uncompressed size limit.");
    }
    entries.set(name as EditorInputPath, {
      originalSize,
    });
    offset = end;
  }
  if (offset !== eocd || entries.size !== EDITOR_INPUT_PATHS.length) {
    invalid("The editor-input ZIP directory is invalid.");
  }
  return entries;
}

function extractEditorInput(
  archiveBytes: Uint8Array,
): Record<EditorInputPath, Uint8Array> {
  const declared = validateZipDirectory(archiveBytes);
  const extracted = new Map<EditorInputPath, Uint8Array>();
  let total = 0;
  let failure: Error | null = null;
  const archive = new Unzip((file) => {
    if (
      !EXPECTED_PATHS.has(file.name) ||
      extracted.has(file.name as EditorInputPath)
    ) {
      failure = new Error("unexpected ZIP entry");
      file.terminate();
      return;
    }
    const path = file.name as EditorInputPath;
    const chunks: Uint8Array[] = [];
    let fileSize = 0;
    file.ondata = (error, chunk, final) => {
      if (error !== null) {
        failure = error;
        return;
      }
      fileSize += chunk.byteLength;
      total += chunk.byteLength;
      if (
        fileSize > (declared.get(path)?.originalSize ?? -1) ||
        total > MAX_EDITOR_INPUT_BYTES
      ) {
        failure = new Error("uncompressed editor input is too large");
        file.terminate();
        return;
      }
      chunks.push(chunk);
      if (!final) return;
      if (fileSize !== declared.get(path)?.originalSize) {
        failure = new Error("ZIP entry size mismatch");
        return;
      }
      const bytes = new Uint8Array(fileSize);
      let offset = 0;
      for (const item of chunks) {
        bytes.set(item, offset);
        offset += item.byteLength;
      }
      extracted.set(path, bytes);
    };
    file.start();
  });
  archive.register(UnzipInflate);
  try {
    archive.push(archiveBytes, true);
  } catch {
    invalid("The editor-input ZIP could not be decompressed.");
  }
  if (failure !== null || extracted.size !== EDITOR_INPUT_PATHS.length) {
    invalid("The editor-input ZIP could not be decompressed safely.");
  }
  return Object.fromEntries(extracted) as Record<EditorInputPath, Uint8Array>;
}

function utf8(bytes: Uint8Array, label: string): string {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    invalid(`${label} is not valid UTF-8.`);
  }
}

export function parseEditorInputArchive(
  archive: Uint8Array,
  expectedSourceCommit: string,
): EditorInputFiles {
  if (!COMMIT.test(expectedSourceCommit)) {
    throw new TypeError(
      "expectedSourceCommit must be a full lowercase Git SHA",
    );
  }
  const files = extractEditorInput(archive);
  utf8(files["edit/config.json"], "edit/config.json");
  utf8(files["edit/records.ttl"], "edit/records.ttl");
  let catalog: unknown;
  try {
    catalog = JSON.parse(
      utf8(
        files["edit/data/record-sources.json"],
        "edit/data/record-sources.json",
      ),
    ) as unknown;
  } catch (error) {
    if (error instanceof HttpError) throw error;
    invalid("edit/data/record-sources.json is not valid JSON.");
  }
  const value = object(catalog, "Editor record catalog");
  if (
    value.format !== "orinoco-static-record-sources" ||
    value.version !== 2 ||
    !Array.isArray(value.records) ||
    value.source_commit !== expectedSourceCommit
  ) {
    invalid(
      "The editor record catalog does not match the exact source commit.",
    );
  }
  return { files, sourceCommit: expectedSourceCommit };
}

function artifactCandidate(
  value: unknown,
  expectedName: string,
  now: number,
): ArtifactCandidate {
  const artifact = object(value, "Editor-input artifact");
  const workflow = object(artifact.workflow_run, "Artifact workflow run");
  const expiresAt = timestamp(artifact.expires_at, "Artifact expires_at");
  if (
    artifact.name !== expectedName ||
    artifact.expired !== false ||
    expiresAt <= now ||
    typeof workflow.head_sha !== "string" ||
    !COMMIT.test(workflow.head_sha) ||
    !Number.isSafeInteger(artifact.size_in_bytes) ||
    Number(artifact.size_in_bytes) < 1 ||
    Number(artifact.size_in_bytes) > MAX_EDITOR_INPUT_ARCHIVE_BYTES
  ) {
    invalid("The exact-head editor-input artifact is expired or mismatched.");
  }
  return {
    createdAt: timestamp(artifact.created_at, "Artifact created_at"),
    id: positiveInteger(artifact.id, "Artifact id"),
    runHeadSha: workflow.head_sha,
    runId: positiveInteger(workflow.id, "Artifact workflow-run id"),
  };
}

function verifySuccessfulRun(
  value: unknown,
  repository: string,
  defaultBranch: string,
  runId: number,
  artifactRunHeadSha: string,
  expectedHeadSha: string,
): void {
  const run = object(value, "Editor-input workflow run");
  const runRepository = object(run.repository, "Workflow-run repository");
  if (
    run.id !== runId ||
    run.name !== TRUSTED_WORKFLOW_NAME ||
    run.path !== TRUSTED_WORKFLOW_PATH ||
    !TRUSTED_WORKFLOW_EVENTS.has(String(run.event)) ||
    run.head_branch !== defaultBranch ||
    run.head_sha !== artifactRunHeadSha ||
    (run.event === "push" && run.head_sha !== expectedHeadSha) ||
    run.status !== "completed" ||
    run.conclusion !== "success" ||
    !Number.isSafeInteger(run.run_attempt) ||
    Number(run.run_attempt) < 1 ||
    typeof runRepository.full_name !== "string" ||
    runRepository.full_name.toLowerCase() !== repository.toLowerCase()
  ) {
    invalid(
      "The editor-input artifact was not produced by a successful exact-head run.",
    );
  }
}

export async function loadExactHeadEditorInput(
  github: EditorInputGitHub,
  repositoryValue: string,
  exactHeadSha: string,
  now: number = Date.now(),
): Promise<ExactHeadEditorInput> {
  const repository = parseRepository(repositoryValue);
  if (!COMMIT.test(exactHeadSha)) {
    throw new TypeError("exactHeadSha must be a full lowercase Git SHA");
  }
  if (!Number.isFinite(now)) throw new TypeError("now must be finite");
  const repositoryCoordinates = await github.repository(repository);
  const artifactName = `orinoco-shacl-vue-input-${exactHeadSha}`;
  const [owner, name] = splitRepository(repository);
  const listing = object(
    await github.json(
      `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}` +
        `/actions/artifacts?name=${encodeURIComponent(artifactName)}` +
        `&per_page=${ARTIFACT_PAGE_SIZE}&page=1`,
    ),
    "Actions artifact listing",
  );
  if (
    !Number.isSafeInteger(listing.total_count) ||
    Number(listing.total_count) < 1 ||
    Number(listing.total_count) > ARTIFACT_PAGE_SIZE ||
    !Array.isArray(listing.artifacts) ||
    listing.artifacts.length !== Number(listing.total_count)
  ) {
    invalid("GitHub did not return one bounded editor-input artifact listing.");
  }
  const candidates = listing.artifacts
    .filter(
      (item) =>
        item !== null &&
        typeof item === "object" &&
        !Array.isArray(item) &&
        (item as Record<string, unknown>).expired === false,
    )
    .map((item) => artifactCandidate(item, artifactName, now))
    .sort(
      (left, right) => right.createdAt - left.createdAt || right.id - left.id,
    );
  const artifact = candidates[0];
  if (artifact === undefined) {
    invalid("No unexpired exact-head editor-input artifact is available.");
  }
  const runPath =
    `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}` +
    `/actions/runs/${artifact.runId}`;
  verifySuccessfulRun(
    await github.json(runPath),
    repository,
    repositoryCoordinates.defaultBranch,
    artifact.runId,
    artifact.runHeadSha,
    exactHeadSha,
  );
  const parsed = parseEditorInputArchive(
    await github.artifactArchive(repository, artifact.id),
    exactHeadSha,
  );
  return {
    ...parsed,
    artifactId: artifact.id,
    headSha: exactHeadSha,
    workflowRunId: artifact.runId,
  };
}
