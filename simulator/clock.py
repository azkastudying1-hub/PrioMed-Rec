"""
simulator/clock.py
-------------------
Jam virtual (virtual clock) untuk Hospital Simulator.

Mendukung percepatan 1×–240×, jeda, dan reset.
Dipakai bersama oleh semua agen dan generator.

Contoh:
  clock = VirtualClock(speed=60.0, start_hour=7)
  # 1 menit real = 60 menit virtual → 1 jam RS
  clock.advance(real_seconds=1.0)  → virtual +60 detik
  clock.virtual_now               → datetime UTC virtual saat ini
  clock.virtual_hour              → 0–23
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional


class VirtualClock:
    """
    Jam virtual yang dapat dipercepat, dijeda, dan di-reset.

    Thread-safe (Lock).
    """

    def __init__(
        self,
        speed: float = 60.0,
        start_virtual_time: Optional[datetime] = None,
        start_real_time: Optional[float] = None,
    ):
        """
        Args:
            speed: Faktor percepatan (1.0 = real-time, 60.0 = 1 mnt real = 1 jam virtual).
            start_virtual_time: Waktu virtual awal (default: sekarang UTC).
            start_real_time: Waktu real epoch awal (default: time.time()).
        """
        self._speed = max(0.001, speed)
        self._start_virtual = start_virtual_time or datetime.now(timezone.utc)
        self._start_real    = start_real_time or time.time()
        self._paused        = False
        self._pause_real_at: Optional[float] = None
        self._accumulated_pause_s: float = 0.0
        self._lock          = Lock()

    # ------------------------------------------------------------------
    # Akses waktu
    # ------------------------------------------------------------------

    @property
    def virtual_now(self) -> datetime:
        """Waktu virtual saat ini."""
        with self._lock:
            return self._compute_virtual_now()

    def _compute_virtual_now(self) -> datetime:
        if self._paused and self._pause_real_at is not None:
            elapsed_real = self._pause_real_at - self._start_real - self._accumulated_pause_s
        else:
            elapsed_real = time.time() - self._start_real - self._accumulated_pause_s
        elapsed_virtual_s = max(0.0, elapsed_real) * self._speed
        return self._start_virtual + timedelta(seconds=elapsed_virtual_s)

    @property
    def virtual_hour(self) -> int:
        """Jam virtual (0–23)."""
        return self.virtual_now.hour

    @property
    def virtual_day_of_week(self) -> int:
        """Hari dalam pekan (0=Senin, 6=Minggu)."""
        return self.virtual_now.weekday()

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def is_paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------
    # Kontrol
    # ------------------------------------------------------------------

    def pause(self) -> None:
        """Jeda jam virtual."""
        with self._lock:
            if not self._paused:
                self._paused = True
                self._pause_real_at = time.time()

    def resume(self) -> None:
        """Lanjutkan jam virtual setelah dijeda."""
        with self._lock:
            if self._paused and self._pause_real_at is not None:
                paused_duration = time.time() - self._pause_real_at
                self._accumulated_pause_s += paused_duration
                self._paused = False
                self._pause_real_at = None

    def set_speed(self, new_speed: float) -> None:
        """Ubah kecepatan tanpa reset waktu virtual."""
        with self._lock:
            current_virtual = self._compute_virtual_now()
            self._start_virtual = current_virtual
            self._start_real    = time.time()
            self._accumulated_pause_s = 0.0
            self._pause_real_at = None
            self._paused = False
            self._speed  = max(0.001, new_speed)

    def reset(self, start_virtual_time: Optional[datetime] = None) -> None:
        """Reset jam ke waktu virtual tertentu."""
        with self._lock:
            self._start_virtual = start_virtual_time or datetime.now(timezone.utc)
            self._start_real    = time.time()
            self._accumulated_pause_s = 0.0
            self._paused = False
            self._pause_real_at = None

    # ------------------------------------------------------------------
    # Konversi waktu
    # ------------------------------------------------------------------

    def real_seconds_for_virtual(self, virtual_seconds: float) -> float:
        """Berapa detik real untuk menunggu virtual_seconds jam virtual."""
        return virtual_seconds / self._speed

    def virtual_seconds_elapsed_since(self, virtual_checkpoint: datetime) -> float:
        """Berapa detik virtual sudah berlalu sejak checkpoint."""
        now = self.virtual_now
        return (now - virtual_checkpoint).total_seconds()

    # ------------------------------------------------------------------
    # String
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        vn = self.virtual_now
        return (
            f"VirtualClock(speed={self._speed}×, "
            f"virtual={vn.strftime('%Y-%m-%d %H:%M')}, "
            f"paused={self._paused})"
        )
