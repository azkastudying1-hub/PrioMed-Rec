"""
api/services/queue_event_bus.py
--------------------------------
In-process wake-up bus untuk SSE `/api/v1/events/queue`.

SSE saat ini membaca tabel `queue_events` secara periodik. Tanpa bus ini,
klien harus menunggu poll interval (sebelumnya 2 detik). Simulation engine
(thread APScheduler) memanggil `publish()` setiap selesai satu langkah,
sehingga SSE langsung membaca event baru tanpa menunggu timer.

Desain:
  - Ringan, tanpa Redis/broker — cukup untuk demo satu proses uvicorn.
  - Thread-safe: `publish()` boleh dipanggil dari thread mana pun.
  - Jika ada beberapa worker uvicorn, SSE tetap punya fallback polling
    (1 detik) sehingga update tetap terkirim, hanya sedikit lebih lambat.
  - Listener `after_commit` SQLAlchemy memicu publish untuk semua commit,
    sehingga klaim/aksi pengguna juga langsung terlihat oleh klien lain.

Tidak ada data klinis yang dikirim lewat bus — hanya sinyal "ada perubahan".
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import List, Tuple

from sqlalchemy import event
from sqlalchemy.orm import Session

logger = logging.getLogger("priomed.event_bus")

# (loop, event) — event dibuat di event loop SSE masing-masing klien.
_subscribers: List[Tuple[asyncio.AbstractEventLoop, asyncio.Event]] = []
_lock = threading.Lock()


def subscribe(loop: asyncio.AbstractEventLoop, wake: asyncio.Event) -> None:
    """Daftarkan event SSE. Dipanggil dari dalam event loop."""
    with _lock:
        _subscribers.append((loop, wake))


def unsubscribe(loop: asyncio.AbstractEventLoop, wake: asyncio.Event) -> None:
    with _lock:
        try:
            _subscribers.remove((loop, wake))
        except ValueError:
            pass


def publish() -> None:
    """Bangunkan semua klien SSE. Aman dipanggil dari thread mana pun."""
    with _lock:
        subscribers = list(_subscribers)
    for loop, wake in subscribers:
        try:
            if loop.is_closed():
                continue
            loop.call_soon_threadsafe(wake.set)
        except RuntimeError:
            # Loop sudah berhenti — abaikan; subscriber akan dibersihkan saat disconnect.
            continue
        except Exception as exc:  # pragma: no cover - defensif
            logger.debug("[event_bus] publish gagal: %s", exc)


# ---------------------------------------------------------------------------
# SQLAlchemy hook: setiap commit membangunkan SSE.
# Ini menangkap klaim, rilis, review, BPMH submit, dan perubahan antrean lain
# tanpa perlu menambahkan publish() manual di setiap route.
# ---------------------------------------------------------------------------

@event.listens_for(Session, "after_commit")
def _after_commit(_session: Session) -> None:  # pragma: no cover - dipicu DB
    publish()
