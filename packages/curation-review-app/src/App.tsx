import { useEffect, useMemo, useRef, useState } from "react";
import {
  isSafeEditorOrigin,
  isShaclHandoffNonce,
  MAX_SHACL_BUNDLE_BYTES,
  type ShaclProposalReadyMessage,
  type CurationSubmission,
  type Disposition,
  type ReviewCandidate,
  type ReviewDiscovery,
  type ReviewProposal,
  type SessionStatus,
  type ShaclBundleMessage,
  type ShaclProposalRequest,
  type ShaclProposalResult,
  type ShaclReviewBundle,
} from "../shared/contracts";
import {
  ApiError,
  authenticationUrl,
  discoveryAuthenticationUrl,
  loadDiscovery,
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
  editorOrigin?: string;
  expectedHeadSha?: string;
  handoffNonce?: string;
  pullRequest?: number;
  repository: string;
}

type DecisionState = Record<string, Disposition | undefined>;
type DecisionFilter = "all" | "unresolved" | Disposition;

function currentTarget(): Target | null {
  if (
    window.location.pathname !== "/" &&
    window.location.pathname !== "/review" &&
    window.location.pathname !== "/review/"
  ) {
    return null;
  }
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

function contextualRepository(): string | null {
  if (
    window.location.pathname !== "/" &&
    window.location.pathname !== "/review" &&
    window.location.pathname !== "/review/"
  ) {
    return null;
  }
  const query = new URLSearchParams(window.location.search);
  const values = query.getAll("repository");
  const value = values[0] ?? null;
  return values.length === 1 && validRepository(value) ? value : null;
}

function message(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "The review could not be loaded.";
}

interface LandingProps {
  discovery: ReviewDiscovery | null;
  failure: string | null;
  repository: string | null;
  session: SessionStatus | null;
}

function Landing({
  discovery,
  failure,
  repository,
  session,
}: LandingProps): React.JSX.Element {
  const requested = useMemo(
    () => new URLSearchParams(window.location.search),
    [],
  );
  const [selectedPull, setSelectedPull] = useState("");
  const [selectedArtifact, setSelectedArtifact] = useState("");
  const selectedProposal = discovery?.pull_requests.find(
    (pull) => String(pull.number) === selectedPull,
  );
  const artifacts = selectedProposal?.artifacts ?? [];

  useEffect(() => {
    if (discovery === null) return;
    const requestedPull = requested.get("pull_request");
    const requestedExists = discovery.pull_requests.some(
      (pull) => String(pull.number) === requestedPull,
    );
    if (requestedExists) {
      setSelectedPull(requestedPull ?? "");
    } else if (discovery.pull_requests.length === 1) {
      setSelectedPull(String(discovery.pull_requests[0]?.number ?? ""));
    } else {
      setSelectedPull("");
    }
  }, [discovery, requested]);

  useEffect(() => {
    const requestedArtifact = requested.get("artifact_id");
    const requestedExists = artifacts.some(
      (artifact) => String(artifact.id) === requestedArtifact,
    );
    if (requestedExists) {
      setSelectedArtifact(requestedArtifact ?? "");
    } else if (artifacts.length === 1) {
      setSelectedArtifact(String(artifacts[0]?.id ?? ""));
    } else {
      setSelectedArtifact("");
    }
  }, [artifacts, requested]);

  function selectRepository(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const query = new URLSearchParams({
      repository: String(data.get("repository") ?? ""),
    });
    window.location.assign(`/?${query.toString()}`);
  }

  function openReview(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (repository === null || selectedPull === "" || selectedArtifact === "") {
      return;
    }
    const query = new URLSearchParams({
      artifact_id: selectedArtifact,
      pull_request: selectedPull,
      repository,
    });
    window.location.assign(`/review/?${query.toString()}`);
  }

  if (repository === null) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Orinoco Lite</p>
        <h1>Review repository metadata</h1>
        <p className="lede">
          Start from a repository or pull-request link. The repository remains
          explicit because one GitHub identity can curate more than one site.
        </p>
        <form className="target-form" onSubmit={selectRepository}>
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
          <button type="submit">Continue</button>
        </form>
        <p className="quiet">
          The application stores no metadata or review decisions.
        </p>
      </main>
    );
  }

  if (session === null) {
    return (
      <main className="landing" id="main-content">
        <p>Checking the GitHub session…</p>
      </main>
    );
  }

  if (!session.authenticated) {
    return (
      <main className="landing" id="main-content">
        <p className="eyebrow">Authenticated curation</p>
        <h1>Continue with {repository}</h1>
        <p className="lede">
          Sign in to list only this repository&apos;s open curation proposals
          and available review artifacts.
        </p>
        <a
          className="button-link"
          href={discoveryAuthenticationUrl(repository)}
        >
          Continue with GitHub
        </a>
        <p className="quiet">
          GitHub limits access to collaborators with write or admin permission.
        </p>
      </main>
    );
  }

  return (
    <main className="landing" id="main-content">
      <p className="eyebrow">Signed in as {session.login}</p>
      <h1>Curate {repository}</h1>
      <p className="lede">
        Choose from the open proposals and expiring artifacts verified directly
        from GitHub. A fully populated pull-request link opens its exact review
        immediately.
      </p>
      {failure !== null && <p className="feedback">{failure}</p>}
      {discovery === null && failure === null ? (
        <p>Loading open proposals from GitHub…</p>
      ) : (
        <>
          <form className="target-form" onSubmit={openReview}>
            <label>
              Repository
              <input readOnly value={repository} />
            </label>
            <label>
              Open curation pull request
              <select
                aria-label="Open curation pull request"
                onChange={(event) => setSelectedPull(event.target.value)}
                required
                value={selectedPull}
              >
                <option value="">Choose a pull request</option>
                {discovery?.pull_requests.map((pull) => (
                  <option key={pull.number} value={pull.number}>
                    #{pull.number} — {pull.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Review artifact
              <select
                aria-label="Review artifact"
                disabled={selectedProposal === undefined}
                onChange={(event) => setSelectedArtifact(event.target.value)}
                required
                value={selectedArtifact}
              >
                <option value="">Choose an artifact</option>
                {artifacts.map((artifact) => (
                  <option key={artifact.id} value={artifact.id}>
                    {artifact.id} — expires {artifact.expires_at}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={selectedPull === "" || selectedArtifact === ""}
              type="submit"
            >
              Open review
            </button>
          </form>
          {discovery?.pull_requests.length === 0 && (
            <p className="quiet">
              No open source-adapter curation pull requests are available.
            </p>
          )}
          {selectedProposal !== undefined && artifacts.length === 0 && (
            <p className="quiet">
              This proposal has no unexpired matching review artifact. Rerun its
              trusted proposal workflow to reproduce one.
            </p>
          )}
        </>
      )}
      <p className="quiet">
        The application stores no metadata, bundles, or review decisions.
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

  function chooseUnresolved(value: Disposition): void {
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
                disabled={unresolved === 0}
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
              href={`/edit/?${new URLSearchParams({
                expected_head_sha: proposal.head_sha,
                pull_request: String(proposal.pull_request),
                repository: proposal.repository,
              }).toString()}`}
            >
              Propose downloaded SHACL bundle
            </a>
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
  const repository = contextualRepository();
  const [session, setSession] = useState<SessionStatus | null>(null);
  const [discovery, setDiscovery] = useState<ReviewDiscovery | null>(null);
  const [proposal, setProposal] = useState<ReviewProposal | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    if (target === null && shaclTarget === null && repository === null) return;
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
        } else if (
          current.authenticated &&
          target === null &&
          shaclTarget === null &&
          repository !== null
        ) {
          const loaded = await loadDiscovery(repository);
          if (active) setDiscovery(loaded);
        }
      } catch (error) {
        if (active) setFailure(message(error));
      }
    })();
    return () => {
      active = false;
    };
  }, [
    repository,
    shaclTarget?.expectedHeadSha,
    shaclTarget?.pullRequest,
    shaclTarget?.repository,
    target?.artifactId,
    target?.pullRequest,
    target?.repository,
  ]);

  if (target === null && shaclTarget === null) {
    return (
      <Landing
        discovery={discovery}
        failure={failure}
        repository={repository}
        session={session}
      />
    );
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
    return (
      <Landing
        discovery={discovery}
        failure={failure}
        repository={repository}
        session={session}
      />
    );
  }
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
