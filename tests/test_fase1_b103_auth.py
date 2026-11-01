"""
tests/test_fase1_b103_auth.py
------------------------------
Tes unit untuk B-103: JWT auth + RBAC.
"""
import pytest
from api.auth.jwt import JWTError


def test_create_and_verify_access_token():
    from api.auth.jwt import create_access_token, verify_token
    token = create_access_token(user_id="u1", username="apoteker1", role="PHARMACIST")
    assert isinstance(token, str)
    data = verify_token(token, token_type="access")
    assert data.user_id == "u1"
    assert data.role == "PHARMACIST"
    assert data.actor_type == "human"


def test_verify_wrong_type_raises():
    from api.auth.jwt import create_access_token, verify_token
    token = create_access_token(user_id="u1", username="x", role="PHARMACIST")
    with pytest.raises(JWTError):
        verify_token(token, token_type="refresh")


def test_refresh_token_round_trip():
    from api.auth.jwt import create_refresh_token, verify_token
    token = create_refresh_token(user_id="u2", username="ttk1", role="TECHNICIAN")
    data = verify_token(token, token_type="refresh")
    assert data.user_id == "u2"
    assert data.role == "TECHNICIAN"


def test_expired_token_raises():
    from api.auth.jwt import create_access_token, verify_token
    from datetime import timedelta
    token = create_access_token("u1", "x", "PHARMACIST", expires_delta=timedelta(seconds=-1))
    with pytest.raises(JWTError):
        verify_token(token)


def test_hash_and_verify_password():
    from api.auth.password import hash_password, verify_password
    hashed = hash_password("secretpass")
    assert verify_password("secretpass", hashed)
    assert not verify_password("wrongpass", hashed)


def test_user_role_constants():
    from api.auth.rbac import UserRole
    assert "PHARMACIST" in UserRole.ALL_ROLES
    assert "ADMIN" in UserRole.ALL_ROLES
    assert len(UserRole.ALL_ROLES) == 5
