export type Role = "owner" | "admin" | "operator" | "viewer";

export interface User {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
}

export type Readiness = "simulated" | "configured" | "live";
export type ExecutionMode = "simulated" | "live";

export interface Agent {
  id: string;
  organization_id: string;
  name: string;
  role: string;
  description: string;
  system_instructions: string;
  objectives: string[];
  provider: string;
  model: string;
  autonomy_level: number;
  supervisor_agent_id: string | null;
  execution_mode: ExecutionMode;
  status: string;
  version: number;
  created_at: string;
  updated_at: string;
  readiness: Readiness;
  available_actions: string[];
}

export interface AgentCreate {
  name: string;
  role: string;
  description: string;
  system_instructions: string;
  objectives: string[];
  provider: string;
  model: string;
  autonomy_level: number;
  supervisor_agent_id: string | null;
  execution_mode: ExecutionMode;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Execution {
  id: string;
  agent_id: string;
  input_prompt: string;
  output: string | null;
  error: string | null;
  status: "queued" | "running" | "succeeded" | "failed";
  mode: ExecutionMode;
  provider: string;
  model: string;
  agent_version: number;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  cost_usd: number | null;
  trace_id: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ModelInfo {
  provider: string;
  id: string;
  live_available: boolean;
  input_per_mtok: number | null;
  output_per_mtok: number | null;
}

export interface ModelList {
  default_provider: string;
  default_model: string;
  models: ModelInfo[];
}

export interface AuditLog {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string | null;
  trace_id: string | null;
  created_at: string;
}

export interface HealthItem {
  ok: boolean;
  detail: string | null;
}

export interface DashboardSummary {
  agents: {
    total: number;
    active: number;
    paused: number;
    by_status: Record<string, number>;
    by_readiness: Record<Readiness, number>;
  };
  executions: { queued: number; running: number; succeeded: number; failed: number; total: number };
  tokens: { input: number; output: number; total: number };
  health: Record<"postgres" | "neo4j" | "kafka" | "redis", HealthItem>;
}

export interface GraphNode {
  id: string;
  type: "Organization" | "User" | "Agent" | "Model";
  label: string;
  properties: Record<string, unknown>;
}
export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}
export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface EventEnvelope {
  event_id: string;
  type: string;
  version: number;
  organization_id: string;
  occurred_at: string;
  correlation_id: string;
  trace_id: string;
  payload: Record<string, unknown>;
}
