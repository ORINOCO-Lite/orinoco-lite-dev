import { useEffect, useRef, useState } from "react";
import {
  isSafeEditorOrigin,
  isSafeReviewOrigin,
  isReviewHandoffNonce,
  isShaclHandoffNonce,
  MAX_SHACL_BUNDLE_BYTES,
  type ShaclProposalReadyMessage,
  type CurationSubmission,
  type ReviewCoordinates,
  type ReviewConfirmationPendingMessage,
  type ReviewConfirmationReadyMessage,
  type ReviewPostStartedMessage,
  type ReviewProposal,
  type ReviewProposalMessage,
  type ReviewSubmissionResultMessage,
  type ReviewTransportReadyMessage,
  type SessionStatus,
  type ShaclBundleMessage,
  type ShaclProposalRequest,
  type ShaclProposalResult,
  type ShaclReviewBundle,
} from "../shared/contracts";
import {
  ApiError,
  authenticationUrl,
  loadProposal,
  loadSession,
  logout,
  proposeShaclEdit,
  shaclAuthenticationUrl,
  submitDecisions,
} from "./api";

interface Target {
  artifactId: number;
  handoffNonce: string;
  pullRequest: number;
  repository: string;
  reviewOrigin: string;
}

interface BoundReviewProposal extends ReviewProposal {
  review_service_origin: string;
  review_site_url: string;
}

interface ShaclTarget {
  editorOrigin?: string;
  expectedHeadSha?: string;
  handoffNonce?: string;
  pullRequest?: number;
  repository: string;
}

function currentTarget(): Target | null {
  if (
    window.location.pathname !== "/review-transport" &&
    window.location.pathname !== "/review-transport/"
  ) {
    return null;
  }
  const query = new URLSearchParams(window.location.search);
  const allowed = new Set([
    "artifact_id",
    "handoff_nonce",
    "pull_request",
    "repository",
    "review_origin",
  ]);
  if ([...query.keys()].some((key) => !allowed.has(key))) return null;
  const artifact = query.get("artifact_id");
  const handoffNonce = query.get("handoff_nonce");
  const repository = query.get("repository");
  const number = query.get("pull_request");
  const reviewOrigin = query.get("review_origin");
  if (
    [...allowed].some((key) => query.getAll(key).length !== 1) ||
    artifact === null ||
    !/^[1-9][0-9]{0,15}$/.test(artifact) ||
    repository === null ||
    !/^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/.test(
      repository,
    ) ||
    number === null ||
    !/^[1-9][0-9]{0,9}$/.test(number) ||
    !isSafeReviewOrigin(reviewOrigin) ||
    !isReviewHandoffNonce(handoffNonce)
  ) {
    return null;
  }
  const artifactId = Number(artifact);
  if (!Number.isSafeInteger(artifactId)) return null;
  return {
    artifactId,
    handoffNonce,
    pullRequest: Number(number),
    repository,
    reviewOrigin,
  };
}

function validRepository(value: string | null): value is string {
  return (
    value !== null &&
    /^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/.test(
      value,
    ) &&
    !value.includes("..")
  );
}

function currentShaclTarget(): ShaclTarget | null {
  if (
    window.location.pathname !== "/edit" &&
    window.location.pathname !== "/edit/"
  ) {
    return null;
  }
  const query = new URLSearchParams(window.location.search);
  const allowed = new Set([
    "editor_origin",
    "expected_head_sha",
    "handoff_nonce",
    "pull_request",
    "repository",
  ]);
  if ([...query.keys()].some((key) => !allowed.has(key))) return null;
  const repository = query.get("repository");
  if (query.getAll("repository").length !== 1 || !validRepository(repository)) {
    return null;
  }
  const pullValues = query.getAll("pull_request");
  const headValues = query.getAll("expected_head_sha");
  const editorOrigins = query.getAll("editor_origin");
  const handoffNonces = query.getAll("handoff_nonce");
  if (
    (editorOrigins.length === 0 && handoffNonces.length !== 0) ||
    (editorOrigins.length !== 0 && handoffNonces.length === 0) ||
    editorOrigins.length > 1 ||
    handoffNonces.length > 1 ||
    (editorOrigins.length === 1 &&
      (!isSafeEditorOrigin(editorOrigins[0]) ||
        !isShaclHandoffNonce(handoffNonces[0])))
  ) {
    return null;
  }
  const handoff =
    editorOrigins.length === 1
      ? {
          editorOrigin: editorOrigins[0],
          handoffNonce: handoffNonces[0],
        }
      : {};
  if (pullValues.length === 0 && headValues.length === 0) {
    return { repository, ...handoff };
  }
  if (
    pullValues.length !== 1 ||
    headValues.length !== 1 ||
    !/^[1-9][0-9]{0,9}$/.test(pullValues[0] ?? "") ||
    !/^[0-9a-f]{40}$/.test(headValues[0] ?? "")
  ) {
    return null;
  }
  return {
    expectedHeadSha: headValues[0],
    pullRequest: Number(pullValues[0]),
    repository,
    ...handoff,
  };
}

function message(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "The review could not be loaded.";
}

function retrySafeSubmissionFailure(error: unknown): boolean {
  return error instanceof ApiError && error.status >= 400 && error.status < 500;
}

function SignIn({ target }: { target: Target }): React.JSX.Element {
  return (
    <main className="landing" id="main-content">
      <p className="eyebrow">Authenticated review</p>
      <h1>Sign in to review pull request #{target.pullRequest}</h1>
      <p className="lede">
        GitHub limits access to collaborators with write or admin permission.
        The short-lived session is used only to read this proposal and its
        presentation artifact, then post your decision comment.
      </p>
      <a
        className="button-link"
        href={authenticationUrl(
          target.repository,
          target.pullRequest,
          target.artifactId,
          target.reviewOrigin,
          target.handoffNonce,
        )}
        rel="noreferrer"
        target="orinoco-review-auth"
      >
        Continue with GitHub
      </a>
      <p className="quiet">Repository: {target.repository}</p>
    </main>
  );
}

function matchingReviewGrant(
  session: Extract<SessionStatus, { authenticated: true }>,
  target: Target,
): boolean {
  const grant = session.review_grant;
  return (
    grant !== null &&
    grant.artifact_id === target.artifactId &&
    grant.handoff_nonce === target.handoffNonce &&
    grant.pull_request === target.pullRequest &&
    grant.repository.toLowerCase() === target.repository.toLowerCase() &&
    grant.review_origin === target.reviewOrigin
  );
}

function coordinates(target: Target): ReviewCoordinates {
  return {
    artifact_id: target.artifactId,
    handoff_nonce: target.handoffNonce,
    pull_request: target.pullRequest,
    repository: target.repository,
  };
}

function exactCoordinates(
  value: Record<string, unknown>,
  target: Target,
): boolean {
  return (
    value.artifact_id === target.artifactId &&
    value.handoff_nonce === target.handoffNonce &&
    value.pull_request === target.pullRequest &&
    typeof value.repository === "string" &&
    value.repository.toLowerCase() === target.repository.toLowerCase()
  );
}

function sameJson(
  expected: unknown,
  observed: unknown,
  seen = new WeakSet<object>(),
): boolean {
  if (expected === observed) return true;
  if (
    expected === null ||
    observed === null ||
    typeof expected !== "object" ||
    typeof observed !== "object" ||
    Array.isArray(expected) !== Array.isArray(observed) ||
    seen.has(observed)
  ) {
    return false;
  }
  seen.add(observed);
  if (Array.isArray(expected) && Array.isArray(observed)) {
    if (expected.length !== observed.length) return false;
    return expected.every((item, index) =>
      sameJson(item, observed[index], seen),
    );
  }
  const expectedRecord = expected as Record<string, unknown>;
  const observedRecord = observed as Record<string, unknown>;
  const expectedKeys = Object.keys(expectedRecord).sort();
  const observedKeys = Object.keys(observedRecord).sort();
  return (
    expectedKeys.length === observedKeys.length &&
    expectedKeys.every(
      (key, index) =>
        key === observedKeys[index] &&
        sameJson(expectedRecord[key], observedRecord[key], seen),
    )
  );
}

function verifiedSubmission(
  value: unknown,
  proposal: BoundReviewProposal,
  target: Target,
): CurationSubmission | null {
  if (
    !exactKeys(value, [
      "adapter",
      "decisions",
      "format",
      "head_sha",
      "proposal_sha",
      "pull_request",
      "repository",
      "source_coordinate",
    ])
  ) {
    return null;
  }
  const submitted = value as Record<string, unknown>;
  if (
    submitted.adapter !== proposal.adapter ||
    submitted.format !== "orinoco-lite-curation-submission-v1" ||
    submitted.head_sha !== proposal.head_sha ||
    submitted.proposal_sha !== proposal.proposal_sha ||
    submitted.pull_request !== target.pullRequest ||
    typeof submitted.repository !== "string" ||
    submitted.repository.toLowerCase() !== target.repository.toLowerCase() ||
    !sameJson(proposal.source_coordinate, submitted.source_coordinate) ||
    !Array.isArray(submitted.decisions) ||
    submitted.decisions.length !== proposal.candidates.length
  ) {
    return null;
  }
  for (let index = 0; index < proposal.candidates.length; index += 1) {
    const candidate = proposal.candidates[index];
    const decision = submitted.decisions[index];
    if (
      candidate === undefined ||
      !exactKeys(decision, ["disposition", "operation", "pid", "record_path"])
    ) {
      return null;
    }
    const item = decision as Record<string, unknown>;
    if (
      (item.disposition !== "accept" &&
        item.disposition !== "reject" &&
        item.disposition !== "defer") ||
      item.operation !== candidate.operation ||
      item.pid !== candidate.pid ||
      item.record_path !== candidate.record_path
    ) {
      return null;
    }
  }
  return submitted as unknown as CurationSubmission;
}

function boundReviewProposal(
  value: ReviewProposal,
  target: Target,
): BoundReviewProposal | null {
  const record = value as ReviewProposal & {
    review_service_origin?: unknown;
    review_site_url?: unknown;
  };
  if (
    record.review_service_origin !== window.location.origin ||
    !oneLine(record.review_site_url)
  ) {
    return null;
  }
  let site: URL;
  try {
    site = new URL(record.review_site_url);
  } catch {
    return null;
  }
  if (
    site.href !== record.review_site_url ||
    site.origin !== target.reviewOrigin ||
    !site.pathname.endsWith("/review/") ||
    site.search !== "" ||
    site.hash !== "" ||
    value.pull_request !== target.pullRequest ||
    value.repository.toLowerCase() !== target.repository.toLowerCase()
  ) {
    return null;
  }
  return record as BoundReviewProposal;
}

interface TransportRelayState {
  active: boolean;
  confirmationAcknowledged: boolean;
  opener: Window;
  postStarted: boolean;
  proposalSent: boolean;
  resultSent: boolean;
  submissionAccepted: boolean;
}

interface ReviewTransportProps {
  proposal: BoundReviewProposal;
  session: Extract<SessionStatus, { authenticated: true }>;
  target: Target;
}

function ReviewTransport({
  proposal,
  session,
  target,
}: ReviewTransportProps): React.JSX.Element {
  const relay = useRef<TransportRelayState | null>(null);
  const [submission, setSubmission] = useState<CurationSubmission | null>(null);
  const [feedback, setFeedback] = useState(
    "Waiting for the deployed review page to request the verified proposal.",
  );
  const [confirmationReady, setConfirmationReady] = useState(false);
  const [posting, setPosting] = useState(false);

  useEffect(() => {
    const opener = window.opener;
    if (opener === null) {
      setFeedback(
        "This transport must be opened from the deployed downstream review page.",
      );
      return;
    }
    const state: TransportRelayState = {
      active: true,
      confirmationAcknowledged: false,
      opener,
      postStarted: false,
      proposalSent: false,
      resultSent: false,
      submissionAccepted: false,
    };
    relay.current = state;

    function postedMessage(event: MessageEvent<unknown>): void {
      if (
        !state.active ||
        event.source !== opener ||
        event.origin !== target.reviewOrigin ||
        event.data === null ||
        typeof event.data !== "object" ||
        Array.isArray(event.data)
      ) {
        return;
      }
      const value = event.data as Record<string, unknown>;
      if (value.format === "orinoco-lite-review-proposal-request-v1") {
        if (
          state.proposalSent ||
          !exactKeys(value, [
            "artifact_id",
            "format",
            "handoff_nonce",
            "pull_request",
            "repository",
          ]) ||
          !exactCoordinates(value, target)
        ) {
          return;
        }
        state.proposalSent = true;
        const response: ReviewProposalMessage = {
          ...coordinates(target),
          format: "orinoco-lite-review-proposal-message-v1",
          login: session.login,
          proposal,
        };
        opener.postMessage(response, target.reviewOrigin);
        setFeedback(
          "The verified proposal is connected to the downstream review page.",
        );
        return;
      }
      if (value.format === "orinoco-lite-review-confirmation-ready-v1") {
        if (
          !state.submissionAccepted ||
          state.confirmationAcknowledged ||
          state.postStarted ||
          !exactKeys(value, [
            "artifact_id",
            "format",
            "handoff_nonce",
            "pull_request",
            "repository",
          ]) ||
          !exactCoordinates(value, target)
        ) {
          return;
        }
        state.confirmationAcknowledged = true;
        setConfirmationReady(true);
        setFeedback(
          "The downstream review is waiting for this final confirmation.",
        );
        return;
      }
      if (value.format !== "orinoco-lite-review-submission-message-v1") return;
      if (
        !state.proposalSent ||
        state.submissionAccepted ||
        !exactKeys(value, [
          "artifact_id",
          "format",
          "handoff_nonce",
          "pull_request",
          "repository",
          "submission",
        ]) ||
        !exactCoordinates(value, target)
      ) {
        return;
      }
      const accepted = verifiedSubmission(value.submission, proposal, target);
      if (accepted === null) return;
      state.submissionAccepted = true;
      setSubmission(accepted);
      const acknowledgement: ReviewConfirmationPendingMessage = {
        ...coordinates(target),
        format: "orinoco-lite-review-confirmation-pending-v1",
      };
      opener.postMessage(acknowledgement, target.reviewOrigin);
      setFeedback(
        "Confirm this read-only decision summary before posting to GitHub.",
      );
    }

    window.addEventListener("message", postedMessage);
    const ready: ReviewTransportReadyMessage = {
      ...coordinates(target),
      format: "orinoco-lite-review-transport-ready-v1",
    };
    opener.postMessage(ready, target.reviewOrigin);
    return () => {
      state.active = false;
      if (relay.current === state) relay.current = null;
      window.removeEventListener("message", postedMessage);
    };
  }, [
    proposal,
    session.login,
    target.artifactId,
    target.handoffNonce,
    target.pullRequest,
    target.repository,
    target.reviewOrigin,
  ]);

  async function confirmPost(): Promise<void> {
    const state = relay.current;
    if (
      state === null ||
      !state.active ||
      state.opener.closed ||
      submission === null ||
      !state.confirmationAcknowledged ||
      state.postStarted ||
      state.resultSent
    ) {
      return;
    }
    state.postStarted = true;
    const started: ReviewPostStartedMessage = {
      ...coordinates(target),
      format: "orinoco-lite-review-post-started-v1",
    };
    state.opener.postMessage(started, target.reviewOrigin);
    setPosting(true);
    setFeedback("Posting the confirmed decision state to GitHub…");
    let response: ReviewSubmissionResultMessage;
    try {
      const result = await submitDecisions(
        submission,
        session.csrf_token,
        target.artifactId,
      );
      response = {
        ...coordinates(target),
        comment_url: result.comment_url,
        error: null,
        format: "orinoco-lite-review-submission-result-v1",
        retry_safe: false,
      };
      setFeedback("The authenticated decision comment was posted to GitHub.");
    } catch (error) {
      response = {
        ...coordinates(target),
        comment_url: null,
        error: message(error),
        format: "orinoco-lite-review-submission-result-v1",
        retry_safe: retrySafeSubmissionFailure(error),
      };
      setFeedback(
        response.error ?? "The confirmed decisions could not be posted.",
      );
    }
    if (state.active && !state.resultSent) {
      state.resultSent = true;
      state.opener.postMessage(response, target.reviewOrigin);
    }
    setPosting(false);
  }

  if (submission !== null) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Authenticated GitHub confirmation</p>
        <h1>Confirm decisions before posting</h1>
        <p className="lede">
          The downstream site collected these choices. This central-origin page
          is the final read-only confirmation before the authenticated write.
        </p>
        <dl>
          <dt>Signed in as</dt>
          <dd>{session.login}</dd>
          <dt>Repository</dt>
          <dd>{target.repository}</dd>
          <dt>Pull request</dt>
          <dd>#{target.pullRequest}</dd>
          <dt>Proposal SHA</dt>
          <dd>{proposal.proposal_sha}</dd>
          <dt>Head SHA</dt>
          <dd>{proposal.head_sha}</dd>
        </dl>
        <h2>Complete decision state</h2>
        <ul aria-label="Confirmed decisions">
          {proposal.candidates.map((candidate, index) => (
            <li key={candidate.record_path}>
              <code>{candidate.record_path}</code> ({candidate.friendly_id}) →{" "}
              <strong>{submission.decisions[index]?.disposition}</strong>
            </li>
          ))}
        </ul>
        <button
          disabled={
            posting || !confirmationReady || relay.current?.postStarted === true
          }
          onClick={() => void confirmPost()}
          type="button"
        >
          {posting
            ? "Posting confirmed decisions…"
            : !confirmationReady
              ? "Waiting for downstream acknowledgement…"
              : "Post these decisions to GitHub"}
        </button>
        <p className="feedback" role="status">
          {feedback}
        </p>
      </main>
    );
  }

  return (
    <main className="landing" id="main-content">
      <p className="eyebrow">Authenticated GitHub transport</p>
      <h1>Connected to the downstream review</h1>
      <p className="lede">
        Candidate review stays in the deployed static website. Keep this small
        window open while it relays the verified proposal. GitHub posting
        requires a separate confirmation here; no token is sent downstream.
      </p>
      <p className="feedback" role="status">
        {feedback}
      </p>
      <p className="quiet">
        {target.repository} pull request #{target.pullRequest}; signed in as{" "}
        {session.login}.
      </p>
    </main>
  );
}

function AuthComplete(): React.JSX.Element {
  return (
    <main className="landing" id="main-content">
      <p className="eyebrow">GitHub sign-in complete</p>
      <h1>Return to the review transport</h1>
      <p className="lede">
        The transport window will detect this short-lived session and reconnect
        to the deployed review page. This window can now be closed.
      </p>
      <button onClick={() => window.close()} type="button">
        Close sign-in window
      </button>
    </main>
  );
}

function ServiceLanding(): React.JSX.Element {
  return (
    <main className="landing" id="main-content">
      <p className="eyebrow">Orinoco Lite GitHub transport</p>
      <h1>Open review from the deployed website</h1>
      <p className="lede">
        Source-adapter review is part of each downstream static site at its
        <code> /review/</code> route. This service only provides short-lived
        GitHub authentication and authenticated transport; it does not host a
        second review application.
      </p>
    </main>
  );
}

function ShaclSignIn({ target }: { target: ShaclTarget }): React.JSX.Element {
  return (
    <main className="landing" id="main-content">
      <p className="eyebrow">Authenticated human edit</p>
      <h1>Sign in to propose a SHACL Vue edit</h1>
      <p className="lede">
        GitHub limits this explicit write operation to collaborators with write
        or admin permission. Secure GitHub sign-in intentionally ends this
        popup&apos;s live link to the editor. Keep the static editor open; after
        sign-in, download its normal bundle and select that file here, or sign
        in first and choose <strong>Propose via GitHub</strong> again for a
        direct in-memory handoff. This page does not host a second editor or
        store the bundle.
      </p>
      <a
        className="button-link"
        href={shaclAuthenticationUrl(
          target.repository,
          target.pullRequest,
          target.expectedHeadSha,
          target.editorOrigin,
          target.handoffNonce,
        )}
      >
        Continue with GitHub
      </a>
      <p className="quiet">Repository: {target.repository}</p>
    </main>
  );
}

function exactKeys(value: unknown, expected: readonly string[]): boolean {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const observed = Object.keys(value).sort();
  const required = [...expected].sort();
  return (
    observed.length === required.length &&
    observed.every((key, index) => key === required[index])
  );
}

function oneLine(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= 4_096 &&
    !/[\u0000-\u001f\u007f]/.test(value)
  );
}

function validRecordPath(value: string): boolean {
  const root = "metadata/records/";
  return (
    value.startsWith(root) &&
    (value.endsWith(".yaml") || value.endsWith(".yml")) &&
    value.length <= 1_024 &&
    !/[\\\u0000-\u001f\u007f]/.test(value) &&
    value
      .slice(root.length)
      .split("/")
      .every(
        (part) =>
          part.length > 0 &&
          part !== "." &&
          part !== ".." &&
          !part.startsWith("."),
      )
  );
}

function browserBundle(value: unknown): ShaclReviewBundle | null {
  if (!exactKeys(value, ["format", "records", "source_commit", "version"])) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (
    record.format !== "orinoco-shacl-review-bundle" ||
    record.version !== 2 ||
    typeof record.source_commit !== "string" ||
    !/^[0-9a-f]{40}$/.test(record.source_commit) ||
    !Array.isArray(record.records) ||
    record.records.length === 0 ||
    record.records.length > 50
  ) {
    return null;
  }
  const records = [];
  const pids = new Set<string>();
  const paths = new Set<string>();
  for (const item of record.records) {
    if (
      !exactKeys(item, [
        "pid",
        "rdf_turtle",
        "schema_type",
        "source_path",
        "source_sha256",
      ])
    ) {
      return null;
    }
    const candidate = item as Record<string, unknown>;
    if (
      !oneLine(candidate.pid) ||
      !oneLine(candidate.schema_type) ||
      !oneLine(candidate.source_path) ||
      !validRecordPath(candidate.source_path) ||
      typeof candidate.source_sha256 !== "string" ||
      !/^[0-9a-f]{64}$/.test(candidate.source_sha256) ||
      typeof candidate.rdf_turtle !== "string" ||
      candidate.rdf_turtle.trim().length === 0 ||
      candidate.rdf_turtle.includes("\0") ||
      pids.has(candidate.pid) ||
      paths.has(candidate.source_path)
    ) {
      return null;
    }
    pids.add(candidate.pid);
    paths.add(candidate.source_path);
    records.push({
      pid: candidate.pid,
      rdf_turtle: candidate.rdf_turtle,
      schema_type: candidate.schema_type,
      source_path: candidate.source_path,
      source_sha256: candidate.source_sha256,
    });
  }
  const bundle: ShaclReviewBundle = {
    format: "orinoco-shacl-review-bundle",
    records,
    source_commit: record.source_commit,
    version: 2,
  };
  if (
    new TextEncoder().encode(`${JSON.stringify(bundle, null, 2)}\n`)
      .byteLength > MAX_SHACL_BUNDLE_BYTES
  ) {
    return null;
  }
  return bundle;
}

function messageBundle(
  value: unknown,
  repository: string,
  handoffNonce: string,
): ShaclReviewBundle | null {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    return null;
  const message = value as Partial<ShaclBundleMessage>;
  if (
    message.format !== "orinoco-lite-shacl-bundle-message-v1" ||
    message.handoff_nonce !== handoffNonce ||
    typeof message.repository !== "string" ||
    message.repository.toLowerCase() !== repository.toLowerCase()
  ) {
    return null;
  }
  return browserBundle(message.bundle);
}

interface ShaclHandoffProps {
  session: Extract<SessionStatus, { authenticated: true }>;
  target: ShaclTarget;
}

function ShaclHandoff({
  session,
  target,
}: ShaclHandoffProps): React.JSX.Element {
  const [bundle, setBundle] = useState<ShaclReviewBundle | null>(null);
  const [bundleSource, setBundleSource] = useState<string | null>(null);
  const [acknowledgePublicData, setAcknowledgePublicData] = useState(false);
  const [kind, setKind] = useState<"pull_request" | "standalone">(
    target.pullRequest === undefined ? "standalone" : "pull_request",
  );
  const [pullRequest, setPullRequest] = useState(
    target.pullRequest === undefined ? "" : String(target.pullRequest),
  );
  const [feedback, setFeedback] = useState<string | null>(null);
  const [result, setResult] = useState<ShaclProposalResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  useEffect(() => {
    function postedMessage(event: MessageEvent<unknown>): void {
      if (
        target.editorOrigin === undefined ||
        target.handoffNonce === undefined ||
        window.opener === null ||
        event.source !== window.opener ||
        event.origin !== target.editorOrigin
      ) {
        return;
      }
      const received = messageBundle(
        event.data,
        target.repository,
        target.handoffNonce,
      );
      if (received === null) return;
      if (
        target.expectedHeadSha !== undefined &&
        target.expectedHeadSha !== received.source_commit
      ) {
        setFeedback(
          "The received bundle does not match the exact pull-request head in this link.",
        );
        return;
      }
      setBundle(received);
      setBundleSource(event.origin);
      setAcknowledgePublicData(false);
      setFeedback(null);
      setResult(null);
    }

    window.addEventListener("message", postedMessage);
    if (
      window.opener !== null &&
      target.editorOrigin !== undefined &&
      target.handoffNonce !== undefined
    ) {
      const ready: ShaclProposalReadyMessage = {
        format: "orinoco-lite-shacl-proposal-ready-v1",
        handoff_nonce: target.handoffNonce,
        repository: target.repository,
      };
      window.opener.postMessage(ready, target.editorOrigin);
    }
    return () => {
      window.removeEventListener("message", postedMessage);
    };
  }, [
    target.editorOrigin,
    target.expectedHeadSha,
    target.handoffNonce,
    target.repository,
  ]);

  async function loadBundleFile(
    event: React.ChangeEvent<HTMLInputElement>,
  ): Promise<void> {
    const input = event.currentTarget;
    const file = input.files?.[0];
    input.value = "";
    if (file === undefined) return;
    if (file.size > MAX_SHACL_BUNDLE_BYTES) {
      setFeedback("The review bundle file must be no larger than 10 MiB.");
      return;
    }
    try {
      const received = browserBundle(JSON.parse(await file.text()) as unknown);
      if (received === null) {
        setFeedback("The selected file is not a SHACL Vue v2 review bundle.");
        return;
      }
      if (
        target.expectedHeadSha !== undefined &&
        target.expectedHeadSha !== received.source_commit
      ) {
        setFeedback(
          "The selected bundle does not match the exact pull-request head in this link.",
        );
        return;
      }
      setBundle(received);
      setBundleSource(`downloaded file: ${file.name}`);
      setAcknowledgePublicData(false);
      setFeedback(null);
      setResult(null);
    } catch {
      setFeedback("The selected file is not valid JSON.");
    }
  }

  async function propose(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (bundle === null) {
      setFeedback("Generate and send a SHACL Vue bundle before proposing it.");
      return;
    }
    if (!acknowledgePublicData) {
      setFeedback(
        "Confirm that the bundle contains no secrets and is approved for public Git history.",
      );
      return;
    }
    if (
      target.expectedHeadSha !== undefined &&
      target.expectedHeadSha !== bundle.source_commit
    ) {
      setFeedback(
        "The received bundle does not match the exact pull-request head used to open this handoff.",
      );
      return;
    }
    let proposalTarget: ShaclProposalRequest["target"];
    if (kind === "pull_request") {
      if (!/^[1-9][0-9]{0,9}$/.test(pullRequest)) {
        setFeedback("Enter a valid draft pull-request number.");
        return;
      }
      proposalTarget = {
        expected_head_sha: bundle.source_commit,
        kind: "pull_request",
        pull_request: Number(pullRequest),
      };
    } else {
      proposalTarget = { kind: "standalone" };
    }
    const proposal: ShaclProposalRequest = {
      acknowledge_public_data: true,
      bundle,
      format: "orinoco-lite-shacl-proposal-v1",
      repository: target.repository,
      target: proposalTarget,
    };
    setSubmitting(true);
    setFeedback(null);
    try {
      const created = await proposeShaclEdit(proposal, session.csrf_token);
      setResult(created);
      setBundle(null);
      setAcknowledgePublicData(false);
      setFeedback(
        kind === "standalone"
          ? "GitHub created the attributed bundle commit and draft pull request. The in-memory bundle was released."
          : "GitHub appended the attributed bundle commit at the exact draft pull-request head. The in-memory bundle was released.",
      );
    } catch (error) {
      setFeedback(message(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function signOut(): Promise<void> {
    await logout(session.csrf_token);
    window.location.reload();
  }

  return (
    <>
      <header className="topbar">
        <div>
          <p className="eyebrow">SHACL Vue proposal</p>
          <h1>{target.repository}</h1>
        </div>
        <div className="account">
          <span>
            Signed in as <strong>{session.login}</strong>
          </span>
          <button
            className="text-button"
            onClick={() => void signOut()}
            type="button"
          >
            Sign out
          </button>
        </div>
      </header>
      <main id="main-content">
        <section className="review-summary">
          <div>
            <p className="eyebrow">Browser-memory handoff</p>
            <h2>Propose the normal SHACL Vue bundle through GitHub</h2>
            <p>
              Continue editing on the downstream static site. This page only
              receives that editor&apos;s normal bundle in browser memory,
              confirms the public Git operation, and asks GitHub to create or
              update a draft proposal. The trusted workflow performs conversion
              and validation.
            </p>
            {target.pullRequest !== undefined &&
              target.expectedHeadSha !== undefined && (
                <p className="coordinate-lock">
                  Bound to draft pull request #{target.pullRequest} at{" "}
                  <code>{target.expectedHeadSha}</code>.
                </p>
              )}
          </div>
        </section>

        {bundle === null ? (
          <section className="handoff-waiting" aria-live="polite">
            <h2>Waiting for the static editor</h2>
            <p>
              Choose <strong>Propose via GitHub</strong> in the downstream
              editor. If you were already signed in when this window opened, the
              bundle can arrive directly while both windows remain open. GitHub
              sign-in ends that live link, so download the unchanged bundle in
              the still-open editor and select it below.
            </p>
            <label className="bundle-upload">
              Use a downloaded review bundle
              <input
                accept="application/json,.json"
                onChange={(event) => void loadBundleFile(event)}
                type="file"
              />
            </label>
          </section>
        ) : (
          <section className="handoff-bundle" aria-labelledby="bundle-title">
            <div>
              <p className="eyebrow">Bundle received</p>
              <h2 id="bundle-title">
                {bundle.records.length} edited{" "}
                {bundle.records.length === 1 ? "record" : "records"}
              </h2>
              <p>
                Source commit: <code>{bundle.source_commit}</code>
              </p>
              <p className="quiet">Browser source: {bundleSource}</p>
            </div>
            <ul>
              {bundle.records.map((record) => (
                <li key={record.pid}>
                  <strong>{record.pid}</strong>
                  <span>{record.source_path}</span>
                  <span>sha256:{record.source_sha256}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <form
          className="handoff-form"
          onSubmit={(event) => void propose(event)}
        >
          <fieldset>
            <legend>GitHub proposal target</legend>
            <label>
              <input
                checked={kind === "pull_request"}
                name="proposal-kind"
                onChange={() => setKind("pull_request")}
                type="radio"
              />
              Append to an existing same-repository draft pull request
            </label>
            <label>
              <input
                checked={kind === "standalone"}
                disabled={target.pullRequest !== undefined}
                name="proposal-kind"
                onChange={() => setKind("standalone")}
                type="radio"
              />
              Create a branch and new draft pull request
            </label>
          </fieldset>
          {kind === "pull_request" && (
            <label>
              Draft pull request
              <input
                disabled={target.pullRequest !== undefined}
                inputMode="numeric"
                min="1"
                onChange={(event) => setPullRequest(event.target.value)}
                required
                type="number"
                value={pullRequest}
              />
            </label>
          )}
          <p className="handoff-warning">
            The temporary bundle is public while its Git ref exists and may be
            retained by GitHub after the ref becomes unreachable. Do not merge
            while the temporary bundle path exists.
          </p>
          <label className="public-data-acknowledgement">
            <input
              checked={acknowledgePublicData}
              onChange={(event) =>
                setAcknowledgePublicData(event.target.checked)
              }
              required
              type="checkbox"
            />
            <span>
              I confirm this bundle contains no secrets and is approved for
              public Git history, including GitHub retention after its temporary
              ref becomes unreachable.
            </span>
          </label>
          <button
            disabled={bundle === null || !acknowledgePublicData || submitting}
            type="submit"
          >
            {submitting ? "Writing to GitHub…" : "Propose via GitHub"}
          </button>
        </form>
        {feedback !== null && (
          <p
            className={result === null ? "feedback" : "feedback success"}
            role="status"
          >
            {feedback}{" "}
            {result !== null && (
              <a href={result.pull_request_url}>Open draft pull request</a>
            )}
          </p>
        )}
      </main>
    </>
  );
}

export default function App(): React.JSX.Element {
  const target = currentTarget();
  const shaclTarget = currentShaclTarget();
  const [session, setSession] = useState<SessionStatus | null>(null);
  const [proposal, setProposal] = useState<BoundReviewProposal | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const authComplete =
    window.location.pathname === "/review-auth-complete" ||
    window.location.pathname === "/review-auth-complete/";

  useEffect(() => {
    if (target === null && shaclTarget === null) return;
    let active = true;
    void (async () => {
      try {
        const current = await loadSession();
        if (active) setSession(current);
      } catch (error) {
        if (active) setFailure(message(error));
      }
    })();
    return () => {
      active = false;
    };
  }, [
    shaclTarget?.expectedHeadSha,
    shaclTarget?.handoffNonce,
    shaclTarget?.pullRequest,
    shaclTarget?.repository,
    target?.artifactId,
    target?.handoffNonce,
    target?.pullRequest,
    target?.repository,
    target?.reviewOrigin,
  ]);

  const grantMatches =
    target !== null &&
    session !== null &&
    session.authenticated &&
    matchingReviewGrant(session, target);

  useEffect(() => {
    if (target === null || grantMatches) return;
    let active = true;
    const interval = window.setInterval(() => {
      void loadSession()
        .then((current) => {
          if (active) setSession(current);
        })
        .catch((error) => {
          if (active) setFailure(message(error));
        });
    }, 1_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [grantMatches, target?.artifactId, target?.handoffNonce]);

  useEffect(() => {
    if (
      target === null ||
      session === null ||
      !session.authenticated ||
      !matchingReviewGrant(session, target)
    ) {
      return;
    }
    let active = true;
    void loadProposal(target.repository, target.pullRequest, target.artifactId)
      .then((loaded) => {
        if (!active) return;
        const bound = boundReviewProposal(loaded, target);
        if (bound === null) {
          setFailure(
            "The proposal is not bound to this transport and downstream review route.",
          );
          return;
        }
        setProposal(bound);
      })
      .catch((error) => {
        if (active) setFailure(message(error));
      });
    return () => {
      active = false;
    };
  }, [
    grantMatches,
    session,
    target?.artifactId,
    target?.pullRequest,
    target?.repository,
  ]);

  if (authComplete) return <AuthComplete />;
  if (target === null && shaclTarget === null) {
    if (
      window.location.pathname === "/review-transport" ||
      window.location.pathname === "/review-transport/"
    ) {
      return (
        <main className="landing" id="main-content">
          <p className="eyebrow">Transport unavailable</p>
          <h1>The downstream handoff link is invalid</h1>
          <p className="feedback">
            Reopen the transport from the deployed site&apos;s{" "}
            <code>/review/</code>
            route.
          </p>
        </main>
      );
    }
    return <ServiceLanding />;
  }
  if (failure !== null) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Review unavailable</p>
        <h1>The proposal could not be opened</h1>
        <p className="feedback">{failure}</p>
        <a href="/">Return to the service entry page</a>
      </main>
    );
  }
  if (session === null)
    return (
      <main className="landing" id="main-content">
        <p>Loading review…</p>
      </main>
    );
  if (shaclTarget !== null) {
    if (!session.authenticated) return <ShaclSignIn target={shaclTarget} />;
    return <ShaclHandoff session={session} target={shaclTarget} />;
  }
  if (target === null) {
    return <ServiceLanding />;
  }
  if (!session.authenticated || !matchingReviewGrant(session, target)) {
    return <SignIn target={target} />;
  }
  if (proposal === null)
    return (
      <main className="landing" id="main-content">
        <p>Loading proposal from GitHub…</p>
      </main>
    );
  return (
    <ReviewTransport proposal={proposal} session={session} target={target} />
  );
}
