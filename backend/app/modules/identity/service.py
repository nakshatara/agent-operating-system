from __future__ import annotations

import asyncio
import re
import secrets
import uuid
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import utcnow
from app.core.deps import Principal, RequestContext
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    role_at_least,
    verify_password,
)
from app.modules.audit import service as audit
from app.modules.events.envelope import EventType
from app.modules.events.outbox import emit
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    InviteUserRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.modules.organizations.models import Organization


def user_snapshot(user: User) -> dict:
    """Event/graph payload. Deliberately excludes email and credentials."""
    return {
        "id": str(user.id),
        "organization_id": str(user.organization_id),
        "full_name": user.full_name,
        "role": user.role,
    }


def organization_snapshot(org: Organization) -> dict:
    return {"id": str(org.id), "name": org.name, "slug": org.slug}


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "org"
    return f"{base}-{secrets.token_hex(3)}"


@lru_cache
def _dummy_hash() -> str:
    return hash_password("not-a-real-password")


def _token_response(user: User) -> TokenResponse:
    token = create_access_token(
        user_id=user.id, organization_id=user.organization_id, role=user.role
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_ttl_minutes * 60,
        user=UserOut.model_validate(user),
    )


async def register(db: AsyncSession, data: RegisterRequest, ctx: RequestContext) -> TokenResponse:
    email = data.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "email_taken", "An account with this email already exists")
    password_hash = await asyncio.to_thread(hash_password, data.password)

    org = Organization(id=uuid.uuid4(), name=data.organization_name.strip(), slug=_slugify(data.organization_name))
    db.add(org)
    await db.flush()
    user = User(
        id=uuid.uuid4(),
        organization_id=org.id,
        email=email,
        full_name=data.full_name.strip(),
        password_hash=password_hash,
        role="owner",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    emit(db, EventType.ORGANIZATION_CREATED, org.id, {"organization": organization_snapshot(org)}, trace_id=ctx.trace_id)
    emit(db, EventType.USER_CREATED, org.id, {"user": user_snapshot(user)}, trace_id=ctx.trace_id)
    audit.record(
        db,
        organization_id=org.id,
        actor_user_id=user.id,
        action="organization.create",
        resource_type="organization",
        resource_id=org.id,
        after=organization_snapshot(org),
        ctx=ctx,
    )
    audit.record(
        db,
        organization_id=org.id,
        actor_user_id=user.id,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        after=user_snapshot(user),
        ctx=ctx,
    )
    await db.commit()
    return _token_response(user)


async def login(db: AsyncSession, data: LoginRequest, ctx: RequestContext) -> TokenResponse:
    email = data.email.lower()
    user = await db.scalar(select(User).where(User.email == email))
    # Always run one verification so response time doesn't reveal whether the email exists.
    ok = await asyncio.to_thread(
        verify_password, data.password, user.password_hash if user else _dummy_hash()
    )
    if user is None or not ok or not user.is_active:
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    user.last_login_at = utcnow()
    audit.record(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
        ctx=ctx,
    )
    await db.commit()
    return _token_response(user)


async def list_users(db: AsyncSession, organization_id: uuid.UUID) -> list[User]:
    rows = await db.execute(
        select(User).where(User.organization_id == organization_id).order_by(User.created_at)
    )
    return list(rows.scalars().all())


async def invite_user(
    db: AsyncSession, principal: Principal, ctx: RequestContext, data: InviteUserRequest
) -> tuple[User, str | None]:
    # Nobody can grant a role above their own; only owners can mint owners.
    if data.role == "owner" and principal.role != "owner":
        raise AppError(403, "forbidden", "Only an owner can create another owner")
    if not role_at_least(principal.role, data.role):
        raise AppError(403, "forbidden", "Cannot grant a role above your own")
    email = data.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "email_taken", "An account with this email already exists")
    temp_password = None
    password = data.password
    if password is None:
        temp_password = secrets.token_urlsafe(12)
        password = temp_password
    password_hash = await asyncio.to_thread(hash_password, password)
    user = User(
        id=uuid.uuid4(),
        organization_id=principal.organization_id,  # from the token, never the request body
        email=email,
        full_name=data.full_name.strip(),
        password_hash=password_hash,
        role=data.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    emit(db, EventType.USER_CREATED, user.organization_id, {"user": user_snapshot(user)}, trace_id=ctx.trace_id)
    audit.record_for(db, principal, ctx, "user.create", "user", user.id, after=user_snapshot(user))
    await db.commit()
    return user, temp_password
