"""Needs PostgreSQL with migrations applied (`make up && make migrate`, DATABASE_URL pointing at it)."""

import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app.core.db import dispose_engine, get_sessionmaker
from app.core.redis import close_redis
from app.modules.audit.models import AuditLog
from app.modules.events.models import OutboxEvent

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    await dispose_engine()
    await close_redis()


async def test_register_create_activate_execute_audit_outbox():
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        email = f"it-{uuid.uuid4().hex[:8]}@example.com"
        r = await c.post(
            "/api/v1/auth/register",
            json={"organization_name": "IT Org", "full_name": "Tester", "email": email, "password": "a-long-test-password"},
        )
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        org_id = r.json()["user"]["organization_id"]
        h = {"Authorization": f"Bearer {token}"}

        r = await c.post("/api/v1/agents", headers=h, json={"name": "A1", "role": "Tester", "execution_mode": "simulated"})
        assert r.status_code == 201, r.text
        agent = r.json()
        assert agent["status"] == "draft" and agent["readiness"] == "simulated"

        # not active yet -> cannot execute
        r = await c.post(f"/api/v1/agents/{agent['id']}/executions", headers=h, json={"prompt": "hi"})
        assert r.status_code == 409

        # invalid transition -> 409
        r = await c.post(f"/api/v1/agents/{agent['id']}/lifecycle/pause", headers=h)
        assert r.status_code == 409

        r = await c.post(f"/api/v1/agents/{agent['id']}/lifecycle/activate", headers=h)
        assert r.status_code == 200 and r.json()["status"] == "active"

        r = await c.post(f"/api/v1/agents/{agent['id']}/executions", headers=h, json={"prompt": "hello"})
        assert r.status_code == 202, r.text
        ex = r.json()
        assert ex["mode"] == "simulated"

        # background task ran after the response (ASGITransport awaits it)
        r = await c.get(f"/api/v1/executions/{ex['id']}", headers=h)
        body = r.json()
        assert body["status"] == "succeeded", body
        assert body["output"].startswith("[SIMULATED]")

        # tenant isolation: another org cannot see it
        r2 = await c.post(
            "/api/v1/auth/register",
            json={"organization_name": "Other", "full_name": "X", "email": f"o-{uuid.uuid4().hex[:8]}@example.com", "password": "a-long-test-password"},
        )
        h2 = {"Authorization": f"Bearer {r2.json()['access_token']}"}
        assert (await c.get(f"/api/v1/agents/{agent['id']}", headers=h2)).status_code == 404

    async with get_sessionmaker()() as db:
        actions = set(
            (await db.execute(select(AuditLog.action).where(AuditLog.organization_id == uuid.UUID(org_id)))).scalars()
        )
        assert {"agent.create", "agent.activate", "execution.create", "user.create"} <= actions
        types = set(
            (await db.execute(select(OutboxEvent.type).where(OutboxEvent.organization_id == uuid.UUID(org_id)))).scalars()
        )
        assert {"AGENT_CREATED", "AGENT_ACTIVATED", "EXECUTION_STARTED", "EXECUTION_COMPLETED", "USER_CREATED", "ORGANIZATION_CREATED"} <= types
        n = await db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.organization_id == uuid.UUID(org_id)))
        assert n >= 6
