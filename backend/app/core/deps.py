from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import AppError
from app.core.logging import trace_id_var
from app.core.security import ROLE_RANK, InvalidToken, decode_token, role_at_least
from app.modules.identity.models import User

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. organization_id ALWAYS comes from here, never from a request body."""

    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    email: str = ""


@dataclass(frozen=True)
class RequestContext:
    ip: str | None
    trace_id: str


async def get_request_context(request: Request) -> RequestContext:
    trace_id = getattr(request.state, "trace_id", None) or trace_id_var.get() or uuid.uuid4().hex
    ip = request.client.host if request.client else None
    return RequestContext(ip=ip, trace_id=trace_id)


async def get_current_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if creds is None:
        raise AppError(401, "unauthenticated", "Missing bearer token")
    try:
        claims = decode_token(creds.credentials)
    except InvalidToken:
        raise AppError(401, "invalid_token", "Invalid or expired token") from None
    # The database is authoritative for role/active state so revocations and role changes apply at once.
    user = await db.get(User, claims.user_id)
    if user is None or not user.is_active or user.organization_id != claims.org_id:
        raise AppError(401, "invalid_token", "Invalid or expired token")
    return Principal(
        user_id=user.id, organization_id=user.organization_id, role=user.role, email=user.email
    )


def require_role(minimum: str) -> Callable[..., Awaitable[Principal]]:
    """Dependency factory: caller must hold at least `minimum` (viewer < operator < admin < owner)."""
    if minimum not in ROLE_RANK:
        raise ValueError(f"unknown role {minimum}")

    async def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not role_at_least(principal.role, minimum):
            raise AppError(403, "forbidden", f"Requires role '{minimum}' or higher")
        return principal

    return dependency
