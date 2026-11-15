# Architecture (Phase 1)

A modular monolith (`backend/app/modules/*`): identity, organizations, agents, runtime, model_gateway, graph, events, audit, dashboard. Modules talk through service functions and events so each can later be extracted. Cross-cutting code lives in `app/core`.

## Request flow
Router -> dependency (JWT -> user row, role check) -> service (tenant-scoped queries; organization id always from the token) -> state change + outbox row + audit row in ONE transaction -> commit.

## Event backbone
1. Services call `events.outbox.emit()` inside the same DB transaction as the change (transactional outbox, table `outbox_events`).
2. The relay task polls unpublished rows with `FOR UPDATE SKIP LOCKED`, publishes the versioned envelope to Kafka topic `agentos.events` (key = organization id), then marks rows published. Delivery is at-least-once.
3. Two in-process consumers, each its own consumer group: `agentos-graph-projector` (idempotent Cypher MERGE into Neo4j, version-guarded for agents) and `agentos-live-fanout` (Redis pub/sub `events:{org}` which the WebSocket endpoint streams).
4. Idempotency ledger: `processed_events (consumer, event_id)`. Infrastructure outages (Neo4j/Redis) are retried indefinitely; other failures are retried a bounded number of times and then written to `agentos.events.dlq`.
5. The graph can always be rebuilt from PostgreSQL via `POST /api/v1/graph/reconcile`.

## Execution
`POST /agents/{id}/executions` stores a queued row, returns 202, and a FastAPI background task runs it via the model gateway. Not durable: on restart, stranded executions are marked failed. A durable runner (Temporal) is on the roadmap. Prompts and model output are stored as opaque data; they never influence configuration or permissions.

## Model gateway
`ModelProvider` protocol (`complete(request) -> ModelResponse`); adapters for Anthropic Messages, OpenAI Chat Completions (raw httpx, bounded retries on timeout/429/5xx) and `SimulatedProvider`. Mode `simulated` always selects the simulated adapter.

## Honest limitations
Single backend replica assumed; per-agent autonomy level is stored but not enforced; the org rename is not projected to the graph until reconcile (no ORGANIZATION_UPDATED event defined in this phase).
