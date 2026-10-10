"""
streamlit_app/components/result_view.py
-----------------------------------------
Pharmacist-friendly result renderer for PrioMed-Rec.

Renders the 8 mandatory sections from the /analyze response:
  1. Patient Summary
  2. Admission Summary
  3. Medication Review Priority (badge)
  4. Predicted Discrepancy Likelihood
  5. Top Contributing Factors (SHAP table)
  6. Potential Medication Discrepancies (flag cards)
  7. Model/Rule Explanation (LLM report)
  8. Safety Notice
"""

from __future__ import annotations

import streamlit as st


_PRIORITY_CSS = {
    "HIGH":   ("🔴", "#fee2e2", "#991b1b", "TINGGI — Segera review"),
    "MEDIUM": ("🟡", "#fef9c3", "#854d0e", "SEDANG — Review hari ini"),
    "LOW":    ("🟢", "#dcfce7", "#166534", "RENDAH"),
}


def render_result(data: dict) -> None:
    """
    Render the full pharmacist result view for an /analyze response dict.
    """
    patient_id   = data.get("patient_id", "—")
    encounter_id = data.get("encounter_id", "—")
    priority     = data.get("review_priority") or data.get("priority", "LOW")
    likelihood   = data.get("discrepancy_likelihood") or data.get("risk_probability", 0.0)
    model_ver    = data.get("model_version", "—")
    rule_ver     = data.get("rule_version", "—")
    top_features = data.get("top_features", [])
    flags        = data.get("flags", [])
    report       = data.get("report", "")
    report_ok    = data.get("report_available", False)

    emoji, bg, fg, label = _PRIORITY_CSS.get(priority, ("⚪", "#f7f8fa", "#1f2328", priority))

    # ── 1. Patient Summary ─────────────────────────────────────────────────
    st.subheader("👤 Patient Summary")
    c1, c2 = st.columns(2)
    c1.markdown(f"**Patient ID:** `{patient_id}`")
    c2.markdown(f"**Encounter ID:** `{encounter_id}`")

    # ── 2. Admission Summary ───────────────────────────────────────────────
    enc_meta = data.get("encounter_meta", {})
    if enc_meta:
        with st.expander("🏥 Admission Summary", expanded=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("Encounter Class", enc_meta.get("encounter_class", "—"))
            col2.metric("Admission Date",  enc_meta.get("encounter_start", "—")[:10] if enc_meta.get("encounter_start") else "—")
            col3.metric("Age",             f"{enc_meta.get('age', '—')} yr" if enc_meta.get("age") else "—")
    else:
        st.markdown(f"**Encounter:** `{encounter_id}`")

    st.divider()

    # ── 3 + 4. Priority badge + Likelihood ────────────────────────────────
    col_prio, col_like, col_flags = st.columns(3)

    with col_prio:
        st.markdown("##### 🎯 Medication Review Priority")
        st.markdown(
            f'<div style="background:{bg};color:{fg};padding:10px 18px;'
            f'border-radius:20px;font-weight:700;font-size:1.1rem;'
            f'display:inline-block;">{emoji} {label}</div>',
            unsafe_allow_html=True,
        )

    with col_like:
        st.markdown("##### 📊 Predicted Discrepancy Likelihood")
        pct = round(likelihood * 100, 1)
        st.metric(label="", value=f"{pct}%")

    with col_flags:
        st.markdown("##### ⚠️ Potential Discrepancies")
        st.metric(label="", value=f"{len(flags)} flag(s)")

    st.divider()

    # ── 5. Top Contributing Factors (SHAP) ────────────────────────────────
    if top_features:
        st.subheader("📊 Top Contributing Factors (SHAP)")
        import pandas as pd
        feat_df = pd.DataFrame(top_features)[
            [c for c in ["feature", "value", "shap_value", "direction"] if c in pd.DataFrame(top_features).columns]
        ]
        feat_df.columns = [c.replace("_", " ").title() for c in feat_df.columns]
        st.dataframe(feat_df, use_container_width=True, hide_index=True)

    # ── 6. Potential Medication Discrepancies ──────────────────────────────
    st.subheader("🚨 Potential Medication Discrepancies")
    if flags:
        for flag in flags:
            ftype    = flag.get("flag_type", "?")
            med_name = flag.get("medication_name") or flag.get("medication_code", "?")
            severity = flag.get("severity", "REVIEW")
            evidence = flag.get("evidence", "")
            rule_id  = flag.get("rule_id", "")
            sev_emoji = "🔴" if severity in ("HIGH", "CRITICAL") else "🟡"
            st.markdown(
                f"""<div style="background:#fff7ed;border-left:4px solid #f97316;
                padding:10px 14px;margin:6px 0;border-radius:4px;">
                {sev_emoji} <strong>{ftype}</strong> — {med_name}
                &nbsp;|&nbsp; Severity: <strong>{severity}</strong>
                &nbsp;|&nbsp; Rule: <code>{rule_id}</code><br>
                <small>{evidence}</small><br>
                <small>✅ <strong>Wajib diverifikasi farmasis</strong></small>
                </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.success("✅ Tidak ada potensi masalah obat terdeteksi oleh rule engine.")

    st.divider()

    # ── 7. SBAR Clinical Review Draft ──────────────────────────────────────
    st.subheader("📋 Draf Laporan Telaah Klinis SBAR (Siap Telaah Apoteker)")
    _LLM_FAIL_MARKERS = (
        "LLM service unavailable",
        "LLM response was blocked",
        "LLM tidak tersedia",
        "[Error: RuntimeError]",
        "[Error: LLMError]",
    )
    _report_is_llm = report and not any(m in report for m in _LLM_FAIL_MARKERS)

    if _report_is_llm:
        st.markdown(report)
    else:
        st.warning("⚠️ Mode Fallback Berbasis Aturan (Gemini kuota tercapai atau tidak aktif).")
        if report:
            st.markdown(report)
        else:
            st.info("Penjelasan SBAR tidak tersedia.")

    if report:
        with st.expander("📋 Salin Teks Draf SBAR (Teks Polos Siap Copy-Paste)", expanded=False):
            st.code(report, language="markdown")


    # Model metadata (collapsed by default)
    with st.expander("🔧 Metadata (model & rule versions)", expanded=False):
        st.markdown(f"- **Model version:** `{model_ver}`")
        st.markdown(f"- **Rule version:** `{rule_ver}`")
        st.markdown(
            "⚠️ Metrics reflect SYNTHETIC label performance. "
            "Not validated for clinical use."
        )

    # ── 8. Safety Notice ──────────────────────────────────────────────────
    st.markdown(
        """<div style="background:#fef9c3;border:1px solid #f59e0b;border-radius:6px;
        padding:12px 16px;margin-top:16px;">
        ⚠️ <strong>Safety Notice:</strong> PrioMed-Rec adalah <em>decision-support prototype</em>.
        Sistem ini <strong>tidak menggantikan</strong> penilaian klinis farmasis.
        Setiap potensi discrepancy <strong>wajib diverifikasi</strong> oleh farmasis.
        Tidak untuk digunakan dalam setting klinis nyata tanpa validasi lebih lanjut.
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Optional: raw JSON (developer view) ────────────────────────────────
    with st.expander("🔧 Raw JSON (developer view)", expanded=False):
        st.json(data)
