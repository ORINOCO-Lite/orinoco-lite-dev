import type { AuthenticationChannel, SubmissionAccess } from "./submission";

export interface BrowserAuthentication extends AuthenticationChannel {
  ready: Promise<{ login: string }>;
  credentials(sourceCommit: string): Promise<SubmissionAccess>;
  release(): Promise<void>;
  cancel(): void;
}

/** Open synchronously from the user's click, keeping OAuth outside the editor. */
export function openAuthentication(
  value: {
    repository: string;
    service_origin: string;
    kind: "shacl" | "review";
    pull_request?: number;
    artifact_id?: number;
  },
  target: Window = window,
): BrowserAuthentication {
  const service = new URL(value.service_origin);
  if (
    service.origin !== value.service_origin ||
    (service.protocol !== "https:" &&
      !(
        service.protocol === "http:" &&
        ["localhost", "127.0.0.1"].includes(service.hostname)
      ))
  )
    throw new Error("The website has an invalid authentication service URL.");
  if (target.top !== target.self)
    throw new Error("Open the website in its own tab to sign in.");
  function randomId(bytes: number): string {
    return Array.from(
      target.crypto.getRandomValues(new Uint8Array(bytes)),
      (byte) => byte.toString(16).padStart(2, "0"),
    ).join("");
  }
  const nonce = randomId(32);
  const url = new URL("/api/transport", service);
  url.searchParams.set("kind", value.kind);
  url.searchParams.set("repository", value.repository);
  url.searchParams.set("handoff_nonce", nonce);
  url.searchParams.set(
    value.kind === "review" ? "review_origin" : "editor_origin",
    target.location.origin,
  );
  if (value.kind === "review") {
    url.searchParams.set("pull_request", String(value.pull_request));
    url.searchParams.set("artifact_id", String(value.artifact_id));
  }
  const pending = new Map<
    string,
    { resolve(value: any): void; reject(error: Error): void }
  >();
  let resolveReady!: (value: { login: string }) => void;
  let rejectReady!: (error: Error) => void;
  const ready = new Promise<{ login: string }>((resolve, reject) => {
    resolveReady = resolve;
    rejectReady = reject;
  });
  // A popup can be closed while the editor is still preparing its input.
  void ready.catch(() => undefined);
  let popup: Window | null = null;
  let ended = false;
  let timer: number | undefined;
  let closedPoll: number | undefined;
  function dispose(
    error = new Error(
      "GitHub sign-in was closed. Your edit is still available.",
    ),
  ) {
    if (ended) return;
    ended = true;
    target.removeEventListener("message", receive);
    target.clearTimeout(timer);
    target.clearInterval(closedPoll);
    rejectReady(error);
    for (const request of pending.values()) request.reject(error);
    pending.clear();
    popup?.close();
  }
  function errorFrom(value: any): Error {
    return Object.assign(
      new Error(
        typeof value?.message === "string"
          ? value.message
          : "GitHub authentication failed.",
      ),
      {
        code: value?.code,
        status: value?.status,
      },
    );
  }
  function receive(event: MessageEvent) {
    const message = event.data;
    if (
      ended ||
      event.source !== popup ||
      event.origin !== service.origin ||
      message?.handoff_nonce !== nonce ||
      message?.repository !== value.repository
    )
      return;
    if (message.format === "orinoco-lite-transport-error-v1") {
      dispose(errorFrom(message));
      return;
    }
    if (
      message.format === "orinoco-authentication-ready-v1" &&
      typeof message.login === "string"
    ) {
      resolveReady({ login: message.login });
      return;
    }
    if (
      message.format !== "orinoco-authentication-response-v1" ||
      typeof message.id !== "string"
    )
      return;
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(errorFrom(message.error));
    else request.resolve(message.result);
  }
  async function request(method: string, input: unknown): Promise<any> {
    await ready;
    if (ended || !popup || popup.closed)
      throw new Error(
        "Reconnect to GitHub to continue. Your edit is still available.",
      );
    const id = randomId(16);
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      popup!.postMessage(
        {
          format: "orinoco-authentication-request-v1",
          handoff_nonce: nonce,
          repository: value.repository,
          id,
          method,
          input,
        },
        service.origin,
      );
    });
  }
  target.addEventListener("message", receive);
  popup = target.open(
    url.href,
    `orinoco-github-${nonce}`,
    "popup,width=720,height=760,resizable=yes,scrollbars=yes",
  );
  if (!popup) {
    dispose();
    throw new Error("Allow the GitHub sign-in popup and try again.");
  }
  timer = target.setTimeout(
    () =>
      dispose(
        new Error(
          "GitHub sign-in expired. Reconnect to resume the same submission.",
        ),
      ),
    10 * 60 * 1000,
  );
  closedPoll = target.setInterval(() => {
    if (popup?.closed) dispose();
  }, 500);
  return {
    ready,
    credentials: (source_commit) => request("credentials", { source_commit }),
    authorize: (input) => request("authorize", input),
    async release() {
      try {
        if (!ended) await request("release", {});
      } finally {
        dispose();
      }
    },
    cancel: () => dispose(),
  };
}
