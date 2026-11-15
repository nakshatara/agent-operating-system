import time
import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    InvalidToken,
    create_access_token,
    decode_token,
    hash_password,
    role_at_least,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("correct horse battery")
    assert h != "correct horse battery"
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", "not-a-hash")


def test_jwt_roundtrip():
    uid, oid = uuid.uuid4(), uuid.uuid4()
    claims = decode_token(create_access_token(user_id=uid, organization_id=oid, role="admin"))
    assert (claims.user_id, claims.org_id, claims.role) == (uid, oid, "admin")


def test_jwt_expired():
    token = create_access_token(
        user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role="viewer", expires_delta=timedelta(seconds=-5)
    )
    with pytest.raises(InvalidToken):
        decode_token(token)


def test_jwt_tampered_and_wrong_key():
    token = create_access_token(user_id=uuid.uuid4(), organization_id=uuid.uuid4(), role="viewer")
    with pytest.raises(InvalidToken):
        decode_token(token[:-2] + "xx")
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "org": str(uuid.uuid4()), "role": "owner", "exp": time.time() + 60},
        "another-secret-another-secret-another",
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidToken):
        decode_token(forged)
    with pytest.raises(InvalidToken):
        decode_token("garbage")


def test_role_rank():
    assert role_at_least("owner", "admin")
    assert role_at_least("admin", "admin")
    assert not role_at_least("viewer", "operator")
    assert not role_at_least("bogus", "viewer")
