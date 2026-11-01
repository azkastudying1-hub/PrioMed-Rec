"""
api/auth.py
-----------
Simple API key authentication for PrioMed-Rec.

Two roles:
  pharmacist — full access (POST/PUT/GET)
  readonly   — GET only

Keys stored in environment variables:
  API_KEY_PHARMACIST=<key>
  API_KEY_READONLY=<key>  (optional)

Usage:
  from api.auth import require_pharmacist_key, require_any_key
  
  @router.post("/endpoint", dependencies=[Depends(require_pharmacist_key)])
  def my_endpoint(): ...
"""

from __future__ import annotations

import os
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_pharmacist_key() -> str:
    return os.getenv("API_KEY_PHARMACIST", "").strip()


def _get_readonly_key() -> str:
    return os.getenv("API_KEY_READONLY", "").strip()


def _is_auth_enabled() -> bool:
    """Auth is disabled if no keys are configured (dev/testing mode)."""
    return bool(_get_pharmacist_key())


async def require_pharmacist_key(api_key: str = Security(_KEY_HEADER)) -> str:
    """
    Dependency: requires pharmacist-level API key.
    If API_KEY_PHARMACIST is not set, auth is disabled (development mode).
    """
    if not _is_auth_enabled():
        return "dev-mode"  # No key configured — allow all (dev)
    
    ph_key = _get_pharmacist_key()
    if api_key and (api_key == ph_key):
        return api_key
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key. Set X-API-Key header with valid pharmacist key.",
        headers={"WWW-Authenticate": "ApiKey"},
    )


async def require_any_key(api_key: str = Security(_KEY_HEADER)) -> str:
    """
    Dependency: accepts both pharmacist and readonly keys.
    """
    if not _is_auth_enabled():
        return "dev-mode"
    
    ph_key = _get_pharmacist_key()
    ro_key = _get_readonly_key()
    
    if api_key and (api_key == ph_key or (ro_key and api_key == ro_key)):
        return api_key
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key.",
        headers={"WWW-Authenticate": "ApiKey"},
    )
