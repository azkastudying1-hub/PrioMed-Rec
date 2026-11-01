"""
api/tasks/scheduler.py
------------------------
APScheduler background task runner (B-106).

Jobs:
  - sla_check: jalankan SLA check setiap 60 detik (idempoten)

Scheduler distart saat lifespan FastAPI startup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger("priomed.scheduler")

_scheduler = None


def start_scheduler() -> None:
    """Inisialisasi dan start APScheduler background scheduler."""
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from api.services.sla_service import run_sla_check
        from api.tasks.queue_tick import run_queue_tick

        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_job(
            run_sla_check,
            trigger="interval",
            seconds=60,
            id="sla_check",
            replace_existing=True,
            max_instances=1,  # Jangan jalankan tumpang tindih
        )
        _scheduler.add_job(
            run_queue_tick,
            trigger="interval",
            seconds=60,
            id="queue_tick",
            replace_existing=True,
            max_instances=1,  # Idempoten — hanya satu instance berjalan
        )
        _scheduler.start()
        logger.info("[scheduler] APScheduler started: sla_check + queue_tick every 60s")
    except ImportError:
        logger.warning("[scheduler] APScheduler tidak tersedia — SLA/queue tick tidak aktif")
    except Exception as exc:
        logger.error(f"[scheduler] Gagal start scheduler: {exc}")


def stop_scheduler() -> None:
    """Hentikan scheduler dengan bersih saat shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] APScheduler stopped.")
