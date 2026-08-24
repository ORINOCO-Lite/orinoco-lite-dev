import { useEffect, useMemo, useRef, useState } from "react";
import type {
  CurationSubmission,
  Disposition,
  ReviewCandidate,
  ReviewProposal,
  SessionStatus,
  ShaclBundleMessage,
  ShaclProposalRequest,
  ShaclProposalResult,
  ShaclReviewBundle,
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
  pullRequest: number;
  repository: string;
}

interface ShaclTarget {
  expectedHeadSha?: string;
  pullRequest?: number;
  repository: string;
}

type DecisionState = Record<string, Disposition | undefined>;
type DecisionFilter = "all" | "unresolved" | Disposition;

function currentTarget(): Target | null {
  if (window.location.pathname !== "/") return null;
  const query = new URLSearchParams(window.location.search);
  const artifact = query.get("artifact_id");
  const repository = query.get("repository");
  const number = query.get("pull_request");
  if (
    artifact === null ||
    !/^[1-9][0-9]{0,15}$/.test(artifact) ||
    repository === null ||
    !/^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/.test(
      repository,
    ) ||
    number === null ||
    !/^[1-9][0-9]{0,9}$/.test(number)
  ) {
    return null;
  }
  const artifactId = Number(artifact);
  if (!Number.isSafeInteger(artifactId)) return null;
  return { artifactId, pullRequest: Number(number), repository };
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
  if (window.location.pathname !== "/edit") return null;
  const query = new URLSearchParams(window.location.search);
  const allowed = new Set(["expected_head_sha", "pull_request", "repository"]);
  if ([...query.keys()].some((key) => !allowed.has(key))) return null;
  const repository = query.get("repository");
  if (query.getAll("repository").length !== 1 || !validRepository(repository)) {
    return null;
  }
  const pullValues = query.getAll("pull_request");
  const headValues = query.getAll("expected_head_sha");
  if (pullValues.length === 0 && headValues.length === 0) {
    return { repository };
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
  };
}

function message(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "The review could not be loaded.";
}

function Landing(): React.JSX.Element {
  function open(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const query = new URLSearchParams({
      artifact_id: String(data.get("artifact_id") ?? ""),
      pull_request: String(data.get("pull_request") ?? ""),
      repository: String(data.get("repository") ?? ""),
    });
    window.location.assign(`/?${query.toString()}`);
  }

  function openEdit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const query = new URLSearchParams({
      repository: String(data.get("repository") ?? ""),
    });
    window.location.assign(`/edit?${query.toString()}`);
  }

  return (
    <main className="landing" id="main-content">
      <p className="eyebrow">Orinoco Lite</p>
      <h1>Review a metadata proposal</h1>
      <p className="lede">
        Enter the GitHub repository, pull request, and review artifact created
        by the trusted source-adapter workflow.
      </p>
      <form className="target-form" onSubmit={open}>
        <label>
          Repository
          <input
            autoComplete="off"
            name="repository"
            pattern="[^/]+/[^/]+"
            placeholder="owner/repository"
            required
          />
        </label>
        <label>
          Pull request
          <input
            inputMode="numeric"
            min="1"
            name="pull_request"
            placeholder="42"
            required
            type="number"
          />
        </label>
        <label>
          Artifact ID
          <input
            inputMode="numeric"
            min="1"
            name="artifact_id"
            placeholder="123456789"
            required
            type="number"
          />
        </label>
        <button type="submit">Open review</button>
      </form>
      <section className="edit-entry" aria-labelledby="edit-entry-title">
        <h2 id="edit-entry-title">Propose a SHACL Vue edit</h2>
        <p>
          Open the browser-memory handoff for a normal SHACL Vue v2 bundle. The
          service does not retain the bundle.
        </p>
        <form className="edit-target-form" onSubmit={openEdit}>
          <label>
            Repository
            <input
              autoComplete="off"
              name="repository"
              pattern="[^/]+/[^/]+"
              placeholder="owner/repository"
              required
            />
          </label>
          <button type="submit">Open edit handoff</button>
        </form>
      </section>
      <p className="quiet">
        The application stores no metadata or review decisions.
      </p>
    </main>
  );
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
        )}
      >
        Continue with GitHub
      </a>
      <p className="quiet">Repository: {target.repository}</p>
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
        or admin permission. Keep the editor window open: after sign-in it can
        send the bundle again without storing it on the service.
      </p>
      <a
        className="button-link"
        href={shaclAuthenticationUrl(
          target.repository,
          target.pullRequest,
          target.expectedHeadSha,
        )}
      >
        Continue with GitHub
      </a>
      <p className="quiet">Repository: {target.repository}</p>
    </main>
  );
}

function browserBundle(value: unknown): ShaclReviewBundle | null {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    return null;
  const record = value as Record<string, unknown>;
  if (
    record.format !== "orinoco-shacl-review-bundle" ||
    record.version !== 2 ||
    typeof record.source_commit !== "string" ||
    !/^[0-9a-f]{40}$/.test(record.source_commit) ||
    !Array.isArray(record.records) ||
    record.records.length === 0 ||
    record.records.length > 50 ||
    record.records.some(
      (item) =>
        item === null ||
        typeof item !== "object" ||
        Array.isArray(item) ||
        typeof (item as Record<string, unknown>).pid !== "string" ||
        typeof (item as Record<string, unknown>).rdf_turtle !== "string" ||
        typeof (item as Record<string, unknown>).schema_type !== "string" ||
        typeof (item as Record<string, unknown>).source_path !== "string" ||
        typeof (item as Record<string, unknown>).source_sha256 !== "string",
    )
  ) {
    return null;
  }
  return value as ShaclReviewBundle;
}

function messageBundle(
  value: unknown,
  repository: string,
): ShaclReviewBundle | null {
  if (value === null || typeof value !== "object" || Array.isArray(value))
    return null;
  const message = value as Partial<ShaclBundleMessage>;
  if (
    message.format !== "orinoco-lite-shacl-bundle-message-v1" ||
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
  const [bundleOrigin, setBundleOrigin] = useState<string | null>(null);
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
    function receive(value: unknown, origin: string): void {
      const received = browserBundle(value);
      if (received === null) {
        setFeedback("The received value is not a normal SHACL Vue v2 bundle.");
        return;
      }
      setBundle(received);
      setBundleOrigin(origin);
      setFeedback(null);
      setResult(null);
    }

    function customEvent(event: Event): void {
      receive((event as CustomEvent<unknown>).detail, window.location.origin);
    }

    function postedMessage(event: MessageEvent<unknown>): void {
      if (window.opener === null || event.source !== window.opener) return;
      const received = messageBundle(event.data, target.repository);
      if (received === null) return;
      setBundle(received);
      setBundleOrigin(event.origin);
      setFeedback(null);
      setResult(null);
    }

    window.addEventListener("orinoco:review-bundle", customEvent);
    window.addEventListener("message", postedMessage);
    window.opener?.postMessage(
      {
        format: "orinoco-lite-shacl-handoff-ready-v1",
        repository: target.repository,
      },
      "*",
    );
    return () => {
      window.removeEventListener("orinoco:review-bundle", customEvent);
      window.removeEventListener("message", postedMessage);
    };
  }, [target.repository]);

  async function propose(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (bundle === null) {
      setFeedback("Generate and send a SHACL Vue bundle before proposing it.");
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
      setBundleOrigin(null);
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
              This wrapper receives the bundle from the editor in browser
              memory. The service writes only the fixed temporary bundle path;
              the trusted workflow performs conversion and validation.
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
            <h2>Waiting for a SHACL Vue v2 bundle</h2>
            <p>
              Generate the normal bundle in the editor and choose its GitHub
              proposal action. Keep that editor window open through sign-in so
              it can resend the in-memory value.
            </p>
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
              {bundleOrigin !== null && (
                <p className="quiet">Browser source: {bundleOrigin}</p>
              )}
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
          <button disabled={bundle === null || submitting} type="submit">
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

function RecordSide({
  label,
  value,
}: {
  label: string;
  value: string | null;
}): React.JSX.Element {
  return (
    <section className="record-side">
      <h4>{label}</h4>
      <pre>{value ?? "Record does not exist."}</pre>
    </section>
  );
}

interface CandidateCardProps {
  candidate: ReviewCandidate;
  decision: Disposition | undefined;
  index: number;
  onDecision: (value: Disposition) => void;
  register: (element: HTMLElement | null) => void;
}

function CandidateCard({
  candidate,
  decision,
  index,
  onDecision,
  register,
}: CandidateCardProps): React.JSX.Element {
  const changed = candidate.before !== candidate.after;
  return (
    <article
      aria-labelledby={`candidate-${index}`}
      className={`candidate ${decision === undefined ? "candidate-unresolved" : ""}`}
      data-candidate-index={index}
      ref={register}
      tabIndex={-1}
    >
      <header className="candidate-header">
        <div>
          <p className="candidate-id">{candidate.friendly_id}</p>
          <h2 id={`candidate-${index}`}>{candidate.label}</h2>
        </div>
        <div className="badges">
          <span className={`badge badge-${candidate.operation}`}>
            {candidate.operation}
          </span>
          {!changed && <span className="badge">matches baseline at head</span>}
        </div>
      </header>

      <div
        className="record-diff"
        aria-label={`Before and after for ${candidate.label}`}
      >
        <RecordSide label="Before proposal" value={candidate.before} />
        <RecordSide label="Current pull-request head" value={candidate.after} />
      </div>

      <details className="details">
        <summary>Source and proposal details</summary>
        <dl>
          <dt>PID</dt>
          <dd>{candidate.pid}</dd>
          <dt>Source record</dt>
          <dd>{candidate.source_record_id}</dd>
          <dt>Source namespace</dt>
          <dd>{candidate.source_namespace}</dd>
          <dt>Path</dt>
          <dd>{candidate.record_path}</dd>
          <dt>Claim hash</dt>
          <dd>{candidate.claim_sha256}</dd>
        </dl>
        {candidate.blockers.length > 0 && (
          <div className="blockers">
            <h4>Diagnostics</h4>
            <ul>
              {candidate.blockers.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </details>

      <fieldset className="decision-group">
        <legend>Decision for {candidate.friendly_id}</legend>
        {(["accept", "reject", "defer"] as const).map((value) => (
          <label className={`decision decision-${value}`} key={value}>
            <input
              checked={decision === value}
              name={`decision-${index}`}
              onChange={() => onDecision(value)}
              type="radio"
              value={value}
            />
            <span>
              {value[0]?.toUpperCase()}
              {value.slice(1)}
            </span>
          </label>
        ))}
      </fieldset>
    </article>
  );
}

interface ReviewProps {
  artifactId: number;
  proposal: ReviewProposal;
  session: Extract<SessionStatus, { authenticated: true }>;
}

function Review({
  artifactId,
  proposal,
  session,
}: ReviewProps): React.JSX.Element {
  const [decisions, setDecisions] = useState<DecisionState>({});
  const [filter, setFilter] = useState<DecisionFilter>("all");
  const [query, setQuery] = useState("");
  const [changedOnly, setChangedOnly] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [commentUrl, setCommentUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [focusCandidate, setFocusCandidate] = useState<number | null>(null);
  const cards = useRef<Array<HTMLElement | null>>([]);

  const unresolved = proposal.candidates.filter(
    (candidate) => decisions[candidate.record_path] === undefined,
  ).length;
  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return proposal.candidates.filter((candidate) => {
      const disposition = decisions[candidate.record_path];
      if (filter === "unresolved" && disposition !== undefined) return false;
      if (filter !== "all" && filter !== "unresolved" && disposition !== filter)
        return false;
      if (changedOnly && candidate.before === candidate.after) return false;
      if (!needle) return true;
      return [
        candidate.friendly_id,
        candidate.label,
        candidate.pid,
        candidate.record_path,
        candidate.source_namespace,
        candidate.source_record_id,
      ].some((value) => value.toLocaleLowerCase().includes(needle));
    });
  }, [changedOnly, decisions, filter, proposal.candidates, query]);
  const visibleIndices = useMemo(
    () => visible.map((candidate) => proposal.candidates.indexOf(candidate)),
    [proposal.candidates, visible],
  );

  useEffect(() => {
    if (focusCandidate === null) return;
    const card = cards.current[focusCandidate];
    if (card === null || card === undefined) return;
    card.focus();
    setFocusCandidate(null);
  }, [focusCandidate, visibleIndices]);

  useEffect(() => {
    function shortcut(event: KeyboardEvent): void {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey)
        return;
      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        target instanceof HTMLButtonElement
      )
        return;
      const current =
        document.activeElement instanceof HTMLElement
          ? Number(document.activeElement.dataset.candidateIndex)
          : -1;
      if (event.key === "j" || event.key === "k") {
        event.preventDefault();
        if (visibleIndices.length === 0) return;
        const direction = event.key === "j" ? 1 : -1;
        const currentPosition = visibleIndices.indexOf(current);
        const start =
          currentPosition >= 0
            ? currentPosition
            : direction > 0
              ? -1
              : visibleIndices.length;
        const nextPosition = Math.min(
          visibleIndices.length - 1,
          Math.max(0, start + direction),
        );
        const next = visibleIndices[nextPosition];
        if (next !== undefined) cards.current[next]?.focus();
      } else if (
        (event.key === "a" || event.key === "r" || event.key === "d") &&
        current >= 0
      ) {
        event.preventDefault();
        const candidate = proposal.candidates[current];
        if (candidate !== undefined) {
          const value =
            event.key === "a"
              ? "accept"
              : event.key === "r"
                ? "reject"
                : "defer";
          setDecisions((existing) => ({
            ...existing,
            [candidate.record_path]: value,
          }));
        }
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, [proposal.candidates, visibleIndices]);

  function choose(candidate: ReviewCandidate, value: Disposition): void {
    setDecisions((existing) => ({
      ...existing,
      [candidate.record_path]: value,
    }));
    setFeedback(null);
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (unresolved > 0) {
      setFeedback(
        `${unresolved} ${unresolved === 1 ? "record still needs" : "records still need"} an Accept, Reject, or Defer decision.`,
      );
      const first = proposal.candidates.findIndex(
        (candidate) => decisions[candidate.record_path] === undefined,
      );
      setQuery("");
      setFilter("unresolved");
      setChangedOnly(false);
      setFocusCandidate(first);
      return;
    }
    const submission: CurationSubmission = {
      adapter: proposal.adapter,
      decisions: proposal.candidates.map((candidate) => ({
        disposition: decisions[candidate.record_path] as Disposition,
        operation: candidate.operation,
        pid: candidate.pid,
        record_path: candidate.record_path,
      })),
      format: "orinoco-lite-curation-submission-v1",
      head_sha: proposal.head_sha,
      proposal_sha: proposal.proposal_sha,
      pull_request: proposal.pull_request,
      repository: proposal.repository,
      source_coordinate: proposal.source_coordinate,
    };
    setSubmitting(true);
    setFeedback(null);
    try {
      const result = await submitDecisions(
        submission,
        session.csrf_token,
        artifactId,
      );
      setCommentUrl(result.comment_url);
      setFeedback(
        "The complete decision state was posted to GitHub. The trusted workflow will revalidate it before committing.",
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
          <p className="eyebrow">Metadata proposal</p>
          <h1>
            {proposal.repository} #{proposal.pull_request}
          </h1>
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
        <section className="review-summary" aria-labelledby="review-title">
          <div>
            <p className="eyebrow">{proposal.adapter}</p>
            <h2 id="review-title">Review every proposed record</h2>
            <p>
              The pull request contains the authoritative diff. Your complete
              decision state is posted as an authenticated comment and rechecked
              at the exact head.
            </p>
          </div>
          <div className="completion" aria-live="polite">
            <strong>
              {proposal.candidates.length - unresolved}/
              {proposal.candidates.length}
            </strong>
            <span>decisions complete</span>
          </div>
        </section>

        <section className="filters" aria-label="Review filters">
          <label className="search">
            Search records
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Label, PID, source, or path"
              type="search"
              value={query}
            />
          </label>
          <label>
            Decision
            <select
              onChange={(event) =>
                setFilter(event.target.value as DecisionFilter)
              }
              value={filter}
            >
              <option value="all">All</option>
              <option value="unresolved">Unresolved</option>
              <option value="accept">Accepted</option>
              <option value="reject">Rejected</option>
              <option value="defer">Deferred</option>
            </select>
          </label>
          <label className="checkbox">
            <input
              checked={changedOnly}
              onChange={(event) => setChangedOnly(event.target.checked)}
              type="checkbox"
            />
            Changed at current head only
          </label>
          <a href={proposal.pull_request_url} rel="noreferrer" target="_blank">
            Open GitHub diff
          </a>
        </section>

        <p className="keyboard-help">
          Keyboard: J/K moves between records; A accepts, R rejects, and D
          defers the focused record.
        </p>

        <form onSubmit={(event) => void submit(event)}>
          <div className="candidate-list">
            {visible.map((candidate) => {
              const index = proposal.candidates.indexOf(candidate);
              return (
                <CandidateCard
                  candidate={candidate}
                  decision={decisions[candidate.record_path]}
                  index={index}
                  key={candidate.record_path}
                  onDecision={(value) => choose(candidate, value)}
                  register={(element) => {
                    cards.current[index] = element;
                  }}
                />
              );
            })}
            {visible.length === 0 && (
              <p className="empty">No records match the current filters.</p>
            )}
          </div>

          <section className="submission-panel">
            <div>
              <h2>Submit complete decision state</h2>
              <p>
                {unresolved === 0
                  ? "Every candidate has one decision."
                  : `${unresolved} remaining.`}
              </p>
            </div>
            <button disabled={submitting || commentUrl !== null} type="submit">
              {submitting
                ? "Posting…"
                : commentUrl === null
                  ? "Post decisions to GitHub"
                  : "Decisions posted"}
            </button>
          </section>
          {feedback !== null && (
            <p
              className={commentUrl === null ? "feedback" : "feedback success"}
              role="status"
            >
              {feedback}{" "}
              {commentUrl !== null && (
                <a href={commentUrl}>View authenticated comment</a>
              )}
            </p>
          )}
        </form>
      </main>
    </>
  );
}

export default function App(): React.JSX.Element {
  const target = currentTarget();
  const shaclTarget = currentShaclTarget();
  const [session, setSession] = useState<SessionStatus | null>(null);
  const [proposal, setProposal] = useState<ReviewProposal | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (target === null && shaclTarget === null) return;
    let active = true;
    void (async () => {
      try {
        const current = await loadSession();
        if (!active) return;
        setSession(current);
        if (current.authenticated && target !== null) {
          const loaded = await loadProposal(
            target.repository,
            target.pullRequest,
            target.artifactId,
          );
          if (active) setProposal(loaded);
        }
      } catch (error) {
        if (active) setFailure(message(error));
      }
    })();
    return () => {
      active = false;
    };
  }, [
    shaclTarget?.expectedHeadSha,
    shaclTarget?.pullRequest,
    shaclTarget?.repository,
    target?.artifactId,
    target?.pullRequest,
    target?.repository,
  ]);

  if (target === null && shaclTarget === null) return <Landing />;
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
  if (target === null) return <Landing />;
  if (!session.authenticated) return <SignIn target={target} />;
  if (proposal === null)
    return (
      <main className="landing" id="main-content">
        <p>Loading proposal from GitHub…</p>
      </main>
    );
  return (
    <Review
      artifactId={target.artifactId}
      proposal={proposal}
      session={session}
    />
  );
}
