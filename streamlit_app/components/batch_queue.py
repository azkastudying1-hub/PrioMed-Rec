"""
streamlit_app/components/batch_queue.py
-----------------------------------------
Ranked Patient Priority Queue component for PrioMed-Rec.

Allows clinical pharmacists to view and filter a ranked worklist of 
dozens or hundreds of admitted patients sorted from Highest Risk to Lowest Risk.
"""

from __future__ import annotations

import os
import requests
import pandas as pd
import streamlit as st

API_URL = os.getenv("PRIOMEDREC_API_URL", "http://localhost:8000")


def render_batch_queue() -> None:
    """Render the cohort patient priority queue tab."""
    st.subheader("📋 Antrean Prioritas Rekonsiliasi Obat Pasien (Worklist)")
    st.caption(
        "Memeringkat seluruh pasien admisi rawat inap berdasarkan Predicted Discrepancy Likelihood (Risiko Tertinggi ke Terendah)."
    )

    # Controls
    col_limit, col_filter, col_fetch = st.columns([2, 2, 1])
    with col_limit:
        limit = st.slider("Jumlah Pasien yang Dinilai", min_value=10, max_value=200, value=50, step=10)
    with col_filter:
        prio_filter = st.selectbox("Filter Prioritas", ["SEMUA", "HIGH", "MEDIUM", "LOW"])
    with col_fetch:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_btn = st.button("🔄 Refresh Worklist", type="primary", use_container_width=True)

    # Fetch data
    filter_arg = None if prio_filter == "SEMUA" else prio_filter

    with st.spinner(f"⏳ Memeringkat {limit} pasien admisi..."):
        data = _fetch_batch_data(limit=limit, priority_filter=filter_arg)

    if not data or "ranked_patients" not in data:
        st.error("❌ Gagal memuat antrean prioritas pasien. Pastikan FastAPI berjalan.")
        return

    total   = data.get("total_analyzed", 0)
    high_c  = data.get("high_priority_count", 0)
    med_c   = data.get("medium_priority_count", 0)
    low_c   = data.get("low_priority_count", 0)

    # KPI Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Pasien Dievaluasi", total)
    m2.metric("🔴 Prioritas TINGGI", high_c)
    m3.metric("🟡 Prioritas SEDANG", med_c)
    m4.metric("🟢 Prioritas RENDAH", low_c)

    st.divider()

    patients = data.get("ranked_patients", [])
    if not patients:
        st.info("Tidak ada pasien yang sesuai dengan filter prioritas ini.")
        return

    # Prepare DataFrame for table view
    rows = []
    for p in patients:
        prio = p.get("review_priority", "LOW")
        badge = "🔴 HIGH" if prio == "HIGH" else ("🟡 MEDIUM" if prio == "MEDIUM" else "🟢 LOW")
        prob_pct = f"{round(p.get('discrepancy_likelihood', 0) * 100, 1)}%"
        
        rows.append({
            "Rank": f"#{p.get('rank')}",
            "Patient ID": p.get("patient_id"),
            "Prioritas": badge,
            "Likelihood Risk": prob_pct,
            "Faktor Utama Risiko": p.get("top_risk_driver", "—"),
            "Usia": f"{int(p.get('age', 0))} thn" if p.get("age") else "—",
            "Pre Meds": p.get("pre_admission_med_count", 0),
            "Adm Meds": p.get("admission_med_count", 0),
            "High Alert Meds": p.get("high_alert_count", 0),
        })

    df = pd.DataFrame(rows)

    st.markdown(f"### 🎯 Urutan Review Pasien (Top {len(patients)})")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # Quick selector to launch 1-on-1 analysis
    st.markdown("#### 🔍 Buka Analisis Detail Pasien")
    selected_pid = st.selectbox(
        "Pilih Patient ID dari antrean untuk analisis detail & laporan Gemini LLM:",
        options=[p.get("patient_id") for p in patients],
        key="batch_select_pid",
    )

    if st.button("🚀 Buka Laporan Detail Pasien Ini", type="primary"):
        st.session_state["selected_from_batch"] = f"Analisis pasien {selected_pid}"
        st.rerun()


def _fetch_batch_data(limit: int, priority_filter: str | None = None) -> dict:
    """Fetch batch prioritization from API or direct fallback."""
    payload = {"limit": limit}
    if priority_filter:
        payload["priority_filter"] = priority_filter

    try:
        resp = requests.post(f"{API_URL}/prioritize/batch", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        # Fallback direct call
        try:
            from api.services.prioritization_service import prioritize_batch
            return prioritize_batch(limit=limit, priority_filter=priority_filter)
        except Exception as exc:
            return {"error": str(exc)}
