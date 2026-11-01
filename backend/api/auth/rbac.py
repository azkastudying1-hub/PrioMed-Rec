"""
api/auth/rbac.py
-----------------
Role-Based Access Control (RBAC) for PrioMed-Rec (B-103).

Roles:
  PHARMACIST   — review decisions, claim cases, APPROVE/EDIT/REJECT/ESCALATE
  TECHNICIAN   — fill BPMH, read-only worklist
  COORDINATOR  — read all, escalate, manage worklist
  ADMIN        — configure SLA, manage users, seed data
  AUDITOR      — read-only access to all audit data

Identity ALWAYS comes from the verified JWT token, never from request body.
Service tokens (Langflow, MCP) use actor_type="agent_via_mcp" with API key.
"""

from __future__ import annotations

import os
from typing import List, Optional, Set

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from api.auth.jwt import JWTError, TokenData, verify_token

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

class UserRole:
    PHARMACIST  = "PHARMACIST"
    TECHNICIAN  = "TECHNICIAN"
    COORDINATOR = "COORDINATOR"
    ADMIN       = "ADMIN"
    AUDITOR     = "AUDITOR"

    ALL_ROLES: Set[str] = {PHARMACIST, TECHNICIAN, COORDINATOR, ADMIN, AUDITOR}

    # Roles that can take clinical decisions
    CLINICAL_ROLES: Set[str] = {PHARMACIST, COORDINATOR}

    # Roles that can write BPMH
    BPMH_ROLES: Set[str] = {PHARMACIST, TECHNICIAN}


# Roles granted to service tokens (Langflow / MCP)
SERVICE_TOKEN_ROLES: Set[str] = {UserRole.PHARMACIST, UserRole.COORDINATOR}

# ---------------------------------------------------------------------------
# Security schemes
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Service API keys from env (for Langflow / MCP integration)
_SERVICE_API_KEYS: Set[str] = {
    k for k in [
        os.getenv("SERVICE_API_KEY_LANGFLOW", ""),
        os.getenv("SERVICE_API_KEY_MCP", ""),
        os.getenv("API_KEY_PHARMACIST", ""),  # legacy key from api/auth.py
    ]
    if k
}


def verify_service_token(api_key: str) -> Optional[TokenData]:
    """
    Verify a service API key.
    Returns a synthetic TokenData for service actors.
    Returns None if key is invalid.
    """
    if not _SERVICE_API_KEYS:
        return None
    if api_key in _SERVICE_API_KEYS:
        return TokenData(
            user_id="service",
            username="service",
            role=UserRole.PHARMACIST,  # Service tokens get pharmacist-level read
            actor_type="agent_via_mcp",
        )
    return None


# ---------------------------------------------------------------------------
# Dependency: get current user from JWT or API key
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    api_key: Optional[str] = Security(_api_key_header),
) -> TokenData:
    """
    Resolve current user from Bearer JWT or X-API-Key header.
    Raises 401 if neither is provided or both are invalid.
    """
    # Try Bearer JWT first
    if credentials and credentials.credentials:
        try:
            token_data = verify_token(credentials.credentials, token_type="access")
            return token_data
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token JWT tidak valid: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    # Try API key (service token)
    if api_key:
        token_data = verify_service_token(api_key)
        if token_data:
            return token_data
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key tidak valid.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autentikasi diperlukan: sertakan Bearer token atau X-API-Key.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    api_key: Optional[str] = Security(_api_key_header),
) -> Optional[TokenData]:
    """
    Like get_current_user but returns None instead of raising 401.
    Use for endpoints that allow anonymous access with degraded features.
    """
    try:
        return await get_current_user(credentials=credentials, api_key=api_key)
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# Role guard factory
# ---------------------------------------------------------------------------

def require_roles(*roles: str):
    """
    Dependency factory that restricts access to specified roles.

    Usage:
        @router.post("/...")
        async def endpoint(current_user: TokenData = Depends(require_roles("PHARMACIST", "ADMIN"))):
            ...
    """
    allowed = set(roles)

    async def _check(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Akses ditolak. Peran '{user.role}' tidak diizinkan. Diperlukan: {sorted(allowed)}",
            )
        return user

    return _check


# Convenience shorthands
def require_pharmacist():
    return require_roles(UserRole.PHARMACIST)

def require_coordinator():
    return require_roles(UserRole.COORDINATOR, UserRole.ADMIN)

def require_admin():
    return require_roles(UserRole.ADMIN)

def require_auditor():
    return require_roles(UserRole.AUDITOR, UserRole.ADMIN)
