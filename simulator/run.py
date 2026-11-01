"""
simulator/run.py
-----------------
Entry point Hospital Simulator.

Perintah:
  python -m simulator.run --size M --speed 60 --scenario evening_surge --seed 42
  python -m simulator.run --size S --speed 120 --offline  # tanpa server HTTP

LABEL WAJIB:
  "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"
"""
from __future__ import annotations

import argparse
import logging
import heapq
import math
import queue
import random
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from simulator.agents import (
    ArrivalAgent,
    EventAgent,
    MetricsAgent,
    PharmacistAgent,
    SimulatorState,
    TTKAgent,
)
from simulator.api_client import SimApiClient
from simulator.clock import VirtualClock
from simulator.config import (
    BPMH_DURATION_MEDIAN_MIN,
    BPMH_DURATION_SIGMA_LOG,
    REVIEW_DURATION_BY_TIER,
    P_PHARMACIST_ABANDON_CLAIM,
    P_TRANSFER_PER_HOUR,
    P_CRITICAL_LAB_PER_HOUR,
    P_DISCHARGE_BEFORE_REVIEW,
    P_CANCEL_ADMISSION,
    P_DPJP_DELAY,
    TRANSFER_ROUTES,
    SCENARIOS,
    SEED_SIZES,
    SimulatorConfig,
)
from simulator.patient_generator import (
    generate_patient_profile,
    generate_seed_batch,
    sample_interarrival_seconds,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("priomed.simulator.run")

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

SIMULATION_LABEL = (
    "[SIMULASI] Data simulasi - parameter berbasis asumsi, belum dikalibrasi dengan RS"
)

_BANNER = """
+------------------------------------------------------------------+
|        PrioMed-Rec - Hospital Simulator (Q-007)                  |
|  Mensimulasikan RS skala nyata untuk demo dan uji beban          |
+------------------------------------------------------------------+
{label}

Ukuran : {size}  ({open_entries} entri terbuka awal, {history_entries} riwayat)
Skenario: {scenario} - {scenario_desc}
Kecepatan: {speed}x (1 menit real = {speed} menit virtual)
Seed    : {seed}
Mode    : {mode}
API     : {api}
--------------------------------------------------------------------
"""


# ---------------------------------------------------------------------------
# Seeder — ingest backlog awal ke API/DB
# ---------------------------------------------------------------------------

def seed_database(
    cfg: SimulatorConfig,
    client: SimApiClient,
    state: SimulatorState,
    rng: random.Random,
    now: Optional[datetime] = None,
) -> None:
    """
    Ingest backlog awal (open_entries) ke sistem.

    Dipanggil sekali saat startup sebelum simulator mulai.
    Batch insert → tidak memanggil API per-pasien (lebih cepat di offline mode).
    """
    logger.info(f"[seeder] Memulai seeding ukuran {cfg.size}...")
    seed_size = cfg.seed_size
    seed_now = now or datetime(2026, 10, 29, 7, 0, 0, tzinfo=timezone.utc)

    open_patients, history_patients = generate_seed_batch(cfg, rng, seed_now)

    admitted = 0
    errors   = 0
    batch_size = 50  # Batch log setiap 50

    for i, profile in enumerate(open_patients):
        try:
            if client.offline_mode:
                client.admit_offline(
                    encounter_id=profile["encounter_id"],
                    ward=profile["ward"],
                    admitted_at=profile["admitted_at"],
                    ml_score=profile["ml_score"],
                    has_rule_finding=profile["has_rule_finding"],
                )
            else:
                client.admit(
                    encounter_id=profile["encounter_id"],
                    ward=profile["ward"],
                    admitted_at=profile["admitted_at"],
                    ml_score=profile["ml_score"],
                    has_rule_finding=profile["has_rule_finding"],
                )
            state.register_patient(profile)
            admitted += 1
            if admitted % batch_size == 0:
                logger.info(f"[seeder] Admitted {admitted}/{len(open_patients)}...")
        except Exception as exc:
            errors += 1
            if errors <= 5:
                logger.warning(f"[seeder] Error admit {profile['encounter_id'][:8]}: {exc}")

    logger.info(
        f"[seeder] Seeding selesai: {admitted} admitted, {errors} errors. "
        f"(Riwayat {len(history_patients)} tidak di-ingest — hanya statistik)"
    )


def run_discrete_simulation(cfg: SimulatorConfig) -> Dict[str, Any]:
    """
    Simulasi Kejadian Diskrit (Discrete Event Simulation - DES) 100% deterministik.
    Menghilangkan jitter scheduling OS thread, menjamin 2x run dengan seed sama
    menghasilkan laporan akhir yang 100% identik (ADR-22).
    """
    scenario = cfg.scenario_obj
    seed_size = cfg.seed_size

    print(_BANNER.format(
        label=SIMULATION_LABEL,
        size=cfg.size,
        open_entries=seed_size.open_entries,
        history_entries=seed_size.history_entries,
        scenario=cfg.scenario,
        scenario_desc=scenario.description,
        speed=cfg.speed,
        seed=cfg.seed,
        mode="Discrete Event Simulation (Deterministik)",
        api=cfg.api_base_url,
    ))

    rng = random.Random(cfg.seed)
    start_vt = datetime(2026, 10, 29, 7, 0, 0, tzinfo=timezone.utc)
    max_hours = cfg.max_virtual_hours if cfg.max_virtual_hours is not None else 24.0
    end_s = max_hours * 3600.0

    client = SimApiClient(
        base_url=cfg.api_base_url,
        token=cfg.api_token,
        offline_mode=True,
    )
    state = SimulatorState(cfg)

    # 1. Seeding backlog awal
    logger.info("[DES] Seeding backlog awal...")
    seed_database(cfg, client, state, rng, now=start_vt)

    # 2. Priority queue: (t_s, event_counter, event_type, data)
    event_counter = 0
    pq: List[Any] = []

    def push_event(t_s: float, ev_type: str, data: Any = None):
        nonlocal event_counter
        if t_s <= end_s:
            heapq.heappush(pq, (t_s, event_counter, ev_type, data))
            event_counter += 1

    # Jadwalkan kedatangan pasien (Inhomogeneous Poisson Process)
    current_t = 0.0
    while current_t < end_s:
        vh = int((start_vt + timedelta(seconds=current_t)).hour)
        inter_s = sample_interarrival_seconds(vh, cfg, rng)
        current_t += inter_s
        if current_t < end_s:
            push_event(current_t, "ARRIVAL")

    # Jadwalkan tick event acak setiap 300 detik virtual
    t_ev = 300.0
    while t_ev < end_s:
        push_event(t_ev, "RANDOM_EVENTS")
        t_ev += 300.0

    # Jadwalkan check rutin apoteker setiap 60 detik virtual
    t_ph = 60.0
    while t_ph < end_s:
        push_event(t_ph, "PHARMACIST_POLL")
        t_ph += 60.0

    # Pekerja TTK & Apoteker (status idle/busy)
    ttk_idle = [f"TTK-{i+1:02d}" for i in range(cfg.ttk_count)]
    shifts = ["pagi", "siang", "malam"]
    pharmacists = [
        {"id": f"APT-{i+1:02d}", "shift": shifts[i % len(shifts)], "busy": False}
        for i in range(cfg.pharmacist_count)
    ]

    def is_ph_working(ph: Dict[str, Any], vh: int) -> bool:
        shift = ph["shift"]
        if shift == "pagi":
            return 7 <= vh < 15
        elif shift == "siang":
            return 14 <= vh < 22
        else:
            return vh >= 21 or vh < 7

    def try_assign_ttk(current_time: float):
        while ttk_idle and state.bpmh_pending_ids():
            pending = sorted(state.bpmh_pending_ids())
            enc_id = rng.choice(pending)
            ttk_id = ttk_idle.pop(0)

            dur_min = rng.lognormvariate(math.log(BPMH_DURATION_MEDIAN_MIN), BPMH_DURATION_SIGMA_LOG)
            dur_min = max(15.0, min(120.0, dur_min))
            push_event(current_time + (dur_min * 60.0), "BPMH_FINISH", (enc_id, ttk_id))

    def try_assign_pharmacists(current_time: float):
        current_vt = start_vt + timedelta(seconds=current_time)
        vh = current_vt.hour
        for ph in pharmacists:
            if not ph["busy"] and is_ph_working(ph, vh):
                case = client.queue_next_offline(user_id=ph["id"], queue_type="REVIEW", now=current_vt)
                if case:
                    ph["busy"] = True
                    enc_id = case.get("encounter_id")
                    tier = {2: "HIGH", 1: "MEDIUM", 0: "LOW"}.get(case.get("tier_rank", 1), "MEDIUM")
                    state.incr_global_stat("cases_claimed")

                    if rng.random() < P_PHARMACIST_ABANDON_CLAIM:
                        state.incr_global_stat("claims_abandoned")
                        push_event(current_time + 60.0, "PHARMACIST_FREE", ph["id"])
                    else:
                        p = REVIEW_DURATION_BY_TIER.get(tier, REVIEW_DURATION_BY_TIER["MEDIUM"])
                        rev_min = rng.lognormvariate(math.log(p["median"]), p["sigma_log"])
                        rev_min = max(3.0, min(120.0, rev_min))
                        push_event(current_time + (rev_min * 60.0), "REVIEW_FINISH", (enc_id, ph["id"]))

    # Mulai penugasan awal
    try_assign_ttk(0.0)
    try_assign_pharmacists(0.0)

    # 3. Main event execution loop
    while pq:
        t_s, _, ev_type, data = heapq.heappop(pq)
        vt_now = start_vt + timedelta(seconds=t_s)

        if ev_type == "ARRIVAL":
            profile = generate_patient_profile(rng=rng, admitted_at=vt_now, cfg=cfg)
            client.admit_offline(
                encounter_id=profile["encounter_id"],
                ward=profile["ward"],
                admitted_at=profile["admitted_at"],
                ml_score=profile["ml_score"],
                has_rule_finding=profile["has_rule_finding"],
                now=vt_now,
            )
            state.register_patient(profile)
            state.incr_global_stat("admitted")
            try_assign_ttk(t_s)

        elif ev_type == "BPMH_FINISH":
            enc_id, ttk_id = data
            ttk_idle.append(ttk_id)
            has_rule = rng.random() < 0.12
            is_high_alert = rng.random() < 0.10
            client.bpmh_submit_offline(enc_id, has_rule_finding=has_rule, is_high_alert=is_high_alert, now=vt_now)
            state.bpmh_done(enc_id)
            state.incr_global_stat("bpmh_completed")
            try_assign_ttk(t_s)
            try_assign_pharmacists(t_s)

        elif ev_type == "REVIEW_FINISH":
            enc_id, ph_id = data
            state.review_done(enc_id)
            state.incr_global_stat("reviews_completed")
            for ph in pharmacists:
                if ph["id"] == ph_id:
                    ph["busy"] = False
                    break
            try_assign_pharmacists(t_s)

        elif ev_type == "PHARMACIST_FREE":
            ph_id = data
            for ph in pharmacists:
                if ph["id"] == ph_id:
                    ph["busy"] = False
                    break
            try_assign_pharmacists(t_s)

        elif ev_type == "PHARMACIST_POLL":
            try_assign_pharmacists(t_s)

        elif ev_type == "RANDOM_EVENTS":
            active = sorted(list(state.active_patients.keys()))
            step_h = 300.0 / 3600.0
            p_trans = P_TRANSFER_PER_HOUR * step_h
            p_crit = P_CRITICAL_LAB_PER_HOUR * step_h * scenario.p_critical_lab_multiplier
            p_disc = P_DISCHARGE_BEFORE_REVIEW * step_h
            p_canc = P_CANCEL_ADMISSION * step_h
            p_dpjp = P_DPJP_DELAY * step_h

            for eid in active:
                roll = rng.random()
                if roll < p_canc:
                    state.discharge_patient(eid, reason="CANCELLED")
                    state.incr_global_stat("cancellations")
                elif roll < p_canc + p_disc:
                    client.discharge_offline(eid, workflow_status="IN_PROGRESS", now=vt_now)
                    state.discharge_patient(eid, reason="DISCHARGE_BEFORE_REVIEW")
                    state.incr_global_stat("discharges_early")
                elif roll < p_canc + p_disc + p_trans:
                    prof = state.active_patients.get(eid)
                    if prof:
                        cur_w = prof.get("ward", "PENYAKIT_DALAM")
                        targets = TRANSFER_ROUTES.get(cur_w, [])
                        if targets:
                            nw = rng.choice(targets)
                            client.transfer_offline(eid, new_ward=nw, now=vt_now)
                            prof["ward"] = nw
                            state.incr_global_stat("transfers")
                elif roll < p_canc + p_disc + p_trans + p_crit:
                    prof = state.active_patients.get(eid)
                    if prof:
                        client.admit_offline(
                            eid,
                            ward=prof.get("ward", "ICU"),
                            admitted_at=prof.get("admitted_at", vt_now.isoformat()),
                            ml_score=prof.get("ml_score"),
                            has_rule_finding=True,
                            now=vt_now,
                        )
                        prof["has_rule_finding"] = True
                        state.incr_global_stat("critical_labs")
                elif roll < p_canc + p_disc + p_trans + p_crit + p_dpjp:
                    state.incr_global_stat("dpjp_delays")

    snap = state.get_stats_snapshot()
    end_vt = start_vt + timedelta(seconds=end_s)
    print("\n" + "-" * 66)
    print(f"  Laporan Akhir Simulator - {end_vt.strftime('%Y-%m-%d %H:%M')}")
    print(f"  {SIMULATION_LABEL}")
    print("-" * 66)
    print(f"  Pasien masuk         : {snap.get('admitted', 0)}")
    print(f"  BPMH selesai         : {snap.get('bpmh_completed', 0)}")
    print(f"  Telaah selesai       : {snap.get('reviews_completed', 0)}")
    print(f"  Missed reconciliation: {snap['missed_rec']}")
    print(f"  Transfer bangsal     : {snap.get('transfers', 0)}")
    print(f"  Lab kritis           : {snap.get('critical_labs', 0)}")
    print(f"  Batal admisi         : {snap.get('cancellations', 0)}")
    print(f"  Error (API)          : {snap.get('admit_errors', 0) + snap.get('bpmh_errors', 0)}")
    print("-" * 66)
    logger.info("[DES] Simulator deterministik selesai.")
    return snap


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(cfg: SimulatorConfig) -> Optional[Dict[str, Any]]:
    """
    Jalankan Hospital Simulator sesuai konfigurasi.
    """
    if cfg.deterministic:
        return run_discrete_simulation(cfg)

    scenario = cfg.scenario_obj
    seed_size = cfg.seed_size

    # Banner
    print(_BANNER.format(
        label=SIMULATION_LABEL,
        size=cfg.size,
        open_entries=seed_size.open_entries,
        history_entries=seed_size.history_entries,
        scenario=cfg.scenario,
        scenario_desc=scenario.description,
        speed=cfg.speed,
        seed=cfg.seed,
        mode="Offline (direct DB)" if True else "Online (HTTP API)",
        api=cfg.api_base_url,
    ))

    # RNG deterministik
    rng = random.Random(cfg.seed)

    # Jam virtual (mulai jam 07:00 hari ini)
    start_vt = datetime.now(timezone.utc).replace(hour=7, minute=0, second=0, microsecond=0)
    clock = VirtualClock(speed=cfg.speed, start_virtual_time=start_vt)

    # API client (selalu offline untuk demo karena HTTP mungkin tidak tersedia)
    client = SimApiClient(
        base_url=cfg.api_base_url,
        token=cfg.api_token,
        offline_mode=True,  # Gunakan offline mode secara default agar demo tidak perlu server HTTP
    )

    state       = SimulatorState(cfg)
    stop_event  = threading.Event()
    arrival_q   = queue.Queue()

    # -----------------------------------------------------------------------
    # Seed database
    # -----------------------------------------------------------------------
    logger.info("[run] Seeding database...")
    try:
        seed_database(cfg, client, state, rng)
    except Exception as exc:
        logger.error(f"[run] Seeding gagal: {exc}. Simulator berjalan dengan DB kosong.")

    # -----------------------------------------------------------------------
    # Spawn agen
    # -----------------------------------------------------------------------
    agents: List = []

    # Arrival agent
    arrival_agent = ArrivalAgent(
        agent_id="ArrivalAgent",
        clock=clock,
        client=client,
        rng=random.Random(rng.randint(0, 2**32)),
        cfg=cfg,
        state=state,
        stop_event=stop_event,
        arrival_queue=arrival_q,
    )
    agents.append(arrival_agent)

    # TTK agents
    for i in range(cfg.ttk_count):
        ttk = TTKAgent(
            agent_id=f"TTK-{i+1:02d}",
            clock=clock,
            client=client,
            rng=random.Random(rng.randint(0, 2**32)),
            cfg=cfg,
            state=state,
            stop_event=stop_event,
        )
        agents.append(ttk)

    # Pharmacist agents (distribusi shift)
    shifts = ["pagi", "siang", "malam"]
    for i in range(cfg.pharmacist_count):
        shift = shifts[i % len(shifts)]
        ph = PharmacistAgent(
            agent_id=f"APT-{i+1:02d}",
            clock=clock,
            client=client,
            rng=random.Random(rng.randint(0, 2**32)),
            cfg=cfg,
            state=state,
            stop_event=stop_event,
            shift=shift,
        )
        agents.append(ph)

    # Event agent
    event_agent = EventAgent(
        agent_id="EventAgent",
        clock=clock,
        client=client,
        rng=random.Random(rng.randint(0, 2**32)),
        cfg=cfg,
        state=state,
        stop_event=stop_event,
    )
    agents.append(event_agent)

    # Metrics agent
    metrics_agent = MetricsAgent(
        agent_id="MetricsAgent",
        clock=clock,
        client=client,
        rng=random.Random(rng.randint(0, 2**32)),
        cfg=cfg,
        state=state,
        stop_event=stop_event,
    )
    agents.append(metrics_agent)

    # -----------------------------------------------------------------------
    # Graceful shutdown
    # -----------------------------------------------------------------------
    def _shutdown(signum=None, frame=None):
        logger.info("[run] Menghentikan simulator (graceful shutdown)...")
        stop_event.set()

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # -----------------------------------------------------------------------
    # Start semua agen
    # -----------------------------------------------------------------------
    for agent in agents:
        agent.start()

    logger.info(
        f"[run] {len(agents)} agen berjalan. "
        f"TTK={cfg.ttk_count}, Apoteker={cfg.pharmacist_count}. "
        f"Tekan Ctrl+C untuk berhenti."
    )

    # -----------------------------------------------------------------------
    # Loop utama — cetak statistik + cek durasi
    # -----------------------------------------------------------------------
    stats_interval_real = 10.0  # Cetak statistik setiap 10 dtk real
    last_stats_at = time.time()

    while not stop_event.is_set():
        time.sleep(0.5)

        now_real = time.time()
        if now_real - last_stats_at >= stats_interval_real:
            last_stats_at = now_real
            snap = state.get_stats_snapshot()
            vt   = clock.virtual_now.strftime("%Y-%m-%d %H:%M")
            print(
                f"\r[{vt}] aktif={snap['active']:4d} "
                f"bpmh_pending={snap['bpmh_pending']:4d} "
                f"review={snap['review_pending']:4d} "
                f"selesai={snap.get('reviews_completed', 0):4d} "
                f"missed={snap['missed_rec']:3d} "
                f"masuk={snap.get('admitted', 0):4d}",
                end="", flush=True,
            )

        # Cek max_virtual_hours
        if cfg.max_virtual_hours is not None:
            elapsed_virtual_h = (
                clock.virtual_now - start_vt
            ).total_seconds() / 3600.0
            if elapsed_virtual_h >= cfg.max_virtual_hours:
                logger.info(
                    f"[run] Durasi {cfg.max_virtual_hours}h virtual selesai. Berhenti."
                )
                _shutdown()

    # -----------------------------------------------------------------------
    # Tunggu agen selesai
    # -----------------------------------------------------------------------
    print()  # Newline setelah stats line
    for agent in agents:
        agent.join(timeout=5.0)

    client.close()

    # -----------------------------------------------------------------------
    # Laporan akhir
    # -----------------------------------------------------------------------
    snap = state.get_stats_snapshot()
    print("\n" + "-" * 66)
    print(f"  Laporan Akhir Simulator - {clock.virtual_now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  {SIMULATION_LABEL}")
    print("-" * 66)
    print(f"  Pasien masuk         : {snap.get('admitted', 0)}")
    print(f"  BPMH selesai         : {snap.get('bpmh_completed', 0)}")
    print(f"  Telaah selesai       : {snap.get('reviews_completed', 0)}")
    print(f"  Missed reconciliation: {snap['missed_rec']}")
    print(f"  Transfer bangsal     : {snap.get('transfers', 0)}")
    print(f"  Lab kritis           : {snap.get('critical_labs', 0)}")
    print(f"  Batal admisi         : {snap.get('cancellations', 0)}")
    print(f"  Error (API)          : {snap.get('admit_errors', 0) + snap.get('bpmh_errors', 0)}")
    print("-" * 66)
    logger.info("[run] Simulator berhenti.")
    return snap


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PrioMed-Rec Hospital Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Ukuran:
  S  — RS ~250 tt, 80 entri terbuka, demo cepat
  M  — RS ~500 tt, 300 entri terbuka, demo utama (default)
  L  — uji beban (2.000 entri)
  XL — uji stres (5.000 entri)

Skenario: {', '.join(SCENARIOS.keys())}

Contoh:
  python -m simulator.run --size M --speed 60 --scenario evening_surge --seed 42
  python -m simulator.run --size S --speed 120 --max-hours 8 --verbose

{SIMULATION_LABEL}
""",
    )
    parser.add_argument("--size",        default="M",            choices=list(SEED_SIZES.keys()))
    parser.add_argument("--speed",       type=float, default=60.0, help="Faktor percepatan (1×–240×)")
    parser.add_argument("--scenario",    default="normal",       choices=list(SCENARIOS.keys()))
    parser.add_argument("--seed",        type=int,   default=42,  help="Seed RNG (reprodusibel)")
    parser.add_argument("--api-url",     default="http://localhost:8000/api/v1")
    parser.add_argument("--api-token",   default="")
    parser.add_argument("--ttk-count",   type=int,   default=3)
    parser.add_argument("--pharmacist-count", type=int, default=3)
    parser.add_argument("--deterministic", action="store_true", help="Jalankan discrete event simulation (100% deterministik)")
    parser.add_argument("--max-hours",   type=float, default=None, help="Durasi maks (jam virtual)")
    parser.add_argument("--verbose",     action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cfg = SimulatorConfig(
        size=args.size,
        speed=args.speed,
        scenario=args.scenario,
        seed=args.seed,
        api_base_url=args.api_url,
        api_token=args.api_token,
        ttk_count=args.ttk_count,
        pharmacist_count=args.pharmacist_count,
        deterministic=args.deterministic,
        max_virtual_hours=args.max_hours,
        verbose=args.verbose,
    )
    run(cfg)


if __name__ == "__main__":
    main()
