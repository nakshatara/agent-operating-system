# Code tour: how to read this project

This is a plain-language guide to where things live and what happens when you use the app.
Read it top to bottom once; after that, use it as a map.

## The big picture

There are two programs:

- `backend/` is the server. It is written in Python with FastAPI. It stores data, runs agents, and exposes a web API under `/api/v1`.
- `frontend/` is the website. It is written in TypeScript with Next.js. It shows pages and calls the backend API.

The backend uses four supporting services, started by `docker-compose.yml`:

| Service | What it is used for here |
|---|---|
| PostgreSQL | The main database. Users, organizations, agents, executions, audit logs. This is the source of truth. |
| Kafka | A message stream. Every important change is published here as an event. |
| Neo4j | A graph database. It holds who-reports-to-whom and which agent uses which model. It is rebuilt from events. |
| Redis | Fast temporary storage. Used for live updates to the browser and for login rate limiting. |

## What happens when you click "Create agent"

Following one action end to end is the fastest way to understand the code.

1. The page `frontend/src/app/(app)/agents/page.tsx` collects the form and calls a function in `frontend/src/lib/api.ts`.
2. `api.ts` sends `POST /api/v1/agents` with your login token.
3. In the backend, `app/modules/agents/router.py` receives the request. `app/core/deps.py` checks the token and your role first.
4. The router calls `app/modules/agents/service.py`, which validates the data (for example, the supervisor must be in your organization and must not create a loop; see `hierarchy.py`).
5. In one database transaction the service saves three things: the agent row, an audit log row (`app/modules/audit/service.py`), and an event row in the outbox table (`app/modules/events/outbox.py`).
6. A background worker, `app/modules/events/relay.py`, picks up the outbox row and publishes it to Kafka.
7. Two listeners in `app/modules/events/consumers.py` receive the event:
   - `app/modules/graph/projector.py` writes the agent into Neo4j.
   - `app/modules/events/fanout.py` pushes it to Redis, and `ws.py` forwards it to every open browser over a WebSocket.
8. The dashboard page receives the event through `frontend/src/lib/ws.ts` and shows it in the live feed.

Step 5 is called the "transactional outbox" pattern. It guarantees that a change and its event are saved together, so the graph and the live feed can never miss a change that the database has.

## What happens when you run an agent

1. The agent detail page (`frontend/src/app/(app)/agents/[id]/page.tsx`) sends your prompt to `POST /api/v1/agents/{id}/executions`.
2. `app/modules/runtime/service.py` checks the agent is `active` and ready, creates an execution row, and starts the run in the background.
3. The run goes through `app/modules/model_gateway/gateway.py`, which picks an adapter:
   - `anthropic.py` or `openai.py` call the real provider over HTTP. These need an API key in `.env`.
   - `simulated.py` does not call any model. Its output always starts with `[SIMULATED]`, and the UI shows a SIMULATED badge.
4. The result, token counts and timing are saved on the execution row, and an event is published as above.

## Agent status and lifecycle

`app/modules/agents/lifecycle.py` holds one table that lists every allowed status change (draft, active, paused, disabled, archived, terminated). If a change is not in the table, the API answers with error 409. `terminated` is final.

`app/modules/agents/readiness.py` decides the badge you see:

- `simulated`: the agent is set to simulated mode.
- `configured`: the agent is set to live mode but the provider has no API key, so it cannot run yet.
- `live`: the agent can make real model calls.

## Backend folder map

```
backend/app/
  main.py            Builds the FastAPI app and plugs in every router.
  workers.py         Starts and stops the background workers (relay, consumers).
  core/              Shared plumbing: settings, database session, login tokens, errors, logging.
  modules/
    identity/        Register, login, users.
    organizations/   The tenant (company) record.
    agents/          Agent records, lifecycle, hierarchy checks, readiness.
    runtime/         Executions: running an agent on a prompt.
    model_gateway/   One interface, several model providers.
    events/          Outbox, Kafka, consumers, WebSocket.
    graph/           Neo4j connection, schema setup, queries.
    audit/           Append-only log of who did what.
    dashboard/       Numbers and health shown on the overview page.
backend/alembic/     Database migrations (the table definitions for PostgreSQL).
backend/tests/       Automated tests.
```

Most modules follow the same four-file layout, so once you know one you know them all:

- `models.py`: the database tables.
- `schemas.py`: the shapes of API requests and responses.
- `service.py`: the actual logic.
- `router.py`: the URLs, each a thin wrapper that calls the service.

## Frontend folder map

```
frontend/src/
  app/login, app/register      Public pages.
  app/(app)/                   Pages that need a login; layout.tsx adds the sidebar.
    dashboard/  agents/  agents/[id]/  graph/  audit/  settings/
  components/                  Sidebar and small shared UI pieces.
  lib/api.ts                   Every backend call, in one file.
  lib/auth.tsx                 Remembers who is logged in.
  lib/ws.ts                    The live-update WebSocket connection.
  lib/types.ts                 TypeScript types matching the backend schemas.
```

## Two rules the code follows everywhere

- **Tenant isolation.** Every database and graph query filters by the organization id taken from your login token, never from the request body. One organization cannot see another's data.
- **Honesty about execution.** Nothing pretends to be a model. Simulated output is labelled, and an agent without an API key is shown as not runnable.

## Where to go next

- `README.md`: how to start everything, and what has and has not been tested.
- `docs/architecture.md`: the same design in more technical detail.
- `docs/data-ownership.md`: which database owns which kind of data.
- `docs/roadmap.md`: what is planned but not built (workflows, approvals, policies, and more).
