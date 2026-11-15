from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, utcnow
from app.core.deps import (
    Principal,
    RequestContext,
    get_request_context,
    require_role,
)
from app.core.errors import not_found
from app.modules.audit import service as audit
from app.modules.organizations.models import Organization
from app.modules.organizations.schemas import OrganizationOut, OrganizationUpdate

router = APIRouter(prefix="/organization", tags=["organization"])


async def _load(db: AsyncSession, principal: Principal) -> Organization:
    # Tenant comes from the token only.
    org = await db.get(Organization, principal.organization_id)
    if org is None:
        raise not_found("Organization")
    return org


@router.get("", response_model=OrganizationOut)
async def get_organization(
    principal: Principal = Depends(require_role("viewer")), db: AsyncSession = Depends(get_db)
) -> OrganizationOut:
    return OrganizationOut.model_validate(await _load(db, principal))


@router.patch("", response_model=OrganizationOut)
async def update_organization(
    data: OrganizationUpdate,
    principal: Principal = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> OrganizationOut:
    org = await _load(db, principal)
    before = {"name": org.name}
    org.name = data.name.strip()
    org.updated_at = utcnow()
    audit.record_for(
        db, principal, ctx, "organization.update", "organization", org.id, before=before, after={"name": org.name}
    )
    await db.commit()
    return OrganizationOut.model_validate(org)
