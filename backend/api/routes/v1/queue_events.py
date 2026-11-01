"""
api/routes/v1/queue_events.py
-------------------------------
SSE endpoint /events/queue — streaming diff antrean ke klien.

Protokol:
  GET /events/queue?ward=ICU&queue_type=REVIEW&since_version=N

Event yang dikirim:
  event: upsert   data: {encounter_id, tier_rank, priority_score, queue_version, ...}
  event: remove   data: {encounter_id, queue_version}
  event: claim    data: {encounter_id, claimed_by, queue_version}
  event: expire   data: {encounter_id, queue_version}
  event: promote  data: {encounter_id, from_tier, to_tier, queue_version}
  event: heartbeat data: {queue_version, ts}  (setiap 15 dtk)

Resync:
  Klien kirim Last-Event-ID: <seq> → server kirim events sejak seq itu.
  Jika tertinggal > RESYNC_THRESHOLD events → kirim event "resync" → klien muat ulang halaman.

Keselamatan:
  Tidak ada data klinis sensitif di stream (hanya tier, skor, encounter_id).
  Auth diperlukan (JWT Bearer).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from api.auth.rbac import TokenData, require_roles, UserRole
from api.db.session import session_scope as get_session
from api.services.queue_event_bus import subscribe as _bus_subscribe
from api.services.queue_event_bus import unsubscribe as _bus_unsubscribe

router = APIRouter(prefix="/events", tags=["queue-events"])
logger = logging.getLogger("priomed.sse")

HEARTBEAT_INTERVAL = 15    # detik
RESYNC_THRESHOLD   = 200   # events tertinggal → minta resync
FALLBACK_POLL      = 1.0   # detik — cadangan bila event bus tidak tersedia (multi-worker)


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------

async def _sse_generator(
    request: Request,
    ward: Optional[str],
    queue_type: Optional[str],
    since_seq: Optional[int],
) -> AsyncGenerator[str, None]:
    """
    Generator SSE: membaca `queue_events` segera setelah simulation engine /
    aksi pengguna melakukan commit (in-process event bus), dengan fallback
    polling 1 detik dan heartbeat 15 detik.
    """
    last_seq = since_seq or 0
    loop = asyncio.get_running_loop()
    wake = asyncio.Event()
    _bus_subscribe(loop, wake)
    last_heartbeat = time.monotonic()

    try:
        while True:
            # Cek koneksi client masih hidup
            if await request.is_disconnected():
                break

            try:
                with get_session() as session:
                    # Ambil queue_events baru sejak last_seq
                    query_text = """
                        SELECT seq, encounter_id, kind, payload_json, at
                        FROM queue_events
                        WHERE seq > :last_seq
                        ORDER BY seq ASC
                        LIMIT 100
                    """
                    rows = session.execute(
                        sa.text(query_text), {"last_seq": last_seq}
                    ).fetchall()

                    if rows:
                        # Cek apakah tertinggal terlalu jauh
                        lag = rows[-1][0] - last_seq if rows else 0
                        if lag > RESYNC_THRESHOLD:
                            yield _sse_event("resync", {
                                "message": "Tertinggal terlalu jauh — muat ulang halaman.",
                                "queue_version": rows[-1][0],
                            })
                            last_seq = rows[-1][0]
                            await asyncio.sleep(0.5)
                            continue

                        for seq, enc_id, kind, payload_json, at in rows:
                            # Filter per ward/queue_type jika diminta
                            try:
                                payload = json.loads(payload_json) if payload_json else {}
                            except Exception:
                                payload = {}

                            if ward and payload.get("ward") != ward:
                                # Skip jika beda bangsal — tapi tetap update last_seq
                                last_seq = seq
                                continue
                            if queue_type and payload.get("queue_type") != queue_type.upper():
                                last_seq = seq
                                continue

                            event_data = {
                                "encounter_id":  enc_id,
                                "kind":          kind,
                                "seq":           seq,
                                "at":            at,
                                **payload,
                            }
                            yield _sse_event(kind, event_data, event_id=str(seq))
                            last_seq = seq

            except Exception as exc:
                logger.warning(f"[SSE] Error saat polling: {exc}")

            # Heartbeat setiap HEARTBEAT_INTERVAL detik
            now_mono = time.monotonic()
            if now_mono - last_heartbeat >= HEARTBEAT_INTERVAL:
                last_heartbeat = now_mono
                try:
                    with get_session() as session:
                        max_seq = session.execute(
                            sa.text("SELECT COALESCE(MAX(seq), 0) FROM queue_events")
                        ).scalar() or 0
                    yield _sse_event("heartbeat", {
                        "queue_version": max_seq,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    yield _sse_event("heartbeat", {"ts": datetime.now(timezone.utc).isoformat()})

            # Tunggu sinyal bus; fallback poll agar tetap jalan di multi-worker.
            try:
                await asyncio.wait_for(wake.wait(), timeout=FALLBACK_POLL)
            except asyncio.TimeoutError:
                pass
            wake.clear()
    finally:
        _bus_unsubscribe(loop, wake)


def _sse_event(event_type: str, data: dict, event_id: Optional[str] = None) -> str:
    """Format SSE event."""
    lines = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/queue", summary="SSE — stream diff antrean real-time")
async def stream_queue_events(
    request: Request,
    ward:        Optional[str] = Query(None, description="Filter bangsal"),
    queue_type:  Optional[str] = Query(None, description="BPMH | REVIEW"),
    from_now:    bool = Query(False, description="Mulai dari event terbaru (tanpa memutar ulang riwayat)"),
    current_user: TokenData = Depends(
        require_roles(UserRole.PHARMACIST, UserRole.TECHNICIAN,
                      UserRole.COORDINATOR, UserRole.ADMIN)
    ),
):
    """
    Server-Sent Events stream.

    Klien connect:
        const es = new EventSource('/api/v1/events/queue', {headers: {Authorization: 'Bearer ...'}})
        es.addEventListener('upsert', e => patch_cache(JSON.parse(e.data)))

    Reconnect otomatis dengan Last-Event-ID header.
    """
    # Ambil since_seq dari Last-Event-ID header
    last_event_id = request.headers.get("Last-Event-ID")
    since_seq = None
    if last_event_id:
        try:
            since_seq = int(last_event_id)
        except ValueError:
            pass

    if since_seq is None and from_now:
        with get_session() as session:
            since_seq = session.execute(
                sa.text("SELECT COALESCE(MAX(seq), 0) FROM queue_events")
            ).scalar() or 0

    return StreamingResponse(
        _sse_generator(request, ward=ward, queue_type=queue_type, since_seq=since_seq),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
