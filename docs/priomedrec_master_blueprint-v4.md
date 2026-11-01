# PRIOMED-REC: AI-POWERED MEDICATION RECONCILIATION PRIORITIZATION SYSTEM
## CETAK BIRU UTAMA ARSITEKTUR & LANDASAN PENGEMBANGAN SISTEM (VERSI 4.0 - ENHANCED)
**Target Platform:** IBM Langflow (Primary Visual Orchestration Engine), IBM Bob (AI SDLC & MCP Agent Partner), FastAPI Micro-Backend, Machine Learning (XGBoost), Open Knowledge Base, & Dashboard Apoteker Web UI  
**Target Kompetisi:** IBM SkillsBuild University Education National Hackathon x Hacktiv8  
**Prinsip Utama:** *AI decides WHO FIRST. Rules surface WHAT TO CHECK. Langflow & IBM Bob orchestrate HOW TO HELP. Pharmacist decides WHAT TO DO.*

---

## 1. LANDASAN FILOSOFI, BUKTI REGULASI, & CLINICAL GOVERNANCE

### 1.1 Problem Statement & Realitas Klinis Rumah Sakit Indonesia
* **Beban Kerja Apoteker (*Pharmacist Workload Bottleneck*):** Di rumah sakit umum dan pendidikan di Indonesia, pelayanan farmasi klinik diatur oleh **Permenkes No. 72 Tahun 2016 tentang Standar Pelayanan Kefarmasian di Rumah Sakit**. Apoteker klinis di unit UGD dan bangsal rawat inap (Penyakit Dalam, Bedah, Geriatri, Pediatri) harus menelaah puluhan hingga ratusan pasien rawat inap baru (*admission encounters*) setiap hari.
* **Durasi Ulasan Manual:** Berdasarkan panduan WHO, FIP (*International Pharmaceutical Federation*), dan studi *time-and-motion*, satu proses rekonsiliasi obat manual komprehensif memerlukan waktu **15–50 menit per pasien**.
* **Ketimpangan Antrean & Peninjauan Acak (FIFO):** Jika peninjauan dilakukan berdasarkan urutan kedatangan biasa (*First-In, First-Out / FIFO*), sekitar **79% waktu ulasan apoteker terbuang untuk memeriksa pasien berisiko rendah** yang resepnya sudah aman. Sebaliknya, pasien berisiko tinggi (lansia, polifarmasi $\ge 5$ obat, atau pengguna obat *High-Alert*) yang masuk belakangan berisiko mengalami kesalahan obat fatal (*Adverse Drug Events / ADE*) yang tidak terdeteksi.
* **Risiko Diskrepansi Terbawa (*Carried-Over Discrepancies*):** Studi klinis membuktikan bahwa **50.5% ketidaksesuaian resep (*unintended discrepancies*) yang terlewat saat admisi akan terus terbawa sepanjang masa perawatan hingga tercetak di surat pemulangan pasien (*discharge letter*)**, memicu kejadian obat yang merugikan dan re-admisi rumah sakit.
* **Solusi PrioMed-Rec:** PrioMed-Rec berfungsi sebagai *Clinical Decision Support System* (CDSS) hibrida berbasis AI & Rule Engine yang memprioritaskan antrean pasien (*WHO FIRST*), mengaudit kesalahan resep secara deterministik (*WHAT TO CHECK*), serta mengomunikasikan draf Laporan SBAR untuk diverifikasi apoteker (*WHAT TO DO*).

### 1.2 Resolusi Dilema Etika: *Two-Tier Service* & *Pending MedRec Safety Net*
Untuk mengatasi potensi ketidakadilan antrean bagi pasien berkategori *LOW Risk*, PrioMed-Rec menerapkan sistem **Dua Lapis Layanan (*Two-Tier Service*)** dan modul pengaman **Pending MedRec Safety Net**:
1. **Tier 1 (Skrining Otomatis Universal - 100% Pasien):** *Rule Engine* deterministik langsung mengaudit 100% resep admisi begitu data masuk SIMRS untuk mendeteksi omisi dan duplikasi dasar secara instan tanpa menunggu antrean.
2. **Tier 2 (Rekonsiliasi Komprehensif Berbasis Risiko):** Apoteker memfokuskan ulasan mendalam, wawancara obat rumah (*BPMH*), dan konfirmasi DPJP pada pasien berkategori **HIGH Risk**.
3. **Pagar Pengaman (*Safety Net Rules*):**
   * **`PENDING_REVIEW` Status:** Seluruh pasien admisi diberi status *Pending* secara transparan (0% data terhilang).
   * **Dynamic SLA Escalation:** Pasien *LOW Risk* yang menunggu melebihi batas waktu SLA (12–24 jam atau sebelum jam *visit* dokter berikutnya) otomatis didongkrak prioritasnya ke `HIGH` agar tidak pernah terabaikan di dasar antrean.
   * **High-Alert Mandatory Hard Stop:** Peringatan wajib ter-lock jika terdapat obat *High-Alert* (antikoagulan, insulin, antiepileptik, opioid, imunosupresan, obat Parkinson).
   * **Discharge Gatekeeper:** Sistem SIMRS menolak penutupan status *discharge* jika masih terdapat kasus diskrepansi kritis atau status *Pending* yang belum diselesaikan apoteker.

### 1.3 6 Pilar Tata Kelola AI Klinis (*Clinical AI Governance*)
1. **Human-in-the-Loop (HITL) Wajib:** AI hanya memberikan rekomendasi (*decision support*). Keputusan klinis akhir 100% di tangan apoteker (`POST /review`).
2. **Deterministic Zero Hallucination Rules:** Pengecekan omisi, duplikasi, dan interaksi obat dieksekusi 100% oleh *Rule Engine* berbasis pustaka terverifikasi (RxNorm, DDInter), bukan oleh LLM.
3. **Grounded LLM Reasoning:** Model Generatif (LLM Gemini) dipagari *prompt context* terikat data faktual tanpa izin mengarang atau berasumsi.
4. **Transparansi SHAP (Explainable AI):** Setiap prediksi risiko wajib menyertakan Top-5 SHAP features pemicu skor risiko.
5. **No Autonomous Action:** LLM dan ML dilarang keras mengubah, menambah, atau menghentikan resep obat secara mandiri.
6. **Output Validation Guardrails:** 6 pemeriksaan pengaman otomatis (`output_validator.py`) memvalidasi respon LLM sebelum disajikan ke antarmuka apoteker.

---

## 2. BENCHMARKING & ANALISIS APLIKASI SERUPA (MEDREC & CDS LEADERS)

Untuk memastikan PrioMed-Rec memiliki tingkat kegunaan (*usability*) dan dampak klinis terbaik, dilakukan analisis komparatif terhadap aplikasi terkemuka di tingkat global:

### 2.1 Matriks Komparasi Aplikasi Pembanding

| Nama Aplikasi / Sistem | Fokus Utama | Fitur Paling Relevan yang Diadopsi PrioMed-Rec | Keunggulan Spesifik PrioMed-Rec |
| :--- | :--- | :--- | :--- |
| **Synapse Medicine** (Froance/US) | *Medication Intelligence & CDS* terintegrasi EHR | • Analysis of Drug-Drug Interactions (DDI), Duplications, & Geriatric Dosing.<br>• Severity-based alert filtering.<br>• Reconciliation conciliation workflow. | PrioMed-Rec menambahkan **Prioritisasi Risiko Pasien berbasis ML (XGBoost)** dan **SBAR Copilot otomatis**, tidak hanya menampilkan alert statis. |
| **VA Medication Reconciliation** (US Dept of Veterans Affairs) | Rekonsiliasi obat pada admisi dan discharge pasien veteran | • *Order Couplets* (Add, Discontinue, Change, Leave As-Is).<br>• Multi-facility drug history mapping. | PrioMed-Rec mengadopsi tampilan visual *Order Couplets* pada panel komparasi *side-by-side* untuk mempercepat keputusan apoteker dalam 1–3 menit. |
| **MHK CareProminence Pharmacy Management** | Manajemen review farmasi & operasional klinik | • Case volume visibility & turnaround time tracking.<br>• Decision tree logic & intervention audit trail. | PrioMed-Rec mengadopsi *Turnaround Time Tracking* melalui **Dynamic SLA Countdown Timer** dan *Audit Trail* medikolegal. |
| **MedAware / EHR MedRec Modules** (Epic/Cerner) | E-Prescribing & error detection berbasis pola pasien | • Contextual alert filtering untuk mengurangi *alert fatigue*.<br>• Matching nama generik vs merek dagang. | PrioMed-Rec mengintegrasikan **SHAP Explainability Card** untuk menjelaskan alasan di balik skor risiko secara transparan. |

### 2.2 Prinsip UI/UX Hasil Adopsi Aplikasi Terkemuka
1. **Satu Layar, Satu Keputusan (*Single-Screen Decision Layout*):** Apoteker tidak perlu berpindah tab untuk memahami satu kasus pasien.
2. **Prioritas Lebih Penting daripada Kelengkapan Data:** Tampilkan pasien paling urgent di posisi paling atas antrean kerja (*Risk-Ranked Worklist*).
3. **Peringatan Harus Dapat Ditindaklanjuti (*Actionable Alerts*):** Setiap alert dilengkapi severity tag (`HIGH`/`MODERATE`), mekanisme klinis, dan rekomendasi konfirmasi ke DPJP.
4. **AI adalah Draf, Bukan Keputusan:** Seluruh ringkasan buatan LLM diberi label draf transparan yang mewajibkan konfirmasi apoteker (`APPROVE`/`EDIT`/`REJECT`).

---

## 3. MEMAKSIMALKAN LANGFLOW SEBAGAI ORCHESTRATION LAYER UTAMA (THE BRAIN)

Sesuai dengan kriteria penilaian utama **IBM SkillsBuild University Education National Hackathon**, **Langflow difungsikan secara maksimal sebagai ORCHESTRATION LAYER UTAMA (The Brain)**, sementara FastAPI digeser menjadi *Micro-Backend & Data Storage Provider* yang ringan.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       USER INTERFACE (DASHBOARD / CHAT)                     │
│               Apoteker Web Dashboard  |  IBM Bob Chat Widget                │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │ (MCP Protocol / REST API)
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LANGFLOW ORCHESTRATION LAYER (THE BRAIN)                 │
│                                                                             │
│ [Chat Input / API Trigger] ──► [Intent Classifier Agent]                   │
│                                       │                                     │
│        ┌──────────────────────────────┼──────────────────────────────┐      │
│        ▼                              ▼                              ▼      │
│ [Tool: POST /prioritize]   [Tool: POST /discrepancies]  [Tool: Drug KB Lookup] │
│ (ML Risk + SHAP)           (Rule Engine Audit)          (RxNorm/DDInter CSV)  │
│        │                              │                              │      │
│        └──────────────────────────────┼──────────────────────────────┘      │
│                                       ▼                                     │
│                          [Prompt Context Builder]                           │
│                                       │                                     │
│                                       ▼                                     │
│                            [Bounded LLM Gemini Node]                        │
│                                       │                                     │
│                                       ▼                                     │
│                       [Output Guardrail Check Node]                         │
│                                       │                                     │
│                                       ▼                                     │
│                            [Structured Output Node]                         │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│               FASTAPI MICRO-BACKEND & DATA STORAGE PROVIDER                 │
│   • Model ML Inference (XGBoost)        • Local DDInter CSV & SQLite DB     │
│   • Micro-routes (/prioritize, /discrepancies, /review, /worklist)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Rincian 4 Flow Utama di Langflow

#### A. Flow 1: MedRec Orchestrator Flow (`priomedrec_orchestrator.json`)
* **Fungsi:** Alur utama yang mengolah data admisi pasien, memanggil tools ML dan Rule Engine, menyintesis Laporan SBAR, dan memeriksa keamanan teks.
* **Komponen Node Langflow:**
  1. **Chat Input Node:** Menerima payload data pasien atau instruksi dari UI/IBM Bob.
  2. **Intent Classifier Node (Agent Node):** Menentukan intent (*PATIENT_PRIORITIZATION*, *DISCREPANCY_ANALYSIS*, *SBAR_GENERATION*).
  3. **Custom Component Tool Nodes (Paralel Execution):**
     * `API Tool: /prioritize` -> Memanggil model XGBoost & SHAP Explainer.
     * `API Tool: /discrepancies` -> Memanggil Rule Engine (omisi, duplikasi, DDI).
     * `API Tool: /knowledge/drugs` -> Memanggil RxNorm API / DDInter CSV.
  4. **Prompt Context Builder Node (Prompt Template):** Menggabungkan payload JSON dari ML dan Rule Engine menjadi konteks faktual terikat (*grounded*).
  5. **LLM Gemini Component Node:** Menyintesis draf Laporan SBAR bahasa alami.
  6. **Custom Guardrail Python Component Node (`output_validator.py`):** Menjalankan 6 pemeriksaan pengaman otomatis.
  7. **Chat Output Node:** Menampilkan draf SBAR dan rekomendasi ke antarmuka.

#### B. Flow 2: Pharmacist Copilot Flow (`priomedrec_copilot.json`)
* **Fungsi:** Menjawab pertanyaan interaktif apoteker saat menelaah kasus pasien (contoh: *"Mengapa Tn. Ahmad dikategorikan HIGH risk?"* atau *"Apakah Warfarin berinteraksi dengan Aspirin?"*).
* **Komponen Node:** Chat Input -> Case Context Retriever -> DDI Interaction Tool -> Grounded LLM Response -> Chat Output.

#### C. Flow 3: SBAR Generator Flow (`priomedrec_sbar.json`)
* **Fungsi:** Mengonversi temuan diskrepansi dan data risiko pasien menjadi draf komunikasi medis terstruktur SBAR (*Situation, Background, Assessment, Recommendation*) untuk diajukan ke DPJP.

#### D. Flow 4: Review Loop & Audit Trail Flow (`priomedrec_review.json`)
* **Fungsi:** Menangkap aksi verifikasi apoteker (`APPROVE`, `EDIT`, `REJECT`, `ESCALATE`) beserta catatan klinis, lalu mengunci log ke database backend (`POST /review`).

---

## 4. PERAN MEMAKSIMALKAN IBM BOB VIA MODEL CONTEXT PROTOCOL (MCP)

### 4.1 Positioning IBM Bob yang Tepat
Dalam PrioMed-Rec, **IBM Bob diposisikan sebagai AI SDLC, Data Quality, Rule Engineering, Model Governance, & Integration Agent Partner**, bukan sebagai "apoteker virtual" otonom yang mengambil keputusan terapi.

### 4.2 Alasan Penggunaan Langflow & IBM Bob Secara Bersamaan
* **Langflow Menangani Eksekusi (*Execution Layer*):** Tempat menyimpan *workflow* terstruktur yang dapat diulang (prompt, API tool call, RAG, ML inference, output validation).
* **IBM Bob Menangani Interaksi & Operasional Agent (*Agent & Ops Layer*):** IBM Bob berbicara secara alami, memahami intent, memilih *tools* yang tepat melalui protokol MCP, serta mengaudit kualitas data dan model.

### 4.3 Rincian 8 Peran Utama IBM Bob via MCP (`mcp_settings.json`)

| No | Peran IBM Bob | Fungsi & Skenario Penggunaan | Nilai Bagi Proyek PrioMed-Rec |
| :--- | :--- | :--- | :--- |
| 1 | **MedRec Developer Copilot** | Membantu menggenerasi kode FastAPI, skrip pelatihan XGBoost, unit test, dan dokumentasi API. | Mempercepat siklus pengembangan MVP. |
| 2 | **Data Quality Agent** | Memeriksa *missing values*, anomali data, dan kesiapan dataset Synthea sebelum digunakan untuk pelatihan model. | Menjamin kualitas data masukan model. |
| 3 | **Rule Engineering Agent** | Membantu menyusun dan menguji aturan audit biner (omisi, duplikasi ATC, interaksi DDInter) pada `discrepancy_rules.json`. | Memastikan aturan audit teruji secara klinis. |
| 4 | **Model Governance & Audit Agent** | Mengaudit versi model XGBoost, threshold `HIGH/MED`, kalibrasi probabilitas, dan kepatuhan standar TRIPOD-AI. | Mendukung akuntabilitas dan keselamatan AI. |
| 5 | **Knowledge Base Agent** | Terhubung ke API RxNorm, DailyMed, openFDA, dan dataset DDInter CSV melalui MCP server untuk pencarian obat instan. | Memperkaya fitur pengetahuan obat. |
| 6 | **SIM-RS / FHIR Integration Agent** | Menyiapkan skema integrasi HL7 FHIR (`MedicationRequest`, `Patient`, `Encounter`) untuk tahap pilot rumah sakit. | Mempermudah interoperabilitas SIMRS. |
| 7 | **Clinical QA Agent** | Menggenerasi skenario uji klinis otomatis berbasis kasus pasien riil untuk menguji ketahanan guardrail. | Meminimalkan bug dan *false positive*. |
| 8 | **Hackathon Demo Agent** | Menjelaskan arsitektur hibrida dan mensimulasikan live demo interaksi alat di hadapan juri. | Meningkatkan nilai presentasi kompetisi. |

### 4.4 Spesifikasi Kontrak MCP (`mcp_settings.json`)
```json
{
  "mcpServers": {
    "priomedrec-orchestrator": {
      "command": "python",
      "args": ["-m", "priomedrec.mcp_server"],
      "tools": [
        {
          "name": "rank_admission_risk",
          "description": "Menjalankan prediksi risiko ML XGBoost dan ekstraksi SHAP Top-5",
          "endpoint": "/prioritize"
        },
        {
          "name": "detect_medication_discrepancy",
          "description": "Mengaudit omisi, duplikasi ATC, dan interaksi obat DDInter",
          "endpoint": "/discrepancies"
        },
        {
          "name": "record_pharmacist_review",
          "description": "Merekam keputusan verifikasi apoteker (APPROVE/EDIT/REJECT) ke audit trail",
          "endpoint": "/review"
        },
        {
          "name": "lookup_drug_knowledge",
          "description": "Mencari data obat via RxNorm API & DDInter CSV matrix",
          "endpoint": "/knowledge/drugs"
        }
      ]
    }
  }
}
```

---

## 5. FITUR UTAMA, FITUR PENGAMAN, & FITUR TAMBAHAN

Seluruh fitur PrioMed-Rec dikelompokkan secara terstruktur untuk memberikan manfaat maksimal bagi apoteker rumah sakit:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. FITUR UTAMA (CORE VALUE)                                                 │
│    • Risk-Ranked Dynamic Worklist (Pengurutan antrean berbasis ML XGBoost)  │
│    • Side-by-Side Medication Comparison with Visual Order Couplets          │
│    • Grounded SBAR Clinical Copilot (Draf Laporan SBAR Otomatis)            │
│    • Human-in-the-Loop Review Loop & Digital Audit Trail                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. FITUR PENGAMAN (SAFETY NET RULES)                                        │
│    • Pending MedRec Status (100% Tracking Universal - 0% Data Loss)         │
│    • Dynamic SLA Escalation (Eskalasi Otomatis Pasien LOW Risk >12-24 Jam)   │
│    • High-Alert Mandatory Hard Stop (Penguncian Resep Obat Berisiko Tinggi)  │
│    • Discharge Safety Gatekeeper (Mencegah Pemulangan Pasien Kasus Pending) │
│    • 6 Output Safety Guardrail Checks (Mencegah Halusinasi LLM)            │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. FITUR TAMBAHAN (VALUE-ADD & ENGAGEMENT)                                  │
│    • Explainable SHAP Feature Card (Visualisasi Top-5 Pemicu Risiko)        │
│    • Conversational Interface via IBM Bob & Langflow Chat Widget            │
│    • Clinical Re-Triage Trigger (Re-scoring Otomatis saat Lab Ginjal Turun) │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 Rincian Matriks Fitur & Manfaat Apoteker RS

| Kategori | Nama Fitur | Input -> Process -> Output | Manfaat Spesifik bagi Apoteker RS |
| :--- | :--- | :--- | :--- |
| **Utama** | **Risk-Ranked Worklist** | 16 Fitur Pra-Admisi -> Prediksi ML XGBoost -> Antrean Pasien Terurut (`HIGH`/`MED`/`LOW`) | Memastikan apoteker langsung menangani pasien paling kritis pada menit pertama dinas. |
| **Utama** | **Side-by-Side Comparison** | Daftar BPMH vs Order Admisi -> Rule Engine ATC Pairwise -> Tabel Komparasi dengan Order Couplets | Memangkas waktu verifikasi resep dari 30 menit menjadi <3 menit per pasien. |
| **Utama** | **Grounded SBAR Copilot** | Payload ML & Rule Engine -> Langflow Context Builder + Gemini -> Draf SBAR Terstruktur | Mempercepat penyusunan draf rekomendasi klinis untuk dikomunikasikan ke DPJP. |
| **Utama** | **HITL Review & Audit Trail** | Input Aksi Apoteker -> `POST /review` -> Database Log & Status *RESOLVED* | Menjamin kepatuhan medikolegal dan keterlacakan rekam medis terintegrasi. |
| **Pengaman** | **Pending MedRec Status** | Patient Admission -> SIMRS Event Listener -> Status `PENDING_REVIEW` | Menjamin 100% pasien rawat inap baru masuk ke radar pemantauan farmasi. |
| **Pengaman** | **Dynamic SLA Escalation** | Timer Pasien `LOW Risk` (>12–24 Jam) -> Rule Check -> Re-ranking Prioritas ke `HIGH` | Menjamin pasien antrean bawah tidak pernah terabaikan (*Universal Patient Safety*). |
| **Pengaman** | **High-Alert Hard Stop** | Order Obat High-Alert (Warfarin/Insulin) -> Hard Stop Rule -> Alert Terkunci | Mencegah kejadian obat fatal pada kelompok obat berisiko tinggi. |
| **Pengaman** | **Discharge Gatekeeper** | SIMRS Discharge Request -> Audit Status MedRec -> Approval / Block Status | Mencegah diskrepansi obat terbawa sampai pasien pulang ke rumah. |
| **Pengaman** | **6 Safety Guardrails** | Respon Teks LLM -> Regex & Logic Check -> Teks Lolos / Re-prompt | Menjamin respon AI 100% aman, faktual, dan bebas dari halusinasi peresepan otonom. |
| **Tambahan** | **Explainable SHAP Card** | XGBoost TreeExplainer -> SHAP Value Extraction -> Bar Chart Top-5 Contributing Features | Memberikan transparansi ilmiah di balik skor risiko AI (*No Black Box*). |
| **Tambahan** | **IBM Bob Conversational UI** | Teks Bahasa Alami Apoteker -> MCP Tool Calling -> Respon Kontekstual | Mempermudah pencarian data dan navigasi tanpa perlu menghafal menu SIMRS. |

---

## 6. KONSEP ALUR KERJA APOTEKER RS INDONESIA (PERMENKES 72/2016)

Agar PrioMed-Rec dapat diterima dengan mudah di rumah sakit Indonesia, arsitektur sistem diselaraskan dengan alur kerja pelayanan farmasi klinik nyata:

```text
  [ PATIENT ADMISSION AT ED / ADMISSION DESK ]
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 1: PENELUSURAN RIWAYAT OBAT (BPMH)                                    │
│ • Tenaga Teknis Kefarmasian (TTK) / Mahasiswa Magang mengumpulkan riwayat   │
│   obat bawaan rumah dari pasien/keluarga/botol obat/apotek asal.            │
│ • Data diinput ke SIMRS / PrioMed-Rec. Status pasien: PENDING_REVIEW.       │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 2: OTOMATISASI TRIASE & AUDIT PRIOMED-REC (LANGFLOW ENGINE)           │
│ • Tier 1: Rule Engine mengaudit 100% resep untuk omisi & duplikasi dasar.    │
│ • Tier 2: Model XGBoost memeringkat pasien ke Risk Worklist (HIGH/MED/LOW).│
│ • Langflow menyintesis draf Laporan SBAR untuk pasien HIGH Risk.            │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 3: REKONSILIASI KLINIS OLEH APOTEKER KLINIK (HUMAN-IN-THE-LOOP)       │
│ • Apoteker menelaah draf SBAR dan panel komparasi side-by-side.              │
│ • Apoteker melakukan verifikasi: [APPROVE], [EDIT], atau [REJECT].          │
│ • Rekomendasi SBAR dikomunikasikan ke Dokter Penanggung Jawab (DPJP).       │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 4: TRANSFER BANGSAL & DISCHARGE GATEKEEPER                            │
│ • PrioMed-Rec memicu re-triase jika pasien pindah bangsal (ICU -> Inpatient).│
│ • Saat pemulangan, Discharge Gatekeeper memastikan seluruh status MedRec    │
│   telah RESOLVED sebelum surat pulang terbit.                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. MACHINE LEARNING (XGBOOST) & OPEN KNOWLEDGE BASE PIPELINE

### 7.1 Set Fitur Klinis Pra-Admisi (16 Feature Matrix)
1. `age` (Usia) | 2. `age_65_plus` / `is_geriatric` | 3. `gender_encoded` | 4. `pre_admission_medication_count` | 5. `admission_medication_count` | 6. `total_medication_count` | 7. `new_medication_count` | 8. `discontinued_medication_count` | 9. `polypharmacy_flag` ($\ge 5$ obat) | 10. `high_alert_flag` | 11. `high_alert_count` | 12. `potential_duplicate_candidates` | 13. `active_condition_count` | 14. `prior_encounter_count` | 15. `allergy_count` | 16. `has_drug_allergy`.

### 7.2 Strategi Dataset Dua Lapis (Two-Layer Dataset Strategy)
* **Lapis 1 (Data Pasien & Kunjungan):** Synthea Synthetic EHR Data (FHIR R4) untuk skema database, simulasi workflow, dan pengujian MVP secara *Zero-PII Compliance*.
* **Lapis 2 (Data Pengetahuan Obat Open-Access):**
  * **RxNorm API & RxClass API:** REST API gratis dari US NIH/NLM untuk normalisasi nama obat ke RXCUI dan pemetaan kelas terapi WHO ATC.
  * **DailyMed API & openFDA API:** REST API gratis dari FDA untuk label dosis harian dan laporan efek samping (*FAERS*).
  * **DDInter CSV Dataset:** Dataset matriks interaksi obat luring (*offline DDI pairwise matrix*) untuk audit interaksi berkecepatan tinggi (<0.1 detik) tanpa *latency* jaringan.
  * **KFA API SATUSEHAT:** API Kemenkes RI untuk pemetaan merek obat lokal Indonesia.

### 7.3 Pipeline Pelatihan & Evaluasi Model ML
* **Model Selection:** `XGBClassifier` dengan `objective="binary:logistic"` dan `eval_metric=["aucpr", "auc", "logloss"]`.
* **Data Partitioning (Pencegahan Leakage):** Pemisahan data wajib menggunakan **`StratifiedGroupKFold` (5-Fold) berdasarkan `patient_id`** agar riwayat kunjungan pasien yang sama tidak bocor ke data *training* dan *testing*.
* **Penanganan Class Imbalance:** Menggunakan `scale_pos_weight = (count_negative / count_positive)` atau `SMOTE` **khusus pada *training fold*** (`imbalanced-learn`).
* **Post-Training Recalibration:** Skor mentah XGBoost dikalibrasi ulang pada *validation set* menggunakan **`CalibratedClassifierCV` (Platt Scaling / Sigmoid)** agar nilai `risk_probability` [0.0 – 1.0] mencerminkan proporsi risiko klinis riil untuk mengunci ambang prioritas (`HIGH >= 0.70`, `MED >= 0.40`, `LOW < 0.40`).
* **Target Metrik Utama:** Memaksimalkan **RECALL / Sensitivity ($\ge 75–80\%$)** dan **AUCPR** untuk meminimalkan *False Negative* (pasien berisiko terlewat).

---

## 8. DESAIN UI/UX FRONTEND DASHBOARD APOTEKER

Dashboard Web Apoteker (dikembangkan via Web Native / React terhubung ke Langflow API & IBM Bob Widget) memiliki 4 area utama:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PRIOMED-REC DASHBOARD                            │
├───────────────────────────────┬─────────────────────────────────────────────┤
│ 1. RISK-RANKED WORKLIST       │ 2. SIDE-BY-SIDE MEDICATION COMPARISON       │
│                               │ Pasien: Tn. Ahmad (72 Th) | ID: ENC-10203   │
│ [HIGH] Tn. Ahmad (72 Th)      │ DPJP: dr. Budi, Sp.PD | Bangsal: Melati 3   │
│   Skor: 0.82 | SLA: 15m sisa  ├─────────────────────────────────────────────┤
│   • Polifarmasi (9 Obat)      │ Obat Rumah (BPMH)     │ Order Admisi Baru   │
│   • High-Alert (Warfarin)     │ • Amlodipine 10mg     │ [!] TERLEWAT (Omisi)│
│                               │ • Warfarin 5mg        │ • Warfarin 5mg      │
│ [MED]  Ny. Siti (58 Th)       │ • Metformin 500mg     │ • Aspirin 81mg      │
│   Skor: 0.54 | SLA: 2h sisa   │                       │ [!] DUPLIKASI       │
│   • Discontinued Meds (1)     │                       │   Clexane / Lovenox │
│                               ├─────────────────────────────────────────────┤
│ [LOW]  Tn. Budi (34 Th)       │ 3. SHAP EXPLAINABILITY & SBAR COPILOT       │
│   Skor: 0.21 | SLA: 18h sisa  │ Top SHAP Features: Polifarmasi (+0.30)      │
│                               │ SBAR Draft:                                 │
│                               │ • S: Pasien admisi dengan 3 diskrepansi.    │
│                               │ • B: Riwayat HT & antikoagulan rutin.       │
│                               │ • A: Omisi Amlodipine, duplikasi Enoxaparin.│
│                               │ • R: Konfirmasi DPJP untuk revisi resep.    │
│                               ├─────────────────────────────────────────────┤
│                               │ 4. HUMAN-IN-THE-LOOP ACTIONS                │
│                               │ Catatan: [_________________________________]│
│                               │ [ APPROVE ]   [ EDIT ]   [ REJECT ]         │
└───────────────────────────────┴─────────────────────────────────────────────┘
```

---

## 9. ROADMAP IMPLEMENTASI & VALIDASI BERSAMBANG (4-STAGE ROADMAP)

```text
┌──────────────────────────┐      ┌──────────────────────────┐      ┌──────────────────────────┐
│ STAGE 1: SYNTHETIC POC   │      │ STAGE 2: SHADOW TESTING  │      │ STAGE 3: PILOT CLINICAL  │
│ Data Synthea (Zero-PII)  │ ──►  │ Data Historis SIMRS RS   │ ──►  │ Uji Coba Terbatas UGD    │
│ Validasi Langflow & ML   │      │ Retrospective Validation │      │ Prospective Implementation│
└──────────────────────────┘      └──────────────────────────┘      └──────────────────────────┘
                                                                                  │
                                                                                  ▼
                                                                    ┌──────────────────────────┐
                                                                    │ STAGE 4: ENTERPRISE SIMRS│
                                                                    │ Integrasi Full FHIR/EHR  │
                                                                    │ Multi-Center Deployment  │
                                                                    └──────────────────────────┘
```

---

## 10. KESIMPULAN & NARASI PITCHING UNTUK JURI HACKATHON

### 10.1 Ringkasan Nilai Proyek
Sistem **PrioMed-Rec** memadukan keunggulan **Machine Learning XGBoost** untuk efisiensi triase (*WHO FIRST*), **Deterministic Rule Engine** untuk kepastian faktual tanpa halusinasi (*WHAT TO CHECK*), **Langflow Engine** sebagai *Visual Orchestrator Utama*, dan **IBM Bob MCP** sebagai *AI SDLC & Governance Partner*.

Dengan dilengkapi modul **Pending MedRec Safety Net**, aturan **Hard Stop Obat High-Alert**, dan mekanisme **Human-in-the-Loop**, PrioMed-Rec tidak pernah menggantikan peran apoteker, melainkan menjadi *copilot* tepercaya yang meningkatkan keselamatan pasien dan efisiensi farmasi rumah sakit secara signifikan.

### 10.2 Narasi Unggulan Pitching (Siap Diberikan ke Juri)
> *"PrioMed-Rec bukan sekadar aplikasi deteksi interaksi obat biasa. Ia adalah Worklist Cerdas Berbasis Risiko untuk Apoteker Rumah Sakit Indonesia. Memaksimalkan **IBM Langflow** sebagai orchestration engine utama dan **IBM Bob via MCP** sebagai AI governance partner, PrioMed-Rec memprioritaskan pasien berisiko tinggi pada menit pertama dinas, membandingkan obat bawaan rumah dengan resep admisi, menjelaskan alasan risiko secara transparan melalui SHAP, dan menyintesis draf Laporan SBAR otomatis.*
> 
> *Dengan modul **Pending MedRec Safety Net** dan **Dynamic SLA Escalation**, PrioMed-Rec menjamin bahwa pasien antrean bawah tidak akan pernah terabaikan. PrioMed-Rec membuktikan bahwa AI dapat meningkatkan keselamatan pasien secara terukur tanpa pernah mengambil alih wewenang apoteker klinis maupun dokter."*
