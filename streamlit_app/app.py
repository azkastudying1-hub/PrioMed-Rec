"""
streamlit_app/app.py
---------------------
PrioMed-Rec — Pharmacist-facing Streamlit UI (v2)

ONE CHAT INPUT interface.

Examples:
  "Analisis pasien P001"
  "Kenapa pasien P001 diprioritaskan?"
  "Apa potensi medication discrepancy pasien P001?"
  "Berikan ringkasan medication reconciliation P001"

Architecture:
  User input → Chat Handler → Langflow Orchestrator
    → FastAPI /analyze (patient_id-driven, internal feature construction)
    → ML + Rule Engine + LLM
    → Structured Result
    → Pharmacist Result View (8 sections)
    → APPROVE / REJECT / EDIT

Run:
    streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="PrioMed-Rec",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a8a 100%);
        color: white;
        padding: 1.2rem 1.8rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
    }
    .main-header h2 { margin: 0; font-size: 1.6rem; }
    .main-header p  { margin: 4px 0 0 0; opacity: 0.85; font-size: 0.95rem; }
    .chat-hint {
        background: #f7f8fa;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 0.88rem;
        color: #57606a;
        margin-bottom: 12px;
    }
    .stTextInput > div > div > input {
        font-size: 1rem;
        padding: 10px 14px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-header">
    <h2>💊 PrioMed-Rec</h2>
    <p>AI-assisted Admission Medication Reconciliation Prioritization — Decision Support for Clinical Pharmacists</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API health check (sidebar)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ System Status")
    if st.button("🔄 Check API Health"):
        from streamlit_app.utils.langflow_client import check_api_health
        healthy, msg = check_api_health()
        if healthy:
            st.success(f"✅ {msg}")
        else:
            st.error(f"❌ {msg}")

    st.divider()
    st.markdown("**Instructions:**")
    st.markdown(
        "1. Type a patient query in the chat box\n"
        "2. Press Enter or click **Analyze**\n"
        "3. Review the result\n"
        "4. Click APPROVE / EDIT / REJECT"
    )
    st.divider()

    pharmacist_id = st.text_input(
        "Pharmacist ID",
        value=st.session_state.get("pharmacist_id", "PHARM-001"),
        key="pharmacist_id_input",
    )
    st.session_state["pharmacist_id"] = pharmacist_id

    st.divider()
    st.markdown("**Example queries:**")
    examples = [
        "Analisis pasien P001",
        "Kenapa pasien P001 diprioritaskan?",
        "Apa potensi discrepancy pasien P001?",
        "Ringkasan medication reconciliation P001",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex[:15]}", use_container_width=True):
            st.session_state["last_query"] = ex

# ---------------------------------------------------------------------------
# Navigation Tabs
# ---------------------------------------------------------------------------

tab_queue, tab_single = st.tabs([
    "📋 Ranked Priority Queue (Worklist Puluhan/Ratusan Pasien)",
    "🔍 Analisis Detail 1 Pasien & Laporan LLM",
])

# ── TAB 1: BATCH QUEUE WORKLIST ─────────────────────────────────────────────
with tab_queue:
    from streamlit_app.components.batch_queue import render_batch_queue
    render_batch_queue()

# ── TAB 2: SINGLE PATIENT DEEP DIVE ─────────────────────────────────────────
with tab_single:
    st.markdown(
        '<div class="chat-hint">'
        '💬 Ketik query pasien, contoh: <code>Analisis pasien db586118-697b-59be-a1ac-2d5a6b6717f1</code> '
        'atau pilih pasien dari Tab Worklist di atas.'
        '</div>',
        unsafe_allow_html=True,
    )

    # Pre-fill from sidebar example button or batch queue selection
    default_query = st.session_state.pop("last_query", "")
    if not default_query and "selected_from_batch" in st.session_state:
        default_query = st.session_state.pop("selected_from_batch")

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_input = st.text_input(
            "Query",
            value=default_query,
            placeholder="Contoh: Analisis pasien db586118-697b-59be-a1ac-2d5a6b6717f1",
            label_visibility="collapsed",
            key="chat_input",
        )
    with col_btn:
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)

    # Trigger analysis
    if analyze_btn or (user_input and user_input != st.session_state.get("_last_processed")):
        if user_input.strip():
            st.session_state["_last_processed"] = user_input

            with st.spinner("⏳ Menganalisis... (Langflow → FastAPI → ML + LLM)"):
                from streamlit_app.components.chat_handler import handle_chat
                result = handle_chat(user_input)

            st.session_state["last_result"] = result

            source = result.get("_source", "")
            if source == "langflow":
                st.info("🔗 Hasil dari Langflow orchestrator")
            elif source == "fastapi_direct":
                st.warning("⚡ Langflow tidak tersedia — hasil langsung dari FastAPI")

    result = st.session_state.get("last_result")

    if result:
        if result.get("error") == "connection_failed":
            st.error(result.get("report", "Server tidak tersedia."))
            st.code("uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")
        elif result.get("error") == "patient_not_found":
            st.error(result.get("report", "Pasien tidak ditemukan."))
        elif result.get("error") == "no_patient_id":
            st.warning(result.get("report", "Patient ID tidak ditemukan."))
        elif result.get("error") == "empty_input":
            st.info(result.get("report", "Ketik query untuk memulai."))
        else:
            if result.get("_source") == "langflow" and not result.get("review_priority"):
                st.subheader("📋 Hasil Analisis")
                st.markdown(result.get("report", ""))
            else:
                from streamlit_app.components.result_view import render_result
                render_result(result)

            st.divider()

            from streamlit_app.components.review_panel import render_review_panel
            render_review_panel(
                data=result,
                pharmacist_id=st.session_state.get("pharmacist_id", "PHARM-001"),
                key_prefix="main_review",
            )
    else:
        st.markdown(
            """
            <div style="text-align:center;padding:60px 20px;color:#57606a;">
                <div style="font-size:3rem;">💊</div>
                <h3 style="color:#1f2328;">Siap untuk analisis detail 1-on-1</h3>
                <p>Ketik ID pasien di atas atau pilih dari Tab Antrean Prioritas Pasien di sebelah kiri.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.markdown(
    "<div style='text-align:center;font-size:0.8rem;color:#57606a;'>"
    "⚠️ <strong>Clinical Safety Notice:</strong> PrioMed-Rec adalah <em>decision-support prototype</em>. "
    "Farmasis <strong>selalu</strong> membuat keputusan akhir. "
    "Tidak untuk keputusan terapi otonom. "
    "Data Synthea synthetic — bukan data pasien nyata. "
    "| PrioMed-Rec v2.0.0 | model-0.3.0"
    "</div>",
    unsafe_allow_html=True,
)
