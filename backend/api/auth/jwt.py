"""
api/auth/jwt.py
----------------
JWT token creation and verification (B-103).

- Access token: 15 minutes (HS256, configurable)
- Refresh token: 7 days (HS256, separate secret)
- Payload fields: sub (user_id), role, username, actor_type
- Secret from JWT_SECRET_KEY env var (required in production)

Implementation uses Python stdlib only (base64/hmac/json) — no python-jose.
A JWTError class is provided to maintain API compatibility.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Config — read from env (defaults only safe for local dev)
# ---------------------------------------------------------------------------

_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_in_production_min_32chars!!")
_REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", _SECRET_KEY + "_refresh")
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "15"))
_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))


class JWTError(Exception):
    """JWT validation error — API-compatible with python-jose."""


class TokenData(BaseModel):
    """Payload decoded from a JWT token."""
    user_id: str
    username: str
    role: str
    actor_type: str = "human"  # human | agent_via_mcp


# ---------------------------------------------------------------------------
# Minimal HS256 JWT (RFC 7519) — no external dependency
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    # Add padding
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def _sign(header_b64: str, payload_b64: str, secret: str) -> str:
    msg = f"{header_b64}.{payload_b64}".encode()
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return _b64url_encode(sig)


def _encode(payload: dict, secret: str) -> str:
    """Encode a dict as a signed JWT string."""
    header = {"alg": "HS256", "typ": "JWT"}
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    # Convert datetime objects to timestamps
    clean = {}
    for k, v in payload.items():
        if isinstance(v, datetime):
            clean[k] = int(v.timestamp())
        else:
            clean[k] = v
    p = _b64url_encode(json.dumps(clean, separators=(",", ":")).encode())
    sig = _sign(h, p, secret)
    return f"{h}.{p}.{sig}"


def _decode(token: str, secret: str) -> dict:
    """Decode and verify a JWT string; raises JWTError on any failure."""
    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("Token format tidak valid")
    h, p, sig = parts
    expected = _sign(h, p, secret)
    if not hmac.compare_digest(expected, sig):
        raise JWTError("Signature token tidak valid")
    try:
        payload = json.loads(_b64url_decode(p))
    except Exception as exc:
        raise JWTError("Token payload tidak dapat di-decode") from exc
    exp = payload.get("exp")
    if exp is not None and time.time() > float(exp):
        raise JWTError("Token sudah kedaluwarsa")
    return payload


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    username: str,
    role: str,
    actor_type: str = "human",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "actor_type": actor_type,
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    return _encode(payload, _SECRET_KEY)


def create_refresh_token(
    user_id: str,
    username: str,
    role: str,
) -> str:
    """Create a signed JWT refresh token (longer-lived)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "actor_type": "human",
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }
    return _encode(payload, _REFRESH_SECRET_KEY)


def verify_token(token: str, token_type: str = "access") -> TokenData:
    """
    Verify a JWT token and return its decoded payload.

    Raises:
        JWTError: if token is invalid, expired, or wrong type.
    """
    secret = _REFRESH_SECRET_KEY if token_type == "refresh" else _SECRET_KEY
    payload = _decode(token, secret)

    if payload.get("type") != token_type:
        raise JWTError(f"Token type mismatch: expected '{token_type}', got '{payload.get('type')}'")

    user_id = payload.get("sub")
    username = payload.get("username")
    role = payload.get("role")
    actor_type = payload.get("actor_type", "human")

    if not user_id or not role:
        raise JWTError("Token payload tidak lengkap: sub atau role kosong")

    return TokenData(
        user_id=user_id,
        username=username or "",
        role=role,
        actor_type=actor_type,
    )
