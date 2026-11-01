"""
simulator/config.py
--------------------
Konfigurasi Hospital Simulator.

Parameter berdasarkan asumsi awal — wajib dikalibrasi dengan data RS mitra.
Lihat §9.2 PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md untuk justifikasi angka.

Label wajib: "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Laju kedatangan λ per jam (Poisson tak homogen)
# 24 nilai: λ[0] = jam 00:00-01:00, λ[6] = jam 06:00-07:00, dst.
# Satuan: pasien/jam (asumsi RS 500 tempat tidur, BOR 75%, ALOS 5 hari ≈ 75/hari)
# Puncak sore-malam (17-22) dan Senin pagi — dilebihkan untuk efek demo.
# WAJIB DIKALIBRASI dengan data RS mitra.
# ---------------------------------------------------------------------------
LAMBDA_BY_HOUR: List[float] = [
    0.5,  # 00  — tengah malam, rendah
    0.3,  # 01
    0.2,  # 02
    0.2,  # 03
    0.3,  # 04
    0.5,  # 05  — mulai naik (serah terima)
    1.5,  # 06  — masuk pagi, serah terima shift
    3.5,  # 07  — puncak pagi, pasien dari IGD malam
    4.0,  # 08  — puncak admisi ruang
    3.5,  # 09
    3.0,  # 10
    2.5,  # 11
    2.0,  # 12  — siang, agak sepi
    2.0,  # 13
    2.5,  # 14
    3.0,  # 15
    4.0,  # 16  — puncak sore, IGD mulai ramai
    4.5,  # 17
    5.0,  # 18  — puncak sore-malam (Lonjakan IGD)
    4.5,  # 19
    4.0,  # 20
    3.5,  # 21
    2.0,  # 22
    0.8,  # 23
]

# ---------------------------------------------------------------------------
# Bangsal rumah sakit
# ---------------------------------------------------------------------------
WARD_LIST: List[str] = [
    "IGD",
    "ICU",
    "PENYAKIT_DALAM",
    "BEDAH",
    "JANTUNG",
    "SARAF",
    "ANAK",
    "KEBIDANAN",
    "ONKOLOGI",
    "ORTOPEDI",
]

# Distribusi bangsal masuk (proporsional — asumsi)
WARD_WEIGHTS: List[float] = [
    0.18,  # IGD
    0.08,  # ICU
    0.25,  # PENYAKIT_DALAM
    0.15,  # BEDAH
    0.08,  # JANTUNG
    0.06,  # SARAF
    0.07,  # ANAK
    0.05,  # KEBIDANAN
    0.04,  # ONKOLOGI
    0.04,  # ORTOPEDI
]

# ---------------------------------------------------------------------------
# Profil pasien (asumsi awal — dikalibrasi RS)
# ---------------------------------------------------------------------------
# P(obat rutin > 5) → ML score tinggi
P_HIGH_ALERT_MED:   float = 0.12  # 12% obat dengan potensi tinggi
P_ALLERGY_HIDDEN:   float = 0.08  # 8% alergi tidak tercatat di anamnesa awal
P_COMORBID_3PLUS:   float = 0.35  # 35% pasien dengan ≥3 komorbid

# Distribusi jumlah obat rutin
MED_COUNT_DISTRIBUTION = {
    "1-3":  0.25,
    "4-6":  0.35,
    "7-10": 0.25,
    "11+":  0.15,
}

# ---------------------------------------------------------------------------
# Distribusi tier awal (ML + rules — asumsi, untuk dikalibrasi)
# ---------------------------------------------------------------------------
TIER_INIT_DISTRIBUTION = {
    "HIGH_RULE":   0.05,  # 5% ada temuan aturan klinis langsung
    "HIGH_ML":     0.15,  # 15% skor ML tinggi tanpa rule finding
    "MEDIUM":      0.45,  # 45%
    "LOW":         0.35,  # 35%
}

# ---------------------------------------------------------------------------
# Waktu BPMH per TTK (menit, lognormal)
# ---------------------------------------------------------------------------
BPMH_DURATION_MEDIAN_MIN:  float = 45.0   # median ±45 menit (asumsi)
BPMH_DURATION_SIGMA_LOG:   float = 0.4    # σ log-normal
P_BPMH_INCOMPLETE:         float = 0.15   # 15% BPMH tidak lengkap pertama kali
P_BPMH_DELAYED:            float = 0.20   # 20% TTK butuh waktu >60 mnt

# ---------------------------------------------------------------------------
# Waktu telaah apoteker (menit, lognormal) per tier
# ---------------------------------------------------------------------------
REVIEW_DURATION_BY_TIER = {
    "HIGH":   {"median": 30.0, "sigma_log": 0.35},
    "MEDIUM": {"median": 20.0, "sigma_log": 0.30},
    "LOW":    {"median": 8.0,  "sigma_log": 0.50},
}

# Probabilitas apoteker meninggalkan klaim (lease test)
P_PHARMACIST_ABANDON_CLAIM: float = 0.05  # 5%

# ---------------------------------------------------------------------------
# Probabilitas event dinamis per pasien per jam-virtual
# (asumsi awal — wajib dikalibrasi)
# ---------------------------------------------------------------------------
P_TRANSFER_PER_HOUR:          float = 0.03 / 24  # ±3%/admisi = ±0.125%/jam
P_CRITICAL_LAB_PER_HOUR:      float = 0.02 / 24
P_DISCHARGE_BEFORE_REVIEW:    float = 0.05 / 24  # ±5%/admisi
P_CANCEL_ADMISSION:           float = 0.01 / 24
P_DPJP_DELAY:                 float = 0.08 / 24

# Transfer tujuan (sumber → tujuan)
TRANSFER_ROUTES = {
    "IGD":            ["ICU", "PENYAKIT_DALAM", "BEDAH", "JANTUNG"],
    "ICU":            ["PENYAKIT_DALAM", "BEDAH", "JANTUNG"],
    "PENYAKIT_DALAM": ["ICU", "BEDAH"],
    "BEDAH":          ["ICU", "PENYAKIT_DALAM"],
    "JANTUNG":        ["ICU", "PENYAKIT_DALAM"],
    "SARAF":          ["ICU", "PENYAKIT_DALAM"],
}

# ---------------------------------------------------------------------------
# Ukuran seed (§9.2)
# ---------------------------------------------------------------------------

@dataclass
class SeedSize:
    name: str
    open_entries: int       # Entri terbuka awal (backlog)
    history_entries: int    # Riwayat selesai awal
    pharmacists_per_day: int
    pharmacists_per_shift: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.pharmacists_per_shift:
            p = self.pharmacists_per_day
            self.pharmacists_per_shift = {
                "pagi":  max(1, p // 2),
                "siang": max(1, p // 3),
                "malam": max(0, p - p // 2 - p // 3),
            }


SEED_SIZES: Dict[str, SeedSize] = {
    "S": SeedSize("S", open_entries=80,   history_entries=400,   pharmacists_per_day=3),
    "M": SeedSize("M", open_entries=300,  history_entries=4000,  pharmacists_per_day=6),
    "L": SeedSize("L", open_entries=2000, history_entries=20000, pharmacists_per_day=12),
    "XL": SeedSize("XL", open_entries=5000, history_entries=50000, pharmacists_per_day=20),
}

# ---------------------------------------------------------------------------
# Skenario
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    name: str
    description: str
    lambda_multiplier: float = 1.0        # Pengali laju kedatangan
    pharmacist_multiplier: float = 1.0    # Pengali kapasitas apoteker
    p_critical_lab_multiplier: float = 1.0
    ml_failure: bool = False              # ML mati → default ML score 0.5
    langflow_failure: bool = False        # Langflow mati (tidak mempengaruhi antrean)
    duration_virtual_hours: Optional[float] = None  # Durasi skenario dalam jam-virtual


SCENARIOS: Dict[str, Scenario] = {
    "normal": Scenario(
        name="normal",
        description="Operasi normal hari kerja biasa",
    ),
    "evening_surge": Scenario(
        name="evening_surge",
        description="Lonjakan IGD sore–malam (kedatangan ×1.8)",
        lambda_multiplier=1.8,
        p_critical_lab_multiplier=1.5,
    ),
    "staff_shortage": Scenario(
        name="staff_shortage",
        description="Kekurangan staf (kapasitas apoteker −40%)",
        pharmacist_multiplier=0.6,
    ),
    "seasonal_flu": Scenario(
        name="seasonal_flu",
        description="Flu musiman — kedatangan ×2 selama 8 jam virtual",
        lambda_multiplier=2.0,
        duration_virtual_hours=8.0,
    ),
    "ml_failure": Scenario(
        name="ml_failure",
        description="Model ML mati — skor default 0.5, aturan klinis tetap berlaku",
        ml_failure=True,
    ),
    "langflow_failure": Scenario(
        name="langflow_failure",
        description="Langflow mati — antrean tetap bergerak (jalur deterministik)",
        langflow_failure=True,
    ),
    "mass_casualty": Scenario(
        name="mass_casualty",
        description="Bencana/mass casualty — kedatangan ×3, lab kritis ×3",
        lambda_multiplier=3.0,
        p_critical_lab_multiplier=3.0,
    ),
}

# ---------------------------------------------------------------------------
# Konfigurasi runtime simulator
# ---------------------------------------------------------------------------

@dataclass
class SimulatorConfig:
    """Konfigurasi lengkap satu sesi simulator."""

    size:           str   = "M"
    speed:          float = 60.0      # Kecepatan virtual: 60× → 1 jam RS = 1 menit real
    scenario:       str   = "normal"
    seed:           int   = 42
    api_base_url:   str   = "http://localhost:8000/api/v1"
    api_token:      str   = ""        # JWT token
    tick_interval_s: float = 1.0     # Interval tick real (detik)
    max_virtual_hours: Optional[float] = None  # None = jalan terus
    ttk_count:      int   = 3         # Jumlah agen TTK
    pharmacist_count: int = 3         # Jumlah agen apoteker
    deterministic:   bool = False     # Mode kejadian diskrit (100% deterministik antar-run)
    verbose:        bool  = False

    @property
    def seed_size(self) -> SeedSize:
        return SEED_SIZES.get(self.size, SEED_SIZES["M"])

    @property
    def scenario_obj(self) -> Scenario:
        return SCENARIOS.get(self.scenario, SCENARIOS["normal"])

    def effective_lambda(self, hour_of_day: int) -> float:
        """Laju kedatangan efektif (pasien/jam), disesuaikan skenario."""
        base = LAMBDA_BY_HOUR[hour_of_day % 24]
        return base * self.scenario_obj.lambda_multiplier

    def effective_ml_score(self, base_score: float) -> float:
        """ML score efektif — default jika ML mati."""
        if self.scenario_obj.ml_failure:
            return 0.5
        return base_score

    @classmethod
    def from_env(cls) -> "SimulatorConfig":
        return cls(
            size=os.getenv("SIM_SIZE", "M"),
            speed=float(os.getenv("SIM_SPEED", "60")),
            scenario=os.getenv("SIM_SCENARIO", "normal"),
            seed=int(os.getenv("SIM_SEED", "42")),
            api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000/api/v1"),
            api_token=os.getenv("SIM_API_TOKEN", ""),
        )
