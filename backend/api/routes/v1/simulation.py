"""
api/routes/v1/simulation.py
----------------------------
Kontrol simulation engine replay CSV.

  POST /api/v1/simulation/start   — mulai replay (1 pasien per interval)
  POST /api/v1/simulation/stop    — hentikan replay
  POST /api/v1/simulation/step    — jalankan N langkah manual (demo)
  GET  /api/v1/simulation/status  — status & metrik ringkas

Keselamatan:
  - Hanya peran klinis/koordinator/admin yang boleh mengubah simulasi.
  - Endpoint ini tidak memanggil LLM/Langflow (ADR-20).
  - Data yang ditulis adalah data simulasi dan diberi label di UI.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.auth.rbac import TokenData, UserRole, require_roles
from api.services.simulation_service import get_engine

router = APIRouter(prefix="/simulation", tags=["simulation"])

_ALLOWED = (UserRole.PHARMACIST, UserRole.COORDINATOR, UserRole.ADMIN)


class SimulationStartRequest(BaseModel):
    interval_seconds: float = Field(
        6.0, ge=1.0, le=120.0,
        description="Jeda antar pasien (detik). 5–10 detik disarankan untuk demo.",
    )
    max_patients: int = Field(
        60, ge=1, le=5000,
        description="Jumlah pasien yang di-replay pada sesi ini.",
    )
    sla_scale: float = Field(
        0.0025, gt=0.0, le=1.0,
        description=(
            "Pengali ambang SLA. 1.0 = produksi (jam). "
            "0.0025 mempercepat eskalasi agar terlihat dalam demo."
        ),
    )
    dataset_path: Optional[str] = Field(
        None, description="Path CSV alternatif (default data/processed/model_ready.csv)."
    )
    cases_path: Optional[str] = Field(
        None, description="Path CSV data obat (default data/processed/synthetic_cases.csv)."
    )
    fresh_ids: bool = Field(
        True,
        description="Buat ID encounter baru per sesi agar replay bisa diulang.",
    )
    drain_ticks: int = Field(
        30,
        ge=0,
        le=600,
        description=(
            "Jumlah tick tambahan setelah semua pasien masuk. Dipakai agar "
            "eskalasi SLA tetap terlihat sebelum simulasi berhenti."
        ),
    )


class SimulationStepRequest(BaseModel):
    count: int = Field(1, ge=1, le=50)


@router.post("/start", summary="Mulai replay CSV sebagai pasien baru")
async def start_simulation(
    body: SimulationStartRequest,
    current_user: TokenData = Depends(require_roles(*_ALLOWED)),
):
    """
    Mulai simulasi replay CSV.
    
    Simulasi akan:
    1. Memuat data dari model_ready.csv dan synthetic_cases.csv
    2. Setiap tick (interval_seconds), satu pasien masuk ke antrean
    3. XGBoost model + rule engine dijalankan untuk setiap pasien
    4. Pasien otomatis berpindah dari BPMH → REVIEW setelah 1-2 tick
    5. SLA escalation terlihat dalam demo (sla_scale=0.0025 = 1 jam → 9 detik)
    """
    engine = get_engine()
    
    # Ensure any previous simulation is stopped
    if engine._status.running:
        engine.stop()
    
    status = engine.start(
        interval_seconds=body.interval_seconds,
        max_patients=body.max_patients,
        sla_scale=body.sla_scale,
        dataset_path=body.dataset_path,
        cases_path=body.cases_path,
        fresh_ids=body.fresh_ids,
        drain_ticks=body.drain_ticks,
    )
    return {
        "ok": True, 
        "started_by": current_user.user_id, 
        "status": status,
        "message": f"Simulasi dimulai: {body.max_patients} pasien, interval {body.interval_seconds}s"
    }


@router.post("/stop", summary="Hentikan replay")
async def stop_simulation(
    current_user: TokenData = Depends(require_roles(*_ALLOWED)),
):
    return {"ok": True, "stopped_by": current_user.user_id, "status": get_engine().stop()}


@router.post("/step", summary="Jalankan langkah simulasi manual")
async def step_simulation(
    body: SimulationStepRequest,
    current_user: TokenData = Depends(require_roles(*_ALLOWED)),
):
    return {"ok": True, "stepped_by": current_user.user_id, **get_engine().step(body.count)}


@router.get("/status", summary="Status simulation engine")
async def simulation_status(
    current_user: TokenData = Depends(require_roles(*_ALLOWED)),
):
    return get_engine().status()
