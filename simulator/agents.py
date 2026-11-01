"""
simulator/agents.py
--------------------
Agen-agen simulasi: TTK, Apoteker, DPJP, EventGenerator.

Setiap agen berjalan dalam thread terpisah, menggunakan jam virtual,
dan memanggil SimApiClient untuk berinteraksi dengan sistem nyata.

ADR-20: Tidak ada LLM/Langflow per pasien per tick.
§9.1 PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md
"""
from __future__ import annotations

import logging
import math
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from simulator.clock import VirtualClock
from simulator.config import (
    BPMH_DURATION_MEDIAN_MIN,
    BPMH_DURATION_SIGMA_LOG,
    P_BPMH_INCOMPLETE,
    P_BPMH_DELAYED,
    REVIEW_DURATION_BY_TIER,
    P_PHARMACIST_ABANDON_CLAIM,
    P_TRANSFER_PER_HOUR,
    P_CRITICAL_LAB_PER_HOUR,
    P_DISCHARGE_BEFORE_REVIEW,
    P_CANCEL_ADMISSION,
    P_DPJP_DELAY,
    TRANSFER_ROUTES,
    SimulatorConfig,
)
from simulator.patient_generator import sample_discharge_time

logger = logging.getLogger("priomed.simulator.agents")

# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------

class BaseAgent(threading.Thread):
    """Thread dasar untuk semua agen simulator."""

    def __init__(
        self,
        agent_id: str,
        clock: VirtualClock,
        client,
        rng: random.Random,
        cfg: SimulatorConfig,
        state: "SimulatorState",
        stop_event: threading.Event,
    ):
        super().__init__(name=agent_id, daemon=True)
        self.agent_id   = agent_id
        self.clock      = clock
        self.client     = client
        self.rng        = rng
        self.cfg        = cfg
        self.state      = state
        self.stop_event = stop_event
        self.stats: Dict[str, int] = {}

    def real_sleep(self, virtual_seconds: float) -> None:
        """Tidur selama virtual_seconds jam virtual (dikonversi ke real time)."""
        real_s = self.clock.real_seconds_for_virtual(virtual_seconds)
        # Tidur dalam potongan kecil agar bisa dihentikan
        deadline = time.time() + real_s
        while time.time() < deadline and not self.stop_event.is_set():
            time.sleep(min(0.1, deadline - time.time()))

    def log(self, msg: str, level: str = "info") -> None:
        ts = self.clock.virtual_now.strftime("%H:%M")
        full = f"[{ts}] [{self.agent_id}] {msg}"
        getattr(logger, level)(full)
        if self.cfg.verbose:
            print(full)

    def incr_stat(self, key: str, n: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + n
        self.state.incr_global_stat(key, n)

    def run(self) -> None:
        try:
            self._run_loop()
        except Exception as exc:
            logger.error(f"[{self.agent_id}] Fatal error: {exc}", exc_info=True)


# ---------------------------------------------------------------------------
# SimulatorState — shared state antar agen
# ---------------------------------------------------------------------------

class SimulatorState:
    """State bersama antar semua agen (thread-safe)."""

    def __init__(self, cfg: SimulatorConfig):
        self._lock = threading.Lock()
        self.cfg   = cfg

        # Daftar encounter yang aktif di simulator
        self.active_patients: Dict[str, Dict[str, Any]] = {}  # enc_id → profile
        self.bpmh_pending:    Dict[str, Dict[str, Any]] = {}  # enc_id → profile (menunggu TTK)
        self.review_pending:  Dict[str, Dict[str, Any]] = {}  # enc_id → profile (di antrean telaah)
        self.completed:       Dict[str, Dict[str, Any]] = {}  # enc_id → hasil
        self.missed_rec:      Dict[str, Dict[str, Any]] = {}  # enc_id → info

        # Statistik global
        self._global_stats: Dict[str, int] = {}

        # Metrik terakhir dari API
        self.last_metrics: Optional[Dict[str, Any]] = None
        self.last_metrics_at: Optional[float] = None

    def register_patient(self, profile: Dict[str, Any]) -> None:
        with self._lock:
            enc_id = profile["encounter_id"]
            self.active_patients[enc_id] = profile
            self.bpmh_pending[enc_id]    = profile

    def bpmh_done(self, enc_id: str) -> None:
        with self._lock:
            profile = self.bpmh_pending.pop(enc_id, None) or self.active_patients.get(enc_id, {})
            self.review_pending[enc_id] = profile

    def review_done(self, enc_id: str) -> None:
        with self._lock:
            self.review_pending.pop(enc_id, None)
            self.active_patients.pop(enc_id, None)
            self.completed[enc_id] = {"enc_id": enc_id, "status": "COMPLETE"}

    def discharge_patient(self, enc_id: str, reason: str = "DISCHARGE") -> None:
        with self._lock:
            profile = self.active_patients.pop(enc_id, {})
            self.bpmh_pending.pop(enc_id, None)
            self.review_pending.pop(enc_id, None)
            self.missed_rec[enc_id] = {"enc_id": enc_id, "reason": reason, "profile": profile}

    def incr_global_stat(self, key: str, n: int = 1) -> None:
        with self._lock:
            self._global_stats[key] = self._global_stats.get(key, 0) + n

    def get_stats_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "active":        len(self.active_patients),
                "bpmh_pending":  len(self.bpmh_pending),
                "review_pending": len(self.review_pending),
                "completed":     len(self.completed),
                "missed_rec":    len(self.missed_rec),
                **dict(self._global_stats),
            }

    def bpmh_pending_ids(self) -> List[str]:
        with self._lock:
            return list(self.bpmh_pending.keys())

    def review_pending_ids(self) -> List[str]:
        with self._lock:
            return list(self.review_pending.keys())

    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        with self._lock:
            self.last_metrics = metrics
            self.last_metrics_at = time.time()


# ---------------------------------------------------------------------------
# ArrivalAgent — generator kedatangan pasien (Poisson tak homogen)
# ---------------------------------------------------------------------------

class ArrivalAgent(BaseAgent):
    """
    Membangkitkan kedatangan pasien sesuai pola λ(jam).

    Memanggil client.admit() untuk setiap pasien baru.
    Interval antar-kedatangan ~ Exp(1/λ(jam)).
    """

    def __init__(self, arrival_queue, **kwargs):
        super().__init__(**kwargs)
        self._arrival_queue = arrival_queue  # queue.Queue untuk profil pasien baru

    def _run_loop(self) -> None:
        from simulator.patient_generator import (
            generate_patient_profile,
            sample_interarrival_seconds,
        )
        self.log("Arrival agent mulai.")

        while not self.stop_event.is_set():
            vhour = self.clock.virtual_hour
            inter_s = sample_interarrival_seconds(vhour, self.cfg, self.rng)

            # Tidur selama inter-arrival time
            self.real_sleep(inter_s)

            if self.stop_event.is_set():
                break

            try:
                profile = generate_patient_profile(
                    rng=self.rng,
                    admitted_at=self.clock.virtual_now,
                    cfg=self.cfg,
                )

                # Admit ke API
                if self.client.offline_mode:
                    self.client.admit_offline(
                        encounter_id=profile["encounter_id"],
                        ward=profile["ward"],
                        admitted_at=profile["admitted_at"],
                        ml_score=profile["ml_score"],
                        has_rule_finding=profile["has_rule_finding"],
                    )
                else:
                    self.client.admit(
                        encounter_id=profile["encounter_id"],
                        ward=profile["ward"],
                        admitted_at=profile["admitted_at"],
                        ml_score=profile["ml_score"],
                        has_rule_finding=profile["has_rule_finding"],
                    )

                self.state.register_patient(profile)
                self._arrival_queue.put(profile)
                self.incr_stat("admitted")

                self.log(
                    f"Pasien masuk: {profile['encounter_id'][:8]}... "
                    f"bangsal={profile['ward']} "
                    f"ml={profile['ml_score']:.2f} "
                    f"rule={profile['has_rule_finding']}"
                )
            except Exception as exc:
                self.incr_stat("admit_errors")
                self.log(f"Error admit: {exc}", level="warning")


# ---------------------------------------------------------------------------
# TTKAgent — mengisi BPMH
# ---------------------------------------------------------------------------

class TTKAgent(BaseAgent):
    """
    Agen TTK (Tenaga Teknis Kefarmasian) yang mengisi BPMH.

    Memproses pasien dari bpmh_pending secara round-robin.
    Durasi BPMH ~ LogNormal(median=45 mnt, σ=0.4).
    """

    def _run_loop(self) -> None:
        self.log("TTK agent mulai.")
        while not self.stop_event.is_set():
            pending = self.state.bpmh_pending_ids()
            if not pending:
                self.real_sleep(30.0)  # 30 dtk virtual jika tidak ada pasien
                continue

            enc_id = self.rng.choice(pending)

            # Durasi BPMH (detik virtual)
            duration_min = self.rng.lognormvariate(
                math.log(BPMH_DURATION_MEDIAN_MIN), BPMH_DURATION_SIGMA_LOG
            )
            # 15-120 menit
            duration_min = max(15.0, min(120.0, duration_min))
            duration_s   = duration_min * 60.0

            self.real_sleep(duration_s)
            if self.stop_event.is_set():
                break

            # BPMH selesai
            has_rule   = self.rng.random() < 0.12  # 12% ada temuan saat BPMH
            is_high_alert = self.rng.random() < 0.10

            try:
                if self.client.offline_mode:
                    self.client.bpmh_submit_offline(
                        enc_id,
                        has_rule_finding=has_rule,
                        is_high_alert=is_high_alert,
                    )
                else:
                    self.client.bpmh_submit(
                        enc_id,
                        has_rule_finding=has_rule,
                        is_high_alert=is_high_alert,
                    )

                self.state.bpmh_done(enc_id)
                self.incr_stat("bpmh_completed")
                self.log(f"BPMH selesai: {enc_id[:8]}... rule={has_rule} high_alert={is_high_alert}")
            except Exception as exc:
                self.incr_stat("bpmh_errors")
                self.log(f"Error BPMH {enc_id[:8]}: {exc}", level="warning")


# ---------------------------------------------------------------------------
# PharmacistAgent — apoteker mengambil dan menelaah kasus
# ---------------------------------------------------------------------------

class PharmacistAgent(BaseAgent):
    """
    Agen apoteker klinis.

    Setiap siklus: ambil kasus teratas via 'next' → telaah → selesaikan.
    Kadang meninggalkan klaim (lease test).
    Menerapkan jadwal shift (pagi/siang/malam).
    """

    def __init__(self, shift: str = "pagi", **kwargs):
        super().__init__(**kwargs)
        self.shift = shift
        self.current_case: Optional[str] = None

    def _is_working(self) -> bool:
        """Apakah apoteker ini sedang di shift kerja?"""
        vh = self.clock.virtual_hour
        if self.shift == "pagi":
            return 7 <= vh < 15
        elif self.shift == "siang":
            return 14 <= vh < 22
        else:  # malam
            return vh >= 21 or vh < 7

    def _run_loop(self) -> None:
        self.log(f"Apoteker agent mulai, shift={self.shift}.")
        while not self.stop_event.is_set():
            if not self._is_working():
                # Tidur 5 menit virtual sebelum cek lagi
                self.real_sleep(300.0)
                continue

            # Ambil kasus berikutnya
            try:
                if self.client.offline_mode:
                    case = self.client.queue_next_offline(
                        user_id=self.agent_id, queue_type="REVIEW"
                    )
                else:
                    case = self.client.queue_next(queue_type="REVIEW")
            except Exception as exc:
                self.incr_stat("next_errors")
                self.log(f"Error ambil kasus: {exc}", level="warning")
                self.real_sleep(30.0)
                continue

            if not case:
                # Tidak ada kasus → tunggu 30 dtk virtual
                self.real_sleep(30.0)
                continue

            enc_id = case.get("encounter_id")
            tier   = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}.get(case.get("tier_rank", 1), "MEDIUM")
            self.current_case = enc_id
            self.log(f"Mengambil kasus {enc_id[:8]}... tier={tier}")
            self.incr_stat("cases_claimed")

            # Simulasi abandon (menguji lease expiry)
            if self.rng.random() < P_PHARMACIST_ABANDON_CLAIM:
                self.log(f"Meninggalkan klaim {enc_id[:8]}... (lease test)")
                self.incr_stat("claims_abandoned")
                self.current_case = None
                self.real_sleep(60.0)  # Tunggu 1 menit virtual sebelum ambil lagi
                continue

            # Waktu telaah berdasarkan tier
            params = REVIEW_DURATION_BY_TIER.get(tier, REVIEW_DURATION_BY_TIER["MEDIUM"])
            review_min = self.rng.lognormvariate(
                math.log(params["median"]), params["sigma_log"]
            )
            review_min = max(3.0, min(120.0, review_min))
            review_s   = review_min * 60.0

            # Heartbeat setiap 10 mnt virtual selama telaah
            real_per_virt_10min = self.clock.real_seconds_for_virtual(600.0)
            elapsed_s   = 0.0
            while elapsed_s < review_s:
                chunk = min(600.0, review_s - elapsed_s)  # 10 mnt virtual per potongan
                self.real_sleep(chunk)
                elapsed_s += chunk
                if self.stop_event.is_set():
                    break
                # Heartbeat (tidak implementasi di offline mode untuk simplisitas)

            if self.stop_event.is_set():
                break

            # Telaah selesai
            self.state.review_done(enc_id)
            self.incr_stat("reviews_completed")
            self.current_case = None
            self.log(f"Telaah selesai: {enc_id[:8]}... tier={tier} waktu={review_min:.0f} mnt")


# ---------------------------------------------------------------------------
# EventAgent — peristiwa acak (transfer, lab kritis, pulang mendadak, dll)
# ---------------------------------------------------------------------------

class EventAgent(BaseAgent):
    """
    Membangkitkan peristiwa acak pada pasien aktif:
    - Transfer bangsal
    - Lab kritis (naik prioritas)
    - Pulang sebelum telaah (missed reconciliation)
    - Batal admisi
    - Parkir DPJP
    """

    # Tick interval: 5 menit virtual
    TICK_VIRTUAL_S = 300.0

    def _run_loop(self) -> None:
        self.log("Event agent mulai.")
        while not self.stop_event.is_set():
            self.real_sleep(self.TICK_VIRTUAL_S)
            if self.stop_event.is_set():
                break
            self._fire_random_events()

    def _fire_random_events(self) -> None:
        active = list(self.state.active_patients.keys())
        if not active:
            return

        # Peluang per pasien per 5 mnt virtual (konversi dari per jam)
        p_transfer      = P_TRANSFER_PER_HOUR      * (self.TICK_VIRTUAL_S / 3600.0)
        p_critical_lab  = P_CRITICAL_LAB_PER_HOUR  * (self.TICK_VIRTUAL_S / 3600.0) * \
                          self.cfg.scenario_obj.p_critical_lab_multiplier
        p_discharge     = P_DISCHARGE_BEFORE_REVIEW * (self.TICK_VIRTUAL_S / 3600.0)
        p_cancel        = P_CANCEL_ADMISSION        * (self.TICK_VIRTUAL_S / 3600.0)
        p_dpjp          = P_DPJP_DELAY              * (self.TICK_VIRTUAL_S / 3600.0)

        for enc_id in active[:]:  # [:] sehingga aman dari modifikasi
            roll = self.rng.random()

            if roll < p_cancel:
                self._cancel(enc_id)
            elif roll < p_cancel + p_discharge:
                self._discharge(enc_id)
            elif roll < p_cancel + p_discharge + p_transfer:
                self._transfer(enc_id)
            elif roll < p_cancel + p_discharge + p_transfer + p_critical_lab:
                self._critical_lab(enc_id)
            elif roll < p_cancel + p_discharge + p_transfer + p_critical_lab + p_dpjp:
                self._dpjp_delay(enc_id)

    def _transfer(self, enc_id: str) -> None:
        profile = self.state.active_patients.get(enc_id)
        if not profile:
            return
        current_ward = profile.get("ward", "PENYAKIT_DALAM")
        targets = TRANSFER_ROUTES.get(current_ward, [])
        if not targets:
            return
        new_ward = self.rng.choice(targets)
        try:
            if self.client.offline_mode:
                self.client.transfer_offline(enc_id, new_ward=new_ward)
            else:
                self.client.transfer(enc_id, new_ward=new_ward)
            profile["ward"] = new_ward
            self.incr_stat("transfers")
            self.log(f"Transfer: {enc_id[:8]}... {current_ward} → {new_ward}")
        except Exception as exc:
            self.log(f"Error transfer {enc_id[:8]}: {exc}", level="warning")

    def _discharge(self, enc_id: str) -> None:
        try:
            if self.client.offline_mode:
                self.client.discharge_offline(enc_id, workflow_status="IN_PROGRESS")
            else:
                self.client.discharge(enc_id, workflow_status="IN_PROGRESS")
            self.state.discharge_patient(enc_id, reason="DISCHARGE_BEFORE_REVIEW")
            self.incr_stat("discharges_early")
            self.log(f"Pulang sebelum telaah: {enc_id[:8]}... (missed reconciliation)")
        except Exception as exc:
            self.log(f"Error discharge {enc_id[:8]}: {exc}", level="warning")

    def _cancel(self, enc_id: str) -> None:
        try:
            if not self.client.offline_mode:
                self.client._request("POST", f"/queue/{enc_id}/cancel")
            self.state.discharge_patient(enc_id, reason="CANCELLED")
            self.incr_stat("cancellations")
            self.log(f"Batal admisi: {enc_id[:8]}...")
        except Exception as exc:
            self.log(f"Error cancel {enc_id[:8]}: {exc}", level="warning")

    def _critical_lab(self, enc_id: str) -> None:
        """Lab kritis → update rule finding (re-admit / re-triage)."""
        profile = self.state.active_patients.get(enc_id)
        if not profile:
            return
        try:
            # Update tier via admit idempoten dengan has_rule_finding=True
            if self.client.offline_mode:
                self.client.admit_offline(
                    enc_id,
                    ward=profile.get("ward", "ICU"),
                    admitted_at=profile.get("admitted_at", datetime.now(timezone.utc).isoformat()),
                    ml_score=profile.get("ml_score"),
                    has_rule_finding=True,
                )
            else:
                self.client.admit(
                    enc_id,
                    ward=profile.get("ward", "ICU"),
                    admitted_at=profile.get("admitted_at", datetime.now(timezone.utc).isoformat()),
                    ml_score=profile.get("ml_score"),
                    has_rule_finding=True,
                )
            profile["has_rule_finding"] = True
            self.incr_stat("critical_labs")
            self.log(f"Lab kritis: {enc_id[:8]}... → tier naik (RULE)")
        except Exception as exc:
            self.log(f"Error critical_lab {enc_id[:8]}: {exc}", level="warning")

    def _dpjp_delay(self, enc_id: str) -> None:
        """DPJP tidak tersedia — parkir kasus."""
        self.incr_stat("dpjp_delays")
        self.log(f"DPJP delay: {enc_id[:8]}... (kasus dimarkir)")


# ---------------------------------------------------------------------------
# MetricsAgent — polling metrik dari API
# ---------------------------------------------------------------------------

class MetricsAgent(BaseAgent):
    """
    Polling metrik antrean dari API setiap 30 menit virtual.
    Menyimpan hasil di SimulatorState.
    """

    TICK_VIRTUAL_S = 1800.0  # 30 mnt virtual

    def _run_loop(self) -> None:
        self.log("Metrics agent mulai.")
        while not self.stop_event.is_set():
            self.real_sleep(self.TICK_VIRTUAL_S)
            if self.stop_event.is_set():
                break
            try:
                if not self.client.offline_mode:
                    metrics = self.client.get_metrics()
                    self.state.update_metrics(metrics)
                    wip = metrics.get("wip", {}).get("total", "?")
                    sla = metrics.get("sla_compliance", {}).get("HIGH_pct", "?")
                    missed = metrics.get("missed_reconciliations", {}).get("today", "?")
                    self.log(
                        f"Metrik: wip={wip} sla_HIGH={sla}% missed_hari_ini={missed}"
                    )
            except Exception as exc:
                self.log(f"Error ambil metrik: {exc}", level="warning")
