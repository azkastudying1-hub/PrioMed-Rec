"""
api/routes/analyze.py
----------------------
POST /analyze — One-shot patient analysis endpoint (v2 — patient_id-driven).

Two call modes:
  1. Patient-ID mode (recommended — Streamlit / Langflow):
       { "patient_id": "P001" }
       { "patient_id": "P001", "encounter_id": "E123", "question": "Kenapa prioritas tinggi?" }
     Feature construction is done internally. Caller never provides feature fields.

  2. Expert/developer mode (legacy — all 16 features + meds supplied by caller):
       Full AnalyzeRequest body with all numeric feature fields.
     Used for testing and direct API access.

Output: AnalyzeResponse — structured ML/rule data + LLM-generated Markdown report.

Clinical safety:
  - priority and discrepancy_likelihood come from ML only — LLM cannot change them.
  - All discrepancy flags carry verification_required=True.
  - LLM unavailability returns structured data without a report (no fabrication).
  - Terminology: "Medication Review Priority" / "Predicted Discrepancy Likelihood"
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.schemas import MedicationItem, TopFeature, DiscrepancyFlag

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """
    Unified analysis request.

    Simple mode: supply patient_id only (and optional encounter_id + question).
    Expert mode: supply all 16 feature fields + medication lists directly.
    """

    # ── Simple mode (patient_id-driven) ──────────────────────────────────
    patient_id:   str = Field("", description="Patient identifier (simple mode)")
    encounter_id: str = Field("", description="Encounter identifier (optional)")
    question:     Optional[str] = Field(None, description="Optional pharmacist question for Q&A mode")

    # ── Expert/developer mode — 16 ML features (all optional with defaults) ─
    # When patient_id is provided and features are 0/default, patient_resolver is used.
    age:                            Optional[float] = Field(None, ge=0)
    age_65_plus:                    Optional[int]   = Field(None, ge=0, le=1)
    gender_encoded:                 Optional[int]   = Field(None, ge=0, le=1)
    pre_admission_medication_count: Optional[int]   = Field(None, ge=0)
    admission_medication_count:     Optional[int]   = Field(None, ge=0)
    total_medication_count:         Optional[int]   = Field(None, ge=0)
    new_medication_count:           Optional[int]   = Field(None, ge=0)
    discontinued_medication_count:  Optional[int]   = Field(None, ge=0)
    polypharmacy_flag:              Optional[int]   = Field(None, ge=0, le=1)
    high_alert_flag:                Optional[int]   = Field(None, ge=0, le=1)
    high_alert_count:               Optional[int]   = Field(None, ge=0)
    potential_duplicate_candidates: Optional[int]   = Field(None, ge=0)
    active_condition_count:         Optional[int]   = Field(None, ge=0)
    prior_encounter_count:          Optional[int]   = Field(None, ge=0)
    allergy_count:                  Optional[int]   = Field(None, ge=0)
    has_drug_allergy:               Optional[int]   = Field(None, ge=0, le=1)

    # Medication lists (expert mode)
    pre_admission_meds: List[MedicationItem] = Field(default=[])
    admission_meds:     List[MedicationItem] = Field(default=[])

    # Legacy field for backward compatibility
    pharmacist_question: Optional[str] = Field(None)


class AnalyzeResponse(BaseModel):
    """Combined analysis result with Gemini-generated Markdown report."""
    patient_id:                 str
    encounter_id:               str
    # Structured ML/rule data
    discrepancy_likelihood:     float   = Field(description="Predicted Discrepancy Likelihood [0-1]")
    review_priority:            str     = Field(description="Medication Review Priority: HIGH/MEDIUM/LOW")
    model_version:              str
    top_features:               List[TopFeature] = []
    flags:                      List[DiscrepancyFlag] = []
    rule_version:               str
    # LLM-generated human-readable report (Markdown)
    report:                     str
    report_available:           bool
    # Backward-compat alias (internal field name; kept for existing tests)
    risk_probability:           float   = Field(description="Alias for discrepancy_likelihood")
    priority:                   str     = Field(description="Alias for review_priority")


# ---------------------------------------------------------------------------
# Feature key lists
# ---------------------------------------------------------------------------
# All 16 keys accepted in the request body (kept for backward-compat parsing)
_FEATURE_KEYS = [
    "age", "age_65_plus", "gender_encoded",
    "pre_admission_medication_count", "admission_medication_count",
    "total_medication_count", "new_medication_count", "discontinued_medication_count",
    "polypharmacy_flag", "high_alert_flag", "high_alert_count",
    "potential_duplicate_candidates", "active_condition_count",
    "prior_encounter_count", "allergy_count", "has_drug_allergy",
]

# Forbidden features (label-adjacent; must never reach inference)
_FORBIDDEN_FEATURES = {
    "discontinued_medication_count",
    "potential_duplicate_candidates",
    "pre_admission_medication_count",
    "admission_medication_count",
    "new_medication_count",
    "total_medication_count",
}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalyzeResponse, tags=["analyze"])
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    One-shot patient analysis: prioritize + detect discrepancies + LLM report.

    **Simple mode** (recommended):
    ```json
    { "patient_id": "P001" }
    ```
    Feature construction is fully automatic — the caller only provides the
    patient ID. The system resolves the latest admission encounter, builds
    the 16-feature vector, runs ML prioritization, runs the discrepancy
    rule engine, and generates a Gemini explanation.

    **Expert mode** (developer/testing):
    Supply all 16 numeric feature fields directly (legacy behavior).

    Returns structured ML/rule-engine data AND a human-readable Markdown
    report labeled with "Medication Review Priority" and
    "Predicted Discrepancy Likelihood" terminology.
    """
    req = request.model_dump()

    # ── Resolve pharmacist_question / question aliases ─────────────────────
    question = req.get("question") or req.get("pharmacist_question")

    # ── Determine call mode ────────────────────────────────────────────────
    # Patient-ID mode: patient_id provided and no explicit feature fields given
    patient_id = (req.get("patient_id") or "").strip()
    has_features = any(req.get(k) is not None for k in _FEATURE_KEYS)

    resolved_context: dict = {}
    pre_meds: list = []
    adm_meds: list = []

    if patient_id and not has_features:
        # ── Simple mode: resolve patient from data ─────────────────────────
        encounter_id = (req.get("encounter_id") or "").strip() or None
        try:
            from api.services.patient_service import get_patient_context
            resolved_context = get_patient_context(patient_id, encounter_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Patient resolution error: {exc}") from exc

        # Override req fields with resolved data
        req["patient_id"]   = resolved_context["patient_id"]
        req["encounter_id"] = resolved_context["encounter_id"]
        feature_dict        = resolved_context["feature_vector"]
        pre_meds            = resolved_context["pre_admission_meds"]
        adm_meds            = resolved_context["admission_meds"]

    else:
        # ── Expert mode: use caller-provided fields ────────────────────────
        if not patient_id:
            req["patient_id"] = "PATIENT-UNKNOWN"

        # Reject explicitly-supplied forbidden features (non-None values)
        forbidden_supplied = [
            k for k in _FORBIDDEN_FEATURES
            if req.get(k) is not None
        ]
        if forbidden_supplied:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"FORBIDDEN features supplied: {sorted(forbidden_supplied)}. "
                    "These are label-adjacent features excluded from inference. "
                    "Use POST /analyze with patient_id only (simple mode). "
                    "See docs/feature_provenance.md."
                ),
            )

        # Build feature dict from SAFE features only (strip forbidden entirely)
        safe_keys = [k for k in _FEATURE_KEYS if k not in _FORBIDDEN_FEATURES]
        feature_dict = {k: (req[k] if req.get(k) is not None else 0) for k in safe_keys}
        pre_meds     = req.get("pre_admission_meds", [])
        adm_meds     = req.get("admission_meds", [])

    # ── 1. Prioritization (ML + SHAP) ──────────────────────────────────────
    try:
        from api.services.prioritization_service import prioritize as _prioritize
        prio_result = _prioritize(
            feature_dict=feature_dict,
            encounter_id=req["encounter_id"],
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Prioritization error: {exc}") from exc

    # ── 2. Discrepancy detection (rule engine) ─────────────────────────────
    try:
        from api.services.discrepancy_service import detect_discrepancies as _detect
        disc_result = _detect(
            patient_id=req["patient_id"],
            encounter_id=req["encounter_id"],
            pre_admission_meds=pre_meds,
            admission_meds=adm_meds,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Discrepancy detection error: {exc}") from exc

    # ── 3. Determine encounter metadata for LLM context ───────────────────
    enc_meta = resolved_context.get("encounter_meta", {})
    age      = enc_meta.get("age") or feature_dict.get("age", 0)
    gender_code = feature_dict.get("gender_encoded", 0)
    gender_str  = "Laki-laki" if gender_code == 1 else "Perempuan"

    # ── 4. Build LLM context ───────────────────────────────────────────────
    llm_context = {
        "patient": {
            "patient_id":      req["patient_id"],
            "encounter_id":    req["encounter_id"],
            "age":             age,
            "gender":          gender_str,
            "encounter_class": enc_meta.get("encounter_class", ""),
            "encounter_start": enc_meta.get("encounter_start", ""),
        },
        "risk_model": {
            "discrepancy_likelihood": prio_result["risk_probability"],
            "review_priority":        prio_result["priority"],
            "model_version":          prio_result["model_version"],
            "top_features":           prio_result["top_features"],
        },
        "medication_burden": {
            # Only SAFE features are in feature_dict (forbidden features excluded by InferenceGuard policy)
            k: feature_dict.get(k, 0) for k in [
                "polypharmacy_flag", "high_alert_flag", "high_alert_count",
            ]
        },
        "discrepancy_engine": {
            "rule_version": disc_result["rule_version"],
            "flags":        disc_result["flags"],
        },
        "pre_admission_meds": pre_meds,
        "admission_meds":     adm_meds,
    }

    # ── 5. Generate LLM report ─────────────────────────────────────────────
    # Use subprocess-based wrapper so module cache in uvicorn never interferes.
    print("[ANALYZE_V2] using call_llm_fresh", flush=True)
    report_available = False
    report = _fallback_report(prio_result, disc_result, req,
                              pre_meds=pre_meds, adm_meds=adm_meds,
                              enc_meta=enc_meta, feature_dict=feature_dict)

    from api.services.llm_service import call_llm_fresh
    llm_ok, llm_text = call_llm_fresh(llm_context, question=question)
    print(f"[ANALYZE_V2] llm_ok={llm_ok} text_preview={llm_text[:60]!r}", flush=True)
    if llm_ok:
        report = llm_text
        report_available = True
    else:
        report = _fallback_report(
            prio_result, disc_result, req,
            pre_meds=pre_meds, adm_meds=adm_meds,
            enc_meta=enc_meta, feature_dict=feature_dict,
            llm_error=llm_text,
        )

    # risk_probability and priority kept for backward compat
    return AnalyzeResponse(
        patient_id=req["patient_id"],
        encounter_id=req["encounter_id"],
        discrepancy_likelihood=prio_result["risk_probability"],
        review_priority=prio_result["priority"],
        risk_probability=prio_result["risk_probability"],
        priority=prio_result["priority"],
        model_version=prio_result["model_version"],
        top_features=prio_result["top_features"],
        flags=disc_result["flags"],
        rule_version=disc_result["rule_version"],
        report=report,
        report_available=report_available,
    )


# ---------------------------------------------------------------------------
# Fallback report (when LLM is unavailable) — Full SBAR
# ---------------------------------------------------------------------------

def _fallback_report(
    prio: dict,
    disc: dict,
    req: dict,
    *,
    pre_meds: list | None = None,
    adm_meds: list | None = None,
    enc_meta: dict | None = None,
    feature_dict: dict | None = None,
    llm_error: str | None = None,
) -> str:
    """
    Generate a comprehensive, fully-populated SBAR Markdown report without LLM.
    All available patient data (demographics, medication names, SHAP, flags) is included.
    """
    pre_meds     = pre_meds or req.get("pre_admission_meds", []) or []
    adm_meds     = adm_meds or req.get("admission_meds", []) or []
    enc_meta     = enc_meta or {}
    feature_dict = feature_dict or {}

    priority  = prio.get("priority", "LOW")
    risk_pct  = round(prio.get("risk_probability", 0) * 100, 1)
    flags     = disc.get("flags", [])
    top_feats = prio.get("top_features", [])

    patient_id   = req.get("patient_id", "-")
    encounter_id = req.get("encounter_id", "-")

    # Demographics
    age          = enc_meta.get("age") or feature_dict.get("age", "-")
    gender_code  = feature_dict.get("gender_encoded", -1)
    gender_str   = "Laki-laki" if gender_code == 1 else ("Perempuan" if gender_code == 0 else "-")
    enc_class    = enc_meta.get("encounter_class", "-")
    enc_start    = enc_meta.get("encounter_start", "")
    enc_date     = enc_start[:10] if enc_start else "-"

    priority_label = {
        "HIGH":   "🔴 TINGGI — Segera review",
        "MEDIUM": "🟡 SEDANG — Review hari ini",
        "LOW":    "🟢 RENDAH — Monitor rutin",
    }.get(priority, priority)

    # Feature flags
    polypharmacy = feature_dict.get("polypharmacy_flag", 0)
    high_alert   = feature_dict.get("high_alert_flag", 0)
    ha_count     = feature_dict.get("high_alert_count", 0)
    allergy_cnt  = feature_dict.get("allergy_count", 0)
    has_allergy  = feature_dict.get("has_drug_allergy", 0)
    cond_count   = feature_dict.get("active_condition_count", 0)
    prior_enc    = feature_dict.get("prior_encounter_count", 0)

    # ── Helper: render med list ──────────────────────────────────────────
    def _med_list(meds: list, label: str) -> list[str]:
        if not meds:
            return [f"- *{label} tidak tersedia dalam data.*"]
        lines = []
        for i, m in enumerate(meds[:20], 1):
            if isinstance(m, dict):
                name = m.get("medication_name") or m.get("medication_code") or m.get("name", "—")
                dose = m.get("dose") or m.get("dosage", "")
                route = m.get("route", "")
                freq  = m.get("frequency", "")
                parts = [p for p in [dose, route, freq] if p]
                detail = f" ({', '.join(parts)})" if parts else ""
                lines.append(f"   {i}. **{name}**{detail}")
            else:
                lines.append(f"   {i}. {m}")
        if len(meds) > 20:
            lines.append(f"   *... dan {len(meds)-20} obat lainnya.*")
        return lines

    # ── Helper: SHAP direction label ─────────────────────────────────────
    def _dir(tf: dict) -> str:
        d = tf.get("direction", "")
        if d == "increases_risk":
            return "↑ **menaikkan risiko**"
        if d == "decreases_risk":
            return "↓ menurunkan risiko"
        return "—"

    # ────────────────────────────────────────────────────────────────────
    # Build SBAR Markdown
    # ────────────────────────────────────────────────────────────────────
    lines = [
        "## 📋 DRAF TELAAH KLINIS SBAR (SIAP TELAAH APOTEKER)",
        "",
        "> **Catatan:** Laporan ini dihasilkan otomatis oleh sistem PrioMed-Rec sebagai"
        " *decision support*. Seluruh temuan **wajib diverifikasi** oleh apoteker klinis.",
        "",
        "---",
        "",
        # ── S ────────────────────────────────────────────────────────────
        "### 🔴 S — Situation *(Kondisi Saat Ini)*",
        "",
        f"| Field | Detail |",
        f"|-------|--------|",
        f"| **Patient ID** | `{patient_id}` |",
        f"| **Encounter ID** | `{encounter_id}` |",
        f"| **Usia / Jenis Kelamin** | {age} thn, {gender_str} |",
        f"| **Kelas Encounter** | {enc_class} |",
        f"| **Tanggal Masuk** | {enc_date} |",
        f"| **Medication Review Priority** | {priority_label} |",
        f"| **Predicted Discrepancy Likelihood** | **{risk_pct}%** |",
        f"| **Potensi Diskrepansi Terdeteksi** | **{len(flags)} item** |",
        "",
        "---",
        "",
        # ── B ────────────────────────────────────────────────────────────
        "### 🏥 B — Background *(Riwayat Klinis & Beban Obat)*",
        "",
        "**Profil Beban Obat:**",
        "",
        f"| Indikator | Nilai |",
        f"|-----------|-------|",
        f"| Obat Pra-Admisi (PAML) | **{len(pre_meds)} obat** |",
        f"| Obat Saat Admisi (AML) | **{len(adm_meds)} obat** |",
        f"| Status Polifarmasi | {'✅ Ya (≥5 obat)' if polypharmacy else '❌ Tidak'} |",
        f"| Obat High-Alert | {'⚠️ Ada — ' + str(ha_count) + ' item' if high_alert else '✅ Tidak ada'} |",
        f"| Riwayat Alergi Obat | {'⚠️ Ada — ' + str(allergy_cnt) + ' item' if has_allergy else '✅ Tidak ada'} |",
        f"| Kondisi Aktif (EHR) | {cond_count} kondisi |",
        f"| Riwayat Rawat Inap Sebelumnya | {prior_enc} kali |",
        "",
    ]

    # Daftar obat pra-admisi
    lines.append("**Daftar Obat Pra-Admisi (PAML):**")
    lines.extend(_med_list(pre_meds, "Data obat pra-admisi"))
    lines.append("")

    # Daftar obat admisi
    lines.append("**Daftar Obat Saat Admisi (AML):**")
    lines.extend(_med_list(adm_meds, "Data obat admisi"))

    lines += [
        "",
        "---",
        "",
        # ── A ────────────────────────────────────────────────────────────
        "### 📊 A — Assessment *(Analisis & Temuan)*",
        "",
        "#### 🔬 Faktor Pemicu Risiko Utama — Top SHAP Features",
        "",
    ]

    if top_feats:
        lines += [
            "| # | Fitur | Nilai Pasien | SHAP | Kontribusi |",
            "|---|-------|-------------|------|------------|",
        ]
        for i, tf in enumerate(top_feats[:5], 1):
            feat_name = tf.get("feature", "").replace("_", " ").title()
            val       = tf.get("value", "-")
            shap_val  = tf.get("shap_value", "")
            shap_str  = f"`{shap_val:.4f}`" if isinstance(shap_val, (int, float)) else "-"
            dir_str   = _dir(tf)
            lines.append(f"| {i} | {feat_name} | `{val}` | {shap_str} | {dir_str} |")
    else:
        lines.append("- *Data atribusi SHAP tidak tersedia untuk encounter ini.*")

    lines += [
        "",
        "#### 🚨 Temuan Potensi Diskrepansi Obat — Rule Engine",
        "",
    ]

    if flags:
        for i, flag in enumerate(flags, 1):
            ftype    = flag.get("flag_type", "?")
            med_name = flag.get("medication_name") or flag.get("medication_code", "?")
            severity = flag.get("severity", "REVIEW")
            evidence = flag.get("evidence", "")
            rule_id  = flag.get("rule_id", "")
            sev_emoji = {"HIGH": "🔴", "CRITICAL": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚠️")
            lines += [
                f"**{i}. {sev_emoji} {ftype} — {med_name}**",
                f"- Severity: `{severity}` | Rule: `{rule_id}`",
            ]
            if evidence:
                lines.append(f"- Bukti: {evidence}")
            lines.append("- ✅ **Item ini wajib diverifikasi langsung oleh apoteker klinis.**")
            lines.append("")
    else:
        lines.append(
            "- ✅ **Tidak ada diskrepansi terdeteksi** oleh rule engine pada encounter ini."
            " Tetap lakukan review klinis rutin sesuai SOP."
        )

    lines += [
        "",
        "---",
        "",
        # ── R ────────────────────────────────────────────────────────────
        "### 💡 R — Recommendation *(Fokus Verifikasi Klinis Apoteker)*",
        "",
    ]

    # Build personalized recommendations
    rec_no = 1
    recs = []

    if flags:
        omissions   = [f for f in flags if "OMISSION" in f.get("flag_type", "").upper()]
        duplications = [f for f in flags if "DUPLICATION" in f.get("flag_type", "").upper()]

        if omissions:
            med_names = ", ".join(
                f.get("medication_name") or f.get("medication_code", "?")
                for f in omissions[:3]
            )
            recs.append(
                f"**Verifikasi Omission:** Konfirmasi secara langsung dengan pasien/keluarga"
                f" mengenai alasan penghentian obat: **{med_names}**."
                " Pastikan ada alasan klinis terdokumentasi (efek samping, duplikasi terapi, dll)."
            )

        if duplications:
            med_names = ", ".join(
                f.get("medication_name") or f.get("medication_code", "?")
                for f in duplications[:3]
            )
            recs.append(
                f"**Verifikasi Duplikasi:** Klarifikasi kemungkinan duplikasi terapi pada:"
                f" **{med_names}**. Periksa apakah dua obat dalam kelas yang sama diresepkan"
                " secara bersamaan tanpa indikasi jelas."
            )

    if high_alert and ha_count > 0:
        recs.append(
            f"**Verifikasi Obat High-Alert:** Terdapat **{ha_count} obat high-alert**."
            " Periksa dosis, rute, dan frekuensi setiap obat high-alert pada resep rawat inap."
            " Konfirmasi kesesuaian dengan protokol keselamatan obat rumah sakit."
        )

    if has_allergy and allergy_cnt > 0:
        recs.append(
            f"**Verifikasi Riwayat Alergi:** Pasien memiliki **{allergy_cnt} catatan alergi obat**."
            " Pastikan tidak ada obat yang diresepkan yang berpotensi memicu reaksi alergi."
        )

    if polypharmacy:
        recs.append(
            "**Review Polifarmasi:** Pasien menggunakan ≥5 obat secara bersamaan."
            " Lakukan penilaian interaksi obat-obat dan evaluasi kebutuhan setiap obat."
        )

    if len(pre_meds) > 0 and len(adm_meds) > 0:
        recs.append(
            f"**Rekonsiliasi Menyeluruh:** Bandingkan seluruh {len(pre_meds)} obat pra-admisi"
            f" dengan {len(adm_meds)} obat admisi. Dokumentasikan alasan setiap"
            " penambahan, penghentian, atau perubahan obat dalam catatan rekonsiliasi."
        )

    # Default if no specific recs
    if not recs:
        recs.append(
            "Lakukan rekonsiliasi obat menyeluruh: bandingkan PAML vs AML,"
            " konfirmasi riwayat obat dengan pasien/keluarga, dan dokumentasikan"
            " semua perubahan terapi beserta alasan klinisnya."
        )

    for r in recs:
        lines.append(f"{rec_no}. {r}")
        lines.append("")
        rec_no += 1

    lines += [
        "",
        "---",
        "",
        "> ⚠️ **Safety Notice:** Draf ini adalah *decision support* yang dihasilkan otomatis oleh",
        "> sistem PrioMed-Rec (berbasis ML + Rule Engine). **Setiap item wajib diverifikasi**",
        "> oleh apoteker klinis sebelum keputusan medis final. PrioMed-Rec **tidak menggantikan**",
        "> penilaian klinis profesional.",
    ]

    # Error note if LLM failed
    if llm_error:
        s = llm_error.upper()
        if "LLM_API_KEY NOT SET" in s or "NOT SET IN ENVIRONMENT" in s:
            lines += ["", "> ❌ **LLM:** Isi `LLM_API_KEY` di file `.env` untuk mengaktifkan narasi AI."]
        elif "429" in s or "RESOURCE_EXHAUSTED" in s or "QUOTA" in s:
            lines += [
                "",
                "> ⚠️ **Catatan Fallback:** Narasi AI (Gemini/Groq) tidak tersedia karena kuota habis.",
                "> Laporan di atas dihasilkan oleh *rule-based fallback*.",
                "> Tambahkan `LLM_GROQ_API_KEY` di `.env` untuk fallback otomatis ke Groq (gratis).",
            ]
        elif "TIMED OUT" in s or "TIMEOUT" in s:
            lines += ["", "> ⚠️ **Catatan Fallback:** LLM timeout. Laporan berbasis aturan ditampilkan."]
        else:
            lines += ["", f"> ⚠️ **Catatan Fallback:** LLM tidak tersedia. Laporan berbasis aturan ditampilkan."]

    return "\n".join(lines)
