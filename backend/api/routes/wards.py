"""
api/routes/wards.py
--------------------
GET  /wards        — list wards with pharmacist capacity (for worklist filter)
POST /wards/config — update ward capacity (settings page)

Clinical safety: no clinical data here — administrative configuration only.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# Default ward config — in production this would be persisted in a database
_ward_config: list[dict] = [
    {"ward_id": "icu",        "ward_name": "ICU Terpadu",            "capacity": 8,  "allocated": 5,  "pharmacists": 1},
    {"ward_id": "hcu",        "ward_name": "HCU",                    "capacity": 6,  "allocated": 4,  "pharmacists": 1},
    {"ward_id": "interna",    "ward_name": "Penyakit Dalam",         "capacity": 12, "allocated": 9,  "pharmacists": 2},
    {"ward_id": "kardiologi", "ward_name": "Kardiologi",             "capacity": 8,  "allocated": 6,  "pharmacists": 1},
    {"ward_id": "bedah",      "ward_name": "Bedah Umum",             "capacity": 10, "allocated": 4,  "pharmacists": 1},
    {"ward_id": "neurologi",  "ward_name": "Neurologi",              "capacity": 7,  "allocated": 3,  "pharmacists": 1},
    {"ward_id": "geriatri",   "ward_name": "Geriatri",               "capacity": 6,  "allocated": 4,  "pharmacists": 1},
]


class WardItem(BaseModel):
    ward_id:     str
    ward_name:   str
    capacity:    int = Field(ge=1)
    allocated:   int = Field(ge=0)
    pharmacists: int = Field(ge=0)


class WardListResponse(BaseModel):
    total_capacity:  int
    total_allocated: int
    wards:           List[WardItem]


class WardConfigRequest(BaseModel):
    wards: List[WardItem]


@router.get(
    "/wards",
    response_model=WardListResponse,
    tags=["wards"],
    summary="List wards with pharmacist capacity",
)
def list_wards() -> WardListResponse:
    """Return current ward list and pharmacist capacity configuration."""
    try:
        from api.database import get_wards as _db_get_wards
        db_wards = _db_get_wards()
        if db_wards:
            items = [WardItem(**{k: v for k, v in w.items() if k in WardItem.model_fields}) for w in db_wards]
            return WardListResponse(
                total_capacity=sum(w.capacity for w in items),
                total_allocated=sum(w.allocated for w in items),
                wards=items,
            )
    except Exception as exc:
        print(f"[wards] DB read warning: {exc}")

    items = [WardItem(**w) for w in _ward_config]
    return WardListResponse(
        total_capacity=sum(w.capacity for w in items),
        total_allocated=sum(w.allocated for w in items),
        wards=items,
    )


@router.post(
    "/wards/config",
    response_model=WardListResponse,
    tags=["wards"],
    summary="Update ward capacity configuration (Settings page)",
)
def update_wards(request: WardConfigRequest) -> WardListResponse:
    """
    Update ward capacity configuration and persist to database.
    """
    global _ward_config
    if not request.wards:
        raise HTTPException(status_code=422, detail="Ward list cannot be empty.")
    ward_dicts = [w.model_dump() for w in request.wards]
    
    try:
        from api.database import save_wards as _db_save_wards
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        _db_save_wards(ward_dicts, now)
    except Exception as exc:
        print(f"[wards] DB save warning: {exc}")

    _ward_config = ward_dicts
    return list_wards()


# ---------------------------------------------------------------------------
# Local High-Alert endpoints
# ---------------------------------------------------------------------------

class HighAlertItem(BaseModel):
    drug_name: str
    category: Optional[str] = None

class HighAlertRequest(BaseModel):
    drugs: List[HighAlertItem]

class HighAlertResponse(BaseModel):
    drugs: List[HighAlertItem]
    count: int

@router.get(
    "/settings/high-alert",
    response_model=HighAlertResponse,
    tags=["settings"],
    summary="Get local hospital high-alert drug list",
)
def get_local_high_alerts():
    """Return hospital-specific high-alert medications."""
    try:
        from api.database import get_local_high_alerts as _db_get
        drugs = _db_get()
        return HighAlertResponse(
            drugs=[HighAlertItem(drug_name=d["drug_name"], category=d.get("category")) for d in drugs],
            count=len(drugs),
        )
    except Exception as exc:
        return HighAlertResponse(drugs=[], count=0)


@router.post(
    "/settings/high-alert",
    response_model=HighAlertResponse,
    tags=["settings"],
    summary="Update local hospital high-alert drug list",
)
def update_local_high_alerts(request: HighAlertRequest):
    """Update hospital-specific high-alert medications."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    try:
        from api.database import save_local_high_alerts as _db_save
        _db_save(
            drugs=[d.model_dump() for d in request.drugs],
            added_by="pharmacist",
            added_at=now,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    
    return HighAlertResponse(drugs=request.drugs, count=len(request.drugs))
