import type {
  ShaclProposalRequest,
  ShaclProposalTarget,
  ShaclReviewBundle,
  ShaclReviewRecord,
} from "../../shared/contracts";
import { MAX_SHACL_BUNDLE_BYTES } from "../../shared/contracts";
import {
  type MetadataRoots,
  validRepositoryYamlPath,
  validYamlPathBelow,
} from "../../shared/metadata";
import { utf8 } from "./encoding";
import { HttpError, requireExactKeys } from "./http";
import { parseRepository } from "./input";

export const SHACL_BUNDLE_PATH = ".orinoco-lite/shacl-vue-review-bundle.json";
export { MAX_SHACL_BUNDLE_BYTES };
export const MAX_SHACL_PROPOSAL_BODY_BYTES = MAX_SHACL_BUNDLE_BYTES + 64 * 1024;

const COMMIT = /^[0-9a-f]{40}$/;
const DIGEST = /^[0-9a-f]{64}$/;

function invalid(message: string): never {
  throw new HttpError(400, "invalid_shacl_bundle", message);
}

function oneLine(value: unknown, label: string): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > 4_096 ||
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    invalid(`SHACL review bundle ${label} is invalid.`);
  }
  return value;
}

function validRecordPath(value: string): boolean {
  return validRepositoryYamlPath(value);
}

function parseRecord(value: unknown): ShaclReviewRecord {
  requireExactKeys(
    value,
    ["pid", "rdf_turtle", "schema_type", "source_path", "source_sha256"],
    "SHACL review bundle record",
  );
  const pid = oneLine(value.pid, "record PID");
  const schemaType = oneLine(value.schema_type, `schema type for ${pid}`);
  const sourcePath = oneLine(value.source_path, `source path for ${pid}`);
  if (!validRecordPath(sourcePath)) {
    invalid(`SHACL review bundle source path for ${pid} is invalid.`);
  }
  if (
    typeof value.source_sha256 !== "string" ||
    !DIGEST.test(value.source_sha256)
  ) {
    invalid(`SHACL review bundle source digest for ${pid} is invalid.`);
  }
  if (
    typeof value.rdf_turtle !== "string" ||
    value.rdf_turtle.trim().length === 0 ||
    value.rdf_turtle.includes("\0")
  ) {
    invalid(`SHACL review bundle RDF for ${pid} is invalid.`);
  }
  return {
    pid,
    rdf_turtle: value.rdf_turtle,
    schema_type: schemaType,
    source_path: sourcePath,
    source_sha256: value.source_sha256,
  };
}

export function serializeShaclReviewBundle(
  value: ShaclReviewBundle,
): Uint8Array {
  return utf8(`${JSON.stringify(value, null, 2)}\n`);
}

export function parseShaclReviewBundle(value: unknown): ShaclReviewBundle {
  requireExactKeys(
    value,
    ["format", "records", "source_commit", "version"],
    "SHACL review bundle",
  );
  if (
    value.format !== "orinoco-shacl-review-bundle" ||
    value.version !== 2 ||
    typeof value.source_commit !== "string" ||
    !COMMIT.test(value.source_commit) ||
    !Array.isArray(value.records) ||
    value.records.length === 0 ||
    value.records.length > 50
  ) {
    invalid("SHACL review bundle does not satisfy version 2.");
  }
  const records = value.records.map(parseRecord);
  const pids = new Set<string>();
  const paths = new Set<string>();
  for (const record of records) {
    if (pids.has(record.pid) || paths.has(record.source_path)) {
      invalid("SHACL review bundle contains duplicate record coordinates.");
    }
    pids.add(record.pid);
    paths.add(record.source_path);
  }
  const bundle: ShaclReviewBundle = {
    format: "orinoco-shacl-review-bundle",
    records,
    source_commit: value.source_commit,
    version: 2,
  };
  if (serializeShaclReviewBundle(bundle).byteLength > MAX_SHACL_BUNDLE_BYTES) {
    throw new HttpError(
      413,
      "shacl_bundle_too_large",
      "The SHACL review bundle exceeds 10 MiB.",
    );
  }
  return bundle;
}

export function validateShaclRecordPaths(
  bundle: ShaclReviewBundle,
  roots: MetadataRoots,
): void {
  if (
    bundle.records.some(
      (record) => !validYamlPathBelow(record.source_path, roots.records),
    )
  ) {
    invalid(
      "The SHACL review bundle contains a path outside configured metadata records.",
    );
  }
}

function parseTarget(value: unknown): ShaclProposalTarget {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(
      400,
      "invalid_shacl_proposal",
      "The SHACL proposal target is invalid.",
    );
  }
  if ((value as Record<string, unknown>).kind === "standalone") {
    requireExactKeys(value, ["kind"], "standalone SHACL proposal target");
    return { kind: "standalone" };
  }
  requireExactKeys(
    value,
    ["expected_head_sha", "kind", "pull_request"],
    "pull-request SHACL proposal target",
  );
  if (
    value.kind !== "pull_request" ||
    typeof value.expected_head_sha !== "string" ||
    !COMMIT.test(value.expected_head_sha) ||
    !Number.isSafeInteger(value.pull_request) ||
    Number(value.pull_request) < 1 ||
    Number(value.pull_request) > 9_999_999_999
  ) {
    throw new HttpError(
      400,
      "invalid_shacl_proposal",
      "The SHACL pull-request target is invalid.",
    );
  }
  return {
    expected_head_sha: value.expected_head_sha,
    kind: "pull_request",
    pull_request: Number(value.pull_request),
  };
}

export function parseShaclProposalRequest(
  value: unknown,
): ShaclProposalRequest {
  requireExactKeys(
    value,
    ["acknowledge_public_data", "bundle", "format", "repository", "target"],
    "SHACL proposal",
  );
  if (
    value.format !== "orinoco-lite-shacl-proposal-v1" ||
    value.acknowledge_public_data !== true
  ) {
    throw new HttpError(
      400,
      "invalid_shacl_proposal",
      value.acknowledge_public_data !== true
        ? "The SHACL proposal requires explicit confirmation that its bundle contains no secrets and is approved for public Git history."
        : "The SHACL proposal format is invalid.",
    );
  }
  const bundle = parseShaclReviewBundle(value.bundle);
  const target = parseTarget(value.target);
  if (
    target.kind === "pull_request" &&
    target.expected_head_sha !== bundle.source_commit
  ) {
    throw new HttpError(
      409,
      "stale_shacl_proposal",
      "The SHACL bundle source commit does not match the expected pull-request head.",
    );
  }
  return {
    acknowledge_public_data: true,
    bundle,
    format: "orinoco-lite-shacl-proposal-v1",
    repository: parseRepository(
      typeof value.repository === "string" ? value.repository : null,
    ),
    target,
  };
}
