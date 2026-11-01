"""
api/services/simulation_service.py
------------------------------------
CSV replay simulation engine — "setiap baris CSV = satu pasien baru masuk".

Alur per pasien (satu tick APScheduler):
  1. Ambil satu baris dari `data/processed/model_ready.csv` secara berurutan.
  2. Hitung fitur model (10 fitur leakage-safe dari metadata model).
  3. Prediksi XGBoost asli (`backend/models/priomed_prioritization_model.pkl`).
  4. Jalankan rule engine diskrepansi asli (`src.rules.discrepancy_engine`)
     dengan data obat dari `data/processed/synthetic_cases.csv`.
  5. Gabungkan ML + aturan + SLA (`priority_service.compute_priority`).
  6. Tulis ke antrean nyata (`queue_entries`, `queue_events`, `encounters`).
  7. Setelah 1–2 tick, BPMH selesai → pasien pindah ke Antrean B (REVIEW).
  8. Setiap tick juga mengecek SLA dan menaikkan tier bila jatuh tempo.

Hasilnya langsung terlihat di dashboard melalui SSE yang sudah ada.

Catatan keselamatan:
  - `ml_score` adalah estimasi model, BUKAN probabilitas klinis.
  - Semua temuan aturan wajib diverifikasi apoteker (`verification_required`).
  - Tier hanya boleh naik (ADR-21); simulasi tidak pernah menurunkan tier.

Label wajib: "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from priomedrec_core.queue_config import DEFAULT_CONFIG, QueueConfig, SlaThreshold
from priomedrec_core.queue_engine import (
    TIER_FROM_RANK,
    compute_queue_score,
    determine_next_due_at,
)
from priomedrec_core.queue_transitions import bpmh_submit as _bpmh_transition

logger = logging.getLogger("priomed.simulation")

# ---------------------------------------------------------------------------
# Path & konstanta
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "backend" / "models"
CONFIG_DIR = PROJECT_ROOT / "configs"

DEFAULT_DATASET = DATA_DIR / "model_ready.csv"
DEFAULT_CASES = DATA_DIR / "synthetic_cases.csv"
RULES_CONFIG = CONFIG_DIR / "discrepancy_rules.json"
DRUG_CLASS_MAP = CONFIG_DIR / "drug_class_map.json"
HIGH_ALERT_CONFIG = CONFIG_DIR / "high_alert_medications.json"

MODEL_FEATURES: Tuple[str, ...] = (
    "age",
    "age_65_plus",
    "gender_encoded",
    "polypharmacy_flag",
    "high_alert_flag",
    "high_alert_count",
    "active_condition_count",
    "prior_encounter_count",
    "allergy_count",
    "has_drug_allergy",
)

DEFAULT_WARDS: Tuple[str, ...] = (
    "ICU",
    "INTERNA",
    "BEDAH",
    "JANTUNG",
    "PARU",
    "SARAF",
)

SIMULATED_LABEL = (
    "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"
)

TIER_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


# ---------------------------------------------------------------------------
# Util
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _norm_class(value: Optional[str]) -> str:
    """Normalisasi nama kelas: lowercase, tanpa spasi, tanpa 's' di akhir."""
    if not value:
        return ""
    text = str(value).strip().lower().replace(" ", "_")
    if text.endswith("s"):
        text = text[:-1]
    return text


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if result != result:  # NaN
            return default
        return result
    except (TypeError, ValueError):
        return default


def _synthetic_name(patient_id: str) -> str:
    """Nama inisial sintetis (privacy) — deterministik dari patient_id."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"priomed-name:{patient_id}").int
    return f"{alphabet[digest % 26]}{alphabet[(digest // 26) % 26]}."


# ---------------------------------------------------------------------------
# Konfigurasi SLA yang dipercepat untuk demo
# ---------------------------------------------------------------------------

def scaled_queue_config(sla_scale: float = 1.0) -> QueueConfig:
    """
    Salin DEFAULT_CONFIG dengan ambang SLA dikalikan `sla_scale`.

    `sla_scale=1.0` → perilaku produksi (HIGH warning 2 jam, dst).
    `sla_scale=0.0025` → 1 jam SLA menjadi 9 detik; berguna agar eskalasi
    terlihat dalam demo beberapa menit tanpa mengubah data historis.
    """
    scale = max(0.0001, min(float(sla_scale or 1.0), 1.0))
    cfg = QueueConfig(
        version=f"{DEFAULT_CONFIG.version}-sim{scale:g}",
        w_sla_pressure=DEFAULT_CONFIG.w_sla_pressure,
        w_ml_percentile=DEFAULT_CONFIG.w_ml_percentile,
        w_severity_load=DEFAULT_CONFIG.w_severity_load,
        w_discharge_pressure=DEFAULT_CONFIG.w_discharge_pressure,
        w_wait_norm=DEFAULT_CONFIG.w_wait_norm,
        ml_high_quota_pct=DEFAULT_CONFIG.ml_high_quota_pct,
        tier_hysteresis_margin=DEFAULT_CONFIG.tier_hysteresis_margin,
        claim_ttl_seconds=DEFAULT_CONFIG.claim_ttl_seconds,
        review_minutes=dict(DEFAULT_CONFIG.review_minutes),
    )
    cfg.sla = {
        tier: SlaThreshold(
            target_hours=max(0.0001, t.target_hours * scale),
            warning_hours=max(0.0001, t.warning_hours * scale),
            escalate_to=t.escalate_to,
        )
        for tier, t in DEFAULT_CONFIG.sla.items()
    }
    return cfg


def _sla_config_dict(cfg: QueueConfig) -> Dict[str, Dict[str, float]]:
    return {
        tier: {"target_hours": t.target_hours, "warning_hours": t.warning_hours}
        for tier, t in cfg.sla.items()
    }


# ---------------------------------------------------------------------------
# Cache artefak model & konfigurasi aturan
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _model_bundle():
    """Muat model XGBoost + threshold + metadata sekali saja (absolute path)."""
    from src.models.predict import load_metadata, load_model, load_thresholds

    model = load_model(str(MODEL_DIR / "priomed_prioritization_model.pkl"))
    thresholds = load_thresholds(str(MODEL_DIR / "thresholds.json"))
    metadata = load_metadata(str(MODEL_DIR / "metadata.json"))
    logger.info(
        "[simulation] Model dimuat: %s (%s)",
        metadata.get("model_name"),
        metadata.get("model_version"),
    )
    return model, thresholds, metadata


@lru_cache(maxsize=1)
def _rule_config() -> Dict[str, Any]:
    with open(RULES_CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _drug_class_map() -> Dict[str, str]:
    try:
        with open(DRUG_CLASS_MAP, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _high_alert_keywords() -> Tuple[str, ...]:
    try:
        with open(HIGH_ALERT_CONFIG, encoding="utf-8") as fh:
            payload = json.load(fh)
        keywords: List[str] = []
        for med in payload.get("medications", []):
            for kw in med.get("rxnorm_keywords", []):
                if kw and kw not in keywords:
                    keywords.append(str(kw).lower())
        return tuple(keywords)
    except Exception:
        return (
            "warfarin", "heparin", "insulin", "methotrexate", "morphine",
            "oxycodone", "fentanyl", "lithium", "digoxin", "phenytoin",
            "amiodarone", "potassium chloride",
        )


# ---------------------------------------------------------------------------
# Dataset replay
# ---------------------------------------------------------------------------

@dataclass
class ReplayPatient:
    """Satu baris CSV yang siap di-replay."""

    encounter_id: str
    patient_id: str
    features: Dict[str, float]
    pre_medications: Tuple[str, ...]
    admission_medications: Tuple[str, ...]
    mutation_type: str
    has_discrepancy: int
    ward: str


class SimulationDataset:
    """
    Dataset replay: `model_ready.csv` + data obat dari `synthetic_cases.csv`.

    Untuk setiap encounter, data obat dipilih secara deterministik:
      - encounter dengan diskrepansi → kasus OMISSION (prioritas) / DUPLICATION
      - encounter tanpa diskrepansi → kasus NONE
    Kasus DUPLICATION direkonstruksi dengan menggandakan obat pada daftar
    admission agar rule duplikasi benar-benar menyala (bukan flag palsu).
    """

    def __init__(
        self,
        dataset_path: Optional[str | Path] = None,
        cases_path: Optional[str | Path] = None,
        limit: Optional[int] = None,
        ward_cycle: Iterable[str] = DEFAULT_WARDS,
    ):
        self.dataset_path = Path(dataset_path or DEFAULT_DATASET)
        self.cases_path = Path(cases_path or DEFAULT_CASES)
        self.limit = limit
        self.ward_cycle = tuple(ward_cycle) or DEFAULT_WARDS
        self.rows: List[ReplayPatient] = []
        self.loaded_at: Optional[str] = None
        self.load_seconds: float = 0.0

    # -- public ---------------------------------------------------------
    def load(self) -> "SimulationDataset":
        import time

        import pandas as pd

        start = time.perf_counter()
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset simulasi tidak ditemukan: {self.dataset_path}")

        usecols = ["encounter_id", "patient_id", "has_discrepancy", *MODEL_FEATURES]
        df = pd.read_csv(self.dataset_path, usecols=usecols)
        if self.limit:
            df = df.head(int(self.limit)).copy()

        rule_inputs = self._load_rule_inputs(df["encounter_id"].tolist(), pd)

        rows: List[ReplayPatient] = []
        for idx, row in enumerate(df.itertuples(index=False)):
            enc_id = str(getattr(row, "encounter_id"))
            patient_id = str(getattr(row, "patient_id"))
            pre, adm, mutation = rule_inputs.get(enc_id, ((), (), "NONE"))
            features = {
                name: _as_float(getattr(row, name, 0.0)) for name in MODEL_FEATURES
            }
            rows.append(
                ReplayPatient(
                    encounter_id=enc_id,
                    patient_id=patient_id,
                    features=features,
                    pre_medications=pre,
                    admission_medications=adm,
                    mutation_type=mutation,
                    has_discrepancy=int(_as_float(getattr(row, "has_discrepancy", 0))),
                    ward=self.ward_cycle[idx % len(self.ward_cycle)],
                )
            )

        self.rows = rows
        self.loaded_at = _utcnow().isoformat()
        self.load_seconds = round(time.perf_counter() - start, 3)
        logger.info(
            "[simulation] Dataset dimuat: %d pasien dari %s (%.2fs)",
            len(rows), self.dataset_path.name, self.load_seconds,
        )
        return self

    def __len__(self) -> int:
        return len(self.rows)

    # -- private --------------------------------------------------------
    def _load_rule_inputs(
        self, encounter_ids: List[str], pd
    ) -> Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...], str]]:
        if not self.cases_path.exists():
            logger.warning("[simulation] File kasus tidak ditemukan: %s", self.cases_path)
            return {}

        wanted = set(encounter_ids)
        cases = pd.read_csv(
            self.cases_path,
            usecols=[
                "encounter_id",
                "baseline_medications",
                "admission_medications",
                "mutation_type",
            ],
        )
        cases = cases[cases["encounter_id"].isin(wanted)]
        if cases.empty:
            return {}

        # Pilih satu kasus per encounter secara deterministik tanpa loop groupby
        # (31k+ grup membuat load lambat). Prioritas: OMISSION > DUPLICATION >
        # NONE > lainnya.
        preference = {"OMISSION": 0, "DUPLICATION": 1, "NONE": 2}
        cases = cases.assign(
            _pref=cases["mutation_type"].map(preference).fillna(3)
        ).sort_values(["encounter_id", "_pref"], kind="mergesort")
        chosen = cases.drop_duplicates("encounter_id", keep="first")

        result: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...], str]] = {}
        for row in chosen.itertuples(index=False):
            mutation = str(row.mutation_type)
            pre = self._parse_medications(row.baseline_medications, pd)
            adm = self._parse_medications(row.admission_medications, pd)
            if mutation == "DUPLICATION" and adm:
                # Rekonstruksi duplikasi agar rule engine benar-benar menyala.
                adm = adm + adm
            result[str(row.encounter_id)] = (pre, adm, mutation)
        return result

    @staticmethod
    def _parse_medications(value: Any, pd) -> Tuple[str, ...]:
        if value is None or (isinstance(value, float) and value != value):
            return ()
        try:
            if pd.isna(value):
                return ()
        except Exception:
            pass
        return tuple(
            part.strip()
            for part in str(value).split(";")
            if part and part.strip()
        )


# ---------------------------------------------------------------------------
# Rule engine helpers
# ---------------------------------------------------------------------------

def _medication_frame(names: Tuple[str, ...], pd):
    columns = ["medication_code", "medication_name", "status", "dose_value"]
    return pd.DataFrame(
        [
            {
                "medication_code": None,
                "medication_name": name,
                "status": "active",
                "dose_value": None,
            }
            for name in names
        ],
        columns=columns,
    )


def _classify_flag(flag: Dict[str, Any]) -> Tuple[int, bool]:
    """
    Tentukan severity_tier (1/2/3) dan is_high_alert untuk satu flag aturan.

    Sumber:
      - daftar high-alert (`configs/high_alert_medications.json`)
      - peta kelas obat (`configs/drug_class_map.json`)
      - daftar kelas tier-1/2/3 (`configs/discrepancy_rules.json`)
    """
    from src.rules.medication_normalizer import normalize_name

    name = normalize_name(str(flag.get("medication_name") or ""))
    if name and any(kw in name for kw in _high_alert_keywords()):
        return 1, True

    class_map = _drug_class_map()
    drug_class = class_map.get(name)
    if not drug_class and name:
        drug_class = class_map.get(name.split(" ")[0], "")
    drug_class_norm = _norm_class(drug_class)

    omission_cfg = (
        _rule_config().get("rules", {}).get("omission", {}).get("severity_by_class", {})
    )
    for tier_key, severity in (
        ("tier_1_classes", 1),
        ("tier_2_classes", 2),
        ("tier_3_classes", 3),
    ):
        classes = {_norm_class(c) for c in omission_cfg.get(tier_key, [])}
        if drug_class_norm and drug_class_norm in classes:
            return severity, severity == 1

    return 2, False


def _run_rules(patient: ReplayPatient) -> List[Dict[str, Any]]:
    """Jalankan rule engine asli dan kembalikan flag mentah."""
    import pandas as pd

    from src.rules.discrepancy_engine import run_all_rules

    pre = _medication_frame(patient.pre_medications, pd)
    adm = _medication_frame(patient.admission_medications, pd)
    output = run_all_rules(
        patient_id=patient.patient_id,
        encounter_id=patient.encounter_id,
        pre_meds=pre,
        adm_meds=adm,
        config_path=str(RULES_CONFIG),
    )
    return list(output.get("flags", []))


def _priority_for(patient: ReplayPatient, ml_score: float, cfg: QueueConfig) -> Dict[str, Any]:
    """Gabungkan XGBoost + rule engine menjadi tier & alasan prioritas."""
    from api.services.priority_service import compute_priority

    flags = _run_rules(patient)
    discrepancies: List[Dict[str, Any]] = []
    high_alert = False
    counts = {"tier1": 0, "tier2": 0, "tier3": 0}
    for flag in flags:
        severity, is_high_alert = _classify_flag(flag)
        counts[f"tier{severity}"] = counts.get(f"tier{severity}", 0) + 1
        high_alert = high_alert or is_high_alert
        discrepancies.append(
            {
                "rule_type": flag.get("flag_type", "RULE"),
                "drug_name": flag.get("medication_name", ""),
                "severity_tier": severity,
                "is_high_alert": is_high_alert,
            }
        )

    priority = compute_priority(
        ml_score=ml_score,
        discrepancies=discrepancies,
        sla_hours_elapsed=0.0,
        sla_config=_sla_config_dict(cfg),
    )
    priority["flags"] = flags
    priority["discrepancy_counts"] = counts
    priority["has_high_alert"] = high_alert
    priority["has_rule_finding"] = bool(flags)
    return priority


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class _PendingBpmh:
    encounter_id: str
    due_tick: int
    ml_score: float
    priority: Dict[str, Any]
    ward: str


@dataclass
class SimulationStatus:
    running: bool = False
    finished: bool = False
    preparing: bool = False
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    interval_seconds: float = 6.0
    max_patients: int = 60
    sla_scale: float = 0.0025
    drain_ticks: int = 30
    drain_remaining: int = 0
    draining: bool = False
    dataset_path: str = str(DEFAULT_DATASET)
    dataset_rows: int = 0
    next_index: int = 0
    admitted: int = 0
    bpmh_completed: int = 0
    escalated: int = 0
    errors: int = 0
    tick_count: int = 0
    pending_bpmh: int = 0
    last_patient: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    model_version: Optional[str] = None
    label: str = SIMULATED_LABEL
    load_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "finished": self.finished,
            "preparing": self.preparing,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "interval_seconds": self.interval_seconds,
            "max_patients": self.max_patients,
            "sla_scale": self.sla_scale,
            "drain_ticks": self.drain_ticks,
            "drain_remaining": self.drain_remaining,
            "draining": self.draining,
            "dataset_path": self.dataset_path,
            "dataset_rows": self.dataset_rows,
            "next_index": self.next_index,
            "admitted": self.admitted,
            "bpmh_completed": self.bpmh_completed,
            "escalated": self.escalated,
            "errors": self.errors,
            "tick_count": self.tick_count,
            "pending_bpmh": self.pending_bpmh,
            "last_patient": self.last_patient,
            "last_error": self.last_error,
            "model_version": self.model_version,
            "label": self.label,
            "load_seconds": self.load_seconds,
        }


class SimulationEngine:
    """
    Replay CSV satu pasien per tick memakai APScheduler.

    Satu instance per proses (lihat `get_engine()`), tetapi konstruktor
    menerima `session_scope_factory` agar mudah diuji dengan DB temporer.
    """

    def __init__(self, session_scope_factory=None):
        self._session_scope_factory = session_scope_factory
        self._lock = threading.RLock()
        self._scheduler = None
        self._dataset: Optional[SimulationDataset] = None
        self._cfg: QueueConfig = scaled_queue_config(1.0)
        self._pending: List[_PendingBpmh] = []
        self._run_id: Optional[str] = None
        self._fresh_ids = True
        self._status = SimulationStatus()
        self._stop_requested = threading.Event()

    # -- dependencies ---------------------------------------------------
    def _session_scope(self):
        if self._session_scope_factory is not None:
            return self._session_scope_factory()
        from api.db.session import session_scope

        return session_scope()

    # -- public API -----------------------------------------------------
    def status(self) -> Dict[str, Any]:
        with self._lock:
            self._status.pending_bpmh = len(self._pending)
            return self._status.to_dict()

    def start(
        self,
        interval_seconds: float = 6.0,
        max_patients: int = 60,
        sla_scale: float = 0.0025,
        dataset_path: Optional[str] = None,
        cases_path: Optional[str] = None,
        fresh_ids: bool = True,
        limit: Optional[int] = None,
        drain_ticks: int = 30,
    ) -> Dict[str, Any]:
        """
        Mulai replay. Idempoten: bila sudah berjalan, kembalikan status saat ini.
        """
        with self._lock:
            if self._status.running:
                return self._status.to_dict()
            self._stop_scheduler_locked()

            interval = max(1.0, min(float(interval_seconds), 120.0))
            self._cfg = scaled_queue_config(sla_scale)
            self._fresh_ids = bool(fresh_ids)
            self._run_id = (
                _utcnow().strftime("%Y%m%d%H%M%S%f") if fresh_ids else None
            )
            self._pending = []
            self._dataset = None
            self._stop_requested.clear()
            self._status = SimulationStatus(
                running=True,
                finished=False,
                preparing=True,
                started_at=_utcnow().isoformat(),
                interval_seconds=interval,
                max_patients=int(max_patients),
                sla_scale=float(sla_scale),
                drain_ticks=max(0, int(drain_ticks)),
                drain_remaining=max(0, int(drain_ticks)),
                dataset_path=str(dataset_path or DEFAULT_DATASET),
            )

        # Muat dataset di thread terpisah agar endpoint start tetap responsif.
        loader = threading.Thread(
            target=self._prepare_and_run,
            args=(dataset_path, cases_path, limit, interval),
            name="simulation-loader",
            daemon=True,
        )
        loader.start()
        return self.status()

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._stop_requested.set()
            self._status.running = False
            self._status.draining = False
            self._status.stopped_at = _utcnow().isoformat()
            self._stop_scheduler_locked()
            return self._status.to_dict()

    def step(self, count: int = 1) -> Dict[str, Any]:
        """
        Jalankan satu (atau beberapa) langkah manual tanpa menjadwalkan tick.
        Berguna untuk demo "tambah 1 pasien" dan untuk pengujian.
        """
        if self._dataset is None:
            self._ensure_dataset_loaded()
        results = []
        for _ in range(max(1, int(count))):
            result = self._step_once()
            if result is None:
                break
            results.append(result)
        return {"stepped": len(results), "last": results[-1] if results else None, "status": self.status()}

    # -- preparation ----------------------------------------------------
    def _ensure_dataset_loaded(self) -> None:
        if self._dataset is not None:
            return
        dataset = SimulationDataset()
        dataset.load()
        self._dataset = dataset
        try:
            _, _, metadata = _model_bundle()
            self._status.model_version = metadata.get("model_version")
        except Exception as exc:  # pragma: no cover - model harus ada
            logger.exception("[simulation] Gagal memuat model: %s", exc)
            raise
        self._status.dataset_rows = len(dataset)
        self._status.load_seconds = dataset.load_seconds

    def _prepare_and_run(
        self,
        dataset_path: Optional[str],
        cases_path: Optional[str],
        limit: Optional[int],
        interval: float,
    ) -> None:
        try:
            dataset = SimulationDataset(
                dataset_path=dataset_path,
                cases_path=cases_path,
                limit=limit,
            ).load()
            with self._lock:
                self._dataset = dataset
                self._status.dataset_rows = len(dataset)
                self._status.load_seconds = dataset.load_seconds
                self._status.preparing = False
                if self._status.running:
                    self._status.started_at = _utcnow().isoformat()
            try:
                _, _, metadata = _model_bundle()
                with self._lock:
                    self._status.model_version = metadata.get("model_version")
            except Exception as exc:
                logger.exception("[simulation] Gagal memuat model: %s", exc)
                with self._lock:
                    self._status.errors += 1
                    self._status.last_error = f"Model gagal dimuat: {exc}"
                    self._status.running = False
                return

            with self._lock:
                if not self._status.running:
                    return
                self._start_scheduler_locked(interval)
        except Exception as exc:
            logger.exception("[simulation] Gagal menyiapkan dataset: %s", exc)
            with self._lock:
                self._status.preparing = False
                self._status.running = False
                self._status.errors += 1
                self._status.last_error = str(exc)

    def _start_scheduler_locked(self, interval: float) -> None:
        from apscheduler.schedulers.background import BackgroundScheduler

        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(
            self._tick,
            trigger="interval",
            seconds=interval,
            id="simulation_tick",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=max(1, int(interval)),
            next_run_time=_utcnow(),
        )
        self._scheduler.start()
        logger.info("[simulation] Scheduler dimulai (interval %.1fs).", interval)

    def _stop_scheduler_locked(self) -> None:
        scheduler = self._scheduler
        self._scheduler = None
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass

    # -- tick -----------------------------------------------------------
    def _tick(self) -> None:
        if not self._status.running:
            return
        try:
            self._step_once()
        except Exception as exc:  # pragma: no cover - defensif
            logger.exception("[simulation] Tick gagal: %s", exc)
            with self._lock:
                self._status.errors += 1
                self._status.last_error = str(exc)
        finally:
            try:
                from api.services.queue_event_bus import publish

                publish()
            except Exception:
                pass

    def _step_once(self) -> Optional[Dict[str, Any]]:
        if self._dataset is None:
            return None

        with self._lock:
            self._status.tick_count += 1
        now = _utcnow()
        completed = self._complete_due_bpmh(now)
        escalated = self._escalate_due(now)
        admitted = self._admit_next(now)

        with self._lock:
            self._status.escalated += escalated
            self._status.bpmh_completed += completed
            if admitted:
                self._status.admitted += 1
                self._status.last_patient = admitted
            done = (
                self._status.admitted >= self._status.max_patients
                or self._status.next_index >= len(self._dataset)
            )
            if done and not self._pending:
                # Fase drain: terus tick agar eskalasi SLA terlihat di demo.
                if self._status.drain_remaining > 0:
                    self._status.drain_remaining -= 1
                    self._status.draining = True
                else:
                    self._status.draining = False
                    self._status.running = False
                    self._status.finished = True
                    self._status.stopped_at = _utcnow().isoformat()
                    self._stop_scheduler_locked()

        if admitted is not None:
            return admitted
        if completed or escalated:
            return {
                "event": "sla_escalated" if escalated else "bpmh_completed",
                "count": max(completed, escalated),
                "bpmh_completed": completed,
                "escalated": escalated,
            }
        return None

    def _admit_next(self, now: datetime) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._status.next_index >= len(self._dataset or []):
                return None
            if self._status.admitted >= self._status.max_patients:
                return None
            index = self._status.next_index
            patient = self._dataset.rows[index]
            self._status.next_index = index + 1

        enc_id = self._encounter_id_for_run(patient.encounter_id)

        # --- XGBoost asli ---
        model, thresholds, metadata = _model_bundle()
        from src.models.predict import predict_single

        prediction = predict_single(
            feature_dict={**patient.features, "encounter_id": enc_id},
            model=model,
            thresholds=thresholds,
            metadata=metadata,
        )
        ml_score = float(prediction["risk_probability"])

        # --- Rule engine asli + composite priority ---
        priority = _priority_for(patient, ml_score, self._cfg)
        final_tier = str(priority.get("final_tier", prediction.get("priority", "MEDIUM")))
        reasons = list(priority.get("priority_reasons", []))
        has_high_alert = bool(priority.get("has_high_alert"))
        counts = priority.get("discrepancy_counts", {})
        flags = priority.get("flags", [])

        admitted_at = now.isoformat()

        with self._session_scope() as session:
            from api.db.models import Encounter, QueueEntry
            from api.services.queue_service import (
                _append_event,
                _entry_to_dict,
                admit_encounter,
            )

            encounter = session.query(Encounter).filter(Encounter.id == enc_id).first()
            if encounter is None:
                encounter = Encounter(
                    id=enc_id,
                    patient_id=patient.patient_id,
                    patient_name=_synthetic_name(patient.patient_id),
                    patient_gender="L" if patient.features.get("gender_encoded", 0) < 0.5 else "P",
                    ward=patient.ward,
                    admitted_at=admitted_at,
                    workflow_status="MENUNGGU_BPMH",
                    ml_score=ml_score,
                    latest_tier=final_tier,
                    priority_reason=json.dumps(reasons, ensure_ascii=False),
                )
                session.add(encounter)
                session.flush()

            entry_dict = admit_encounter(
                session,
                encounter_id=enc_id,
                ward=patient.ward,
                admitted_at=admitted_at,
                ml_score=ml_score,
                has_rule_finding=has_high_alert,
                cfg=self._cfg,
                now=now,
            )

            entry = session.query(QueueEntry).filter_by(encounter_id=enc_id).first()
            if entry is not None:
                self._apply_priority(entry, final_tier, reasons, ml_score, counts, now)
                _append_event(
                    session,
                    enc_id,
                    "upsert",
                    {
                        "action": "simulation_admit",
                        "queue_type": entry.queue_type,
                        "ward": entry.ward,
                        "tier_rank": entry.tier_rank,
                        "tier_source": entry.tier_source,
                        "ml_score": ml_score,
                        "priority_score": entry.priority_score,
                    },
                )

            encounter.latest_tier = final_tier
            encounter.priority_reason = json.dumps(reasons, ensure_ascii=False)
            encounter.ml_score = ml_score
            encounter.updated_at = now.isoformat()
            session.flush()

        due_tick = self._status.tick_count + 1 + (index % 2)
        with self._lock:
            self._pending.append(
                _PendingBpmh(
                    encounter_id=enc_id,
                    due_tick=due_tick,
                    ml_score=ml_score,
                    priority=priority,
                    ward=patient.ward,
                )
            )

        return {
            "event": "admitted",
            "encounter_id": enc_id,
            "source_encounter_id": patient.encounter_id,
            "patient_id": patient.patient_id,
            "ward": patient.ward,
            "ml_score": round(ml_score, 4),
            "model_priority": prediction.get("priority"),
            "final_tier": final_tier,
            "rules_floor": priority.get("rules_floor"),
            "rule_findings": len(flags),
            "rule_types": sorted({str(f.get("flag_type")) for f in flags}),
            "mutation_type": patient.mutation_type,
            "admitted_at": admitted_at,
        }

    def _complete_due_bpmh(self, now: datetime) -> int:
        with self._lock:
            due = [p for p in self._pending if p.due_tick <= self._status.tick_count]
            if due:
                self._pending = [p for p in self._pending if p.due_tick > self._status.tick_count]

        completed = 0
        for pending in due:
            try:
                self._complete_bpmh(pending, now)
                completed += 1
            except Exception as exc:
                logger.exception("[simulation] Gagal menyelesaikan BPMH %s: %s", pending.encounter_id, exc)
                with self._lock:
                    self._status.errors += 1
                    self._status.last_error = str(exc)
        return completed

    def _complete_bpmh(self, pending: _PendingBpmh, now: datetime) -> None:
        priority = pending.priority
        final_tier = str(priority.get("final_tier", "MEDIUM"))
        reasons = list(priority.get("priority_reasons", []))
        has_high_alert = bool(priority.get("has_high_alert"))
        counts = priority.get("discrepancy_counts", {})

        with self._session_scope() as session:
            from api.db.models import Encounter, QueueEntry
            from api.services.queue_service import _append_event, _entry_to_dict
            from api.services.queue_view_service import advance_encounter

            entry = session.query(QueueEntry).filter_by(encounter_id=pending.encounter_id).first()
            if entry is None or entry.state == "CLOSED":
                return

            updated, event_dict = _bpmh_transition(
                _entry_to_dict(entry),
                has_rule_finding=has_high_alert,
                is_high_alert=has_high_alert,
                discrepancy_counts=counts,
                ml_score=pending.ml_score,
                now=now,
                cfg=self._cfg,
            )

            entry.queue_type = "REVIEW"
            entry.state = "OPEN"
            entry.tier_rank = updated["tier_rank"]
            entry.tier_source = updated["tier_source"]
            entry.priority_score = updated["priority_score"]
            entry.claimed_by = None
            entry.claim_expires_at = None
            entry.queue_version = updated["queue_version"]
            entry.updated_at = updated["updated_at"]

            self._apply_priority(entry, final_tier, reasons, pending.ml_score, counts, now)

            _append_event(
                session,
                pending.encounter_id,
                event_dict["kind"],
                json.loads(event_dict["payload_json"]),
            )

            advance_encounter(session, pending.encounter_id, "MENUNGGU_TELAAH")
            encounter = session.query(Encounter).filter_by(id=pending.encounter_id).first()
            if encounter is not None:
                encounter.latest_tier = final_tier
                encounter.priority_reason = json.dumps(reasons, ensure_ascii=False)
                encounter.ml_score = pending.ml_score
                encounter.updated_at = now.isoformat()
            session.flush()

    def _apply_priority(
        self,
        entry,
        final_tier: str,
        reasons: List[Dict[str, Any]],
        ml_score: float,
        counts: Dict[str, int],
        now: datetime,
    ) -> None:
        """Naikkan tier entri sesuai hasil gabungan ML + aturan (tidak pernah turun)."""
        from api.db.models import QueueEntry  # noqa: F401  (type reference)

        new_rank = TIER_RANK.get(str(final_tier).upper(), 1)
        entry.tier_rank = max(int(entry.tier_rank or 0), new_rank)

        rules_floor = "LOW"
        for reason in reasons:
            if reason.get("source") == "rules":
                tier = str(reason.get("tier", "LOW")).upper()
                rules_floor = max(rules_floor, tier, key=lambda t: TIER_RANK.get(t, 0))
        if rules_floor == "HIGH":
            entry.tier_source = "RULE"
        elif rules_floor == "MEDIUM" and entry.tier_rank <= 1:
            entry.tier_source = "RULE"

        entry_dict = {
            "encounter_id": entry.encounter_id,
            "queue_type": entry.queue_type,
            "ward": entry.ward,
            "state": entry.state,
            "tier_rank": entry.tier_rank,
            "tier_source": entry.tier_source,
            "priority_score": entry.priority_score or 0.0,
            "ml_percentile": entry.ml_percentile,
            "admitted_at": entry.admitted_at,
            "discharge_planned_at": entry.discharge_planned_at,
            "discrepancy_counts": counts,
        }
        ml_percentile = entry.ml_percentile
        if ml_percentile is None:
            ml_percentile = max(0.0, min(1.0, ml_score))
        entry.priority_score = compute_queue_score(entry_dict, now, ml_percentile, self._cfg)

        tier_str = TIER_FROM_RANK.get(entry.tier_rank, "MEDIUM")
        sla = self._cfg.sla.get(tier_str)
        admitted_dt = _parse_dt(entry.admitted_at) or now
        if sla is not None:
            entry.sla_due_at = (admitted_dt + timedelta(hours=sla.target_hours)).isoformat()
        entry.next_due_at = determine_next_due_at(entry_dict, now, self._cfg)
        entry.queue_version = (entry.queue_version or 0) + 1
        entry.updated_at = now.isoformat()

    def _escalate_due(self, now: datetime) -> int:
        """Naikkan tier entri yang melewati ambang SLA (dengan cfg simulasi)."""
        escalated = 0
        with self._session_scope() as session:
            from api.db.models import Encounter, QueueEntry, SlaEvent
            from api.services.queue_service import _append_event, _entry_to_dict

            rows = (
                session.query(QueueEntry)
                .filter(QueueEntry.state.in_(["OPEN", "CLAIMED"]))
                .all()
            )
            for entry in rows:
                due = _parse_dt(entry.next_due_at)
                if due is not None and now >= due and int(entry.tier_rank or 0) < 2:
                    old_rank = int(entry.tier_rank or 0)
                    entry.tier_rank = min(old_rank + 1, 2)
                    entry.tier_source = "SLA"
                    entry.queue_version = (entry.queue_version or 0) + 1
                    entry.updated_at = now.isoformat()
                    escalated += 1

                    session.add(
                        SlaEvent(
                            id=str(uuid.uuid4()),
                            encounter_id=entry.encounter_id,
                            event_type="ESCALATED",
                            from_tier=TIER_FROM_RANK.get(old_rank, "LOW"),
                            to_tier=TIER_FROM_RANK.get(entry.tier_rank, "MEDIUM"),
                            occurred_at=now.isoformat(),
                            notified=False,
                        )
                    )
                    _append_event(
                        session,
                        entry.encounter_id,
                        "promote",
                        {
                            "action": "sla_escalation",
                            "from_tier": old_rank,
                            "to_tier": entry.tier_rank,
                            "queue_type": entry.queue_type,
                            "ward": entry.ward,
                            "reason": "SLA",
                        },
                    )

                    encounter = session.query(Encounter).filter_by(id=entry.encounter_id).first()
                    if encounter is not None:
                        current = TIER_RANK.get(str(encounter.latest_tier or "LOW").upper(), 0)
                        if entry.tier_rank > current:
                            encounter.latest_tier = TIER_FROM_RANK.get(entry.tier_rank, "MEDIUM")
                            encounter.updated_at = now.isoformat()

                # Hitung ambang berikutnya berdasarkan tier terbaru.
                entry.next_due_at = determine_next_due_at(
                    _entry_to_dict(entry), now, self._cfg
                )
            session.flush()
        return escalated

    # -- helpers --------------------------------------------------------
    def _encounter_id_for_run(self, source_id: str) -> str:
        if not self._fresh_ids or not self._run_id:
            return source_id
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"priomed-sim:{self._run_id}:{source_id}"))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine: Optional[SimulationEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> SimulationEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = SimulationEngine()
        return _engine


def stop_simulation() -> None:
    """Dipanggil saat shutdown aplikasi."""
    global _engine
    with _engine_lock:
        engine = _engine
    if engine is not None:
        engine.stop()
