"""
api/auth/password.py
---------------------
Password hashing and verification (B-103).

Strategy (in priority order):
  1. argon2-cffi — modern, fast, secure (preferred)
  2. passlib bcrypt — classic (may fail on Python 3.12 without bcrypt binary)
  3. SHA-256 fallback — ONLY for development/testing, NOT for production

In production, ensure argon2-cffi or bcrypt is installed:
    pip install argon2-cffi
"""

from __future__ import annotations

import hashlib

# ---------------------------------------------------------------------------
# Try argon2-cffi first (modern, no binary dependency issues)
# ---------------------------------------------------------------------------
_ARGON2_AVAILABLE = False
try:
    from argon2 import PasswordHasher as _PasswordHasher
    from argon2.exceptions import VerifyMismatchError as _VerifyMismatchError, VerificationError as _VerificationError
    _ph = _PasswordHasher()
    _ARGON2_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Fall back to passlib bcrypt
# ---------------------------------------------------------------------------
_PASSLIB_AVAILABLE = False
if not _ARGON2_AVAILABLE:
    try:
        from passlib.context import CryptContext as _CryptContext
        _ctx = _CryptContext(schemes=["bcrypt"], deprecated="auto")
        # Test that bcrypt actually works on this platform
        _ctx.hash("test")
        _PASSLIB_AVAILABLE = True
    except Exception:
        pass


def hash_password(plain: str) -> str:
    """Hash a plaintext password."""
    if _ARGON2_AVAILABLE:
        return _ph.hash(plain)
    if _PASSLIB_AVAILABLE:
        return _ctx.hash(plain)
    # Development fallback only — not secure for production
    return "sha256:" + hashlib.sha256(plain.encode()).hexdigest()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    if hashed.startswith("sha256:"):
        return hashed == "sha256:" + hashlib.sha256(plain.encode()).hexdigest()
    if _ARGON2_AVAILABLE:
        try:
            return _ph.verify(hashed, plain)
        except (_VerifyMismatchError, _VerificationError):
            return False
        except Exception:
            pass
    if _PASSLIB_AVAILABLE:
        try:
            return _ctx.verify(plain, hashed)
        except Exception:
            return False
    return False
