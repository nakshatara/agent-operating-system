# Roadmap: what is NOT built

Phase 1 (this repo): auth, orgs, agent registry, lifecycle, basic execution, graph projection, audit, dashboard.

| PRD phase | Not built yet |
|---|---|
| 2 - Orchestration | Workflow builder and engine, Temporal, durable execution, retries/timeouts as workflow semantics, command center |
| 3 - Collaboration | Agent-to-agent messaging, collaboration hub, shared context, task delegation along the hierarchy |
| 4 - Governance | Approvals, policy engine, enforcement of the 4 autonomy levels (currently stored only), human-in-the-loop gates |
| 5 - Knowledge and memory | Qdrant vector store, memory services, knowledge ingestion, retrieval |
| 6 - Enterprise | Keycloak/SSO, ClickHouse analytics and cost reporting, Kubernetes deployment, multi-region, advanced observability |

Also open: agent edit UI (the PATCH endpoint exists), user role changes/deactivation, execution cancel, ORGANIZATION_UPDATED event, pagination on the graph, token price tables (configurable via `PRICING_JSON`, intentionally empty).
