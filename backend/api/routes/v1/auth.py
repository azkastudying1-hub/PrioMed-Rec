"""
api/routes/v1/auth.py
----------------------
Authentication endpoints for PrioMed-Rec (B-103).

POST /api/v1/auth/login   — username+password → access+refresh tokens
POST /api/v1/auth/refresh — refresh token → new access token
POST /api/v1/auth/logout  — invalidate (client-side; server logs audit)
GET  /api/v1/auth/me      — current user profile

Identity is ALWAYS from the token, never from request body.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.auth.jwt import create_access_token, create_refresh_token, verify_token
from api.auth.password import verify_password
from api.auth.rbac import TokenData, get_current_user
from api.db.session import session_scope as get_session
from api.db.models import User, AuditEntry

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    username: str
    user_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    user_id: str
    username: str
    full_name: str
    role: str
    actor_type: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit(session, action: str, actor_id: str, note: str, request: Request):
    """Append a lightweight audit entry for auth events."""
    import hashlib, json
    # Get last seq
    last = session.execute(
        __import__("sqlalchemy").text("SELECT COALESCE(MAX(seq), 0) FROM audit_entries")
    ).scalar()
    seq = last + 1
    prev_entry = session.execute(
        __import__("sqlalchemy").text(
            "SELECT hash FROM audit_entries ORDER BY seq DESC LIMIT 1"
        )
    ).fetchone()
    prev_hash = prev_entry[0] if prev_entry else ""
    payload = json.dumps({"action": action, "actor_id": actor_id, "note": note, "seq": seq}, sort_keys=True)
    entry_hash = hashlib.sha256(f"{prev_hash}{payload}".encode()).hexdigest()

    entry = AuditEntry(
        id=str(uuid.uuid4()),
        seq=seq,
        actor_id=actor_id,
        actor_type="human",
        action=action,
        note=note,
        client_ip=request.client.host if request.client else None,
        prev_hash=prev_hash,
        hash=entry_hash,
        ts=_now_utc(),
    )
    session.add(entry)
    session.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse, summary="Login apoteker")
async def login(body: LoginRequest, request: Request):
    """
    Autentikasi dengan username dan password.
    Mengembalikan access token (15 menit) dan refresh token (7 hari).
    """
    with get_session() as session:
        user = session.query(User).filter(
            User.username == body.username,
            User.is_active == True,  # noqa: E712
        ).first()

        if not user or not verify_password(body.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Username atau password salah.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Update last_login
        user.last_login = _now_utc()
        session.commit()

        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )

        try:
            _audit(session, "LOGIN", user.id, f"Login berhasil dari {request.client.host if request.client else 'unknown'}", request)
        except Exception:
            pass  # Audit failure must not block login

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            role=user.role,
            username=user.username,
            user_id=user.id,
        )


@router.post("/refresh", response_model=AccessTokenResponse, summary="Perbarui access token")
async def refresh(body: RefreshRequest):
    """
    Tukar refresh token yang valid dengan access token baru.
    """
    from api.auth.jwt import JWTError
    try:
        token_data = verify_token(body.refresh_token, token_type="refresh")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Refresh token tidak valid: {exc}",
        ) from exc

    access_token = create_access_token(
        user_id=token_data.user_id,
        username=token_data.username,
        role=token_data.role,
    )
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", summary="Logout (audit trail)")
async def logout(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
):
    """
    Invalidasi sesi (client harus membuang token).
    Mencatat audit trail logout.
    JWT bersifat stateless — revocation sepenuhnya di sisi client.
    Untuk revocation server-side, gunakan daftar hitam token di Redis (stub, belum diimplementasikan).
    """
    try:
        with get_session() as session:
            _audit(session, "LOGOUT", current_user.user_id, "Logout manual", request)
    except Exception:
        pass
    return {"status": "ok", "message": "Logout berhasil. Hapus token di sisi client."}


@router.get("/me", response_model=UserProfile, summary="Profil pengguna aktif")
async def me(current_user: TokenData = Depends(get_current_user)):
    """Mengembalikan profil pengguna dari token yang aktif."""
    with get_session() as session:
        user = session.query(User).filter(User.id == current_user.user_id).first()
        full_name = user.full_name if user else current_user.username
    return UserProfile(
        user_id=current_user.user_id,
        username=current_user.username,
        full_name=full_name,
        role=current_user.role,
        actor_type=current_user.actor_type,
    )
