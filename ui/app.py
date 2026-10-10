"""
ui/app.py
----------
⚠️  DEPRECATED — This file is superseded by streamlit_app/app.py

The original form-based UI (16 ML feature fields + medication lists) has been
replaced by a pharmacist-friendly one-chat-input interface per Spec v2.

MIGRATE TO:
    streamlit run streamlit_app/app.py

This file is retained for reference only. It will not receive updates.
See docs/DECISION_LOG.md — UI-001 for the rationale.
"""

import json
import os
import sys
from pathlib import Path

import requests
import streamlit as st

# Pastikan project root ada di sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------

API_URL = os.getenv("PRIOMEDREC_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="PrioMed-Rec",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS — tampilan bersih
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .main-header {
        background: #1e3a5f;
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    .priority-HIGH   { background:#fee2e2; color:#991b1b; padding:6px 14px; border-radius:20px; font-weight:700; }
    .priority-MEDIUM { background:#fef9c3; color:#854d0e; padding:6px 14px; border-radius:20px; font-weight:700; }
    .priority-LOW    { background:#dcfce7; color:#166534; padding:6px 14px; border-radius:20px; font-weight:700; }
    .metric-box { background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 16px; text-align:center; }
    .flag-row { background:#fff7ed; border-left:4px solid #f97316; padding:10px 14px; margin:6px 0; border-radius:4px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cek status LLM dari .env — tampilkan peringatan jika belum dikonfigurasi
# ---------------------------------------------------------------------------

def _check_llm_config() -> tuple[bool, str]:
    """Return (is_configured, message)."""
    from pathlib import Path
    from dotenv import dotenv_values
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return False, "File `.env` tidak ditemukan. Salin `.env.example` ke `.env` terlebih dahulu."
    cfg = dotenv_values(env_path)
    key = cfg.get("LLM_API_KEY", "")
    if not key or key == "your-gemini-api-key-here":
        return False, "LLM_API_KEY belum diisi di file `.env`."
    provider = cfg.get("LLM_PROVIDER", "gemini")
    return True, f"LLM dikonfigurasi: provider=`{provider}`, model=`{cfg.get('LLM_MODEL_NAME','?')}`"

_llm_ok, _llm_msg = _check_llm_config()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-header">
    <h2 style="margin:0">💊 PrioMed-Rec</h2>
    <p style="margin:4px 0 0 0; opacity:0.85">AI-Powered Admission Risk Prioritization & Medication Reconciliation Support</p>
</div>
""", unsafe_allow_html=True)

if not _llm_ok:
    st.warning(
        f"⚠️ **Gemini belum aktif** — {_llm_msg}\n\n"
        "**Cara mengaktifkan:**\n"
        "1. Buka file `.env` di folder proyek\n"
        "2. Isi `LLM_API_KEY=AIza...` dengan API key dari https://aistudio.google.com/app/apikey\n"
        "3. Restart server: `uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload`\n\n"
        "Analisis tetap berjalan (ML + Rule Engine), tapi laporan bahasa natural Gemini tidak tersedia."
    )
else:
    st.success(f"✅ {_llm_msg}")

# ---------------------------------------------------------------------------
# Sidebar — Input Data Pasien
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("🧑‍⚕️ Data Pasien")

    patient_id   = st.text_input("Patient ID",   value="PATIENT-001")
    encounter_id = st.text_input("Encounter ID", value="ENCOUNTER-001")

    st.subheader("📋 Data Klinis")
    age              = st.number_input("Usia (tahun)", min_value=0, max_value=120, value=65)
    gender           = st.selectbox("Jenis Kelamin", ["Perempuan (0)", "Laki-laki (1)"])
    gender_encoded   = 1 if gender.startswith("Laki") else 0
    age_65_plus      = 1 if age >= 65 else 0

    st.subheader("💊 Beban Obat")
    pre_admission_medication_count = st.number_input("Obat sebelum masuk RS", min_value=0, value=6)
    admission_medication_count     = st.number_input("Obat saat masuk RS",    min_value=0, value=7)
    total_medication_count         = st.number_input("Total obat",            min_value=0, value=9)
    new_medication_count           = st.number_input("Obat baru",             min_value=0, value=3)
    discontinued_medication_count  = st.number_input("Obat dihentikan",       min_value=0, value=2)

    st.subheader("⚠️ Faktor Risiko")
    polypharmacy_flag  = st.checkbox("Polifarmasi (≥5 obat)", value=True)
    high_alert_flag    = st.checkbox("Ada obat high-alert",   value=True)
    high_alert_count   = st.number_input("Jumlah obat high-alert", min_value=0, value=2)
    potential_duplicate_candidates = st.number_input("Kandidat duplikasi", min_value=0, value=1)

    st.subheader("🏥 Riwayat Klinis")
    active_condition_count = st.number_input("Kondisi aktif",       min_value=0, value=5)
    prior_encounter_count  = st.number_input("Riwayat kunjungan",   min_value=0, value=14)
    allergy_count          = st.number_input("Jumlah alergi",       min_value=0, value=0)
    has_drug_allergy       = st.checkbox("Ada alergi obat",         value=False)

# ---------------------------------------------------------------------------
# Tab utama — Daftar Obat + Analisis
# ---------------------------------------------------------------------------

tab1, tab2 = st.tabs(["📝 Daftar Obat & Analisis", "❓ Tanya Farmasis (Q&A)"])

with tab1:
    col1, col2 = st.columns(2)

    # --- Obat sebelum masuk RS ---
    with col1:
        st.subheader("💊 Obat Sebelum Masuk RS")
        n_pre = st.number_input("Jumlah obat", min_value=0, max_value=10, value=1, key="n_pre")
        pre_meds = []
        for i in range(int(n_pre)):
            with st.expander(f"Obat #{i+1}", expanded=(i == 0)):
                code = st.text_input("Kode Obat",  value="316049",    key=f"pre_code_{i}")
                name = st.text_input("Nama Obat",  value="warfarin 5 MG", key=f"pre_name_{i}")
                pre_meds.append({"medication_code": code, "medication_name": name})

    # --- Obat saat admission ---
    with col2:
        st.subheader("🏥 Obat Saat Masuk RS")
        n_adm = st.number_input("Jumlah obat", min_value=0, max_value=10, value=0, key="n_adm")
        adm_meds = []
        for i in range(int(n_adm)):
            with st.expander(f"Obat #{i+1}", expanded=(i == 0)):
                code = st.text_input("Kode Obat", value="", key=f"adm_code_{i}")
                name = st.text_input("Nama Obat", value="", key=f"adm_name_{i}")
                adm_meds.append({"medication_code": code, "medication_name": name})

    st.divider()

    # --- Tombol Analisis ---
    run_btn = st.button("🔍 Analisis Pasien", type="primary", use_container_width=True)

    if run_btn:
        payload = {
            "patient_id":   patient_id,
            "encounter_id": encounter_id,
            "age":          float(age),
            "age_65_plus":  age_65_plus,
            "gender_encoded": gender_encoded,
            "pre_admission_medication_count": int(pre_admission_medication_count),
            "admission_medication_count":     int(admission_medication_count),
            "total_medication_count":         int(total_medication_count),
            "new_medication_count":           int(new_medication_count),
            "discontinued_medication_count":  int(discontinued_medication_count),
            "polypharmacy_flag":  int(polypharmacy_flag),
            "high_alert_flag":    int(high_alert_flag),
            "high_alert_count":   int(high_alert_count),
            "potential_duplicate_candidates": int(potential_duplicate_candidates),
            "active_condition_count": int(active_condition_count),
            "prior_encounter_count":  int(prior_encounter_count),
            "allergy_count":          int(allergy_count),
            "has_drug_allergy":       int(has_drug_allergy),
            "pre_admission_meds": pre_meds,
            "admission_meds":     adm_meds,
        }

        with st.spinner("⏳ Menganalisis data pasien dan membuat laporan..."):
            try:
                resp = requests.post(f"{API_URL}/analyze", json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.ConnectionError:
                st.error(f"❌ Tidak bisa terhubung ke server FastAPI di `{API_URL}`.\n\nPastikan server sudah berjalan:\n```\nuvicorn api.main:app --host 0.0.0.0 --port 8000 --reload\n```")
                st.stop()
            except requests.exceptions.HTTPError as e:
                st.error(f"❌ Server error: {e.response.status_code} — {e.response.text}")
                st.stop()
            except Exception as e:
                st.error(f"❌ Error tidak terduga: {e}")
                st.stop()

        # --- Tampilkan Hasil ---
        st.success("✅ Analisis selesai!")

        # Baris metrik utama
        priority     = data["priority"]
        risk_pct     = round(data["risk_probability"] * 100, 1)
        n_flags      = len(data.get("flags", []))
        priority_map = {"HIGH": "🔴 TINGGI", "MEDIUM": "🟡 SEDANG", "LOW": "🟢 RENDAH"}
        priority_str = priority_map.get(priority, priority)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🎯 Prioritas",       priority_str)
        m2.metric("📊 Risiko",          f"{risk_pct}%")
        m3.metric("⚠️ Potensi Masalah", f"{n_flags} flag")
        m4.metric("🤖 Model",           data.get("model_version", "-"))

        st.divider()

        # Laporan Gemini
        st.subheader("📋 Laporan Analisis")
        if data.get("report_available"):
            st.markdown(data["report"])
        else:
            st.warning("⚠️ LLM tidak tersedia — menampilkan laporan ringkas (tanpa Gemini).")
            st.markdown(data["report"])

        # Tabel SHAP features
        if data.get("top_features"):
            st.subheader("📊 Faktor Paling Berpengaruh (SHAP)")
            import pandas as pd
            feat_df = pd.DataFrame(data["top_features"])[["feature", "value", "shap_value", "direction"]]
            feat_df.columns = ["Fitur", "Nilai", "SHAP Score", "Arah"]
            st.dataframe(feat_df, use_container_width=True, hide_index=True)

        # Tabel flags
        if data.get("flags"):
            st.subheader("🚨 Detail Potensi Masalah Obat")
            for flag in data["flags"]:
                sev_color = "🔴" if flag.get("severity") in ("HIGH", "CRITICAL") else "🟡"
                st.markdown(
                    f"""<div class="flag-row">
                    {sev_color} <strong>{flag.get('flag_type','?')}</strong> — 
                    {flag.get('medication_name') or flag.get('medication_code','?')} 
                    &nbsp;|&nbsp; Severity: <strong>{flag.get('severity','?')}</strong>
                    &nbsp;|&nbsp; Rule: {flag.get('rule_id','?')}<br>
                    <small>{flag.get('evidence','')}</small><br>
                    <small>✅ Wajib diverifikasi farmasis</small>
                    </div>""",
                    unsafe_allow_html=True,
                )
        elif run_btn:
            st.info("✅ Tidak ada potensi masalah obat terdeteksi oleh rule engine.")

        # Expander JSON mentah
        with st.expander("🔧 Data JSON Lengkap (untuk developer)"):
            st.json(data)

# ---------------------------------------------------------------------------
# Tab Q&A
# ---------------------------------------------------------------------------

with tab2:
    st.subheader("❓ Tanya Jawab dengan Gemini")
    st.caption("Ajukan pertanyaan tentang pasien — Gemini menjawab berdasarkan data yang diisi di sidebar.")

    question = st.text_area(
        "Pertanyaan Anda:",
        placeholder="Contoh: Mengapa pasien ini prioritas tinggi? Obat apa yang berpotensi bermasalah?",
        height=100,
    )

    qa_btn = st.button("💬 Tanya Gemini", type="primary")

    if qa_btn and question.strip():
        payload_qa = {
            "patient_id":   patient_id,
            "encounter_id": encounter_id,
            "age":          float(age),
            "age_65_plus":  age_65_plus,
            "gender_encoded": gender_encoded,
            "pre_admission_medication_count": int(pre_admission_medication_count),
            "admission_medication_count":     int(admission_medication_count),
            "total_medication_count":         int(total_medication_count),
            "new_medication_count":           int(new_medication_count),
            "discontinued_medication_count":  int(discontinued_medication_count),
            "polypharmacy_flag":  int(polypharmacy_flag),
            "high_alert_flag":    int(high_alert_flag),
            "high_alert_count":   int(high_alert_count),
            "potential_duplicate_candidates": int(potential_duplicate_candidates),
            "active_condition_count": int(active_condition_count),
            "prior_encounter_count":  int(prior_encounter_count),
            "allergy_count":          int(allergy_count),
            "has_drug_allergy":       int(has_drug_allergy),
            "pre_admission_meds": [],
            "admission_meds":     [],
            "pharmacist_question": question.strip(),
        }

        with st.spinner("💬 Gemini sedang menjawab..."):
            try:
                resp = requests.post(f"{API_URL}/analyze", json=payload_qa, timeout=60)
                resp.raise_for_status()
                data_qa = resp.json()
                st.markdown("### Jawaban Gemini")
                st.markdown(data_qa["report"])
            except Exception as e:
                st.error(f"❌ Error: {e}")

    elif qa_btn:
        st.warning("Tulis pertanyaan terlebih dahulu.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "⚠️ **Clinical Safety Notice:** Sistem ini adalah *decision support only*. "
    "Farmasis **selalu** membuat keputusan akhir. Tidak untuk keputusan terapi otonom. "
    "| PrioMed-Rec v1.0.0"
)
