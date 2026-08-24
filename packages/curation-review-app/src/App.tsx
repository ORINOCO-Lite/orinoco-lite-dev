import { useEffect, useMemo, useRef, useState } from "react";
import type {
  CurationSubmission,
  Disposition,
  ReviewCandidate,
  ReviewProposal,
  SessionStatus,
} from "../shared/contracts";
import {
  ApiError,
  authenticationUrl,
  loadProposal,
  loadSession,
  logout,
  submitDecisions,
} from "./api";

interface Target {
  artifactId: number;
  pullRequest: number;
  repository: string;
}

type DecisionState = Record<string, Disposition | undefined>;
type DecisionFilter = "all" | "unresolved" | Disposition;

function currentTarget(): Target | null {
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
  const [session, setSession] = useState<SessionStatus | null>(null);
  const [proposal, setProposal] = useState<ReviewProposal | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (target === null) return;
    let active = true;
    void (async () => {
      try {
        const current = await loadSession();
        if (!active) return;
        setSession(current);
        if (current.authenticated) {
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
  }, [target?.artifactId, target?.pullRequest, target?.repository]);

  if (target === null) return <Landing />;
  if (failure !== null) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Review unavailable</p>
        <h1>The proposal could not be opened</h1>
        <p className="feedback">{failure}</p>
        <a href="/">Choose another pull request</a>
      </main>
    );
  }
  if (session === null)
    return (
      <main className="landing" id="main-content">
        <p>Loading review…</p>
      </main>
    );
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
