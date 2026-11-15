# Data ownership

| Data | Owner (source of truth) | Notes |
|---|---|---|
| Organizations, users, roles, credentials | PostgreSQL | Argon2 password hashes; email globally unique |
| Agent configuration, lifecycle status, version | PostgreSQL | `agents` table |
| Executions (prompt, output, tokens, latency, mode) | PostgreSQL | `executions` |
| Audit log | PostgreSQL | append-only, enforced by a DB trigger |
| Event outbox + idempotency ledger | PostgreSQL | `outbox_events`, `processed_events` |
| Relationships (reports-to, belongs-to, uses-model) | Neo4j | A projection built from events; disposable and rebuildable from PostgreSQL |
| Event transport / DLQ | Kafka | Transport only, not a system of record |
| Rate-limit counters, live-update pub/sub | Redis | Ephemeral |
| Embeddings / semantic memory | Qdrant (NOT BUILT) | Planned |
| Analytics / time series | ClickHouse (NOT BUILT) | Planned |

Note: the supervisor relationship is stored as `agents.supervisor_agent_id` in PostgreSQL (needed for cycle checks and transactional integrity) and is also projected as `AGENT_REPORTS_TO_AGENT` in Neo4j for traversal and visualisation. PostgreSQL wins on conflict.
