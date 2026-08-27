import { useEffect, useMemo, useRef, useState } from "react";
import type {
  CurationSubmission,
  Disposition,
  ReviewCandidate,
  ReviewProposal,
  SubmitResult,
} from "../shared/contracts";

type DecisionState = Record<string, Disposition | undefined>;
type DecisionFilter = "all" | "unresolved" | Disposition;

function message(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "The review could not be submitted.";
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
  disabled: boolean;
  index: number;
  onDecision: (value: Disposition) => void;
  register: (element: HTMLElement | null) => void;
}

function CandidateCard({
  candidate,
  decision,
  disabled,
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
              disabled={disabled}
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

export interface ReviewProps {
  login: string;
  onSubmit: (submission: CurationSubmission) => Promise<SubmitResult>;
  proposal: ReviewProposal;
}

export function Review({
  login,
  onSubmit,
  proposal,
}: ReviewProps): React.JSX.Element {
  const [decisions, setDecisions] = useState<DecisionState>({});
  const [filter, setFilter] = useState<DecisionFilter>("all");
  const [query, setQuery] = useState("");
  const [changedOnly, setChangedOnly] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [commentUrl, setCommentUrl] = useState<string | null>(null);
  const [pendingSubmission, setPendingSubmission] =
    useState<CurationSubmission | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [focusCandidate, setFocusCandidate] = useState<number | null>(null);
  const cards = useRef<Array<HTMLElement | null>>([]);
  const submissionStarted = useRef(false);

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
      if (submissionStarted.current) return;
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
    if (submissionStarted.current) return;
    setDecisions((existing) => ({
      ...existing,
      [candidate.record_path]: value,
    }));
    setFeedback(null);
  }

  function chooseUnresolved(value: Disposition): void {
    if (submissionStarted.current) return;
    setDecisions((existing) => {
      const next = { ...existing };
      for (const candidate of proposal.candidates) {
        if (next[candidate.record_path] === undefined) {
          next[candidate.record_path] = value;
        }
      }
      return next;
    });
    setFeedback(null);
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (submissionStarted.current) return;
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
    submissionStarted.current = true;
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
    setPendingSubmission(submission);
    setFeedback(
      "Review the complete decision summary below, then confirm the GitHub post.",
    );
  }

  async function confirmSubmission(): Promise<void> {
    if (pendingSubmission === null || submitting || commentUrl !== null) return;
    setSubmitting(true);
    setFeedback(null);
    try {
      const result = await onSubmit(pendingSubmission);
      setCommentUrl(result.comment_url);
      setPendingSubmission(null);
      setFeedback(
        "The complete decision state was posted to GitHub. The trusted workflow will revalidate it before committing.",
      );
    } catch (error) {
      submissionStarted.current = false;
      setPendingSubmission(null);
      setFeedback(message(error));
    } finally {
      setSubmitting(false);
    }
  }

  function cancelConfirmation(): void {
    if (submitting) return;
    submissionStarted.current = false;
    setPendingSubmission(null);
    setFeedback(null);
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
            Connected as <strong>{login}</strong>
          </span>
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

        <section className="bulk-decisions" aria-labelledby="bulk-title">
          <div>
            <h3 id="bulk-title">Set a default decision</h3>
            <p>
              Apply one decision to every unresolved record, then change any
              exceptions in the record cards below. Existing choices are
              preserved.
            </p>
          </div>
          <div className="bulk-decision-actions">
            {(["accept", "reject", "defer"] as const).map((value) => (
              <button
                className={`bulk-decision bulk-decision-${value}`}
                disabled={
                  submitting ||
                  pendingSubmission !== null ||
                  commentUrl !== null ||
                  unresolved === 0
                }
                key={value}
                onClick={() => chooseUnresolved(value)}
                type="button"
              >
                {value[0]?.toUpperCase()}
                {value.slice(1)} all unresolved
              </button>
            ))}
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
          <div className="review-actions">
            <a
              href={proposal.pull_request_url}
              rel="noreferrer"
              target="_blank"
            >
              Open GitHub diff
            </a>
          </div>
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
                  disabled={
                    submitting ||
                    pendingSubmission !== null ||
                    commentUrl !== null
                  }
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

          {pendingSubmission !== null && (
            <section
              className="submission-confirmation"
              aria-labelledby="submission-confirmation-title"
            >
              <p className="eyebrow">Final downstream confirmation</p>
              <h2 id="submission-confirmation-title">
                Confirm the complete decision state
              </h2>
              <p>
                Signed in as <strong>{login}</strong>. This will post one
                authenticated comment to {proposal.repository} pull request #
                {proposal.pull_request}.
              </p>
              <dl>
                <dt>Proposal commit</dt>
                <dd>
                  <code>{proposal.proposal_sha}</code>
                </dd>
                <dt>Current head</dt>
                <dd>
                  <code>{proposal.head_sha}</code>
                </dd>
              </dl>
              <ul aria-label="Decisions awaiting confirmation">
                {proposal.candidates.map((candidate, index) => (
                  <li key={candidate.record_path}>
                    <code>{candidate.record_path}</code> (
                    {candidate.friendly_id}){" → "}
                    <strong>
                      {pendingSubmission.decisions[index]?.disposition}
                    </strong>
                  </li>
                ))}
              </ul>
              <div className="confirmation-actions">
                <button
                  disabled={submitting}
                  onClick={() => void confirmSubmission()}
                  type="button"
                >
                  {submitting ? "Posting…" : "Confirm and post to GitHub"}
                </button>
                <button
                  disabled={submitting}
                  onClick={cancelConfirmation}
                  type="button"
                >
                  Return to decisions
                </button>
              </div>
            </section>
          )}

          <section className="submission-panel">
            <div>
              <h2>Submit complete decision state</h2>
              <p>
                {unresolved === 0
                  ? "Every candidate has one decision."
                  : `${unresolved} remaining.`}
              </p>
            </div>
            <button
              disabled={
                submitting || pendingSubmission !== null || commentUrl !== null
              }
              type="submit"
            >
              {commentUrl === null
                ? pendingSubmission === null
                  ? "Review decisions before posting"
                  : "Awaiting confirmation"
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
