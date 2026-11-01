"""
priomedrec_core/queue_config.py
---------------------------------
Konfigurasi berversi untuk mesin antrean.

ADR-19: bobot skor, kuota HIGH-ML, SLA, lease sebagai konfigurasi — bukan hardcode.
D1    : bobot §4.1 QUEUE_PLAN sebagai titik awal; dikalibrasi via simulator Q-007.

Cara memakai:
    from priomedrec_core.queue_config import QueueConfig, DEFAULT_CONFIG
    cfg = DEFAULT_CONFIG
    # atau dari dict/JSON:
    cfg = QueueConfig.from_dict({"version": "queue-0.2.0", "ml_high_quota_pct": 0.30})
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SlaThreshold:
    """SLA per tier (jam)."""
    target_hours: float
    warning_hours: float
    escalate_to: str | None = None  # tier tujuan saat breach


@dataclass
class QueueConfig:
    """
    Konfigurasi berversi mesin antrean.

    Semua bobot dan kuota adalah titik awal DRAFT (AQ-02, AQ-03 di ASSUMPTIONS.md).
    Wajib dikalibrasi via simulator Q-007 sebelum pilot klinis.
    """
    version: str = "queue-0.1.0"

    # --- Bobot skor komposit (§4.1 QUEUE_PLAN) ---
    # priority_score = 100 × (w_sla·sla_pressure + w_ml·ml_pct + w_sev·severity
    #                        + w_dis·discharge + w_wait·wait_norm)
    w_sla_pressure:      float = 0.40
    w_ml_percentile:     float = 0.25
    w_severity_load:     float = 0.15
    w_discharge_pressure: float = 0.10
    w_wait_norm:         float = 0.10

    # --- Kuota HIGH-ML per bangsal (ADR-21) ---
    # Entri HIGH hanya karena ML dibatasi ≤ kuota ini.
    # HIGH karena RULE/SLA tidak dikuota.
    ml_high_quota_pct: float = 0.25

    # --- Histeresis (§4.3 QUEUE_PLAN) ---
    # Perubahan tier ML hanya berlaku jika selisih skor > margin ini
    tier_hysteresis_margin: float = 0.05

    # --- Lease klaim (ADR-19) ---
    claim_ttl_seconds: int = 900  # 15 menit

    # --- SLA default (D4 QUEUE_PLAN; DRAFT — wajib validasi apoteker CRQ-080) ---
    sla: Dict[str, SlaThreshold] = field(default_factory=lambda: {
        "HIGH":   SlaThreshold(target_hours=4.0,  warning_hours=2.0,  escalate_to=None),
        "MEDIUM": SlaThreshold(target_hours=12.0, warning_hours=6.0,  escalate_to="HIGH"),
        "LOW":    SlaThreshold(target_hours=24.0, warning_hours=12.0, escalate_to="MEDIUM"),
    })

    # --- Menit telaah per tier (untuk kapasitas — DRAFT CRQ-092) ---
    review_minutes: Dict[str, float] = field(default_factory=lambda: {
        "HIGH": 30.0, "MEDIUM": 20.0, "LOW": 8.0,
    })

    def __post_init__(self):
        total = (self.w_sla_pressure + self.w_ml_percentile +
                 self.w_severity_load + self.w_discharge_pressure +
                 self.w_wait_norm)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Bobot skor harus berjumlah 1.0, dapat: {total:.4f} "
                f"(version={self.version})"
            )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QueueConfig":
        """Buat dari dict (mis. dari DB atau JSON konfigurasi)."""
        sla_raw = d.pop("sla", None)
        cfg = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        if sla_raw:
            cfg.sla = {
                tier: SlaThreshold(**vals) if isinstance(vals, dict) else vals
                for tier, vals in sla_raw.items()
            }
        return cfg


# Konfigurasi default — dipakai oleh queue_engine dan tests
DEFAULT_CONFIG = QueueConfig()
