"""
api/errors.py
--------------
Envelope error seragam untuk semua endpoint PrioMed-Rec.

Format standar:
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "...",
      "details": [...],
      "request_id": "uuid"
    }
  }

Dipakai oleh global exception handler di main.py dan oleh
endpoint yang ingin mengembalikan error terstruktur.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Error codes (bertambah sesuai kebutuhan)
# ---------------------------------------------------------------------------

class ErrorCode:
    VALIDATION_ERROR       = "VALIDATION_ERROR"
    NOT_FOUND              = "NOT_FOUND"
    UNAUTHORIZED           = "UNAUTHORIZED"
    FORBIDDEN              = "FORBIDDEN"
    CONFLICT               = "CONFLICT"
    INTERNAL_ERROR         = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE    = "SERVICE_UNAVAILABLE"
    INFERENCE_GUARD        = "INFERENCE_GUARD_ERROR"
    CLINICAL_SAFETY        = "CLINICAL_SAFETY_VIOLATION"
    HIGH_ALERT_UNCONFIRMED = "HIGH_ALERT_UNCONFIRMED"
    INVALID_TRANSITION     = "INVALID_STATE_TRANSITION"
    MISSING_REASON         = "REASON_REQUIRED"
    IDEMPOTENCY_CONFLICT   = "IDEMPOTENCY_CONFLICT"


def error_response(
    code: str,
    message: str,
    status_code: int = 400,
    details: Optional[Any] = None,
    request_id: Optional[str] = None,
) -> JSONResponse:
    """
    Buat JSONResponse dengan envelope error seragam.

    Args:
        code:        Kode error (ErrorCode.*)
        message:     Pesan singkat
        status_code: HTTP status code
        details:     Data tambahan (list error validasi, dll)
        request_id:  UUID request (diambil dari header X-Request-ID atau dibuat baru)
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id or str(uuid.uuid4()),
            }
        },
    )


# ---------------------------------------------------------------------------
# Exception handlers (dipasang di main.py)
# ---------------------------------------------------------------------------

async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handler untuk Pydantic ValidationError."""
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    return error_response(
        code=ErrorCode.VALIDATION_ERROR,
        message="Input validation failed.",
        status_code=422,
        details=[
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ],
        request_id=rid,
    )


async def http_exception_handler_custom(request: Request, exc: Exception) -> JSONResponse:
    """Handler untuk HTTPException — pertahankan status code asli."""
    from fastapi import HTTPException
    if isinstance(exc, HTTPException):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        return error_response(
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            status_code=exc.status_code,
            request_id=rid,
        )
    # Fallback untuk exception non-HTTP
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    return error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message=f"Internal server error: {type(exc).__name__}",
        status_code=500,
        request_id=rid,
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler untuk exception yang tidak tertangani."""
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    return error_response(
        code=ErrorCode.INTERNAL_ERROR,
        message=f"Internal server error: {type(exc).__name__}",
        status_code=500,
        request_id=rid,
    )
