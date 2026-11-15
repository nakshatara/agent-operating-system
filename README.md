# AgentOS - AI Agent Operating System (Phase 1: Foundation)

A graph-native, event-driven platform for creating, organising, running, and centrally controlling teams of AI agents with human oversight. This repository is the first vertical slice: auth and tenants, agent registry and lifecycle, real (or explicitly simulated) agent execution, an event backbone, a Neo4j graph projection, audit logging, and a live dashboard.

## Status (read this first)

Verified (run on a dev machine without Docker):
- Backend: `ruff check` clean; 42 non-integration pytest tests pass; `app.main` imports and the OpenAPI schema generates with no services running; the API boots and answers `/health`, 401 and 422 error envelopes, and `/api/v1/docs`; `alembic upgrade head --sql` renders the expected DDL.
- Frontend: `npm install`, `npx tsc --noEmit`, and `npm run build` succeed.

NOT verified - nothing that touches infrastructure has ever been run:
- No PostgreSQL, Neo4j, Kafka, or Redis was available. The real migration against Postgres, all SQL queries, the outbox relay, Kafka producer/consumers, Cypher statements, the Redis fan-out and the WebSocket stream are untested.
- `docker-compose.yml` and both Dockerfiles have never been built or started.
- The integration test (`backend/tests/test_integration.py`) has never been executed.
- Live calls to Anthropic/OpenAI have never been made; adapters are only tested against `httpx.MockTransport`. Model ids in the registry are as specified, not confirmed against the vendor APIs.
- The frontend has never been exercised against a running backend (no browser run).

Expect first-run bugs. See `docs/roadmap.md` for what is deliberately not built.

## Prerequisites
- Docker Desktop or OrbStack (recommended path).
- Optional, to run outside Docker: Python 3.12 and Node 20.

## Quick start
```bash
cp .env.example .env        # replace every placeholder; JWT_SECRET: openssl rand -hex 32
make up                     # builds and starts postgres, neo4j, redis, kafka, backend, frontend
make logs
```
- UI: http://localhost:3000 (register creates an organization and its owner)
- API docs (OpenAPI): http://localhost:8000/api/v1/docs
- Health: http://localhost:8000/health, readiness: http://localhost:8000/ready
- Neo4j browser: http://localhost:7474

The backend applies Alembic migrations on start (`make migrate` re-runs them). It boots even if Kafka or Neo4j are down and keeps retrying in the background.

## Simulated vs live agents
Every agent has an `execution_mode`:
- `simulated`: runs through an explicit `SimulatedProvider`. No model is called; output is prefixed `[SIMULATED]` and token counts are empty. Executions are stored with `mode=simulated` and badged SIMULATED in the UI.
- `live`: calls the real provider. Set a key in `.env` and restart the backend:
  `ANTHROPIC_API_KEY=...` and/or `OPENAI_API_KEY=...`.

The computed `readiness` field: `simulated`, `configured` (live mode but no provider key - cannot run, executions are rejected with 409), or `live` (live mode with key present). Only `active` agents can execute.

## Tests and lint
```bash
make test     # unit tests in a container (no infrastructure needed)
make lint
# Host: cd backend && uv venv --python 3.12 && uv pip install -e ".[dev]" && pytest -m "not integration"
# Integration (needs `make up` + migrations): cd backend && pytest -m integration
```

## Layout
`backend/` FastAPI modular monolith, `frontend/` Next.js App Router, `docs/` architecture, data ownership, deployment, roadmap.

## Roles
owner > admin > operator > viewer. Viewers read; operators create/edit agents, run lifecycle (except disable/archive/terminate) and executions; admins also manage users, org, audit logs, graph reconcile.
