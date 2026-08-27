import {
  act,
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MAX_SHACL_BUNDLE_BYTES,
  type ReviewProposal,
  type ShaclReviewBundle,
} from "../shared/contracts";
import App from "./App";
import { Review } from "./Review";
import { ARTIFACT_ID, proposal, submission } from "../tests/fixtures";

const EDITOR_ORIGIN = "https://site.example";
const HANDOFF_NONCE = "d".repeat(64);
const REVIEW_ORIGIN = "https://site.example";
const REVIEW_HANDOFF_NONCE = "e".repeat(64);

function liveHandoffTarget(extra = ""): string {
  const query = new URLSearchParams({
    repository: "example/site",
    editor_origin: EDITOR_ORIGIN,
    handoff_nonce: HANDOFF_NONCE,
  });
  return `/edit/?${query.toString()}${extra}`;
}

function json(value: unknown, status = 200): Response {
  return Response.json(value, { status });
}

function reviewTransportTarget(): string {
  const query = new URLSearchParams({
    artifact_id: String(ARTIFACT_ID),
    handoff_nonce: REVIEW_HANDOFF_NONCE,
    pull_request: "42",
    repository: "example/site",
    review_origin: REVIEW_ORIGIN,
  });
  return `/review-transport/?${query.toString()}`;
}

function transportProposal(): ReviewProposal {
  return {
    ...proposal(),
    review_service_origin: window.location.origin,
    review_site_url: `${REVIEW_ORIGIN}/review/`,
  };
}

function renderReview(
  reviewProposal: ReviewProposal = proposal(),
): ReturnType<typeof vi.fn> {
  const onSubmit = vi.fn(async () => ({
    comment_url: "https://github.com/example/site/pull/42#issuecomment-99",
  }));
  render(
    <Review login="octocat" onSubmit={onSubmit} proposal={reviewProposal} />,
  );
  return onSubmit;
}

function shaclBundle(): ShaclReviewBundle {
  return {
    format: "orinoco-shacl-review-bundle",
    records: [
      {
        pid: "example:one",
        rdf_turtle:
          '<https://example.test/one> <https://example.test/p> "x" .\n',
        schema_type: "example:Thing",
        source_path: "metadata/records/Thing/one.yaml",
        source_sha256: "b".repeat(64),
      },
    ],
    source_commit: "a".repeat(40),
    version: 2,
  };
}

function sendEditorBundle(
  source: MessageEventSource,
  value: unknown = shaclBundle(),
  options: {
    nonce?: string;
    origin?: string;
    source?: MessageEventSource | null;
  } = {},
): void {
  act(() => {
    window.dispatchEvent(
      new MessageEvent("message", {
        data: {
          bundle: value,
          format: "orinoco-lite-shacl-bundle-message-v1",
          handoff_nonce: options.nonce ?? HANDOFF_NONCE,
          repository: "example/site",
        },
        origin: options.origin ?? EDITOR_ORIGIN,
        source: options.source ?? source,
      }),
    );
  });
}

function installOpener(): Window & { postMessage: ReturnType<typeof vi.fn> } {
  const opener = { postMessage: vi.fn() } as unknown as Window & {
    postMessage: ReturnType<typeof vi.fn>;
  };
  Object.defineProperty(window, "opener", {
    configurable: true,
    value: opener,
  });
  return opener;
}

beforeEach(() => {
  window.history.replaceState({}, "", "/");
});

afterEach(() => {
  cleanup();
  Object.defineProperty(window, "opener", {
    configurable: true,
    value: null,
  });
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("curation review interface", () => {
  it("shows responsive record diffs and one exclusive decision group per candidate", async () => {
    const user = userEvent.setup();
    renderReview();
    const first = screen.getByRole("article", { name: "First record" });
    expect(
      within(first).getByText("Original first", { exact: false }),
    ).toBeInTheDocument();
    expect(
      within(first).getByText("Current first", { exact: false }),
    ).toBeInTheDocument();
    const accept = within(first).getByRole("radio", { name: "Accept" });
    const reject = within(first).getByRole("radio", { name: "Reject" });
    await user.click(accept);
    expect(accept).toBeChecked();
    await user.click(reject);
    expect(reject).toBeChecked();
    expect(accept).not.toBeChecked();
    expect(
      screen.queryByRole("link", { name: "Edit in SHACL Vue" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Propose downloaded SHACL bundle" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open GitHub diff" }),
    ).toHaveAttribute("href", "https://github.com/example/site/pull/42");
  });

  it("supports filtering, changed-only view, and keyboard decisions", async () => {
    const user = userEvent.setup();
    renderReview();
    const first = screen.getByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });
    first.focus();
    await user.keyboard("a");
    expect(within(first).getByRole("radio", { name: "Accept" })).toBeChecked();
    await user.keyboard("j");
    expect(second).toHaveFocus();
    await user.keyboard("r");
    expect(within(second).getByRole("radio", { name: "Reject" })).toBeChecked();
    await user.click(
      screen.getByRole("checkbox", { name: "Changed at current head only" }),
    );
    expect(
      screen.queryByRole("article", { name: "Second record" }),
    ).not.toBeInTheDocument();
    await user.type(
      screen.getByRole("searchbox", { name: "Search records" }),
      "no match",
    );
    expect(
      screen.getByText("No records match the current filters."),
    ).toBeInTheDocument();
  });

  it("applies a bulk default only to unresolved records", async () => {
    const user = userEvent.setup();
    renderReview();
    const first = screen.getByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });

    await user.click(within(first).getByRole("radio", { name: "Reject" }));
    await user.click(
      screen.getByRole("button", { name: "Accept all unresolved" }),
    );

    expect(within(first).getByRole("radio", { name: "Reject" })).toBeChecked();
    expect(within(second).getByRole("radio", { name: "Accept" })).toBeChecked();
    expect(screen.getByText("2/2")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Defer all unresolved" }),
    ).toBeDisabled();

    await user.click(within(second).getByRole("radio", { name: "Defer" }));
    expect(within(second).getByRole("radio", { name: "Defer" })).toBeChecked();
  });

  it("moves between visible records when a filter hides an intermediate card", async () => {
    const reviewProposal = proposal();
    const firstCandidate = reviewProposal.candidates[0];
    if (firstCandidate === undefined)
      throw new Error("missing fixture candidate");
    reviewProposal.candidates.push({
      ...firstCandidate,
      after: "pid: example:third\ntitle: Current third\n",
      before: "pid: example:third\ntitle: Original third\n",
      claim_sha256: `sha256:${"3".repeat(64)}`,
      friendly_id: "DRI-0003",
      label: "Third record",
      pid: "example:third",
      record_path: "metadata/records/example/third.yaml",
      source_record_id: "item:GHI789",
    });
    const user = userEvent.setup();
    renderReview(reviewProposal);
    const first = screen.getByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });
    const third = screen.getByRole("article", { name: "Third record" });
    await user.click(within(second).getByRole("radio", { name: "Reject" }));
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Decision" }),
      "unresolved",
    );
    first.focus();
    await user.keyboard("j");
    expect(third).toHaveFocus();
  });

  it("reveals and focuses the first unresolved record after incomplete submission", async () => {
    const user = userEvent.setup();
    renderReview();
    const first = screen.getByRole("article", { name: "First record" });
    await user.click(within(first).getByRole("radio", { name: "Accept" }));
    const decisionFilter = screen.getByRole("combobox", { name: "Decision" });
    await user.selectOptions(decisionFilter, "accept");
    expect(
      screen.queryByRole("article", { name: "Second record" }),
    ).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Post decisions to GitHub" }),
    );
    expect(decisionFilter).toHaveValue("unresolved");
    await waitFor(() =>
      expect(
        screen.getByRole("article", { name: "Second record" }),
      ).toHaveFocus(),
    );
  });

  it("freezes the displayed decisions while a submission is pending", async () => {
    let resolveSubmission:
      ((result: { comment_url: string }) => void) | undefined;
    const pendingSubmission = new Promise<{ comment_url: string }>(
      (resolve) => {
        resolveSubmission = resolve;
      },
    );
    const onSubmit = vi.fn(() => pendingSubmission);
    render(
      <Review login="octocat" onSubmit={onSubmit} proposal={proposal()} />,
    );
    const user = userEvent.setup();
    const first = screen.getByRole("article", { name: "First record" });
    const second = screen.getByRole("article", { name: "Second record" });
    const accept = within(first).getByRole("radio", { name: "Accept" });
    const defer = within(second).getByRole("radio", { name: "Defer" });
    await user.click(accept);
    await user.click(defer);
    await user.click(
      screen.getByRole("button", { name: "Post decisions to GitHub" }),
    );
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));

    expect(accept).toBeDisabled();
    expect(defer).toBeDisabled();
    first.focus();
    await user.keyboard("r");
    expect(accept).toBeChecked();
    expect(
      within(first).getByRole("radio", { name: "Reject" }),
    ).not.toBeChecked();

    resolveSubmission?.({
      comment_url: "https://github.com/example/site/pull/42#issuecomment-99",
    });
    expect(
      await screen.findByRole("link", { name: "View authenticated comment" }),
    ).toBeVisible();
    expect(accept).toBeDisabled();
    expect(defer).toBeDisabled();
  });

  it("validates completion and posts the complete ordered decision payload", async () => {
    const onSubmit = renderReview();
    const user = userEvent.setup();
    const first = screen.getByRole("article", { name: "First record" });
    await user.click(within(first).getByRole("radio", { name: "Accept" }));
    await user.click(
      screen.getByRole("button", { name: "Post decisions to GitHub" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "1 record still needs",
    );
    const second = screen.getByRole("article", { name: "Second record" });
    await user.click(within(second).getByRole("radio", { name: "Defer" }));
    await user.click(
      screen.getByRole("button", { name: "Post decisions to GitHub" }),
    );
    await screen.findByRole("link", { name: "View authenticated comment" });
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const body = onSubmit.mock.calls[0]?.[0] as Record<string, unknown>;
    expect(body).not.toHaveProperty("reviewer");
    expect(
      (body.decisions as Array<Record<string, unknown>>).map(
        (item) => item.disposition,
      ),
    ).toEqual(["accept", "defer"]);
  });
});

describe("central authenticated transport", () => {
  it("directs entry-point visitors back to the deployed review route", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);
    expect(
      screen.getByRole("heading", {
        name: "Open review from the deployed website",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not host a second review application/),
    ).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves the exact downstream handoff through GitHub sign-in", async () => {
    window.history.replaceState({}, "", reviewTransportTarget());
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ authenticated: false })),
    );
    render(<App />);
    expect(
      await screen.findByRole("link", { name: "Continue with GitHub" }),
    ).toHaveAttribute(
      "href",
      `/api/auth/start?artifact_id=${ARTIFACT_ID}&pull_request=42&repository=example%2Fsite&review_origin=https%3A%2F%2Fsite.example&handoff_nonce=${REVIEW_HANDOFF_NONCE}`,
    );
    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });

  it("handshakes once and gates one exact submission behind central confirmation", async () => {
    window.history.replaceState({}, "", reviewTransportTarget());
    const opener = installOpener();
    const reviewProposal = transportProposal();
    let resolveSubmit: ((response: Response) => void) | undefined;
    const submitResponse = new Promise<Response>((resolve) => {
      resolveSubmit = resolve;
    });
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/session") {
          return json({
            authenticated: true,
            csrf_token: "csrf-token",
            login: "octocat",
            review_grant: {
              artifact_id: ARTIFACT_ID,
              handoff_nonce: REVIEW_HANDOFF_NONCE,
              pull_request: 42,
              repository: "example/site",
              review_origin: REVIEW_ORIGIN,
            },
          });
        }
        if (url.startsWith("/api/proposal?")) return json(reviewProposal);
        if (url === `/api/submit?artifact_id=${ARTIFACT_ID}`) {
          expect(init?.headers).toMatchObject({ "X-CSRF-Token": "csrf-token" });
          expect(JSON.parse(String(init?.body))).toEqual(submission());
          return submitResponse;
        }
        throw new Error(`Unexpected fetch: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await waitFor(() =>
      expect(opener.postMessage).toHaveBeenCalledWith(
        {
          artifact_id: ARTIFACT_ID,
          format: "orinoco-lite-review-transport-ready-v1",
          handoff_nonce: REVIEW_HANDOFF_NONCE,
          pull_request: 42,
          repository: "example/site",
        },
        REVIEW_ORIGIN,
      ),
    );

    const proposalRequest = {
      artifact_id: ARTIFACT_ID,
      format: "orinoco-lite-review-proposal-request-v1",
      handoff_nonce: REVIEW_HANDOFF_NONCE,
      pull_request: 42,
      repository: "example/site",
    };
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: proposalRequest,
          origin: "https://attacker.example",
          source: opener,
        }),
      );
      window.dispatchEvent(
        new MessageEvent("message", {
          data: { ...proposalRequest, artifact_id: ARTIFACT_ID + 1 },
          origin: REVIEW_ORIGIN,
          source: opener,
        }),
      );
      window.dispatchEvent(
        new MessageEvent("message", {
          data: { ...proposalRequest, extra: true },
          origin: REVIEW_ORIGIN,
          source: opener,
        }),
      );
      window.dispatchEvent(
        new MessageEvent("message", {
          data: proposalRequest,
          origin: REVIEW_ORIGIN,
          source: window,
        }),
      );
    });
    expect(
      opener.postMessage.mock.calls.filter(
        ([value]) =>
          (value as Record<string, unknown>).format ===
          "orinoco-lite-review-proposal-message-v1",
      ),
    ).toHaveLength(0);

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: proposalRequest,
          origin: REVIEW_ORIGIN,
          source: opener,
        }),
      );
    });
    await waitFor(() =>
      expect(opener.postMessage).toHaveBeenCalledWith(
        {
          artifact_id: ARTIFACT_ID,
          format: "orinoco-lite-review-proposal-message-v1",
          handoff_nonce: REVIEW_HANDOFF_NONCE,
          login: "octocat",
          proposal: reviewProposal,
          pull_request: 42,
          repository: "example/site",
        },
        REVIEW_ORIGIN,
      ),
    );

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: proposalRequest,
          origin: REVIEW_ORIGIN,
          source: opener,
        }),
      );
    });
    expect(
      opener.postMessage.mock.calls.filter(
        ([value]) =>
          (value as Record<string, unknown>).format ===
          "orinoco-lite-review-proposal-message-v1",
      ),
    ).toHaveLength(1);

    const request = {
      artifact_id: ARTIFACT_ID,
      format: "orinoco-lite-review-submission-message-v1",
      handoff_nonce: REVIEW_HANDOFF_NONCE,
      pull_request: 42,
      repository: "example/site",
      submission: submission(),
    };
    act(() => {
      for (const [data, origin, source] of [
        [request, "https://attacker.example", opener],
        [{ ...request, repository: "example/other" }, REVIEW_ORIGIN, opener],
        [{ ...request, extra: true }, REVIEW_ORIGIN, opener],
        [request, REVIEW_ORIGIN, window],
      ] as const) {
        window.dispatchEvent(
          new MessageEvent("message", { data, origin, source }),
        );
      }
    });
    expect(
      screen.queryByRole("heading", {
        name: "Confirm decisions before posting",
      }),
    ).not.toBeInTheDocument();

    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: request,
          origin: REVIEW_ORIGIN,
          source: opener,
        }),
      );
      window.dispatchEvent(
        new MessageEvent("message", {
          data: request,
          origin: REVIEW_ORIGIN,
          source: opener,
        }),
      );
    });
    expect(
      await screen.findByRole("heading", {
        name: "Confirm decisions before posting",
      }),
    ).toBeInTheDocument();
    expect(opener.postMessage).toHaveBeenCalledWith(
      {
        artifact_id: ARTIFACT_ID,
        format: "orinoco-lite-review-confirmation-pending-v1",
        handoff_nonce: REVIEW_HANDOFF_NONCE,
        pull_request: 42,
        repository: "example/site",
      },
      REVIEW_ORIGIN,
    );
    expect(
      screen.getByRole("button", {
        name: "Waiting for downstream acknowledgement…",
      }),
    ).toBeDisabled();
    const confirmationReady = {
      artifact_id: ARTIFACT_ID,
      format: "orinoco-lite-review-confirmation-ready-v1",
      handoff_nonce: REVIEW_HANDOFF_NONCE,
      pull_request: 42,
      repository: "example/site",
    };
    act(() => {
      window.dispatchEvent(
        new MessageEvent("message", {
          data: confirmationReady,
          origin: REVIEW_ORIGIN,
          source: opener,
        }),
      );
    });
    expect(screen.getByText("octocat")).toBeVisible();
    expect(screen.getByText("example/site")).toBeVisible();
    expect(screen.getByText("#42")).toBeVisible();
    expect(screen.getByText(reviewProposal.proposal_sha)).toBeVisible();
    expect(screen.getByText(reviewProposal.head_sha)).toBeVisible();
    const confirmed = screen.getByRole("list", { name: "Confirmed decisions" });
    expect(confirmed).toHaveTextContent(
      "metadata/records/example/first.yaml (DRI-0001) → accept",
    );
    expect(confirmed).toHaveTextContent(
      "metadata/records/example/second.yaml (DRI-0002) → defer",
    );
    expect(
      fetchMock.mock.calls.filter(
        ([input]) => String(input) === `/api/submit?artifact_id=${ARTIFACT_ID}`,
      ),
    ).toHaveLength(0);

    const confirm = await screen.findByRole("button", {
      name: "Post these decisions to GitHub",
    });
    act(() => {
      confirm.click();
      confirm.click();
    });
    expect(opener.postMessage).toHaveBeenCalledWith(
      {
        artifact_id: ARTIFACT_ID,
        format: "orinoco-lite-review-post-started-v1",
        handoff_nonce: REVIEW_HANDOFF_NONCE,
        pull_request: 42,
        repository: "example/site",
      },
      REVIEW_ORIGIN,
    );
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(
          ([input]) =>
            String(input) === `/api/submit?artifact_id=${ARTIFACT_ID}`,
        ),
      ).toHaveLength(1),
    );
    expect(
      opener.postMessage.mock.calls.filter(
        ([value]) =>
          (value as Record<string, unknown>).format ===
          "orinoco-lite-review-submission-result-v1",
      ),
    ).toHaveLength(0);

    await act(async () => {
      resolveSubmit?.(
        json(
          {
            comment_url:
              "https://github.com/example/site/pull/42#issuecomment-99",
          },
          201,
        ),
      );
      await submitResponse;
    });
    await waitFor(() =>
      expect(opener.postMessage).toHaveBeenCalledWith(
        {
          artifact_id: ARTIFACT_ID,
          comment_url:
            "https://github.com/example/site/pull/42#issuecomment-99",
          error: null,
          format: "orinoco-lite-review-submission-result-v1",
          handoff_nonce: REVIEW_HANDOFF_NONCE,
          pull_request: 42,
          repository: "example/site",
          retry_safe: false,
        },
        REVIEW_ORIGIN,
      ),
    );
    expect(
      opener.postMessage.mock.calls.filter(
        ([value]) =>
          (value as Record<string, unknown>).format ===
          "orinoco-lite-review-submission-result-v1",
      ),
    ).toHaveLength(1);
    expect(confirm).toBeDisabled();
  });
});

describe("SHACL Vue browser-memory proposal handoff", () => {
  it("preserves exact existing-PR coordinates through user authentication", async () => {
    const source = "a".repeat(40);
    window.history.replaceState(
      {},
      "",
      `${liveHandoffTarget()}&pull_request=42&expected_head_sha=${source}`,
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ authenticated: false })),
    );
    render(<App />);
    expect(
      await screen.findByRole("link", { name: "Continue with GitHub" }),
    ).toHaveAttribute(
      "href",
      `/api/auth/shacl-start?repository=example%2Fsite&editor_origin=https%3A%2F%2Fsite.example&handoff_nonce=${HANDOFF_NONCE}&expected_head_sha=${source}&pull_request=42`,
    );
    expect(
      screen.getByText(/Secure GitHub sign-in intentionally ends this popup/),
    ).toHaveTextContent(
      "after sign-in, download its normal bundle and select that file here",
    );
  });

  it("receives the static editor bundle and performs one acknowledged explicit write", async () => {
    window.history.replaceState({}, "", liveHandoffTarget());
    const opener = installOpener();
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/session") {
          return json({
            authenticated: true,
            csrf_token: "csrf-token",
            login: "octocat",
          });
        }
        if (url === "/api/shacl/propose") {
          expect(init?.headers).toMatchObject({
            "X-CSRF-Token": "csrf-token",
          });
          return json(
            {
              commit_sha: "c".repeat(40),
              commit_url: `https://github.com/example/site/commit/${"c".repeat(40)}`,
              pull_request: 43,
              pull_request_url: "https://github.com/example/site/pull/43",
            },
            201,
          );
        }
        throw new Error(`Unexpected fetch: ${url}`);
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", {
      name: "Waiting for the static editor",
    });
    expect(
      screen.getByText(/If you were already signed in when this window opened/),
    ).toHaveTextContent(
      "GitHub sign-in ends that live link, so download the unchanged bundle",
    );
    expect(opener.postMessage).toHaveBeenCalledWith(
      {
        format: "orinoco-lite-shacl-proposal-ready-v1",
        handoff_nonce: HANDOFF_NONCE,
        repository: "example/site",
      },
      EDITOR_ORIGIN,
    );
    expect(
      screen.queryByTitle("SHACL Vue metadata editor"),
    ).not.toBeInTheDocument();
    const bundle = shaclBundle();
    sendEditorBundle(opener, bundle);
    expect(
      await screen.findByRole("heading", { name: "1 edited record" }),
    ).toBeInTheDocument();
    expect(screen.getByText("example:one")).toBeInTheDocument();
    const propose = screen.getByRole("button", { name: "Propose via GitHub" });
    expect(propose).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: /I confirm this bundle contains no secrets/,
      }),
    );
    expect(propose).toBeEnabled();
    await user.click(propose);
    await screen.findByRole("link", { name: "Open draft pull request" });
    const write = fetchMock.mock.calls.find(
      ([url]) => url === "/api/shacl/propose",
    );
    const submitted = JSON.parse(
      String((write?.[1] as RequestInit).body),
    ) as Record<string, unknown>;
    expect(submitted).toEqual({
      acknowledge_public_data: true,
      bundle,
      format: "orinoco-lite-shacl-proposal-v1",
      repository: "example/site",
      target: { kind: "standalone" },
    });
    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
  });

  it("accepts the typed bundle only from its exact opener, origin, and nonce", async () => {
    window.history.replaceState({}, "", liveHandoffTarget());
    const opener = installOpener();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          authenticated: true,
          csrf_token: "csrf-token",
          login: "octocat",
        }),
      ),
    );
    render(<App />);
    await screen.findByRole("heading", {
      name: "Waiting for the static editor",
    });
    sendEditorBundle(opener, shaclBundle(), {
      origin: "http://editor.example",
    });
    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
    sendEditorBundle(opener, shaclBundle(), { source: window });
    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
    sendEditorBundle(opener, shaclBundle(), { nonce: "e".repeat(64) });
    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
    sendEditorBundle(opener);
    expect(
      await screen.findByRole("heading", { name: "1 edited record" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(`Browser source: ${EDITOR_ORIGIN}`),
    ).toBeInTheDocument();
  });

  it("rejects malformed and oversized live bundles before retaining them", async () => {
    window.history.replaceState({}, "", liveHandoffTarget());
    const opener = installOpener();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          authenticated: true,
          csrf_token: "csrf-token",
          login: "octocat",
        }),
      ),
    );
    render(<App />);
    await screen.findByRole("heading", {
      name: "Waiting for the static editor",
    });

    sendEditorBundle(opener, { ...shaclBundle(), retained_copy: true });
    const duplicate = shaclBundle();
    duplicate.records.push({ ...duplicate.records[0]! });
    sendEditorBundle(opener, duplicate);
    const badPath = shaclBundle();
    badPath.records[0]!.source_path = "../record.yaml";
    sendEditorBundle(opener, badPath);
    const badDigest = shaclBundle();
    badDigest.records[0]!.source_sha256 = "not-a-digest";
    sendEditorBundle(opener, badDigest);
    const oversized = shaclBundle();
    oversized.records[0]!.rdf_turtle = "x".repeat(MAX_SHACL_BUNDLE_BYTES);
    sendEditorBundle(opener, oversized);

    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
    sendEditorBundle(opener);
    expect(
      await screen.findByRole("heading", { name: "1 edited record" }),
    ).toBeInTheDocument();
  });

  it("accepts the unchanged downloaded bundle as a fallback", async () => {
    window.history.replaceState({}, "", "/edit/?repository=example%2Fsite");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          authenticated: true,
          csrf_token: "csrf-token",
          login: "octocat",
        }),
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    const input = await screen.findByLabelText(
      "Use a downloaded review bundle",
    );

    await user.upload(
      input,
      new File([JSON.stringify(shaclBundle())], "review.json", {
        type: "application/json",
      }),
    );

    expect(
      await screen.findByRole("heading", { name: "1 edited record" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Browser source: downloaded file: review.json"),
    ).toBeInTheDocument();
  });

  it("rejects malformed and oversized downloaded bundles", async () => {
    window.history.replaceState({}, "", "/edit/?repository=example%2Fsite");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          authenticated: true,
          csrf_token: "csrf-token",
          login: "octocat",
        }),
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    const input = await screen.findByLabelText(
      "Use a downloaded review bundle",
    );
    const duplicate = shaclBundle();
    duplicate.records.push({ ...duplicate.records[0]! });
    await user.upload(
      input,
      new File([JSON.stringify(duplicate)], "duplicate.json", {
        type: "application/json",
      }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "not a SHACL Vue v2 review bundle",
    );
    await user.upload(
      input,
      new File(["x".repeat(MAX_SHACL_BUNDLE_BYTES + 1)], "oversized.json", {
        type: "application/json",
      }),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "must be no larger than 10 MiB",
    );
    expect(
      screen.queryByRole("heading", { name: "1 edited record" }),
    ).not.toBeInTheDocument();
  });

  it("binds an existing-PR handoff to the received source commit", async () => {
    const source = "a".repeat(40);
    const opener = installOpener();
    window.history.replaceState(
      {},
      "",
      `${liveHandoffTarget()}&pull_request=42&expected_head_sha=${source}`,
    );
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/session") {
          return json({
            authenticated: true,
            csrf_token: "csrf-token",
            login: "octocat",
          });
        }
        const body = JSON.parse(String(init?.body)) as {
          target: Record<string, unknown>;
        };
        expect(body.target).toEqual({
          expected_head_sha: source,
          kind: "pull_request",
          pull_request: 42,
        });
        return json(
          {
            commit_sha: "c".repeat(40),
            commit_url: `https://github.com/example/site/commit/${"c".repeat(40)}`,
            pull_request: 42,
            pull_request_url: "https://github.com/example/site/pull/42",
          },
          201,
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole("heading", {
      name: "Waiting for the static editor",
    });
    sendEditorBundle(opener);
    await screen.findByRole("heading", { name: "1 edited record" });
    expect(
      screen.getByRole("spinbutton", { name: "Draft pull request" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("radio", {
        name: "Create a branch and new draft pull request",
      }),
    ).toBeDisabled();
    expect(
      screen.getByText(`Bound to draft pull request #42 at`, { exact: false }),
    ).toHaveTextContent(source);
    await user.click(
      screen.getByRole("checkbox", {
        name: /I confirm this bundle contains no secrets/,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Propose via GitHub" }),
    );
    await screen.findByRole("link", { name: "Open draft pull request" });
  });
});
