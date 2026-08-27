import { parseDocument } from "yaml";
import type {
  CandidateOperation,
  JsonObject,
  ReviewGrant,
  ReviewProposal,
} from "../../shared/contracts";
import { DEFAULT_CURATION_SERVICE_ORIGIN } from "../../shared/contracts";
import {
  canonicalJson,
  MAX_ARTIFACT_ARCHIVE_BYTES,
  MAX_REVIEW_CANDIDATES,
  MAX_REVIEW_PATHS,
  parseReviewBundle,
  type ReviewBundle,
  type ReviewBundleCandidate,
} from "./bundle";
import { GitHubClient } from "./github";
import { HttpError } from "./http";

const RECORD_ROOT = "metadata/records/";
const ANNOTATION_ROOT = "metadata/overlays/annotations/";
const COMMIT = /^[0-9a-f]{40}$/;
const SUPPORTED_ADAPTERS = new Set(["dump-research-info", "zotero"]);
const DATALAD_MARKER = "\n=== Do not change lines below ===\n";

export { MAX_REVIEW_CANDIDATES, MAX_REVIEW_PATHS } from "./bundle";

function object(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(
      502,
      "github_error",
      `GitHub returned an invalid ${label}.`,
    );
  }
  return value as Record<string, unknown>;
}

function text(value: unknown, label: string): string {
  if (typeof value !== "string" || !value || /[\r\n\0]/.test(value)) {
    throw new HttpError(
      502,
      "github_error",
      `GitHub returned an invalid ${label}.`,
    );
  }
  return value;
}

function commit(value: unknown, label: string): string {
  const result = text(value, label);
  if (!COMMIT.test(result)) {
    throw new HttpError(
      502,
      "github_error",
      `GitHub returned an invalid ${label}.`,
    );
  }
  return result;
}

function invalid(message: string): never {
  throw new HttpError(422, "invalid_proposal", message);
}

interface PullCoordinates {
  headSha: string;
  repository: string;
  url: string;
}

function pullCoordinates(
  value: unknown,
  requestedRepository: string,
  requestedNumber: number,
): PullCoordinates {
  const pull = object(value, "pull request");
  if (pull.number !== requestedNumber || pull.state !== "open") {
    invalid("The requested pull request is not an open review.");
  }
  const base = object(pull.base, "pull-request base");
  const head = object(pull.head, "pull-request head");
  const baseRepo = object(base.repo, "base repository");
  const repository = text(baseRepo.full_name, "base repository name");
  if (repository.toLowerCase() !== requestedRepository.toLowerCase()) {
    invalid("The pull request belongs to a different repository.");
  }
  return {
    headSha: commit(head.sha, "head SHA"),
    repository,
    url: text(pull.html_url, "pull-request URL"),
  };
}

function trailer(lines: string[], name: string): string {
  const prefix = `${name}: `;
  const matches = lines.filter((line) => line.startsWith(prefix));
  if (matches.length !== 1) {
    invalid(`The proposal commit must contain exactly one ${name} trailer.`);
  }
  const value = (matches[0] as string).slice(prefix.length);
  if (!value || value !== value.trim() || /[\r\n\0]/.test(value)) {
    invalid(`The proposal commit ${name} trailer is invalid.`);
  }
  return value;
}

function sourceCoordinate(value: string): JsonObject {
  let coordinate: unknown;
  try {
    coordinate = JSON.parse(value) as unknown;
  } catch {
    invalid("The proposal commit Curation-Source trailer is invalid JSON.");
  }
  if (
    coordinate === null ||
    typeof coordinate !== "object" ||
    Array.isArray(coordinate) ||
    Object.keys(coordinate).length === 0 ||
    canonicalJson(coordinate as JsonObject) !== value
  ) {
    invalid(
      "The proposal commit Curation-Source trailer is not canonical JSON.",
    );
  }
  return coordinate as JsonObject;
}

interface ProposalCommitCoordinates {
  adapter: string;
  baseSha: string;
  proposalSha: string;
  sourceCoordinate: JsonObject;
}

function proposalCommit(value: unknown): ProposalCommitCoordinates {
  const item = object(value, "proposal commit");
  const proposalSha = commit(item.sha, "proposal SHA");
  if (!Array.isArray(item.parents) || item.parents.length !== 1) {
    invalid("The proposal commit must have exactly one parent.");
  }
  const baseSha = commit(
    object(item.parents[0], "proposal parent").sha,
    "proposal parent SHA",
  );
  const data = object(item.commit, "proposal commit data");
  if (typeof data.message !== "string" || /\r|\0/.test(data.message)) {
    invalid("The proposal commit message is invalid.");
  }
  const marker = data.message.indexOf(DATALAD_MARKER);
  if (marker < 0) invalid("The proposal commit is not a DataLad run commit.");
  const lines = data.message.slice(0, marker).split("\n");
  const adapter = trailer(lines, "Curation-Adapter");
  if (!SUPPORTED_ADAPTERS.has(adapter)) invalid("Adapter is unsupported.");
  if (
    lines[0] !== `[DATALAD RUNCMD] chore(curation): propose ${adapter} metadata`
  ) {
    invalid("The proposal commit subject does not match its adapter.");
  }
  trailer(lines, "Curation-Adapter-Agent");
  if (trailer(lines, "Curation-Metadata-Base") !== baseSha) {
    invalid("The proposal metadata base does not match its sole parent.");
  }
  return {
    adapter,
    baseSha,
    proposalSha,
    sourceCoordinate: sourceCoordinate(trailer(lines, "Curation-Source")),
  };
}

interface ArtifactCoordinates {
  runId: number;
}

function artifactCoordinates(
  value: unknown,
  artifactId: number,
  proposalSha: string,
  baseSha: string,
): ArtifactCoordinates {
  const artifact = object(value, "artifact");
  if (
    artifact.id !== artifactId ||
    artifact.name !== `orinoco-curation-review-${proposalSha}` ||
    artifact.expired !== false ||
    !Number.isSafeInteger(artifact.size_in_bytes) ||
    Number(artifact.size_in_bytes) < 1 ||
    Number(artifact.size_in_bytes) > MAX_ARTIFACT_ARCHIVE_BYTES
  ) {
    invalid(
      "The selected review artifact is expired, mismatched, or too large.",
    );
  }
  const workflow = object(artifact.workflow_run, "artifact workflow run");
  if (
    !Number.isSafeInteger(workflow.id) ||
    Number(workflow.id) < 1 ||
    workflow.head_sha !== baseSha
  ) {
    invalid("The review artifact has no valid workflow run.");
  }
  return { runId: Number(workflow.id) };
}

function verifyWorkflowRun(
  value: unknown,
  repository: string,
  runId: number,
  baseSha: string,
): void {
  const run = object(value, "workflow run");
  const runRepository = object(run.repository, "workflow-run repository");
  if (
    run.id !== runId ||
    run.event !== "workflow_dispatch" ||
    run.head_sha !== baseSha ||
    !Number.isSafeInteger(run.run_attempt) ||
    Number(run.run_attempt) < 1 ||
    (run.status !== "in_progress" && run.status !== "completed") ||
    (run.status === "in_progress" && run.conclusion !== null) ||
    (run.status === "completed" && run.conclusion !== "success") ||
    text(
      runRepository.full_name,
      "workflow-run repository name",
    ).toLowerCase() !== repository.toLowerCase()
  ) {
    invalid("The artifact workflow run does not match this repository.");
  }
}

function operation(status: unknown): CandidateOperation {
  if (status === "added") return "add";
  if (status === "modified") return "modify";
  if (status === "removed") return "delete";
  invalid("Proposal record files must be added, modified, or removed.");
}

function validMetadataPath(value: string): boolean {
  const root = value.startsWith(RECORD_ROOT)
    ? RECORD_ROOT
    : value.startsWith(ANNOTATION_ROOT)
      ? ANNOTATION_ROOT
      : null;
  if (
    root === null ||
    (!value.endsWith(".yaml") && !value.endsWith(".yml")) ||
    /[\\\r\n\0]/.test(value)
  ) {
    return false;
  }
  return value
    .slice(root.length)
    .split("/")
    .every(
      (part) =>
        part.length > 0 &&
        part !== "." &&
        part !== ".." &&
        !part.startsWith("."),
    );
}

interface ProposalFiles {
  changedPaths: Set<string>;
  records: Map<string, CandidateOperation>;
}

function proposalFiles(
  value: Record<string, unknown>,
  proposalSha: string,
): ProposalFiles {
  if (value.sha !== proposalSha || !Array.isArray(value.files)) {
    throw new HttpError(
      502,
      "github_error",
      "GitHub returned an invalid proposal commit.",
    );
  }
  const changedPaths = new Set<string>();
  const records = new Map<string, CandidateOperation>();
  for (const fileValue of value.files) {
    const file = object(fileValue, "proposal file");
    const filename = text(file.filename, "proposal filename");
    if (!validMetadataPath(filename)) {
      invalid("The proposal commit changes a path outside the metadata roots.");
    }
    if (file.previous_filename !== undefined || changedPaths.has(filename)) {
      invalid("Metadata renames and repeated paths are not supported.");
    }
    const fileOperation = operation(file.status);
    changedPaths.add(filename);
    if (filename.startsWith(RECORD_ROOT)) records.set(filename, fileOperation);
  }
  if (
    records.size === 0 ||
    records.size > MAX_REVIEW_CANDIDATES ||
    changedPaths.size > MAX_REVIEW_PATHS
  ) {
    invalid("The proposal has an unsupported number of candidate records.");
  }
  for (const path of changedPaths) {
    if (!path.startsWith(ANNOTATION_ROOT)) continue;
    const record = `${RECORD_ROOT}${path.slice(ANNOTATION_ROOT.length)}`;
    if (!records.has(record)) {
      invalid(
        "The proposal changes an annotation without its candidate record.",
      );
    }
  }
  return { changedPaths, records };
}

function sameSet(left: Iterable<string>, right: Iterable<string>): boolean {
  const expected = new Set(left);
  const observed = new Set(right);
  return (
    expected.size === observed.size &&
    [...expected].every((item) => observed.has(item))
  );
}

function verifyBundleCoordinates(
  bundle: ReviewBundle,
  pull: PullCoordinates,
  pullRequest: number,
  proposal: ProposalCommitCoordinates,
  runId: number,
): void {
  if (
    bundle.repository.toLowerCase() !== pull.repository.toLowerCase() ||
    bundle.pull_request !== pullRequest ||
    bundle.workflow_run_id !== runId ||
    bundle.adapter !== proposal.adapter ||
    bundle.metadata_base_sha !== proposal.baseSha ||
    bundle.proposal_sha !== proposal.proposalSha ||
    canonicalJson(bundle.source_coordinate) !==
      canonicalJson(proposal.sourceCoordinate)
  ) {
    invalid("The review artifact does not match the selected proposal.");
  }
}

function bundleCandidates(
  bundle: ReviewBundle,
  files: ProposalFiles,
): Map<string, ReviewBundleCandidate> {
  const byPath = new Map(
    bundle.candidates.map((candidate) => [candidate.record_path, candidate]),
  );
  if (
    byPath.size !== files.records.size ||
    !sameSet(
      bundle.candidates.flatMap((candidate) => candidate.paths),
      files.changedPaths,
    )
  ) {
    invalid("The review artifact does not cover the proposal metadata diff.");
  }
  for (const [path, fileOperation] of files.records) {
    const candidate = byPath.get(path);
    if (candidate === undefined || candidate.operation !== fileOperation) {
      invalid("A review artifact operation does not match the proposal diff.");
    }
    const expectedPaths = [path];
    const companion = `${ANNOTATION_ROOT}${path.slice(RECORD_ROOT.length)}`;
    if (files.changedPaths.has(companion)) expectedPaths.push(companion);
    if (!sameSet(candidate.paths, expectedPaths)) {
      invalid("A review artifact candidate names incorrect metadata paths.");
    }
  }
  return byPath;
}

function recordPid(value: string, label: string): string {
  let parsed: unknown;
  try {
    const document = parseDocument(value, {
      prettyErrors: false,
      schema: "core",
      uniqueKeys: true,
    });
    if (document.errors.length > 0) throw new Error("invalid YAML");
    parsed = document.toJS({ maxAliasCount: 0 }) as unknown;
  } catch {
    invalid(`${label} is not a valid metadata record.`);
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    invalid(`${label} is not a metadata mapping.`);
  }
  const pid = (parsed as Record<string, unknown>).pid;
  if (
    typeof pid !== "string" ||
    !pid ||
    pid !== pid.trim() ||
    /[\r\n\0]/.test(pid)
  ) {
    invalid(`${label} has no valid PID.`);
  }
  return pid;
}

interface ReviewSiteCoordinates {
  reviewServiceOrigin: string;
  reviewSiteUrl: string;
}

function safeSiteUrl(value: unknown): URL | null {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.length > 2_048 ||
    value !== value.trim() ||
    /[\\?#\u0000-\u001f\u007f]/.test(value)
  ) {
    return null;
  }
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  const loopback =
    url.protocol === "http:" &&
    (url.hostname === "127.0.0.1" || url.hostname === "localhost");
  if (
    (url.protocol !== "https:" && !loopback) ||
    url.username !== "" ||
    url.password !== "" ||
    url.search !== "" ||
    url.hash !== ""
  ) {
    return null;
  }
  return url;
}

function reviewSiteCoordinates(value: string | null): ReviewSiteCoordinates {
  if (value === null) {
    invalid("The proposal metadata base has no orinoco.yaml configuration.");
  }
  let parsed: unknown;
  try {
    const document = parseDocument(value, {
      prettyErrors: false,
      schema: "core",
      uniqueKeys: true,
    });
    if (document.errors.length > 0 || document.warnings.length > 0) {
      throw new Error("invalid YAML");
    }
    parsed = document.toJS({ maxAliasCount: 0 }) as unknown;
  } catch {
    invalid("The proposal metadata-base orinoco.yaml is invalid.");
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    invalid("The proposal metadata-base orinoco.yaml is not a mapping.");
  }
  const config = parsed as Record<string, unknown>;
  if (config.contract_version !== 2) {
    invalid("The proposal metadata-base orinoco.yaml contract is unsupported.");
  }
  if (
    config.site === null ||
    typeof config.site !== "object" ||
    Array.isArray(config.site)
  ) {
    invalid("The proposal metadata-base orinoco.yaml site is not a mapping.");
  }
  const site = config.site as Record<string, unknown>;
  const baseUrl = safeSiteUrl(site.base_url);
  if (baseUrl === null) {
    invalid("The proposal metadata-base site.base_url is unsafe.");
  }
  const serviceValue = site.curation_service ?? DEFAULT_CURATION_SERVICE_ORIGIN;
  const serviceUrl = safeSiteUrl(serviceValue);
  if (
    serviceUrl === null ||
    serviceUrl.pathname !== "/" ||
    (serviceValue !== serviceUrl.origin &&
      serviceValue !== `${serviceUrl.origin}/`)
  ) {
    invalid(
      "The proposal metadata-base site.curation_service is not an origin.",
    );
  }
  if (!baseUrl.pathname.endsWith("/")) baseUrl.pathname += "/";
  return {
    reviewServiceOrigin: serviceUrl.origin,
    reviewSiteUrl: new URL("review/", baseUrl).toString(),
  };
}

export function requireReviewTransport(
  proposal: ReviewProposal,
  grant: ReviewGrant,
  serviceOrigin: string,
): void {
  let reviewOrigin: string;
  try {
    reviewOrigin = new URL(proposal.review_site_url).origin;
  } catch {
    throw new HttpError(
      403,
      "review_transport_mismatch",
      "This review does not match the repository's trusted deployment.",
    );
  }
  if (
    proposal.review_service_origin !== serviceOrigin ||
    reviewOrigin !== grant.review_origin
  ) {
    throw new HttpError(
      403,
      "review_transport_mismatch",
      "This review does not match the repository's trusted deployment.",
    );
  }
}

export async function loadReviewProposal(
  github: GitHubClient,
  repository: string,
  pullRequest: number,
  artifactId: number,
): Promise<ReviewProposal> {
  const pull = pullCoordinates(
    await github.pullRequest(repository, pullRequest),
    repository,
    pullRequest,
  );
  const proposal = proposalCommit(
    await github.firstPullRequestCommit(repository, pullRequest),
  );
  const artifact = artifactCoordinates(
    await github.artifactMetadata(repository, artifactId),
    artifactId,
    proposal.proposalSha,
    proposal.baseSha,
  );
  verifyWorkflowRun(
    await github.workflowRun(repository, artifact.runId),
    pull.repository,
    artifact.runId,
    proposal.baseSha,
  );
  const bundle = parseReviewBundle(
    await github.artifactArchive(repository, artifactId),
  );
  verifyBundleCoordinates(bundle, pull, pullRequest, proposal, artifact.runId);
  const files = proposalFiles(
    await github.commit(repository, proposal.proposalSha),
    proposal.proposalSha,
  );
  const presentation = bundleCandidates(bundle, files);

  const recordPaths = [...files.records.keys()].sort();
  const requests = [
    { key: "site-config", path: "orinoco.yaml", ref: proposal.baseSha },
    ...recordPaths.flatMap((path, index) => [
      { key: `before:${index}`, path, ref: proposal.baseSha },
      { key: `proposed:${index}`, path, ref: proposal.proposalSha },
      { key: `after:${index}`, path, ref: pull.headSha },
    ]),
  ];
  const contents = await github.contents(repository, requests);
  const review = reviewSiteCoordinates(contents.get("site-config") ?? null);
  const candidates = recordPaths.map((path, index) => {
    const item = presentation.get(path);
    if (item === undefined) throw new Error("candidate alignment was lost");
    const before = contents.get(`before:${index}`) ?? null;
    const proposed = contents.get(`proposed:${index}`) ?? null;
    const after = contents.get(`after:${index}`) ?? null;
    if (
      (item.operation === "add" && (before !== null || proposed === null)) ||
      (item.operation === "modify" && (before === null || proposed === null)) ||
      (item.operation === "delete" && (before === null || proposed !== null))
    ) {
      invalid("Initial record content does not match the proposal operation.");
    }
    const identityRecord = item.operation === "delete" ? before : proposed;
    if (
      identityRecord === null ||
      recordPid(identityRecord, `Candidate ${path}`) !== item.pid
    ) {
      invalid("A review artifact PID does not match its metadata record.");
    }
    return {
      after,
      before,
      blockers: item.blockers,
      claim_sha256: item.claim_sha256,
      friendly_id: item.friendly_id,
      label: item.label,
      operation: item.operation,
      pid: item.pid,
      record_path: path,
      source_namespace: item.source_namespace,
      source_record_id: item.source_record_id,
    };
  });

  return {
    adapter: proposal.adapter,
    candidates,
    head_sha: pull.headSha,
    proposal_sha: proposal.proposalSha,
    pull_request: pullRequest,
    pull_request_url: pull.url,
    repository: pull.repository,
    review_service_origin: review.reviewServiceOrigin,
    review_site_url: review.reviewSiteUrl,
    source_coordinate: proposal.sourceCoordinate,
  };
}
