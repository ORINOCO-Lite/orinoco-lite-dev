import { useEffect, useRef, useState } from "react";
import {
  isReviewHandoffNonce,
  isSafeReviewOrigin,
  type CurationSubmission,
  type ReviewCandidate,
  type ReviewCoordinates,
  type ReviewProposal,
  type ReviewProposalRequestMessage,
  type ReviewSubmissionMessage,
  type SubmitResult,
} from "../shared/contracts";
import { Review } from "./Review";

const AUTHORIZATION_TIMEOUT_MS = 600_000;
const HANDSHAKE_TIMEOUT_MS = 60_000;
const SUBMISSION_TIMEOUT_MS = 60_000;
const POPUP_POLL_MS = 250;

interface ReviewConfig {
  app_name: string;
  format: "orinoco-curation-review-config";
  repository: string;
  service_origin: string;
  version: 1;
}

interface ReviewTarget {
  artifactId: number;
  pullRequest: number;
  repository: string;
}

interface BoundReviewProposal extends ReviewProposal {
  review_service_origin: string;
  review_site_url: string;
}

interface HandoffState {
  closedPoll: number | null;
  handshakeTimeout: number | null;
  nonce: string;
  popup: Window;
  proposalReceived: boolean;
  proposalRequested: boolean;
  postStarted: boolean;
  resultReceived: boolean;
  submissionSent: boolean;
}

interface PendingSubmission {
  handoff: HandoffState;
  reject: (error: Error) => void;
  resolve: (result: SubmitResult) => void;
  timeout: number | null;
}

function exactKeys(value: object, expected: readonly string[]): boolean {
  const observed = Object.keys(value).sort();
  const required = [...expected].sort();
  return (
    observed.length === required.length &&
    observed.every((key, index) => key === required[index])
  );
}

function oneLine(value: unknown, maximum = 4_096): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= maximum &&
    !/[\u0000-\u001f\u007f]/.test(value)
  );
}

function validRepository(value: unknown): value is string {
  return (
    oneLine(value, 200) &&
    /^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/.test(
      value,
    ) &&
    !value.includes("..")
  );
}

function parseConfig(value: unknown): ReviewConfig | null {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    !exactKeys(value, [
      "app_name",
      "format",
      "repository",
      "service_origin",
      "version",
    ])
  ) {
    return null;
  }
  const config = value as Record<string, unknown>;
  if (
    !oneLine(config.app_name, 256) ||
    config.format !== "orinoco-curation-review-config" ||
    !validRepository(config.repository) ||
    !isSafeReviewOrigin(config.service_origin) ||
    config.version !== 1
  ) {
    return null;
  }
  return config as unknown as ReviewConfig;
}

function currentTarget(): ReviewTarget | null {
  const query = new URLSearchParams(window.location.search);
  const allowed = new Set(["artifact_id", "pull_request", "repository"]);
  if (
    [...query.keys()].some((key) => !allowed.has(key)) ||
    [...allowed].some((key) => query.getAll(key).length !== 1)
  ) {
    return null;
  }
  const artifact = query.get("artifact_id");
  const pullRequest = query.get("pull_request");
  const repository = query.get("repository");
  if (
    artifact === null ||
    !/^[1-9][0-9]{0,15}$/.test(artifact) ||
    pullRequest === null ||
    !/^[1-9][0-9]{0,9}$/.test(pullRequest) ||
    !validRepository(repository)
  ) {
    return null;
  }
  const artifactId = Number(artifact);
  const pull = Number(pullRequest);
  if (!Number.isSafeInteger(artifactId) || !Number.isSafeInteger(pull)) {
    return null;
  }
  return { artifactId, pullRequest: pull, repository };
}

function candidate(value: unknown): value is ReviewCandidate {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    !exactKeys(value, [
      "after",
      "before",
      "blockers",
      "claim_sha256",
      "friendly_id",
      "label",
      "operation",
      "pid",
      "record_path",
      "source_namespace",
      "source_record_id",
    ])
  ) {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    (item.after === null || typeof item.after === "string") &&
    (item.before === null || typeof item.before === "string") &&
    Array.isArray(item.blockers) &&
    item.blockers.every((blocker) => oneLine(blocker)) &&
    typeof item.claim_sha256 === "string" &&
    /^sha256:[0-9a-f]{64}$/.test(item.claim_sha256) &&
    oneLine(item.friendly_id) &&
    oneLine(item.label) &&
    (item.operation === "add" ||
      item.operation === "delete" ||
      item.operation === "modify") &&
    oneLine(item.pid) &&
    oneLine(item.record_path, 1_024) &&
    item.record_path.startsWith("metadata/records/") &&
    oneLine(item.source_namespace) &&
    oneLine(item.source_record_id)
  );
}

function canonicalReviewSiteUrl(): string {
  return new URL(".", window.location.href).href;
}

function exactPullRequestUrl(value: unknown, target: ReviewTarget): boolean {
  if (typeof value !== "string" || value.length > 512) return false;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return false;
  }
  const parts = url.pathname.split("/");
  const [owner, repository] = target.repository.split("/");
  return (
    url.href === value &&
    url.origin === "https://github.com" &&
    url.username === "" &&
    url.password === "" &&
    url.search === "" &&
    url.hash === "" &&
    parts.length === 5 &&
    parts[0] === "" &&
    parts[1]?.toLowerCase() === owner?.toLowerCase() &&
    parts[2]?.toLowerCase() === repository?.toLowerCase() &&
    parts[3] === "pull" &&
    parts[4] === String(target.pullRequest)
  );
}

function exactCommentUrl(
  value: unknown,
  target: ReviewTarget,
): value is string {
  if (typeof value !== "string" || value.length > 512) return false;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return false;
  }
  const parts = url.pathname.split("/");
  const [owner, repository] = target.repository.split("/");
  return (
    url.href === value &&
    url.origin === "https://github.com" &&
    url.username === "" &&
    url.password === "" &&
    url.search === "" &&
    /^#issuecomment-[1-9][0-9]*$/.test(url.hash) &&
    parts.length === 5 &&
    parts[0] === "" &&
    parts[1]?.toLowerCase() === owner?.toLowerCase() &&
    parts[2]?.toLowerCase() === repository?.toLowerCase() &&
    parts[3] === "pull" &&
    parts[4] === String(target.pullRequest)
  );
}

function proposal(
  value: unknown,
  target: ReviewTarget,
  config: ReviewConfig,
): BoundReviewProposal | null {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    !exactKeys(value, [
      "adapter",
      "candidates",
      "head_sha",
      "proposal_sha",
      "pull_request",
      "pull_request_url",
      "repository",
      "review_service_origin",
      "review_site_url",
      "source_coordinate",
    ])
  ) {
    return null;
  }
  const review = value as Record<string, unknown>;
  if (
    !oneLine(review.adapter, 128) ||
    !Array.isArray(review.candidates) ||
    review.candidates.length === 0 ||
    review.candidates.length > 225 ||
    !review.candidates.every(candidate) ||
    typeof review.head_sha !== "string" ||
    !/^[0-9a-f]{40}$/.test(review.head_sha) ||
    typeof review.proposal_sha !== "string" ||
    !/^[0-9a-f]{40}$/.test(review.proposal_sha) ||
    review.pull_request !== target.pullRequest ||
    !exactPullRequestUrl(review.pull_request_url, target) ||
    typeof review.repository !== "string" ||
    review.repository.toLowerCase() !== target.repository.toLowerCase() ||
    review.review_service_origin !== config.service_origin ||
    review.review_site_url !== canonicalReviewSiteUrl() ||
    review.source_coordinate === null ||
    typeof review.source_coordinate !== "object" ||
    Array.isArray(review.source_coordinate)
  ) {
    return null;
  }
  const paths = review.candidates.map((item) => item.record_path);
  if (new Set(paths).size !== paths.length) return null;
  return review as unknown as BoundReviewProposal;
}

function randomNonce(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return [...bytes]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

function exactCoordinates(
  value: Record<string, unknown>,
  target: ReviewTarget,
  nonce: string,
): boolean {
  return (
    value.artifact_id === target.artifactId &&
    value.handoff_nonce === nonce &&
    value.pull_request === target.pullRequest &&
    typeof value.repository === "string" &&
    value.repository.toLowerCase() === target.repository.toLowerCase()
  );
}

function coordinates(target: ReviewTarget, nonce: string): ReviewCoordinates {
  return {
    artifact_id: target.artifactId,
    handoff_nonce: nonce,
    pull_request: target.pullRequest,
    repository: target.repository,
  };
}

function framed(): boolean {
  try {
    return window.top !== window.self;
  } catch {
    return true;
  }
}

export function isSharedGitHubPagesHostname(hostname: string): boolean {
  hostname = hostname.toLowerCase().replace(/\.+$/, "");
  return hostname === "github.io" || hostname.endsWith(".github.io");
}

function sharedGitHubPagesOrigin(): boolean {
  return isSharedGitHubPagesHostname(window.location.hostname);
}

function ReviewSite({ config }: { config: ReviewConfig }): React.JSX.Element {
  const target = currentTarget();
  const handoff = useRef<HandoffState | null>(null);
  const listenerInstalled = useRef(false);
  const pending = useRef<PendingSubmission | null>(null);
  const [listenerReady, setListenerReady] = useState(false);
  const [nonce, setNonce] = useState<string | null>(null);
  const [loadedProposal, setLoadedProposal] =
    useState<BoundReviewProposal | null>(null);
  const [login, setLogin] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [sharedOriginAcknowledged, setSharedOriginAcknowledged] =
    useState(false);

  function clearHandoffTimers(state: HandoffState): void {
    if (state.handshakeTimeout !== null) {
      window.clearTimeout(state.handshakeTimeout);
      state.handshakeTimeout = null;
    }
    if (state.closedPoll !== null) {
      window.clearInterval(state.closedPoll);
      state.closedPoll = null;
    }
  }

  function failHandoff(state: HandoffState, error: Error): void {
    if (handoff.current !== state) return;
    clearHandoffTimers(state);
    handoff.current = null;
    setNonce(null);
    const waiting = pending.current;
    if (waiting?.handoff === state) {
      if (waiting.timeout !== null) window.clearTimeout(waiting.timeout);
      waiting.timeout = null;
      if (state.postStarted) {
        setFeedback(
          "The GitHub post result is uncertain. Check the pull request before taking another action.",
        );
        return;
      }
      pending.current = null;
      waiting.reject(error);
    }
    setFeedback(error.message);
  }

  useEffect(() => {
    document.title = config.app_name;
  }, [config.app_name]);

  useEffect(() => {
    function postedMessage(event: MessageEvent<unknown>): void {
      const state = handoff.current;
      if (
        target === null ||
        state === null ||
        event.source !== state.popup ||
        event.origin !== config.service_origin ||
        event.data === null ||
        typeof event.data !== "object" ||
        Array.isArray(event.data)
      ) {
        return;
      }
      const value = event.data as Record<string, unknown>;
      if (value.format === "orinoco-lite-review-transport-ready-v1") {
        if (
          state.proposalRequested ||
          state.proposalReceived ||
          !exactKeys(value, [
            "artifact_id",
            "format",
            "handoff_nonce",
            "pull_request",
            "repository",
          ]) ||
          !exactCoordinates(value, target, state.nonce)
        ) {
          return;
        }
        state.proposalRequested = true;
        if (state.handshakeTimeout !== null) {
          window.clearTimeout(state.handshakeTimeout);
        }
        state.handshakeTimeout = window.setTimeout(() => {
          failHandoff(
            state,
            new Error(
              "The GitHub transport did not return a proposal in time.",
            ),
          );
        }, HANDSHAKE_TIMEOUT_MS);
        const request: ReviewProposalRequestMessage = {
          ...coordinates(target, state.nonce),
          format: "orinoco-lite-review-proposal-request-v1",
        };
        state.popup.postMessage(request, config.service_origin);
        setFeedback("Loading the verified proposal through GitHub transport…");
        return;
      }
      if (value.format === "orinoco-lite-review-proposal-message-v1") {
        if (
          !state.proposalRequested ||
          state.proposalReceived ||
          !exactKeys(value, [
            "artifact_id",
            "format",
            "handoff_nonce",
            "login",
            "proposal",
            "pull_request",
            "repository",
          ]) ||
          !exactCoordinates(value, target, state.nonce) ||
          !oneLine(value.login, 128)
        ) {
          return;
        }
        state.proposalReceived = true;
        if (state.handshakeTimeout !== null) {
          window.clearTimeout(state.handshakeTimeout);
          state.handshakeTimeout = null;
        }
        const received = proposal(value.proposal, target, config);
        if (received === null) {
          failHandoff(
            state,
            new Error(
              "The authenticated transport returned an invalid proposal.",
            ),
          );
          return;
        }
        setLoadedProposal(received);
        setLogin(value.login);
        setFeedback(null);
        return;
      }
      if (value.format === "orinoco-lite-transport-error-v1") {
        if (
          !exactKeys(value, [
            "format",
            "handoff_nonce",
            "kind",
            "message",
            "repository",
          ]) ||
          value.kind !== "review" ||
          value.handoff_nonce !== state.nonce ||
          typeof value.repository !== "string" ||
          value.repository.toLowerCase() !== target.repository.toLowerCase() ||
          !oneLine(value.message)
        ) {
          return;
        }
        failHandoff(state, new Error(value.message));
        return;
      }
      if (value.format === "orinoco-lite-review-post-started-v1") {
        if (
          !state.submissionSent ||
          state.postStarted ||
          pending.current?.handoff !== state ||
          !exactKeys(value, [
            "artifact_id",
            "format",
            "handoff_nonce",
            "pull_request",
            "repository",
          ]) ||
          !exactCoordinates(value, target, state.nonce)
        ) {
          return;
        }
        state.postStarted = true;
        const waiting = pending.current;
        waiting.timeout = window.setTimeout(() => {
          if (pending.current !== waiting) return;
          waiting.timeout = null;
          setFeedback(
            "The GitHub post result is uncertain. Check the pull request before taking another action.",
          );
        }, SUBMISSION_TIMEOUT_MS);
        setFeedback("Posting the confirmed decisions to GitHub…");
        return;
      }
      if (value.format !== "orinoco-lite-review-submission-result-v1") return;
      if (
        !state.postStarted ||
        state.resultReceived ||
        pending.current?.handoff !== state ||
        !exactKeys(value, [
          "artifact_id",
          "comment_url",
          "error",
          "format",
          "handoff_nonce",
          "pull_request",
          "repository",
          "retry_safe",
        ]) ||
        !exactCoordinates(value, target, state.nonce)
      ) {
        return;
      }
      state.resultReceived = true;
      clearHandoffTimers(state);
      const waiting = pending.current;
      if (waiting.timeout !== null) window.clearTimeout(waiting.timeout);
      waiting.timeout = null;
      if (
        exactCommentUrl(value.comment_url, target) &&
        value.error === null &&
        value.retry_safe === false
      ) {
        pending.current = null;
        waiting.resolve({ comment_url: value.comment_url });
      } else if (
        value.comment_url === null &&
        oneLine(value.error) &&
        value.retry_safe === true
      ) {
        const error = new Error(value.error);
        pending.current = null;
        handoff.current = null;
        setNonce(null);
        setFeedback(
          `${error.message} Check the pull request, then reopen the GitHub transport before retrying.`,
        );
        waiting.reject(error);
      } else {
        const detail =
          value.comment_url === null && oneLine(value.error)
            ? `${value.error} `
            : "";
        setFeedback(
          `${detail}The GitHub post result is uncertain. Check the pull request before taking another action.`,
        );
      }
    }

    listenerInstalled.current = true;
    window.addEventListener("message", postedMessage);
    setListenerReady(true);
    return () => {
      listenerInstalled.current = false;
      window.removeEventListener("message", postedMessage);
    };
  }, [
    config.service_origin,
    target?.artifactId,
    target?.pullRequest,
    target?.repository,
  ]);

  useEffect(
    () => () => {
      const state = handoff.current;
      if (state !== null) clearHandoffTimers(state);
      handoff.current = null;
      const waiting = pending.current;
      if (waiting !== null) {
        pending.current = null;
        if (waiting.timeout !== null) window.clearTimeout(waiting.timeout);
        waiting.reject(new Error("The review page was closed."));
      }
    },
    [],
  );

  function connect(): void {
    if (target === null || !listenerInstalled.current) return;
    if (sharedGitHubPagesOrigin() && !sharedOriginAcknowledged) {
      setFeedback(
        "Acknowledge the shared github.io origin before connecting GitHub.",
      );
      return;
    }
    const previous = handoff.current;
    if (previous !== null) {
      clearHandoffTimers(previous);
      handoff.current = null;
      const waiting = pending.current;
      if (waiting?.handoff === previous) {
        pending.current = null;
        if (waiting.timeout !== null) window.clearTimeout(waiting.timeout);
        waiting.reject(new Error("The GitHub transport was replaced."));
      }
    }
    const nextNonce = randomNonce();
    if (!isReviewHandoffNonce(nextNonce)) {
      setFeedback("The browser could not create a secure review handoff.");
      return;
    }
    const url = new URL("/api/transport", config.service_origin);
    url.searchParams.set("kind", "review");
    url.searchParams.set("artifact_id", String(target.artifactId));
    url.searchParams.set("handoff_nonce", nextNonce);
    url.searchParams.set("pull_request", String(target.pullRequest));
    url.searchParams.set("repository", target.repository);
    url.searchParams.set("review_origin", window.location.origin);
    let opened: Window | null;
    try {
      opened = window.open(
        url,
        "orinoco-review-transport",
        "popup,width=720,height=760,resizable=yes,scrollbars=yes",
      );
    } catch {
      opened = null;
    }
    if (opened === null) {
      setNonce(null);
      setFeedback("Allow the GitHub transport popup, then try again.");
      return;
    }
    const state: HandoffState = {
      closedPoll: null,
      handshakeTimeout: null,
      nonce: nextNonce,
      popup: opened,
      proposalReceived: false,
      proposalRequested: false,
      postStarted: false,
      resultReceived: false,
      submissionSent: false,
    };
    handoff.current = state;
    setNonce(nextNonce);
    setFeedback("Complete GitHub sign-in in the transport window.");
    state.handshakeTimeout = window.setTimeout(() => {
      failHandoff(
        state,
        new Error("GitHub sign-in did not complete before it expired."),
      );
    }, AUTHORIZATION_TIMEOUT_MS);
    state.closedPoll = window.setInterval(() => {
      if (state.popup.closed) {
        failHandoff(
          state,
          new Error(
            "The GitHub transport window was closed. Reopen it to continue.",
          ),
        );
      }
    }, POPUP_POLL_MS);
    if (opened.closed) {
      failHandoff(
        state,
        new Error(
          "The GitHub transport window was closed. Reopen it to continue.",
        ),
      );
      return;
    }
    try {
      opened.focus();
    } catch {
      // Focusing is optional; the authenticated handoff remains usable.
    }
  }

  function submit(submission: CurationSubmission): Promise<SubmitResult> {
    return new Promise((resolve, reject) => {
      const state = handoff.current;
      if (
        target === null ||
        state === null ||
        state.popup.closed ||
        !state.proposalReceived
      ) {
        reject(new Error("Reopen the authenticated GitHub transport first."));
        return;
      }
      if (pending.current !== null || state.submissionSent) {
        reject(new Error("This decision submission has already been sent."));
        return;
      }
      state.submissionSent = true;
      const timeout = window.setTimeout(() => {
        const waiting = pending.current;
        if (waiting?.handoff !== state) return;
        waiting.timeout = null;
        failHandoff(
          state,
          new Error(
            "The GitHub transport did not acknowledge the decisions. Reopen it before retrying.",
          ),
        );
      }, SUBMISSION_TIMEOUT_MS);
      pending.current = { handoff: state, reject, resolve, timeout };
      const request: ReviewSubmissionMessage = {
        ...coordinates(target, state.nonce),
        format: "orinoco-lite-review-submission-message-v1",
        submission,
      };
      try {
        state.popup.postMessage(request, config.service_origin);
      } catch {
        failHandoff(
          state,
          new Error("The GitHub transport could not receive the decisions."),
        );
      }
    });
  }

  if (target === null) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Source metadata review</p>
        <h1>Open an exact proposal link</h1>
        <p className="feedback">
          This route requires one repository, pull request, and review artifact.
          Use the link on the draft curation pull request.
        </p>
      </main>
    );
  }
  if (target.repository.toLowerCase() !== config.repository.toLowerCase()) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Source metadata review</p>
        <h1>The proposal belongs to another repository</h1>
        <p className="feedback">
          This deployed review route is bound to {config.repository}.
        </p>
      </main>
    );
  }
  if (loadedProposal !== null && login !== null) {
    const postUncertain = pending.current?.handoff.postStarted === true;
    return (
      <>
        <div aria-live="polite" className="transport-feedback">
          {feedback !== null && (
            <p className="feedback" role="status">
              {feedback}
            </p>
          )}
          {listenerReady && handoff.current === null && !postUncertain && (
            <button onClick={connect} type="button">
              Reopen GitHub transport
            </button>
          )}
        </div>
        <Review
          key={`${loadedProposal.proposal_sha}:${loadedProposal.head_sha}`}
          login={login}
          onSubmit={submit}
          proposal={loadedProposal}
        />
      </>
    );
  }
  return (
    <main className="landing" id="main-content">
      <p className="eyebrow">Source metadata review</p>
      <h1>Review pull request #{target.pullRequest} here</h1>
      <p className="lede">
        Candidate review remains in this deployed static website. A small GitHub
        transport window authenticates you and verifies the exact proposal. The
        complete decision summary and final confirmation remain on this page.
      </p>
      {sharedGitHubPagesOrigin() && (
        <section
          className="shared-origin-warning"
          aria-labelledby="shared-origin-title"
        >
          <h2 id="shared-origin-title">Shared github.io security boundary</h2>
          <p>
            Every project page under this github.io hostname shares one browser
            origin. Another page on that hostname could impersonate this path. A
            verified custom domain gives this site its own origin and enables
            the normal low-friction GitHub flow.
          </p>
          <label>
            <input
              checked={sharedOriginAcknowledged}
              onChange={(event) =>
                setSharedOriginAcknowledged(event.target.checked)
              }
              type="checkbox"
            />
            I understand this shared-origin risk and want to enable direct
            GitHub submission for this page.
          </label>
        </section>
      )}
      {listenerReady && (
        <button
          disabled={sharedGitHubPagesOrigin() && !sharedOriginAcknowledged}
          onClick={connect}
          type="button"
        >
          {nonce === null ? "Connect with GitHub" : "Reopen GitHub transport"}
        </button>
      )}
      {feedback !== null && (
        <p className="feedback" role="status">
          {feedback}
        </p>
      )}
      <p className="quiet">Repository: {config.repository}</p>
    </main>
  );
}

export default function ReviewSiteLoader(): React.JSX.Element {
  const isFramed = framed();
  const [config, setConfig] = useState<ReviewConfig | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (isFramed) return;
    let active = true;
    void fetch(new URL("config.json", window.location.href), {
      cache: "no-store",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("The review configuration is unavailable.");
        }
        const loaded = parseConfig((await response.json()) as unknown);
        if (loaded === null) {
          throw new Error("The review configuration is invalid.");
        }
        if (active) setConfig(loaded);
      })
      .catch((error) => {
        if (active) {
          setFailure(
            error instanceof Error
              ? error.message
              : "The review configuration could not be loaded.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [isFramed]);

  if (isFramed) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Review unavailable</p>
        <h1>Open this review as a top-level page</h1>
        <p className="feedback">
          For security, source metadata review refuses to run inside a frame.
        </p>
      </main>
    );
  }
  if (failure !== null) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Review unavailable</p>
        <h1>The deployed reviewer could not start</h1>
        <p className="feedback">{failure}</p>
      </main>
    );
  }
  if (config === null) {
    return (
      <main className="landing" id="main-content">
        <p>Loading deployed review configuration…</p>
      </main>
    );
  }
  return <ReviewSite config={config} />;
}
