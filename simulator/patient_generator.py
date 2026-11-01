"""
simulator/patient_generator.py
--------------------------------
Generator profil pasien dan data awal (seed).

Menghasilkan:
  - Profil pasien (encounter_id, ward, komorbid, obat, ML score, has_rule_finding)
  - Seed batch (backlog awal + riwayat selesai)
  - Ingest ke API via admit_encounter

Tidak ada LLM/Langflow per pasien (ADR-20).
Semua angka adalah asumsi — wajib dikalibrasi dengan RS.
"""
from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from simulator.config import (
    LAMBDA_BY_HOUR,
    TIER_INIT_DISTRIBUTION,
    WARD_LIST,
    WARD_WEIGHTS,
    P_HIGH_ALERT_MED,
    P_ALLERGY_HIDDEN,
    P_COMORBID_3PLUS,
    SimulatorConfig,
)


# ---------------------------------------------------------------------------
# Nama obat contoh (simulasi variasi nama dagang/generik)
# ---------------------------------------------------------------------------
_COMMON_DRUGS = [
    "Metformin 500mg", "Amlodipine 10mg", "Atorvastatin 20mg",
    "Omeprazole 20mg", "Furosemide 40mg", "Bisoprolol 5mg",
    "Warfarin 2mg", "Heparin 5000IU", "Digoxin 0.25mg",
    "Insulin Glargine 100IU/mL", "Clopidogrel 75mg", "Aspirin 100mg",
    "Simvastatin 20mg", "Captopril 25mg", "Lisinopril 10mg",
    "Spironolactone 25mg", "Losartan 50mg", "Metoprolol 50mg",
    "Ramipril 5mg", "Amiodarone 200mg", "Phenytoin 100mg",
    "Carbamazepine 200mg", "Valproic Acid 500mg", "Clonazepam 2mg",
    "Alprazolam 0.5mg", "Prednisolone 5mg", "Dexamethasone 4mg",
    "Ciprofloxacin 500mg", "Amoxicillin 500mg", "Ceftriaxone 1g",
]

_HIGH_ALERT_DRUGS = [
    "Warfarin 2mg", "Heparin 5000IU", "Insulin Glargine 100IU/mL",
    "Digoxin 0.25mg", "Amiodarone 200mg", "Phenytoin 100mg",
    "Methotrexate 2.5mg", "Lithium 300mg", "Potassium Chloride 7.5%",
]

_ALLERGIES = ["Penisilin", "Sulfonamida", "NSAID", "Aspirin", "Kodein", "Latex"]

_COMORBIDS = [
    "Diabetes Melitus Tipe 2", "Hipertensi", "Gagal Jantung Kongestif",
    "Penyakit Ginjal Kronis", "PPOK", "Stroke", "Kanker",
    "Hipotiroidisme", "Dislipidemia", "Atrial Fibrilasi",
    "Asma", "Osteoporosis", "Artritis Reumatoid",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _sample_ward(rng: random.Random) -> str:
    """Pilih bangsal berdasarkan distribusi asumsi."""
    return rng.choices(WARD_LIST, weights=WARD_WEIGHTS, k=1)[0]


def _sample_med_count(rng: random.Random) -> int:
    """Jumlah obat rutin acak (distribusi asumsi)."""
    cat = rng.choices(
        ["1-3", "4-6", "7-10", "11+"],
        weights=[0.25, 0.35, 0.25, 0.15],
        k=1
    )[0]
    ranges = {"1-3": (1, 3), "4-6": (4, 6), "7-10": (7, 10), "11+": (11, 16)}
    lo, hi = ranges[cat]
    return rng.randint(lo, hi)


def _compute_ml_score(
    med_count: int,
    has_comorbid_3plus: bool,
    has_high_alert: bool,
    has_allergy_hidden: bool,
    rng: random.Random,
) -> float:
    """
    Hitung skor ML pseudo-realistis.

    Faktor risiko → skor lebih tinggi.
    Ini adalah model sederhana untuk simulator — bukan model ML sesungguhnya.
    Di produksi, nilai ini berasal dari model XGBoost Fase A.

    Skor: 0.0–1.0 (dinormalisasi).
    """
    base = 0.3
    if med_count >= 7:
        base += 0.2
    if med_count >= 11:
        base += 0.1
    if has_comorbid_3plus:
        base += 0.15
    if has_high_alert:
        base += 0.20
    if has_allergy_hidden:
        base += 0.10
    # Noise agar distribusi lebih realistis
    noise = rng.gauss(0, 0.05)
    return round(max(0.05, min(0.98, base + noise)), 3)


def _has_rule_finding(ml_score: float, has_high_alert: bool, rng: random.Random) -> bool:
    """
    Apakah ada temuan aturan klinis (trigger HIGH RULE)?

    Untuk simulator, probabilitas berdasarkan faktor risiko.
    Di produksi, ini dievaluasi oleh discrepancy_engine.
    """
    p = 0.03  # 3% baseline
    if ml_score > 0.7:
        p += 0.10
    if has_high_alert:
        p += 0.08
    return rng.random() < p


# ---------------------------------------------------------------------------
# Generate satu profil pasien
# ---------------------------------------------------------------------------

def generate_patient_profile(
    rng: random.Random,
    admitted_at: Optional[datetime] = None,
    ward: Optional[str] = None,
    encounter_id: Optional[str] = None,
    cfg: Optional[SimulatorConfig] = None,
) -> Dict[str, Any]:
    """
    Buat profil pasien simulasi satu encounter.

    Returns dict yang bisa langsung dipakai untuk POST /queue/admit.
    CATATAN: Data simulasi — asumsi, belum dikalibrasi dengan RS.
    """
    enc_id     = encounter_id or str(uuid.UUID(int=rng.getrandbits(128), version=4))
    ward_name  = ward or _sample_ward(rng)
    admit_dt   = admitted_at or _now_utc()
    med_count  = _sample_med_count(rng)

    # Faktor risiko
    has_comorbid_3plus = rng.random() < P_COMORBID_3PLUS
    has_high_alert     = rng.random() < P_HIGH_ALERT_MED
    has_allergy_hidden = rng.random() < P_ALLERGY_HIDDEN

    # Obat
    all_drugs  = list(_COMMON_DRUGS)
    rng.shuffle(all_drugs)
    drug_list  = all_drugs[:min(med_count, len(all_drugs))]
    if has_high_alert and _HIGH_ALERT_DRUGS:
        drug_list.append(rng.choice(_HIGH_ALERT_DRUGS))

    # Komorbid
    n_comorbid = rng.randint(3, 6) if has_comorbid_3plus else rng.randint(0, 2)
    comorbids  = rng.sample(_COMORBIDS, min(n_comorbid, len(_COMORBIDS)))

    # Alergi
    allergies: List[str] = []
    if rng.random() < 0.3:
        allergies = rng.sample(_ALLERGIES, rng.randint(1, 2))

    # ML score
    base_ml = _compute_ml_score(
        med_count, has_comorbid_3plus, has_high_alert, has_allergy_hidden, rng
    )
    ml_score = cfg.effective_ml_score(base_ml) if cfg else base_ml

    # Rule finding
    has_rule = _has_rule_finding(ml_score, has_high_alert, rng)

    # Usia (condong lansia Penyakit Dalam)
    if ward_name in ("PENYAKIT_DALAM", "JANTUNG", "SARAF"):
        age = int(rng.gauss(68, 12))
    elif ward_name == "ANAK":
        age = int(rng.gauss(8, 5))
    else:
        age = int(rng.gauss(52, 15))
    age = max(1, min(100, age))

    return {
        "encounter_id":    enc_id,
        "ward":            ward_name,
        "admitted_at":     _iso(admit_dt),
        "ml_score":        ml_score,
        "has_rule_finding": has_rule,
        # Metadata tambahan (untuk log/UI — tidak masuk ke queue_service langsung)
        "_profile": {
            "age":             age,
            "med_count":       med_count,
            "drug_list":       drug_list,
            "comorbids":       comorbids,
            "allergies":       allergies,
            "has_high_alert":  has_high_alert,
            "has_allergy_hidden": has_allergy_hidden,
            "base_ml_score":   base_ml,
            "data_note": "Data simulasi — asumsi, belum dikalibrasi dengan RS",
        },
    }


# ---------------------------------------------------------------------------
# Generator kedatangan (Poisson tak homogen)
# ---------------------------------------------------------------------------

def sample_interarrival_seconds(
    virtual_hour: int,
    cfg: SimulatorConfig,
    rng: random.Random,
) -> float:
    """
    Sampel waktu antar-kedatangan (detik virtual) menggunakan distribusi Eksponensial.

    λ(jam) = laju per jam sesuai jam-virtual dan skenario.
    Waktu antar-kedatangan ~ Exp(1/λ) dalam menit.
    Returns: detik virtual.
    """
    lam = cfg.effective_lambda(virtual_hour)
    if lam <= 0:
        return 3600.0  # 1 jam virtual jika tidak ada kedatangan
    mean_minutes = 60.0 / lam
    inter_arrival_min = rng.expovariate(1.0 / mean_minutes)
    return inter_arrival_min * 60.0  # konversi ke detik virtual


# ---------------------------------------------------------------------------
# Generate seed batch (backlog awal)
# ---------------------------------------------------------------------------

def generate_seed_batch(
    cfg: SimulatorConfig,
    rng: random.Random,
    now: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Hasilkan data awal (seed) sesuai ukuran.

    Returns:
      (open_patients, history_patients)
      open_patients: backlog awal yang akan di-admit ke API
      history_patients: riwayat selesai (untuk statistik baseline)

    CATATAN: Data simulasi — asumsi, belum dikalibrasi dengan RS.
    """
    seed_size = cfg.seed_size
    base_now  = now or _now_utc()

    open_patients = []
    history_patients = []

    # --- Backlog awal (open entries) ---
    # Tersebar mundur 0–96 jam dari sekarang (asumsi backlog ±4 hari)
    for i in range(seed_size.open_entries):
        hours_ago = rng.uniform(0.5, 96.0)
        admitted  = base_now - timedelta(hours=hours_ago)
        profile   = generate_patient_profile(rng, admitted_at=admitted, cfg=cfg)
        open_patients.append(profile)

    # --- Riwayat selesai ---
    # Tersebar mundur 4–30 hari dari sekarang
    for i in range(seed_size.history_entries):
        hours_ago = rng.uniform(4 * 24, 30 * 24)
        admitted  = base_now - timedelta(hours=hours_ago)
        profile   = generate_patient_profile(rng, admitted_at=admitted, cfg=cfg)
        profile["_history_status"] = rng.choice(
            ["COMPLETE", "COMPLETE", "COMPLETE", "MISSED_RECONCILIATION"]
        )
        history_patients.append(profile)

    return open_patients, history_patients


# ---------------------------------------------------------------------------
# Discharge timing
# ---------------------------------------------------------------------------

def sample_discharge_time(
    admitted_at: datetime,
    ward: str,
    rng: random.Random,
) -> datetime:
    """
    Sampel waktu rencana pulang berdasarkan ALOS per bangsal (asumsi).

    WAJIB DIKALIBRASI dengan data RS mitra.
    """
    alos_hours_by_ward = {
        "IGD":            8.0,   # IGD sering cepat atau masuk rawat inap
        "ICU":            120.0, # ICU rata-rata 5 hari
        "PENYAKIT_DALAM": 96.0,  # 4 hari
        "BEDAH":          72.0,  # 3 hari
        "JANTUNG":        120.0, # 5 hari
        "SARAF":          144.0, # 6 hari
        "ANAK":           72.0,
        "KEBIDANAN":      48.0,  # 2 hari post-partum
        "ONKOLOGI":       120.0,
        "ORTOPEDI":       96.0,
    }
    median_hours = alos_hours_by_ward.get(ward, 96.0)
    # Log-normal agar ada ekor panjang (pasien yang tinggal lebih lama)
    sigma_log = 0.4
    actual_hours = rng.lognormvariate(math.log(median_hours), sigma_log)
    actual_hours = max(4.0, min(720.0, actual_hours))  # 4 jam – 30 hari
    return admitted_at + timedelta(hours=actual_hours)
