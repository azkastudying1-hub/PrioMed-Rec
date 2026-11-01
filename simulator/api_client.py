"""
simulator/api_client.py
------------------------
Client HTTP untuk memanggil API PrioMed-Rec dari simulator.

Memanggil endpoint nyata (admit, discharge, bpmh_submit, transfer, next, release)
sehingga seluruh stack (auth, queue engine, SLA, SSE, audit) benar-benar diuji.

Timeout default 5 detik — simulator harus tetap berjalan walau API lambat.
Jika API tidak tersedia, mode offline menggunakan direct DB calls (mode_offline=True).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("priomed.simulator.api")


class ApiError(Exception):
    """Error dari API call."""
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class SimApiClient:
    """
    HTTP client yang memanggil API PrioMed-Rec.

    Supports:
      - Retry sederhana (max 2 retry, backoff 0.5 dtk)
      - Mode offline (direct service calls tanpa HTTP)
      - Token refresh (placeholder)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        token: str = "",
        timeout: float = 5.0,
        max_retries: int = 2,
        offline_mode: bool = False,
    ):
        self.base_url   = base_url.rstrip("/")
        self.token      = token
        self.timeout    = timeout
        self.max_retries = max_retries
        self.offline_mode = offline_mode
        self._session   = None

        if not offline_mode:
            try:
                import httpx
                self._session = httpx.Client(
                    base_url=self.base_url,
                    headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
                    timeout=self.timeout,
                )
            except ImportError:
                logger.warning(
                    "httpx tidak tersedia — simulator beralih ke mode offline (direct DB)."
                )
                self.offline_mode = True

    # ------------------------------------------------------------------
    # Core HTTP
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Kirim request HTTP dengan retry."""
        if self.offline_mode:
            raise RuntimeError("Mode offline aktif — gunakan direct service calls.")

        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(method, path, **kwargs)
                if resp.status_code == 204:
                    return {}
                if resp.status_code >= 400:
                    raise ApiError(resp.status_code, resp.text[:200])
                return resp.json()
            except ApiError:
                raise
            except Exception as exc:
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    logger.debug(f"[api_client] Retry {attempt+1}/{self.max_retries}: {exc}")

        raise RuntimeError(f"API tidak dapat dijangkau setelah {self.max_retries} retry: {last_err}")

    # ------------------------------------------------------------------
    # Queue endpoints
    # ------------------------------------------------------------------

    def admit(
        self,
        encounter_id: str,
        ward: str,
        admitted_at: str,
        ml_score: Optional[float] = None,
        has_rule_finding: bool = False,
    ) -> Dict[str, Any]:
        """POST /queue/{encounter_id}/admit"""
        payload = {
            "ward": ward,
            "admitted_at": admitted_at,
            "ml_score": ml_score,
            "has_rule_finding": has_rule_finding,
        }
        return self._request("POST", f"/queue/{encounter_id}/admit", json=payload)

    def discharge(
        self,
        encounter_id: str,
        workflow_status: str = "IN_PROGRESS",
        reason: str = "DISCHARGE_BEFORE_REVIEW",
    ) -> Dict[str, Any]:
        """POST /queue/{encounter_id}/discharge"""
        return self._request(
            "POST", f"/queue/{encounter_id}/discharge",
            json={"workflow_status": workflow_status, "reason": reason}
        )

    def transfer(
        self,
        encounter_id: str,
        new_ward: str,
        has_rule_finding: bool = False,
        ml_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """POST /queue/{encounter_id}/transfer"""
        return self._request(
            "POST", f"/queue/{encounter_id}/transfer",
            json={"new_ward": new_ward, "has_rule_finding": has_rule_finding, "ml_score": ml_score}
        )

    def bpmh_submit(
        self,
        encounter_id: str,
        has_rule_finding: bool = False,
        is_high_alert: bool = False,
        discrepancy_counts: Optional[Dict[str, int]] = None,
        ml_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """POST /queue/{encounter_id}/bpmh_submit"""
        return self._request(
            "POST", f"/queue/{encounter_id}/bpmh_submit",
            json={
                "has_rule_finding": has_rule_finding,
                "is_high_alert": is_high_alert,
                "discrepancy_counts": discrepancy_counts or {},
                "ml_score": ml_score,
            }
        )

    def queue_next(
        self,
        queue_type: str = "REVIEW",
        ward_scope: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """POST /queue/next"""
        params: Dict[str, Any] = {"queue_type": queue_type}
        if ward_scope:
            params["ward_scope"] = ",".join(ward_scope)
        result = self._request("POST", "/queue/next", params=params)
        if not result or "encounter_id" not in result:
            return None
        return result

    def release(self, encounter_id: str) -> Dict[str, Any]:
        """POST /queue/{encounter_id}/release"""
        return self._request("POST", f"/queue/{encounter_id}/release")

    def get_metrics(self) -> Dict[str, Any]:
        """GET /queue/metrics"""
        return self._request("GET", "/queue/metrics")

    def get_queue(
        self,
        state: str = "OPEN",
        limit: int = 20,
        after_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """GET /queue"""
        params: Dict[str, Any] = {"state": state, "limit": limit}
        if after_cursor:
            params["after_cursor"] = after_cursor
        return self._request("GET", "/queue", params=params)

    # ------------------------------------------------------------------
    # Mode offline — panggil service layer langsung (tanpa HTTP)
    # ------------------------------------------------------------------

    def admit_offline(
        self,
        encounter_id: str,
        ward: str,
        admitted_at: str,
        ml_score: Optional[float] = None,
        has_rule_finding: bool = False,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Direct call ke queue_service.admit_encounter (tanpa HTTP)."""
        from api.db.session import session_scope
        from api.services.queue_service import admit_encounter
        with session_scope() as session:
            result = admit_encounter(
                session, encounter_id, ward, admitted_at, ml_score, has_rule_finding, now=now
            )
            session.commit()
        return result

    def discharge_offline(
        self,
        encounter_id: str,
        workflow_status: str = "IN_PROGRESS",
        reason: str = "DISCHARGE_BEFORE_REVIEW",
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Direct call ke queue_service.discharge_encounter."""
        from api.db.session import session_scope
        from api.services.queue_service import discharge_encounter
        with session_scope() as session:
            result = discharge_encounter(session, encounter_id, workflow_status, reason, now=now)
            session.commit()
        return result

    def queue_next_offline(
        self,
        user_id: str,
        queue_type: str = "REVIEW",
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Direct call ke queue_service.next_for_user."""
        from api.db.session import session_scope
        from api.services.queue_service import next_for_user
        with session_scope() as session:
            result = next_for_user(session, user_id, queue_type=queue_type, now=now)
            session.commit()
        return result

    def transfer_offline(
        self,
        encounter_id: str,
        new_ward: str,
        has_rule_finding: bool = False,
        ml_score: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Direct call ke queue_service + transition."""
        from api.db.session import session_scope
        from api.db.models import QueueEntry
        from priomedrec_core.queue_transitions import transfer as _transfer_transition
        from priomedrec_core.queue_config import DEFAULT_CONFIG
        _now = now or datetime.now(timezone.utc)
        with session_scope() as session:
            entry = session.query(QueueEntry).filter_by(encounter_id=encounter_id).first()
            if not entry:
                return {"error": "not_found"}
            existing = {
                "encounter_id":  entry.encounter_id,
                "ward":          entry.ward,
                "tier_rank":     entry.tier_rank,
                "tier_source":   entry.tier_source,
                "priority_score": entry.priority_score,
                "admitted_at":   entry.admitted_at,
                "queue_version": entry.queue_version,
                "state":         entry.state,
            }
            updated, event_dict = _transfer_transition(
                existing_entry=existing,
                new_ward=new_ward,
                has_rule_finding=has_rule_finding,
                ml_score=ml_score,
                now=_now,
                cfg=DEFAULT_CONFIG,
            )
            entry.ward = updated["ward"]
            entry.tier_rank = updated["tier_rank"]
            entry.tier_source = updated["tier_source"]
            entry.priority_score = updated["priority_score"]
            entry.queue_version = (entry.queue_version or 0) + 1
            session.commit()
        return updated

    def bpmh_submit_offline(
        self,
        encounter_id: str,
        has_rule_finding: bool = False,
        is_high_alert: bool = False,
        ml_score: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Direct call ke queue_service + bpmh_submit transition."""
        from api.db.session import session_scope
        from api.db.models import QueueEntry
        from priomedrec_core.queue_transitions import bpmh_submit as _bpmh_transition
        from priomedrec_core.queue_config import DEFAULT_CONFIG
        _now = now or datetime.now(timezone.utc)
        with session_scope() as session:
            entry = session.query(QueueEntry).filter_by(encounter_id=encounter_id).first()
            if not entry:
                return {"error": "not_found"}
            existing = {
                "encounter_id":  entry.encounter_id,
                "ward":          entry.ward,
                "tier_rank":     entry.tier_rank,
                "tier_source":   entry.tier_source,
                "priority_score": entry.priority_score,
                "admitted_at":   entry.admitted_at,
                "queue_version": entry.queue_version,
                "state":         entry.state,
                "queue_type":    entry.queue_type,
            }
            updated, event_dict = _bpmh_transition(
                existing_entry=existing,
                has_rule_finding=has_rule_finding,
                is_high_alert=is_high_alert,
                ml_score=ml_score,
                now=_now,
                cfg=DEFAULT_CONFIG,
            )
            entry.queue_type  = updated.get("queue_type", entry.queue_type)
            entry.state       = updated.get("state", entry.state)
            entry.tier_rank   = updated.get("tier_rank", entry.tier_rank)
            entry.tier_source = updated.get("tier_source", entry.tier_source)
            entry.priority_score = updated.get("priority_score", entry.priority_score)
            entry.queue_version = (entry.queue_version or 0) + 1
            session.commit()
        return updated

    def close(self) -> None:
        if self._session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
