"""
streamlit_app/components/review_panel.py
------------------------------------------
Pharmacist APPROVE / REJECT / EDIT action panel.

Captures pharmacist action and submits to POST /review.
Records model_version and rule_version in the audit trail.
"""

from __future__ import annotations

import os
import requests
import streamlit as st
from typing import Optional

API_URL = os.getenv("PRIOMEDREC_API_URL", "http://localhost:8000")


def render_review_panel(
    data: dict,
    pharmacist_id: str = "PHARM-001",
    key_prefix: str = "review",
) -> None:
    """
    Render the APPROVE / REJECT / EDIT action panel for a given analysis result.

    Parameters
    ----------
    data         : The /analyze response dict.
    pharmacist_id: Pharmacist identifier (from session or config).
    key_prefix   : Unique key prefix for Streamlit widgets (avoids key collisions).
    """
    st.subheader("👨‍⚕️ Pharmacist Review Action")
    st.caption(
        "Setiap output AI membutuhkan review dan keputusan akhir dari farmasis."
    )

    patient_id   = data.get("patient_id", "UNKNOWN")
    encounter_id = data.get("encounter_id", "UNKNOWN")
    model_ver    = data.get("model_version", "unknown")
    rule_ver     = data.get("rule_version", "unknown")

    col1, col2, col3 = st.columns(3)
    action_selected: Optional[str] = None
    if col1.button("✅ APPROVE", key=f"{key_prefix}_approve", use_container_width=True):
        action_selected = "APPROVE"
    if col2.button("✏️ EDIT",    key=f"{key_prefix}_edit",    use_container_width=True):
        action_selected = "EDIT"
    if col3.button("❌ REJECT",  key=f"{key_prefix}_reject",  use_container_width=True):
        action_selected = "REJECT"

    if action_selected:
        st.session_state[f"{key_prefix}_action"] = action_selected

    pending_action = st.session_state.get(f"{key_prefix}_action")

    if pending_action:
        st.markdown(f"**Action selected:** `{pending_action}`")

        note = st.text_area(
            "Pharmacist Note",
            placeholder="Catatan farmasis (opsional untuk APPROVE, wajib untuk REJECT)",
            key=f"{key_prefix}_note",
        )

        edited_result: Optional[dict] = None
        if pending_action == "EDIT":
            st.info("EDIT mode: isi catatan untuk merekam perubahan Anda.")
            edited_result = dict(data)
            edited_result["pharmacist_note"] = note
            edited_result["pharmacist_action"] = "EDITED"

        if st.button("📤 Submit Review", key=f"{key_prefix}_submit", type="primary"):
            _submit_review(
                case_id=f"{patient_id}_{encounter_id}",
                pharmacist_id=pharmacist_id,
                ai_result=data,
                action=pending_action,
                note=note,
                edited_result=edited_result,
                model_version=model_ver,
                rule_version=rule_ver,
                key_prefix=key_prefix,
            )


def _submit_review(
    case_id: str,
    pharmacist_id: str,
    ai_result: dict,
    action: str,
    note: str,
    edited_result: Optional[dict],
    model_version: str,
    rule_version: str,
    key_prefix: str,
) -> None:
    """POST to /review and show confirmation."""
    payload = {
        "case_id":       case_id,
        "pharmacist_id": pharmacist_id,
        "ai_result":     ai_result,
        "action":        action,
        "pharmacist_note": note,
        "edited_result": edited_result,
        "model_version": model_version,
        "rule_version":  rule_version,
    }

    try:
        resp = requests.post(f"{API_URL}/review", json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        st.success(
            f"✅ Review submitted — ID: `{result['review_id']}` | "
            f"Action: **{result['action']}** | "
            f"Timestamp: {result['timestamp'][:19]}"
        )
        st.session_state[f"{key_prefix}_action"] = None  # reset after submit
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Tidak bisa terhubung ke API di `{API_URL}`.")
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Review gagal: {e.response.status_code} — {e.response.text}")
    except Exception as e:
        st.error(f"❌ Error: {e}")
