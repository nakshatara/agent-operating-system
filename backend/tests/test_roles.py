import uuid

import pytest

from app.core.deps import Principal, require_role
from app.core.errors import AppError


def _p(role):
    return Principal(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role=role)


async def test_role_allows_equal_and_higher():
    dep = require_role("admin")
    for role in ("admin", "owner"):
        p = _p(role)
        assert await dep(principal=p) is p


async def test_role_denies_lower():
    dep = require_role("admin")
    for role in ("viewer", "operator"):
        with pytest.raises(AppError) as e:
            await dep(principal=_p(role))
        assert e.value.status_code == 403


def test_unknown_role_rejected():
    with pytest.raises(ValueError):
        require_role("god")
