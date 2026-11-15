import type {
  Agent,
  AgentCreate,
  AuditLog,
  DashboardSummary,
  Execution,
  GraphData,
  ModelList,
  Organization,
  Page,
  TokenResponse,
  User,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "agentos.token";

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function loadToken(): string | null {
  if (token) return token;
  try {
    token = window.localStorage.getItem(TOKEN_KEY);
  } catch {
    token = null;
  }
  return token;
}

export function setToken(value: string | null): void {
  token = value;
  try {
    if (value) window.localStorage.setItem(TOKEN_KEY, value);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: token stays in memory only */
  }
}

export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
  if (init.body) headers["Content-Type"] = "application/json";
  const t = loadToken();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the API");
  }
  if (!res.ok) {
    let code = "http_error";
    let message = res.statusText;
    let details: unknown;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
      details = body?.error?.details;
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 401 && t && onUnauthorized) onUnauthorized();
    throw new ApiError(res.status, code, message, details);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const qs = (params: Record<string, string | number | undefined | null>): string => {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
};

export const api = {
  register: (b: { organization_name: string; full_name: string; email: string; password: string }) =>
    request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(b) }),
  login: (b: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(b) }),
  me: () => request<User>("/auth/me"),

  organization: () => request<Organization>("/organization"),
  updateOrganization: (name: string) =>
    request<Organization>("/organization", { method: "PATCH", body: JSON.stringify({ name }) }),
  users: () => request<User[]>("/users"),
  inviteUser: (b: { email: string; full_name: string; role: string; password?: string }) =>
    request<{ user: User; temporary_password: string | null }>("/users", {
      method: "POST",
      body: JSON.stringify(b),
    }),

  models: () => request<ModelList>("/models"),
  agents: (f: { status?: string; readiness?: string; provider?: string; q?: string; limit?: number; offset?: number } = {}) =>
    request<Page<Agent>>(`/agents${qs(f)}`),
  agent: (id: string) => request<Agent>(`/agents/${id}`),
  createAgent: (b: AgentCreate) => request<Agent>("/agents", { method: "POST", body: JSON.stringify(b) }),
  lifecycle: (id: string, action: string) =>
    request<Agent>(`/agents/${id}/lifecycle/${action}`, { method: "POST" }),
  execute: (id: string, prompt: string) =>
    request<Execution>(`/agents/${id}/executions`, { method: "POST", body: JSON.stringify({ prompt }) }),
  agentExecutions: (id: string, limit = 20) => request<Page<Execution>>(`/agents/${id}/executions${qs({ limit })}`),

  graph: () => request<GraphData>("/graph"),
  reconcileGraph: () => request<{ reconciled: Record<string, number> }>("/graph/reconcile", { method: "POST" }),

  audit: (f: { action?: string; resource_type?: string; limit?: number; offset?: number } = {}) =>
    request<Page<AuditLog>>(`/audit${qs(f)}`),
  dashboard: () => request<DashboardSummary>("/dashboard/summary"),
};

export function eventsUrl(): string | null {
  const t = loadToken();
  if (!t) return null;
  return `${API_URL.replace(/^http/, "ws")}/api/v1/ws/events?token=${encodeURIComponent(t)}`;
}
