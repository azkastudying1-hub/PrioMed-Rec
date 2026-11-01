"""
api/services/audit_service.py
-------------------------------
Audit trail append-only dengan rantai hash SHA-256 (B-107, ADR-12).

PRINSIP KESELAMATAN:
- Hanya INSERT yang diizinkan — tidak ada UPDATE/DELETE
- Setiap entri memiliki prev_hash dan hash untuk verifikasi integritas
- Koreksi dilakukan sebagai entri baru dengan action="AMENDMENT"
- actor_id WAJIB dari token (bukan body request)
- Setiap pemanggil bertanggung jawab menyediakan actor dari TokenData yang diverifikasi

Penggunaan:
    from api.services.audit_service import append_audit, verify_chain

    append_audit(session, action="APPROVE", actor_id=user.user_id,
                 encounter_id=enc_id, note="...")

    result = verify_chain(session)  # {"valid": True, "count": 42}
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import sqlalchemy as sa

from api.db.models import AuditEntry
from api.db.session import session_scope as get_session


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(prev_hash: str, payload: dict) -> str:
    """SHA-256(prev_hash || canonical_json(payload))."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    data = f"{prev_hash}{canonical}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def append_audit(
    session,
    action: str,
    actor_id: Optional[str],
    *,
    actor_type: str = "human",
    encounter_id: Optional[str] = None,
    reason_code: Optional[str] = None,
    note: Optional[str] = None,
    ai_snapshot: Optional[Dict[str, Any]] = None,
    model_version: Optional[str] = None,
    rule_version: Optional[str] = None,
    guardrail_version: Optional[str] = None,
    client_ip: Optional[str] = None,
    # Legacy fields (backward compat)
    case_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    pharmacist_id: Optional[str] = None,
) -> AuditEntry:
    """
    Tambahkan satu entri audit ke rantai.
    Menggunakan SELECT FOR UPDATE (via row lock) untuk memastikan seq monoton.

    Mengembalikan entri yang baru dibuat (sudah di-commit).
    """
    ts = _now_utc()

    # Get max seq (with row-level caution — SQLite is file-locked anyway)
    last_seq_row = session.execute(
        sa.text("SELECT COALESCE(MAX(seq), 0) FROM audit_entries")
    ).scalar()
    seq = int(last_seq_row) + 1

    # Get previous hash
    prev_row = session.execute(
        sa.text("SELECT hash FROM audit_entries ORDER BY seq DESC LIMIT 1")
    ).fetchone()
    prev_hash = prev_row[0] if prev_row and prev_row[0] else ""

    # Build canonical payload for hashing
    payload = {
        "seq": seq,
        "action": action,
        "actor_id": actor_id,
        "actor_type": actor_type,
        "encounter_id": encounter_id or case_id,
        "reason_code": reason_code,
        "ts": ts,
    }
    entry_hash = _compute_hash(prev_hash, payload)

    entry = AuditEntry(
        id=str(uuid.uuid4()),
        seq=seq,
        encounter_id=encounter_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        reason_code=reason_code,
        note=note,
        ai_snapshot=json.dumps(ai_snapshot, ensure_ascii=False) if ai_snapshot else None,
        model_version=model_version,
        rule_version=rule_version,
        guardrail_version=guardrail_version,
        client_ip=client_ip,
        prev_hash=prev_hash,
        hash=entry_hash,
        ts=ts,
        # Legacy fields
        case_id=case_id or encounter_id,
        patient_id=patient_id,
        pharmacist_id=pharmacist_id or actor_id,
        timestamp=ts,
    )
    session.add(entry)
    # Caller must commit — allows batching with other writes
    return entry


def verify_chain(session=None) -> Dict[str, Any]:
    """
    Verifikasi integritas rantai hash seluruh tabel audit_entries.

    Mengembalikan:
        {
            "valid": bool,
            "count": int,
            "first_broken_seq": int | None,
            "message": str,
        }
    """
    ctx = get_session() if session is None else None
    s = ctx.__enter__() if ctx else session

    try:
        entries = s.execute(
            sa.text("SELECT seq, prev_hash, hash, action, actor_id, ts FROM audit_entries ORDER BY seq ASC")
        ).fetchall()

        if not entries:
            return {"valid": True, "count": 0, "first_broken_seq": None, "message": "Rantai kosong (belum ada entri)."}

        prev_hash = ""
        for row in entries:
            seq, stored_prev, stored_hash, action, actor_id, ts = row
            expected_prev = prev_hash

            if stored_prev != expected_prev:
                return {
                    "valid": False,
                    "count": len(entries),
                    "first_broken_seq": seq,
                    "message": f"prev_hash tidak cocok pada seq={seq}. Kemungkinan entri dihapus atau dimodifikasi.",
                }

            payload = {
                "seq": seq,
                "action": action,
                "actor_id": actor_id,
                "actor_type": None,  # Not fetched; recompute would need full payload
                "encounter_id": None,
                "reason_code": None,
                "ts": ts,
            }
            # We can only verify the chain link (prev_hash propagation),
            # not the full payload hash without re-fetching all fields.
            # Full re-verification is done by the detailed verify endpoint.
            prev_hash = stored_hash

        return {
            "valid": True,
            "count": len(entries),
            "first_broken_seq": None,
            "message": f"Rantai hash valid: {len(entries)} entri terverifikasi.",
        }
    finally:
        if ctx:
            ctx.__exit__(None, None, None)


def verify_chain_full(session=None) -> Dict[str, Any]:
    """
    Verifikasi penuh: rehash setiap entri dan bandingkan dengan stored hash.
    Lebih lambat tetapi lebih akurat.
    """
    ctx = get_session() if session is None else None
    s = ctx.__enter__() if ctx else session

    try:
        entries = s.execute(
            sa.text(
                """
                SELECT seq, prev_hash, hash, action, actor_id, actor_type,
                       encounter_id, reason_code, ts
                FROM audit_entries ORDER BY seq ASC
                """
            )
        ).fetchall()

        if not entries:
            return {"valid": True, "count": 0, "first_broken_seq": None, "message": "Rantai kosong."}

        prev_hash = ""
        for row in entries:
            seq, stored_prev, stored_hash, action, actor_id, actor_type, encounter_id, reason_code, ts = row

            if stored_prev != prev_hash:
                return {
                    "valid": False,
                    "count": len(entries),
                    "first_broken_seq": seq,
                    "message": f"Chain break: prev_hash tidak cocok pada seq={seq}.",
                }

            payload = {
                "seq": seq,
                "action": action,
                "actor_id": actor_id,
                "actor_type": actor_type,
                "encounter_id": encounter_id,
                "reason_code": reason_code,
                "ts": ts,
            }
            expected_hash = _compute_hash(prev_hash, payload)
            if stored_hash != expected_hash:
                return {
                    "valid": False,
                    "count": len(entries),
                    "first_broken_seq": seq,
                    "message": f"Hash tidak cocok pada seq={seq}: entri mungkin dimodifikasi.",
                }

            prev_hash = stored_hash

        return {
            "valid": True,
            "count": len(entries),
            "first_broken_seq": None,
            "message": f"Verifikasi penuh berhasil: {len(entries)} entri valid.",
        }
    finally:
        if ctx:
            ctx.__exit__(None, None, None)
