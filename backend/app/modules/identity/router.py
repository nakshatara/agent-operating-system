from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import (
    Principal,
    RequestContext,
    get_current_principal,
    get_request_context,
    require_role,
)
from app.core.errors import not_found
from app.core.ratelimit import auth_rate_limit
from app.modules.identity import service
from app.modules.identity.models import User
from app.modules.identity.schemas import (
    InviteUserRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserCreatedOut,
    UserOut,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


@auth_router.post("/register", response_model=TokenResponse, status_code=201, dependencies=[Depends(auth_rate_limit)])
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> TokenResponse:
    return await service.register(db, data, ctx)


@auth_router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> TokenResponse:
    return await service.login(db, data, ctx)


@auth_router.get("/me", response_model=UserOut)
async def me(
    principal: Principal = Depends(get_current_principal), db: AsyncSession = Depends(get_db)
) -> UserOut:
    user = await db.get(User, principal.user_id)
    if user is None:
        raise not_found("User")
    return UserOut.model_validate(user)


@users_router.get("", response_model=list[UserOut])
async def list_users(
    principal: Principal = Depends(require_role("viewer")), db: AsyncSession = Depends(get_db)
) -> list[UserOut]:
    users = await service.list_users(db, principal.organization_id)
    return [UserOut.model_validate(u) for u in users]


@users_router.post("", response_model=UserCreatedOut, status_code=201)
async def invite_user(
    data: InviteUserRequest,
    principal: Principal = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> UserCreatedOut:
    user, temp = await service.invite_user(db, principal, ctx, data)
    return UserCreatedOut(user=UserOut.model_validate(user), temporary_password=temp)
