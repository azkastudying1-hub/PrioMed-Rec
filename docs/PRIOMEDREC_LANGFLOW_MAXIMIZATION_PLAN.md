# PRIOMED-REC — LANGFLOW MAXIMIZATION PLAN
## Dari "Langflow sebagai pembungkus narasi" menjadi "Langflow sebagai otak orkestrasi seluruh pipeline"

| | |
| :--- | :--- |
| **Dokumen** | Delta Plan v5.1 — **menggantikan** ADR-01, ADR-02 (sebagian), ADR-11 dan daftar 3-flow pada `PRIOMEDREC_STRATEGIC_DEVELOPMENT_PLAN.md` |
| **Tanggal** | 29 Oktober 2026 |
| **Pemicu** | Penilaian hackathon memberi bobot tinggi pada penggunaan Langflow; implementasi saat ini terlalu bertumpu pada FastAPI |
| **Prinsip yang TIDAK berubah** | Keselamatan klinis deterministik · human-in-the-loop · audit tak dapat diubah · LLM tidak memutuskan fakta klinis |

> **Catatan metodologi.** Kemampuan Langflow di bawah ini saya verifikasi dari blog resmi & dokumentasi Langflow (rilis 1.8 s.d. 1.12, per Oktober 2026). Beberapa fitur berstatus **beta** atau perlu **diverifikasi pada versi yang terpasang** di repo Anda. Butir yang harus dicek langsung oleh Bob ditandai **[VERIFIKASI]**. Penilaian "bobot Langflow tinggi" saya ambil dari pernyataan Anda; kriteria resmi juri tidak saya ketahui.

---

## 1. KOREKSI ATAS RENCANA SAYA SEBELUMNYA

Pada rencana sebelumnya saya menetapkan **ADR-01: "FastAPI = inti deterministik; Langflow = lapisan narasi & copilot"**, dan menyusutkan Langflow menjadi 3 flow (Orchestrator+SBAR, Copilot, Review). Itu **aman secara teknis tetapi salah strategi untuk hackathon ini**: Langflow hanya menyentuh sekitar 1 dari 10 langkah pipeline (penulisan SBAR), sementara 9 langkah lain tak terlihat di kanvas Langflow.

Keputusan baru: **Langflow-first, FastAPI sebagai lapisan layanan + pengaman + cadangan.** Keselamatan tidak berkurang, asalkan tiga syarat terpenuhi (lihat §4.3): kode deterministik yang sama dipakai di kedua jalur, ada uji paritas, dan ada verifikator keluaran di backend.

### 1.1 Diagnosis: siapa mengerjakan apa saat ini

| # | Langkah pipeline | Dikerjakan oleh (kondisi saat ini) | Terlihat di kanvas Langflow? |
| :-: | :--- | :--- | :-: |
| 1 | Ekstraksi fitur & InferenceGuard | FastAPI | ❌ |
| 2 | Skor ML (XGBoost) + SHAP | FastAPI | ❌ |
| 3 | Komposisi prioritas | FastAPI | ❌ |
| 4 | Normalisasi nama obat | FastAPI | ❌ |
| 5 | Rule engine diskrepansi | FastAPI | ❌ |
| 6 | Safety flags (ISMP/NTI/Beers) + DDI + alergi | FastAPI | ❌ |
| 7 | Penyusunan SBAR (LLM) | Langflow *(atau fallback FastAPI)* | ✅ |
| 8 | Guardrail LLM | FastAPI | ❌ |
| 9 | Keputusan apoteker & audit | FastAPI | ❌ |
| 10 | Tanya-jawab / copilot | Belum ada | ❌ |
**Cakupan Langflow ≈ 10%. Target: ≥ 80% langkah tampak sebagai node/flow, dapat dijalankan, dilacak (trace), dan didemokan.**

### 1.2 Akar masalah
1. Frontend memanggil FastAPI langsung dan hanya memakai Langflow sebagai jalur opsional dengan fallback ke FastAPI.
2. Logika deterministik tertanam di `api/services` sehingga tidak dapat dipakai sebagai node.
3. Langflow tidak memakai fitur-fitur yang justru paling bernilai: Agent + Tools, Human-in-the-Loop, Policies, MCP dua arah, Traces, Memory/Knowledge, A2A.
4. Tidak ada bukti nyata di antarmuka bahwa suatu hasil diproses oleh Langflow (juri tidak "melihat" Langflow bekerja).

---

## 2. PRINSIP DESAIN BARU (LANGFLOW-FIRST, SAFETY-PRESERVING)

| # | Prinsip | Konsekuensi |
| :-: | :--- | :--- |
| P1 | **Langflow mengorkestrasi seluruh pipeline** analisis (Fase A, Fase B, SBAR) lewat satu *master flow* | FastAPI `/analysis/run` memanggil master flow sebagai jalur **utama** |
| P2 | **Logika deterministik tetap deterministik** — hanya "dikemas" sebagai *custom component* | Kode berasal dari satu paket `priomedrec_core`; tidak ada duplikasi |
| P3 | **Satu sumber kode, dua jalur eksekusi**: Langflow (utama) dan pipeline Python lokal (cadangan) | Hasil harus identik → **uji paritas** otomatis |
| P4 | **FastAPI tetap pemilik state, auth, audit (hash-chain), persistensi** | Langflow stateless untuk data klinis (kecuali memori percakapan copilot) |
| P5 | **Browser tidak memanggil Langflow langsung**; FastAPI menjadi relay (REST + SSE) | Auth, audit, dan kunci API tetap aman |
| P6 | **Human-in-the-Loop dijadikan fitur kelas satu di Langflow** (gerbang persetujuan) | Selaras filosofi "apoteker memutuskan" |
| P7 | **Bukti kerja Langflow harus terlihat** (trace, node stepper, versi flow di UI & audit) | Nilai demo & akuntabilitas |
| P8 | **Pertahankan degradasi anggun**: Langflow mati ≠ aplikasi mati | Fallback lokal + banner "mode cadangan" |

---

## 3. FITUR LANGFLOW YANG DIPAKAI (TERVERIFIKASI) & PEMETAANNYA

Status: **Stabil** = rilis reguler · **Beta** = ditandai beta di dokumentasi · **[VERIFIKASI]** = cek di versi terpasang.

| # | Fitur Langflow | Sejak | Status | Dipakai untuk di PrioMed-Rec | Nilai demo | Catatan/risiko |
| :-: | :--- | :-: | :-: | :--- | :-: | :--- |
| 1 | **Custom Components (Python)** | lama | Stabil | Membungkus rule engine, ML scorer, normalizer, guardrail sebagai node | ★★★★★ | Env `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` & `LANGFLOW_COMPONENTS_PATH` memengaruhi eksekusi komponen kustom — atur sebagai *allow-list* |
| 2 | **Agent component + Tools / Tool Mode** | lama | Stabil | Copilot apoteker: agent memanggil tool (konteks kasus, interaksi, pengetahuan obat, penjelasan prioritas) | ★★★★★ | Komponen mana pun dapat dijadikan tool (Tool Mode) |
| 3 | **Run Flow (flow sebagai tool)** | lama | Stabil | Master flow memanggil sub-flow (Triage, Audit, SBAR); agent memakai flow sebagai tool | ★★★★ | Memudahkan modularitas |
| 4 | **Human-in-the-Loop (Human Input + persetujuan tool agent)** | 1.11 | Stabil (baru) | Gerbang keputusan apoteker (Approve/Edit/Reject/Escalate); persetujuan sebelum tool "draft review" dipanggil | ★★★★★ | Flow berhenti pada *stateful checkpoint*; **[VERIFIKASI]** cara melanjutkan (resume) dari aplikasi eksternal via API |
| 5 | **Policies (ToolGuard)** | 1.9 | **Beta** | Kebijakan bahasa alami dikompilasi menjadi *guard* di sekeliling tool copilot (mis. "tool tidak boleh mengubah status kasus tanpa persetujuan manusia") | ★★★★★ | Build-time memakai LLM → **tinjau kode guard yang dihasilkan** & simpan di git; jangan jadikan satu-satunya pengaman |
| 6 | **MCP untuk IDE/coding agent (Langflow sebagai MCP server)** | 1.9 | Stabil | **IBM Bob dapat membangun & menjalankan flow Langflow langsung**; flow terpapar sebagai tool MCP | ★★★★★ | Sinergi IBM Bob ↔ Langflow = poin kuat |
| 7 | **MCP client component** | lama | Stabil | Flow memanggil `mcp_server.py` (get_worklist, lookup_drug_knowledge, …) | ★★★ | Pastikan token layanan & lingkup tool terbatas |
| 8 | **Langflow Assistant (membangun komponen/flow)** | 1.9 / 1.10 | Stabil | Mempercepat pembuatan komponen & flow; bukti "AI membantu membangun" | ★★★ | Hasil wajib ditinjau |
| 9 | **Flow DevOps Toolkit SDK** | 1.9 | Stabil | Versioning, pengujian, deploy flow dari terminal/CI | ★★★★ | Mengubah flow menjadi artefak yang diuji |
| 10 | **Traces (per run & per komponen)** | 1.8 | Stabil | Bukti eksekusi: waktu, input/output, token per node; span HITL tercatat | ★★★★★ | Simpan `trace_id` di audit |
| 11 | **OpenTelemetry** | 1.12 | Stabil | Ekspor metrik/trace ke backend observabilitas | ★★★ | Tidak mengirim prompt/completion (sesuai catatan rilis) |
| 12 | **Workflow API v2 + AG-UI streaming** | 1.8 / 1.11 | v2 (beta awal) → streaming 1.11 | Menayangkan progres node secara *live* di UI (via relay FastAPI) | ★★★★ | **[VERIFIKASI]** kestabilan endpoint di versi terpasang |
| 13 | **A2A (Agent-to-Agent)** | 1.11 | Stabil (baru) | Menerbitkan flow Audit/Copilot sebagai agen yang dapat ditemukan agen lain; demo interoperabilitas | ★★★★ | *Stretch goal* (P1) |
| 14 | **Memory (Retrieve/Store, Memory bases)** | 1.10 | Stabil | Memori percakapan copilot per encounter | ★★★ | Data sintetis saja; terapkan kebijakan retensi |
| 15 | **Knowledge bases / Vector store (RAG)** | 1.8 | Stabil | Referensi terkurasi (RULEBOOK, daftar ISMP/Beers, formularium, panduan RS) agar copilot menjawab **dengan sitasi** | ★★★★ | RAG hanya untuk penjelasan; **deteksi fakta tetap oleh rule engine** |
| 16 | **Router / Smart Router / Conditional, Loop, Parser, Structured Output, Prompt (Mustache)** | lama–1.8 | Stabil | Routing per tier, loop per temuan, skema SBAR, template prompt | ★★★ | Membuat kanvas informatif |
| 17 | **Webhook / API run** | lama | Stabil | Pemicu event: admisi baru, SLA tick, pindah bangsal | ★★★ | Autentikasi via Langflow API key |
| 18 | **Global model providers + OpenAI-compatible endpoint** | 1.8 / 1.11 | Stabil | Penyedia LLM terpusat; mudah ganti ke watsonx / Ollama / vLLM | ★★★★ | Selaras rantai fallback LLM |
| 19 | **Bundel IBM (`lfx-ibm`)** | 1.10 | Stabil | Komponen IBM (mis. watsonx) untuk keselarasan ekosistem IBM | ★★★★ | **[VERIFIKASI]** komponen yang tersedia; Db2 hanya bila ada kebutuhan nyata — jangan dipaksakan |
| 20 | **Playground / Inspection panel / output freeze** | lama–1.8 | Stabil | Demo langsung di kanvas; membekukan output node untuk demo stabil | ★★★★ | — |

> Detail teknis yang **belum terkonfirmasi** dan wajib diuji Bob: (a) cara *resume* checkpoint HITL dari UI React lewat API, (b) kestabilan Workflow API v2 pada versi terpasang, (c) perilaku `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` + `LANGFLOW_COMPONENTS_PATH`, (d) ketersediaan komponen watsonx pada bundel IBM.

---

## 4. ARSITEKTUR TARGET (LANGFLOW-FIRST)

### 4.1 Diagram

```text
┌───────────────────────────── FRONTEND (React) ─────────────────────────────┐
│ Worklist · Case Workspace · Pipeline Transparency Panel · Copilot · Audit   │
└──────────────┬───────────────────────────────────────▲─────────────────────┘
               │ REST (JWT)                            │ SSE (progres node)
               ▼                                       │
┌──────────────────────────── FASTAPI (gerbang & penjaga) ─────────────────────────────┐
│ Auth/RBAC · State machine · Persistensi · Audit hash-chain · SLA scheduler            │
│ LangflowClient (timeout, retry, circuit breaker) · Output Verifier · Relay SSE        │
│            │ (JALUR UTAMA)                                   │ (JALUR CADANGAN)       │
│            ▼                                                 ▼                        │
│   POST Langflow API/Workflow  ◄──── hasil+trace_id          priomedrec_core.pipeline  │
└────────────┬──────────────────────────────────────────────────▲──────────────────────┘
             ▼                                                   │ kode SAMA (paket pip)
┌────────────────────────────── LANGFLOW (otak orkestrasi) ───────┴──────────────────┐
│ 00 Master Orchestrator ─ Run Flow ─► 01 Triage(Fase A) · 02 MedRec Audit(Fase B)     │
│                                      03 SBAR+Guardrail                                │
│ 04 Pharmacist Copilot (Agent + Tools + Memory + KB + Policies + HITL tool approval)   │
│ 05 Review Gate (Human-in-the-Loop)   06 Discharge Gatekeeper                          │
│ Custom components: priomedrec_components (memuat priomedrec_core)                     │
│ Traces/OTel · Global model provider → watsonx / Gemini / Groq / Ollama                │
└───────────────┬──────────────────────────────────────▲───────────────────────────────┘
                │ MCP (Langflow = MCP server)           │ MCP client (flow→mcp_server.py)
                ▼                                       │
        IBM Bob (membangun, menjalankan, menguji flow)  └── mcp_server.py → FastAPI
```

### 4.2 Pembagian tanggung jawab (revisi)

| Lapisan | Tanggung jawab | Tidak boleh |
| :--- | :--- | :--- |
| **Langflow** | Orkestrasi pipeline analisis, SBAR, copilot, gerbang HITL, routing, jejak eksekusi | Menyimpan data klinis permanen; menjadi satu-satunya penjaga keselamatan |
| **priomedrec_components** | Node deterministik (ML, rules, normalizer, guardrail, composer) | Berisi logika yang berbeda dari `priomedrec_core` |
| **priomedrec_core** | Satu-satunya sumber kode deterministik (dipakai Langflow & FastAPI) | Bergantung pada FastAPI/Langflow (harus *pure Python*) |
| **FastAPI** | Auth, state, persistensi, audit, SLA, verifikator keluaran, relay, cadangan | Memutuskan hasil klinis yang berbeda dari paket inti |
| **LLM** | Narasi SBAR & jawaban copilot dari konteks terstruktur | Mendeteksi/mengarang fakta klinis |
| **Apoteker** | Keputusan akhir (lewat UI/HITL) | — |

### 4.3 Mengapa memindahkan logika ke Langflow tidak menurunkan keselamatan
1. **Kode identik** — komponen hanya *adaptor tipis* atas fungsi di `priomedrec_core`.
2. **Uji paritas** — golden set dijalankan lewat jalur Langflow **dan** jalur lokal; keluaran harus sama (toleransi numerik terdefinisi). Gagal = CI merah.
3. **Verifikator keluaran di FastAPI** — sebelum disimpan, hasil dari Langflow divalidasi ulang: skema, skor tidak berubah, tidak ada obat di luar inventaris, tier Tier-1 → HIGH, versi guardrail ada. Gagal → jalur cadangan.
4. **Circuit breaker + cadangan** — bila Langflow lambat/mati, FastAPI beralih ke pipeline lokal otomatis dan UI menampilkan "Mode cadangan (tanpa Langflow)".
5. **Policies + HITL** sebagai lapisan tambahan, bukan pengganti.

### 4.4 ADR yang direvisi/ditambah

| ID | Keputusan | Status |
| :-: | :--- | :-: |
| ADR-01b | **Langflow-first**: pipeline analisis dijalankan oleh master flow; FastAPI = gerbang, state, audit, verifikator, cadangan | Menggantikan ADR-01 |
| ADR-02b | Browser→FastAPI→Langflow (REST+SSE relay); browser tidak pernah memegang kunci Langflow | Memperjelas ADR-02 |
| ADR-11b | Guardrail dijalankan **di dalam flow (komponen)** dan **diverifikasi ulang di FastAPI** (defense in depth) | Menggantikan ADR-11 |
| ADR-13 | Semua logika deterministik berada di paket `priomedrec_core`; komponen Langflow = adaptor tipis | Baru |
| ADR-14 | Uji paritas Langflow↔lokal wajib di CI | Baru |
| ADR-15 | HITL Langflow dipakai untuk gerbang keputusan & persetujuan tool; keputusan final tetap dicatat di audit FastAPI | Baru |
| ADR-16 | Policies (beta) = lapisan tambahan; kode guard dihasilkan lalu **ditinjau & di-commit**, bukan dibuat saat runtime | Baru |
| ADR-17 | `trace_id` Langflow disimpan pada `analysis_runs` dan `audit_entries` | Baru |
| ADR-18 | Versi Langflow dipinning (≥ 1.11 agar HITL tersedia) dan flow diekspor ke git dengan hash | Baru |

---

## 5. KATALOG FLOW (7 FLOW)

Konvensi: input/output berupa JSON terstruktur; semua flow menyertakan `request_id` dan mengembalikan `flow_version` (hash). Nama file di `langflow/flows/`.

### Flow 00 — `00_master_orchestrator` (jalur utama `/analysis/run`)
```text
[API/Webhook Input: encounter_payload]
   → [PMR: Payload Validator]                       (skema, anonimisasi PII)
   → [Run Flow: 01_triage]            → tier_ML, prob, SHAP
   → [Run Flow: 02_medrec_audit]      → findings[], safety_flags[], interactions[], allergy_conflicts[]
   → [PMR: Priority Composer]         → tier_final + priority_reason[]   (max(ML, aturan, SLA))
   → [Smart/Conditional Router]       → jika ada temuan atau tier≥MED → lanjut SBAR; selain itu ringkasan singkat
   → [Run Flow: 03_sbar_guardrail]    → sbar + guardrail_report + source
   → [PMR: Result Packager]           → analysis_result (kontrak Lampiran A)
   → [Output]
```

### Flow 01 — `01_admission_triage` (Fase A)
`Input → PMR Feature Extractor → PMR InferenceGuard → PMR XGBoost Scorer (model_A/B) → PMR SHAP Explainer (bahasa klinis) → PMR Threshold Mapper → Output {probability, tier_ml, top_drivers, model_version}`

### Flow 02 — `02_medrec_audit` (Fase B)
`Input(BPMH+orders+alergi) → PMR Medication Normalizer → [Parallel] { PMR Omission/Duplication/Substitution Rules · PMR Safety Flags (ISMP/NTI/Beers) · PMR Interaction Checker · PMR Allergy Checker } → PMR Severity Tiering → Loop (per temuan) → PMR Finding Formatter → Output`

### Flow 03 — `03_sbar_guardrail`
```text
Input(analysis_result) → PMR Context Builder (grounded, anonim, <user_note> dibungkus)
 → Prompt (Mustache, prompts/sbar_v1) → LLM (Global Model Provider; watsonx/Gemini/Groq/Ollama)
 → Structured Output (schema S/B/A/R) → PMR Guardrail (9 cek)
 → Conditional Router:  lolos → Output(source=langflow)
                        gagal & percobaan<2 → Loop: re-prompt dengan daftar pelanggaran
                        gagal ≥2 → PMR Deterministic SBAR Template → Output(source=template)
```

### Flow 04 — `04_pharmacist_copilot` (Agent)
```text
Chat Input(encounter_id, pertanyaan)
 → Memory (Retrieve per encounter)
 → AGENT [system prompt ketat: hanya jawab dari konteks/tool; selalu sertakan sumber]
     Tools: ① get_case_context (PMR)  ② explain_priority (PMR, SHAP+alasan)  ③ check_interaction (PMR)
            ④ lookup_drug_knowledge (PMR / MCP)  ⑤ search_reference_kb (Knowledge base/RAG: RULEBOOK, ISMP, Beers, formularium)
            ⑥ Run Flow: 03_sbar_guardrail (regenerasi SBAR)  ⑦ draft_review (PMR, tulis-DRAFT)  ← HITL tool approval
 → [Policies component membungkus seluruh tools]
 → PMR Guardrail (jawaban) → Memory (Store) → Chat Output (+ daftar sumber)
```
**Policies (contoh kebijakan bahasa alami, ditinjau apoteker):**
- "Tool draft_review hanya boleh dipanggil setelah persetujuan manusia."
- "Agen tidak boleh menyarankan memulai, menghentikan, atau mengubah dosis obat; hanya menyarankan konfirmasi/telaah."
- "Agen tidak boleh menyebut obat yang tidak ada dalam konteks kasus atau hasil tool."
- "Agen tidak boleh mengungkap identitas pasien."

### Flow 05 — `05_review_gate_hitl`
```text
Input(analysis_result, sbar) → PMR High-Alert Checker (daftar yang wajib dikonfirmasi)
 → Human Input [User Actions: Approve · Edit · Reject · Escalate]  ← flow berhenti (checkpoint)
     Approve  → PMR Validate (high-alert terkonfirmasi) → Tool: POST FastAPI /review (APPROVE)
     Edit     → Parser(edited_sbar) → Tool: POST /review (EDIT)
     Reject   → Wajib alasan → Tool: POST /review (REJECT)
     Escalate → Tool: POST /review (ESCALATE) + notifikasi
 → Output(audit_id, hash)
```
**[VERIFIKASI] kritis:** Bob harus menguji bagaimana checkpoint HITL dilanjutkan dari aplikasi luar (UI React via relay FastAPI). Bila tidak layak dalam waktu yang ada → **fallback yang disetujui:** keputusan dicatat lewat UI → FastAPI seperti rencana awal, sedangkan Flow 05 dipakai untuk jalur **Playground/Bob/MCP** dan untuk demo gerbang HITL di kanvas. Catat hasil verifikasi di `docs/LANGFLOW_VERIFICATION.md`.

### Flow 06 — `06_discharge_gatekeeper`
`Input(encounter_id) → PMR Case Status Fetcher → PMR Discharge Rules (kasus belum SELESAI, Tier-1 terbuka, high-alert belum dikonfirmasi) → Router (boleh/tertahan) → LLM (opsional: ringkas alasan, lewat guardrail) → Output {status, reasons[]}`

---

## 6. KATALOG CUSTOM COMPONENTS (`langflow/components/priomedrec/`)

Semua komponen = adaptor tipis atas `priomedrec_core`; tiap komponen punya: nama tampilan Indonesia/Inggris konsisten, deskripsi, input/output bertipe, uji unit, dan ikon/warna kategori (mis. *Deterministik*, *ML*, *Guardrail*, *I/O*).

| Komponen | Fungsi | Mode Tool |
| :--- | :--- | :-: |
| `PMR Payload Validator` | Validasi skema + anonimisasi PII | — |
| `PMR Feature Extractor` | Menyusun fitur sesuai manifest | — |
| `PMR InferenceGuard` | Menolak fitur terlarang | — |
| `PMR XGBoost Scorer` | Probabilitas terkalibrasi (model aktif) | — |
| `PMR SHAP Explainer` | Kontributor dalam bahasa klinis | ✅ |
| `PMR Threshold Mapper` | Probabilitas → tier (konfigurasi) | — |
| `PMR Medication Normalizer` | Normalisasi 5 tahap + confidence | ✅ |
| `PMR Discrepancy Rules` | Omisi/duplikasi/substitusi | — |
| `PMR Safety Flags` | ISMP/NTI/Beers | ✅ |
| `PMR Interaction Checker` | DDI terkurasi | ✅ |
| `PMR Allergy Checker` | Konflik alergi & reaksi silang | ✅ |
| `PMR Severity Tiering` | Tier 1/2/3 | — |
| `PMR Priority Composer` | `max(ML, aturan, SLA)` + alasan | ✅ |
| `PMR Context Builder` | Konteks LLM terikat & aman | — |
| `PMR Guardrail` | 9 cek + laporan | — |
| `PMR Deterministic SBAR Template` | SBAR tanpa LLM | — |
| `PMR Case Context (get_case_context)` | Konteks kasus untuk agen | ✅ |
| `PMR Draft Review` | Membuat DRAFT_REVIEW (tulis-draft) | ✅ (HITL) |
| `PMR Result Packager` | Menyusun kontrak hasil | — |

Kerangka komponen (verifikasi jalur impor pada versi terpasang):
```python
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Data
from priomedrec_core.rules import detect_discrepancies   # kode inti bersama

class PMRDiscrepancyRules(Component):
    display_name = "PMR Discrepancy Rules"
    description = "Deteksi omisi/duplikasi/substitusi (deterministik, tanpa LLM)."
    icon = "shield-check"
    inputs = [MessageTextInput(name="payload_json", display_name="BPMH + Orders (JSON)")]
    outputs = [Output(name="findings", display_name="Temuan", method="run")]

    def run(self) -> Data:
        import json
        result = detect_discrepancies(json.loads(self.payload_json))   # sama persis dgn jalur lokal
        return Data(data=result)
```

---

## 7. PERUBAHAN DI FASTAPI

### 7.1 Modul & tanggung jawab baru
```text
priomedrec_core/                 # paket pip lokal, PURE Python (tanpa FastAPI/Langflow)
├── pipeline.py                  # run_phase_a(), run_phase_b(), run_full()  ← jalur CADANGAN
├── features.py  scoring.py  explain.py  normalizer.py  rules.py  safety.py
├── interactions.py  allergy.py  severity.py  priority.py  guardrails.py  sbar_template.py
└── contracts.py                 # Pydantic: input/output kontrak (satu sumber)

api/services/
├── langflow_client.py           # httpx async, timeout, retry, circuit breaker, API key
├── analysis_orchestrator.py     # pilih jalur: Langflow (utama) → lokal (cadangan)
├── output_verifier.py           # validasi ulang hasil Langflow (lihat 7.3)
├── trace_service.py             # simpan trace_id, ambil ringkasan span untuk UI
└── sse_relay.py                 # relay progres node → browser (SSE)
```

### 7.2 Alur `POST /api/v1/analysis/{enc}/run`
```text
1. Bangun payload (BPMH + order + alergi + konfigurasi SLA)         [FastAPI]
2. orchestrator.try_langflow(master_flow, payload, timeout=T)       [Langflow – jalur utama]
      ├─ sukses → output_verifier.verify(result, payload)
      │              ├─ lolos  → simpan analysis_runs (path="langflow", trace_id, flow_version)
      │              └─ gagal  → catat insiden → ke langkah 3
      └─ gagal/timeout/circuit-open → langkah 3
3. priomedrec_core.pipeline.run_full(payload)                       [Cadangan lokal]
      → simpan analysis_runs (path="local_fallback")  + banner "Mode cadangan"
4. Terbitkan event SSE (progres) & notifikasi
```
Setiap `analysis_runs` menyimpan: `execution_path (langflow|local_fallback)`, `langflow_flow_id`, `flow_version_hash`, `trace_id`, `duration_ms`, `component_timings`.

### 7.3 Output Verifier (pertahanan berlapis)
Memeriksa hasil dari Langflow sebelum disimpan: (1) skema Pydantic valid; (2) `probability` sama dengan yang dihitung ulang ringan atau berada pada toleransi; (3) tidak ada obat/ID temuan di SBAR yang tak ada di inventaris; (4) bila ada temuan Tier-1/high-alert → `tier_final == HIGH`; (5) `guardrail_report` ada dan lolos; (6) versi model/aturan/prompt/guardrail terisi; (7) tidak ada PII. Gagal → jalur cadangan + `verifier_fail_total{check}`.

### 7.4 Endpoint baru/diubah
| Endpoint | Perubahan |
| :--- | :--- |
| `POST /analysis/{enc}/run` | Jalur utama Langflow → cadangan lokal |
| `POST /ai/sbar` | Menjalankan Flow 03 (atau lokal) |
| `POST /ai/copilot` (+ `/ai/copilot/stream`) | Meneruskan ke Flow 04 (stream SSE) |
| `POST /review` | Tetap pencatat resmi (audit hash-chain); dapat dipanggil dari Flow 05 |
| `GET /analysis/{enc}/trace` | Ringkasan span/trace (untuk Pipeline Panel) |
| `GET /events/pipeline/{run_id}` | SSE progres node |
| `GET /langflow/flows` | Daftar flow, versi/hash, status kesehatan (untuk halaman Flow Map) |
| `GET /health/deps` | Tambah: Langflow reachable, versi, hash flow, jumlah komponen PMR termuat |
| `POST /internal/tools/*` | (Opsional) endpoint internal untuk tool HTTP bila komponen tidak memuat `priomedrec_core` |

### 7.5 Konfigurasi (`.env`)
```text
LANGFLOW_BASE_URL=http://langflow:7860
LANGFLOW_API_KEY=...                       # JANGAN di frontend
LANGFLOW_MASTER_FLOW_ID=...               # 00_master_orchestrator
LANGFLOW_TIMEOUT_SECONDS=25
LANGFLOW_CIRCUIT_FAILS=3
LANGFLOW_CIRCUIT_RESET_SECONDS=60
EXECUTION_MODE=langflow_first             # langflow_first | local_only | langflow_only (uji)
```

---

## 8. PERUBAHAN DI FRONTEND (BUKTI LANGFLOW TERLIHAT)

| Elemen | Deskripsi | Prio |
| :--- | :--- | :-: |
| **Pipeline Transparency Panel** (di Case Workspace) | Stepper vertikal langkah pipeline: *Validasi → Skor ML → Normalisasi → Rule Engine → Safety/DDI/Alergi → Prioritas → SBAR → Guardrail*, tiap langkah: ikon status, durasi, ringkasan keluaran. Data dari SSE/trace | P0 |
| **Badge sumber eksekusi** | "Diproses oleh Langflow • flow 00_master v7f3a • 1,8 dtk" atau "Mode cadangan (tanpa Langflow)" | P0 |
| **Trace ID & tautan** | Menampilkan `trace_id`; (P1) tombol "Buka di Langflow" (hanya peran Admin/Demo) | P1 |
| **Indikator HITL** | Saat flow menunggu keputusan: label "Menunggu keputusan apoteker (checkpoint)"; hasil Approve/Edit/Reject tampil pada timeline | P0 |
| **Copilot drawer streaming** | Jawaban agen bertahap, menampilkan **tool yang dipanggil** (mis. "check_interaction → warfarin+aspirin") & **sumber KB** | P0 |
| **Persetujuan tool agen** | Bila agen meminta `draft_review`, muncul dialog persetujuan (HITL tool approval) | P1 |
| **Halaman Flow Map** | Diagram 7 flow, versi, status sehat, daftar komponen PMR; tautan ke dokumentasi — dirancang untuk juri | P1 |
| **Kesehatan sistem** | Dashboard: Langflow ✔/⚠, versi, jumlah run hari ini, rasio cadangan | P1 |

Semua tetap melalui FastAPI (ADR-02b). Label "Draf AI — wajib diverifikasi apoteker" tetap permanen.

---

## 9. IBM BOB ↔ LANGFLOW (DUA ARAH)

| Arah | Mekanisme | Hasil |
| :--- | :--- | :--- |
| **Bob → Langflow** | Dukungan MCP Langflow untuk IDE/coding agent (rilis 1.9): Bob membangun, menjalankan, dan menguji flow langsung di Langflow **[VERIFIKASI konfigurasi `mcp_settings.json` & dokumen "Langflow MCP client for coding agents"]** | Bob membuat/memperbaiki flow & komponen; riwayat sesi menjadi bukti |
| **Langflow → Bob/MCP** | Flow terpapar sebagai tool MCP (Langflow sebagai MCP server) | Bob memanggil `analysis`, `copilot`, `discharge` sebagai tool |
| **Langflow → sistem PrioMed-Rec** | Komponen *MCP client* memanggil `mcp_server.py` (get_worklist, lookup_drug_knowledge, …) | Satu rantai: Bob ↔ Langflow ↔ MCP ↔ FastAPI |
| **Penyedia model** | Global model provider → watsonx (bundel `lfx-ibm`) bila tersedia; fallback Gemini/Groq/Ollama | Selaras ekosistem IBM |

Aturan HITL tetap berlaku: tool yang menulis hanya membuat **DRAFT**.

---

## 10. OBSERVABILITAS & ALUR KERJA PENGEMBANGAN FLOW

1. **Traces**: aktifkan; simpan `trace_id` di `analysis_runs` & `audit_entries`; tampilkan di UI (P0) dan Langflow (P1). Span HITL (Approved/Rejected) ikut tercatat.
2. **OpenTelemetry (1.12)**: ekspor OTLP ke backend observabilitas (P1) — prompt/completion tidak ikut dikirim.
3. **Flow DevOps Toolkit SDK (1.9)**: ekspor flow → git; jalankan tes flow di CI; deploy flow terversi ke Langflow.
4. **Hash & versi flow**: hash JSON flow ditampilkan di `/health/deps`, UI badge, dan audit.
5. **Pinning versi**: pin image Langflow (≥ 1.11, dicek terhadap catatan *breaking change* 1.11: password bawaan lama dihapus; komponen berbasis PyTorch tidak lagi bawaan).
6. **Langflow Assistant** boleh dipakai untuk menyusun komponen, namun seluruh hasil **ditinjau** dan diuji sebelum dikomit.

---

## 11. KESELAMATAN & KEAMANAN (YANG TIDAK BOLEH DIKOMPROMIKAN)

| Aspek | Ketentuan |
| :--- | :--- |
| **Fakta klinis** | Hanya dari komponen deterministik; LLM/agen tidak mendeteksi diskrepansi |
| **Agen/Copilot** | Hanya baca + *draft*; tool tulis memerlukan persetujuan manusia (HITL) dan dibungkus Policies |
| **Policies (beta)** | Tambahan; kode guard hasil build-time **ditinjau dan di-commit**; tidak menggantikan guardrail deterministik |
| **Kredensial** | Superuser & API key Langflow kuat (tanpa password bawaan); kunci hanya di backend; rahasia lewat environment/Global Variables |
| **Custom component** | Atur `LANGFLOW_COMPONENTS_PATH` sebagai *allow-list*; nonaktifkan komponen kustom lain bila memungkinkan **[VERIFIKASI semantik env var]** |
| **Data** | Hanya sintetis; anonimisasi sebelum LLM; memori copilot dibatasi per encounter dengan retensi |
| **Jaringan** | Langflow tidak terekspos publik; hanya FastAPI yang dapat mengaksesnya |
| **Cadangan** | Langflow mati → pipeline lokal; uji matikan Langflow wajib lulus |

---

## 12. STRATEGI PENGUJIAN

| Uji | Isi | Gerbang |
| :--- | :--- | :--- |
| **Paritas** | Golden set (≥ 40 kasus) dijalankan via Langflow **dan** `priomedrec_core.pipeline`; bandingkan temuan, tier, skor (toleransi 1e-6), isi SBAR template | 100% sama |
| **Uji komponen** | Tiap komponen PMR: input→output, kasus tepi | ≥ 90% cakupan komponen |
| **Uji flow** (Flow DevOps Toolkit) | Tiap flow dijalankan dengan input contoh; validasi skema keluaran | Hijau di CI |
| **Fallback** | Matikan Langflow / lambatkan (timeout) / kirim keluaran rusak → verifier menolak → cadangan | S5/S6 + varian baru |
| **Guardrail** | LLM menyebut obat fiktif, instruksi terapi, injeksi prompt → ditolak | 100% |
| **Agen** | Copilot tidak memanggil `draft_review` tanpa persetujuan; tidak menjawab di luar konteks; menyertakan sumber | Lulus skenario adversarial |
| **HITL** | Flow berhenti di checkpoint, Approve/Edit/Reject/Escalate memicu cabang benar, alasan wajib | Lulus (atau fallback terdokumentasi) |
| **Performa** | Master flow P95 < 6 dtk tanpa LLM; dengan LLM P95 < 15 dtk | Tercatat di laporan |
| **E2E** | Playwright: Pipeline Panel tampil, badge sumber benar, mode cadangan tampil saat Langflow mati | Hijau |

---

## 13. BACKLOG PEMAKSIMALAN LANGFLOW

Ukuran: S ≤ 1 hari · M 2–4 hari · L 1–2 minggu.

| ID | Item | Ukuran | Prio |
| :-: | :--- | :-: | :-: |
| LF-001 | Audit kondisi Langflow saat ini: versi, flow, cara frontend memanggil; verifikasi butir [VERIFIKASI] §3; tulis `docs/LANGFLOW_VERIFICATION.md`; pin versi ≥ 1.11 | M | P0 |
| LF-002 | Ekstrak `priomedrec_core` (pure Python) dari `src/` & `api/services`; API pipeline lokal; kontrak Pydantic tunggal | L | P0 |
| LF-003 | Bangun `priomedrec_components` (≥ 14 komponen §6) + uji unit | L | P0 |
| LF-004 | Docker: image Langflow terpin + `priomedrec_core` + komponen; env, kredensial, API key, volume, health | M | P0 |
| LF-005 | Flow 01, 02, 03 + Flow 00 master (Run Flow antar-flow) + ekspor ke git | L | P0 |
| LF-006 | FastAPI: `LangflowClient`, `analysis_orchestrator`, `output_verifier`, circuit breaker, simpan `trace_id`/`flow_version` | L | P0 |
| LF-007 | Uji paritas Langflow↔lokal + uji fallback | M | P0 |
| LF-008 | Flow 04 Copilot: Agent + 7 tool + Memory + KB/RAG + Policies + HITL tool approval | L | P0 |
| LF-009 | Frontend: Pipeline Transparency Panel + badge sumber + SSE relay + Copilot streaming | L | P0 |
| LF-010 | Flow 05 Review Gate (HITL) + verifikasi mekanisme resume; fallback bila perlu | M | P0 |
| LF-011 | Integrasi IBM Bob ↔ Langflow via MCP (dua arah) + pembaruan `mcp_server.py` | M | P0 |
| LF-012 | Skrip demo Langflow + rekaman cadangan + dokumentasi | S | P0 |
| LF-020 | Flow 06 Discharge Gatekeeper | M | P1 |
| LF-021 | Publikasi Flow Audit/Copilot sebagai agen **A2A** + demo pemanggilan | M | P1 |
| LF-022 | Penyedia watsonx via `lfx-ibm` (jika tersedia) + rantai fallback | M | P1 |
| LF-023 | OpenTelemetry ekspor + dashboard sederhana | M | P1 |
| LF-024 | AG-UI streaming di Workflow API (bila stabil) | M | P1 |
| LF-025 | Halaman Flow Map + tautan trace | M | P1 |
| LF-026 | Pemicu Webhook (admisi baru, SLA tick, pindah bangsal) | S | P1 |
| LF-027 | Indeksasi Knowledge Base (RULEBOOK, ISMP, Beers, formularium) + sitasi di jawaban | M | P1 |
| LF-028 | Flow DevOps Toolkit di CI (uji & deploy flow) | M | P1 |

**Urutan kritis:** LF-001 → LF-002 → LF-003 → LF-004 → LF-005 → LF-006/007 → LF-009 → LF-008 → LF-010 → LF-011 → LF-012.

---

## 14. NASKAH DEMO REVISI (5 MENIT, LANGFLOW-CENTRIC)

| Menit | Adegan | Yang ditunjukkan |
| :-: | :--- | :--- |
| 0:00 | Masalah & solusi 20 detik | Urgensi |
| 0:20 | **Kanvas Langflow**: master flow berisi 7 sub-flow; sorot komponen PMR (deterministik) vs LLM | "Seluruh pipeline terlihat" |
| 0:55 | Worklist → buka Tn. Ahmad → **Pipeline Panel** berjalan langkah demi langkah (SSE), badge "Diproses Langflow • flow v7f3a" | Langflow benar-benar di jalur nyata |
| 1:40 | Temuan Tier-1 (omisi warfarin) + side-by-side + hard stop | Deterministik & aman |
| 2:15 | **Trace** run: durasi tiap komponen, token LLM | Transparansi/observabilitas |
| 2:40 | **Copilot (Agent)**: "Mengapa pasien ini HIGH?" → tool terpanggil + sumber KB; minta "buat draft review" → **HITL**: Langflow berhenti menunggu persetujuan → apoteker Approve | Agent + Tools + HITL |
| 3:25 | **Policies**: coba perintah "hentikan warfarin pasien" → ditolak oleh guard | Pagar kebijakan |
| 3:50 | **IBM Bob** membuat/menjalankan flow via MCP (tampilkan sesi) | Sinergi Bob↔Langflow |
| 4:15 | Matikan Langflow → banner "Mode cadangan", hasil identik | Ketahanan + paritas |
| 4:40 | Penutup: metrik jujur, peta jalan, A2A (bila ada) | Kredibilitas |

---

## 15. RISIKO & KEPUTUSAN DEFAULT

| # | Risiko | Mitigasi |
| :-: | :--- | :--- |
| R1 | Langflow di jalur utama → latensi/kegagalan saat demo | Timeout + circuit breaker + cadangan lokal + output freeze + rekaman cadangan |
| R2 | Ketidaksesuaian hasil Langflow vs lokal | Satu paket inti + uji paritas di CI |
| R3 | Dependensi (xgboost/shap/pydantic) bentrok di image Langflow | Image khusus terpin; bila gagal pakai komponen yang memanggil `/internal/tools/*` (HTTP) sebagai opsi B |
| R4 | HITL resume dari UI eksternal tidak layak | Fallback terdokumentasi (§5 Flow 05) |
| R5 | Policies masih beta, build-time memakai LLM | Tinjau & komit kode guard; lapisan tambahan saja |
| R6 | Versi Langflow berubah/berbeda dari dokumentasi | Pin versi, `LANGFLOW_VERIFICATION.md`, uji CI |
| R7 | Scope membengkak | P0 vs P1 tegas; A2A/OTel/AG-UI = stretch |
| R8 | Salah paham "semua dipindah ke Langflow = lebih berisiko" | Jelaskan §4.3 (kode sama, paritas, verifier, cadangan) |

**Keputusan default (tanpa perlu ditanya lagi):** Langflow-first dengan cadangan lokal · pin Langflow ≥ 1.11 · 7 flow (00–06) dengan P0 = 00–05 · komponen mengimpor `priomedrec_core` (opsi A), HTTP internal sebagai opsi B jika bentrok dependensi · HITL: coba resume via API, fallback ke pencatatan FastAPI · Policies sebagai lapisan tambahan · watsonx bila `lfx-ibm` menyediakan, selain itu Gemini/Groq/Ollama · A2A, OTel, AG-UI, Flow Map = P1.

---

## LAMPIRAN A — KONTRAK MASTER FLOW

**Input (`00_master_orchestrator`)**
```json
{
  "request_id": "req_8f2c",
  "encounter": {"id": "ENC-10203", "age": 72, "sex": "L", "ward": "Melati 3", "admitted_at": "2026-10-29T08:10:00+07:00",
                "active_conditions": 4, "prior_encounters": 3, "allergies": []},
  "bpmh": {"no_regular_meds": false, "items": [{"raw_name": "warfarin 5mg", "dose": "5 mg", "frequency": "1x1", "disposition": null}]},
  "orders": [{"raw_name": "Clexane 40mg", "dose": "40 mg", "frequency": "1x1", "route": "SC"}],
  "config": {"thresholds_version": "thr-1.1.0", "sla": {"elapsed_hours": 1.5}},
  "options": {"generate_sbar": true}
}
```
**Output** — identik dengan kontrak `analysis` di dokumen strategis (Lampiran A.1), ditambah:
```json
{
  "execution": {"path": "langflow", "flow_id": "…", "flow_version_hash": "7f3a…", "trace_id": "…",
                "duration_ms": 1840, "steps": [
                  {"name": "triage", "status": "ok", "ms": 210},
                  {"name": "medrec_audit", "status": "ok", "ms": 540},
                  {"name": "sbar_guardrail", "status": "ok", "ms": 1020, "source": "langflow"}]}
}
```

## LAMPIRAN B — POTONGAN DOCKER COMPOSE (ILUSTRATIF; Bob menyesuaikan & memverifikasi)
```yaml
services:
  langflow:
    build: ./langflow            # FROM image Langflow terpin; pip install ./priomedrec_core
    environment:
      - LANGFLOW_SUPERUSER=${LANGFLOW_SUPERUSER}
      - LANGFLOW_SUPERUSER_PASSWORD=${LANGFLOW_SUPERUSER_PASSWORD}   # tidak ada password bawaan
      - LANGFLOW_COMPONENTS_PATH=/app/custom_components
      - LANGFLOW_AUTO_LOGIN=false
    volumes:
      - ./langflow/components:/app/custom_components:ro
      - ./langflow/flows:/app/flows
    networks: [internal]         # tidak dipublikasikan ke host kecuali untuk demo
  api:
    depends_on: [langflow]
    environment:
      - LANGFLOW_BASE_URL=http://langflow:7860
      - EXECUTION_MODE=langflow_first
```

---
*Dokumen ini adalah delta atas `PRIOMEDREC_STRATEGIC_DEVELOPMENT_PLAN.md`. Bila terjadi pertentangan, **dokumen ini menang untuk topik Langflow**; keselamatan klinis (S1–S12) tetap berlaku penuh.*
