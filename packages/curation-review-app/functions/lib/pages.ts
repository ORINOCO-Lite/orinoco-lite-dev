export interface Env {
  GITHUB_CLIENT_ID: string;
  GITHUB_CLIENT_SECRET: string;
  PUBLIC_ORIGIN: string;
  SESSION_SEAL_KEY: string;
}

export interface EventContext<TEnv = Env> {
  data: Record<string, unknown>;
  env: TEnv;
  functionPath: string;
  next(input?: Request | string, init?: RequestInit): Promise<Response>;
  params: Record<string, string | string[]>;
  passThroughOnException(): void;
  request: Request;
  waitUntil(promise: Promise<unknown>): void;
}

export type PagesHandler = (
  context: EventContext,
) => Promise<Response> | Response;
