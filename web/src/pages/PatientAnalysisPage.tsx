/**
 * web/src/pages/PatientAnalysisPage.tsx
 *
 * Task 9.1: Migrated from legacy components to uiux/ design system.
 * Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.6, 17.5
 */

import { useEffect, useState } from "react"
import {
  AlertTriangle,
  BookOpenCheck,
  BrainCircuit,
  Check,
  CheckCircle2,
  Copy,
  Edit3,
  ExternalLink,
  ShieldAlert,
  XCircle,
} from "lucide-react"
import type {
  ActionType,
  Discrepancy,
  PageId,
  Patient,
  ViewState,
} from "../types/clinical"
import {
  DATA_MODE,
  analyzePatient,
  checkSafetyFlags,
  type DiscrepancyFlag,
  type SafetyFlag,
} from "../api/client"
import {
  AiDraftNotice,
  DataPlaceholder,
  PatientIdentity,
  PriorityBadge,
  RiskScoreBar,
  SectionHeading,
  ShapContributionList,
  WorkflowStatusBadge,
  type ShapContribution,
} from "../uiux/clinical"
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  Skeleton,
  Textarea,
  cn,
} from "../uiux/primitives"

// Checkbox component (not in primitives, kept local)
function Checkbox({ label }: { label: string }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
      <input type="checkbox" className="size-4 rounded border-slate-300" />
      {label}
    </label>
  )
}

const discrepancyLabels: Record<Discrepancy["type"], string> = {
  POTENTIAL_UNDOCUMENTED_OMISSION: "Potensi obat terlewat",
  POSSIBLE_SUBSTITUTION: "Kemungkinan substitusi",
  POTENTIAL_DUPLICATION: "Potensi duplikasi",
  UNRESOLVED_MATCH: "Padanan belum pasti",
}

export function PatientAnalysisPage({
  patient,
  viewState,
  onViewState,
  onNavigate,
  onUpdatePatient,
  onDecision,
}: {
  patient: Patient
  viewState: ViewState
  onViewState: (state: ViewState) => void
  onNavigate: (page: PageId) => void
  onUpdatePatient: (patient: Patient) => void
  onDecision: (action: ActionType, note: string) => void
}) {
  const [referenceOpen, setReferenceOpen] = useState(false)
  const [decision, setDecision] = useState<ActionType | null>(null)
  const [note, setNote] = useState("")
  const [recommendation, setRecommendation] = useState("")
  const [copied, setCopied] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [aiReport, setAiReport] = useState<string | null>(null)
  const [safetyFlags, setSafetyFlags] = useState<SafetyFlag[]>([])
  const [safetyLoading, setSafetyLoading] = useState(false)
  const [modelVersion, setModelVersion] = useState<string | null>(null)
  const [ruleVersion, setRuleVersion] = useState<string | null>(null)

  // Auto-load safety flags
  useEffect(() => {
    if (DATA_MODE !== "live" || patient.medications.length === 0) return
    setSafetyLoading(true)
    checkSafetyFlags({
      medications: patient.medications.map((m) => ({ medication_name: m.name })),
      patient_age: patient.age ?? null,
    })
      .then((res) => setSafetyFlags(res.flags))
      .catch(() => {/* silent */})
      .finally(() => setSafetyLoading(false))
  }, [patient.id, patient.medications.length])

  const updateDiscrepancy = (id: string, status: Discrepancy["status"]) => {
    onUpdatePatient({
      ...patient,
      discrepancies: patient.discrepancies.map((item) =>
        item.id === id ? { ...item, status } : item,
      ),
    })
  }

  const runAiAnalysis = async () => {
    if (DATA_MODE !== "live") return
    setAiLoading(true)
    setAiError(null)
    setAiReport(null)
    try {
      const res = await analyzePatient(patient.id, patient.admissionId)
      
      // Guard: validate response structure before mapping
      if (!res || typeof res !== 'object') {
        throw new Error("Respons API tidak valid: kosong atau bukan objek")
      }
      
      // Extract data with safe fallbacks
      const flags = Array.isArray(res.flags) ? res.flags : []
      const topFeatures = Array.isArray(res.top_features) ? res.top_features : []
      const discrepancyLikelihood = typeof res.discrepancy_likelihood === 'number' 
        ? res.discrepancy_likelihood 
        : typeof res.risk_probability === 'number' 
          ? res.risk_probability 
          : 0.5
      const reviewPriority = res.review_priority || res.priority || "MEDIUM"
      const modelVersion = res.model_version || "unknown"
      const ruleVersion = res.rule_version || "unknown"
      const report = res.report || ""
      
      const flagTypeMap: Record<string, Discrepancy["type"]> = {
        POTENTIAL_OMISSION:              "POTENTIAL_UNDOCUMENTED_OMISSION",
        POTENTIAL_UNDOCUMENTED_OMISSION: "POTENTIAL_UNDOCUMENTED_OMISSION",
        POSSIBLE_SUBSTITUTION:           "POSSIBLE_SUBSTITUTION",
        POTENTIAL_DUPLICATION:           "POTENTIAL_DUPLICATION",
        UNRESOLVED_MEDICATION_MATCH:     "UNRESOLVED_MATCH",
        UNRESOLVED_MATCH:                "UNRESOLVED_MATCH",
      }
      
      const mapped: Patient["discrepancies"] = flags.map(
        (f: DiscrepancyFlag, i: number) => ({
          id: `api-${i}`,
          type: (flagTypeMap[f.flag_type] ?? "UNRESOLVED_MATCH") as Discrepancy["type"],
          medication: f.medication_name ?? f.medication_code ?? "—",
          home: f.evidence || "Tidak ada detail",
          admission: "—",
          reason: f.evidence || "Flag terdeteksi oleh sistem",
          status: "Perlu konfirmasi" as const,
        }),
      )
      
      // Req 5.5: Save model version and rule version from API response
      setModelVersion(modelVersion)
      setRuleVersion(ruleVersion)

      onUpdatePatient({
        ...patient,
        riskScore: discrepancyLikelihood,
        riskLevel: reviewPriority,
        discrepancies: mapped.length > 0 ? mapped : patient.discrepancies,
        contributions: topFeatures.map((tf) => ({
          label: tf.feature || "Unknown feature",
          value: typeof tf.shap_value === 'number' ? tf.shap_value : 0,
          detail: `Nilai: ${tf.value ?? '-'} · ${tf.direction || 'neutral'}`,
        })),
        sbar: {
          situation: `Pasien ${patient.id} — Medication Review Priority: ${reviewPriority} (${(discrepancyLikelihood * 100).toFixed(1)}%)`,
          background: `${flags.length} potensi diskrepansi terdeteksi. Model: ${modelVersion}`,
          assessment: report.slice(0, 400) || patient.sbar.assessment,
          recommendation: patient.sbar.recommendation,
        },
      })
      setAiReport(report)
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : "Analisis gagal"
      console.error("[PatientAnalysisPage] AI analysis error:", e)
      setAiError(errorMessage)
      
      // Provide user-friendly error message with guidance
      if (errorMessage.includes("API key") || errorMessage.includes("authentication")) {
        setAiError("API key tidak valid. Silakan periksa konfigurasi LLM_API_KEY di file .env")
      } else if (errorMessage.includes("quota") || errorMessage.includes("429")) {
        setAiError("Kuota LLM habis. Tambahkan LLM_GROQ_API_KEY di .env untuk fallback gratis")
      } else if (errorMessage.includes("network") || errorMessage.includes("fetch")) {
        setAiError("Tidak dapat terhubung ke server. Pastikan backend berjalan di port 8001")
      } else if (errorMessage.includes("500") || errorMessage.includes("503")) {
        setAiError("Server error. Periksa log backend untuk detail. Mungkin LLM belum dikonfigurasi.")
      }
    } finally {
      setAiLoading(false)
    }
  }

  const copySbar = async () => {
    const text = `DRAF AI — WAJIB DIVERIFIKASI\n\nS — ${patient.sbar.situation}\nB — ${patient.sbar.background}\nA — ${patient.sbar.assessment}\nR — ${patient.sbar.recommendation}\n\nRekomendasi Apoteker: ${recommendation || "[belum diisi]"}`
    await navigator.clipboard?.writeText(text)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1800)
  }

  // Req 10.6: Use Skeleton from primitives (not PageSkeleton from legacy)
  if (viewState === "loading")
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Card className="space-y-3">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-5 w-1/2" />
        </Card>
        <Card className="space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </Card>
      </div>
    )

  if (viewState === "error")
    return (
      <ErrorState
        description="Analisis pasien tidak dapat dimuat"
        onRetry={() => onViewState("ready")}
      />
    )

  if (viewState === "empty") {
    return (
      <EmptyState
        title="Analisis belum tersedia"
        description="Selesaikan dan submit BPMH pasien sebelum menjalankan analisis discrepancy."
        action={
          <Button onClick={() => onNavigate("bpmh")}>Buka Form BPMH</Button>
        }
      />
    )
  }

  // Build SHAP contributions from patient.contributions
  const shapContributions: ShapContribution[] = (patient.contributions ?? []).map((c) => ({
    feature: c.label,
    shap_value: c.value,
    value: c.detail,
    direction: c.value >= 0 ? "positive" : "negative",
  }))

  // Req 5.4: Determine DataPlaceholder availability
  const shapAvailability =
    shapContributions.length === 0
      ? "unavailable"
      : shapContributions.some((c) => c.value == null)
      ? "needs_verification"
      : "available"

  return (
    <div className="space-y-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onNavigate("worklist")}
        >
          ← Kembali ke Worklist
        </Button>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            {/* Req 10.6: SectionHeading from clinical.tsx */}
            <SectionHeading as="h1" title="Detail Pasien & Analisis" description="Tinjau sumber, alasan flag, dan draf sebelum mengambil keputusan." />
          </div>
          <div className="flex items-center gap-2">
            {/* Req 10.6: WorkflowStatusBadge from clinical.tsx */}
            <WorkflowStatusBadge status={patient.status} />
            {/* Req 10.6: PriorityBadge from clinical.tsx */}
            <PriorityBadge
              tier={patient.riskLevel}
              score={patient.riskScore}
            />
          </div>
        </div>
      </div>

      <Card>
        {/* Req 10.6: PatientIdentity from clinical.tsx */}
        <PatientIdentity
          name={patient.id}
          patientId={patient.id}
          ward={patient.ward}
        />
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {/* Req 5.6: AiDraftNotice from clinical.tsx (not legacy VerificationNotice) */}
          <AiDraftNotice source="template" />
          {DATA_MODE === "live" && (
            <Button
              size="sm"
              variant="secondary"
              onClick={runAiAnalysis}
              disabled={aiLoading}
              loading={aiLoading}
            >
              <BrainCircuit className="size-4" aria-hidden="true" />
              {aiLoading ? "Menganalisis…" : "Analisis AI"}
            </Button>
          )}
          {aiError && (
            <span className="text-xs text-red-600">⚠ {aiError}</span>
          )}
        </div>
        {aiReport && (
          <details className="mt-4">
            <summary className="cursor-pointer text-xs font-bold text-blue-700">
              Lihat laporan lengkap dari AI ▾
            </summary>
            <pre className="mt-2 max-h-64 overflow-y-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs text-slate-700">
              {aiReport}
            </pre>
          </details>
        )}
        
        {/* Show setup instructions when AI is not configured */}
        {aiError && (aiError.includes("LLM") || aiError.includes("API key") || aiError.includes("500") || aiError.includes("503")) && (
          <Card className="mt-4 border-amber-200 bg-amber-50">
            <div className="space-y-3">
              <h4 className="font-bold text-amber-900">🤖 AI Analysis Belum Tersedia</h4>
              <p className="text-sm text-amber-800">
                Untuk mengaktifkan analisis AI, pilih salah satu opsi berikut:
              </p>
              
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-amber-200 bg-white p-3">
                  <h5 className="font-bold text-sm text-slate-800">Option 1: Groq (GRATIS, Recommended)</h5>
                  <ol className="mt-2 space-y-1 text-xs text-slate-600">
                    <li>1. Daftar gratis di <a href="https://console.groq.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">console.groq.com</a></li>
                    <li>2. Buat API Key di <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">console.groq.com/keys</a></li>
                    <li>3. Copy key (dimulai dengan <code className="rounded bg-slate-100 px-1">gsk_</code>)</li>
                    <li>4. Update file <code className="rounded bg-slate-100 px-1">.env</code>:</li>
                  </ol>
                  <pre className="mt-2 overflow-x-auto rounded bg-slate-800 p-2 text-xs text-green-400">
{`LLM_PROVIDER=groq
LLM_API_KEY=gsk_paste_disini
LLM_MODEL_NAME=llama-3.3-70b-versatile`}
                  </pre>
                </div>
                
                <div className="rounded-lg border border-amber-200 bg-white p-3">
                  <h5 className="font-bold text-sm text-slate-800">Option 2: Google Gemini (GRATIS)</h5>
                  <ol className="mt-2 space-y-1 text-xs text-slate-600">
                    <li>1. Dapatkan key gratis di <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">aistudio.google.com</a></li>
                    <li>2. Copy key (dimulai dengan <code className="rounded bg-slate-100 px-1">AIza</code>)</li>
                    <li>3. Update file <code className="rounded bg-slate-100 px-1">.env</code>:</li>
                  </ol>
                  <pre className="mt-2 overflow-x-auto rounded bg-slate-800 p-2 text-xs text-green-400">
{`LLM_PROVIDER=gemini
LLM_API_KEY=AIza_paste_disini
LLM_MODEL_NAME=gemini-2.5-flash`}
                  </pre>
                </div>
              </div>
              
              <p className="text-xs text-amber-700">
                💡 Restart backend setelah mengubah file .env. Lihat <code className="rounded bg-amber-100 px-1">docs/LLM_SETUP.md</code> untuk panduan lengkap.
              </p>
            </div>
          </Card>
        )}
      </Card>

      {/* Req 5.1, 5.2: RiskScoreBar + ShapContributionList from clinical.tsx */}
      <Card>
        <SectionHeading as="h2" title="Analisis Risiko & Kontribusi SHAP" className="mb-4" />
        <RiskScoreBar score={patient.riskScore} />
        <div className="mt-4">
          {/* Req 5.4: DataPlaceholder for missing/partial SHAP data */}
          <DataPlaceholder availability={shapAvailability}>
            {/* Req 5.2, 5.3: ShapContributionList with font-clinical-mono */}
            <ShapContributionList
              contributions={shapContributions}
              modelVersion={modelVersion}
              ruleVersion={ruleVersion}
            />
          </DataPlaceholder>
        </div>
      </Card>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <SectionHeading as="h2" title="Kandidat ketidaksesuaian obat" description={`${patient.discrepancies.length} flag deterministik memerlukan konfirmasi apoteker.`} />
          </div>
          {/* Req 5.6: AiDraftNotice for rule-based content */}
          <AiDraftNotice source="template" detail="Temuan rule-based — konfirmasi ke DPJP sebelum keputusan final." />
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {patient.discrepancies.map((item) => (
            <Card
              key={item.id}
              className={cn("border-l-4 border-l-amber-500", item.status === "Terkonfirmasi" ? "bg-emerald-50/30" : "")}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <Badge tone="warning">{discrepancyLabels[item.type]}</Badge>
                  <p className="mt-2 font-clinical-mono text-[0.6875rem] font-semibold text-slate-500">
                    {item.type}
                  </p>
                </div>
                <Badge
                  tone={
                    item.status === "Terkonfirmasi"
                      ? "success"
                      : item.status === "Diedit"
                        ? "info"
                        : "warning"
                  }
                >
                  {item.status}
                </Badge>
              </div>
              <h3 className="mt-4 text-sm font-bold text-slate-900">{item.medication}</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="rounded-md bg-slate-50 p-3">
                  <p className="text-[0.6875rem] font-bold uppercase text-slate-500">Obat rumah</p>
                  <p className="mt-1 text-sm">{item.home}</p>
                </div>
                <div className="rounded-md bg-slate-50 p-3">
                  <p className="text-[0.6875rem] font-bold uppercase text-slate-500">Order admisi</p>
                  <p className="mt-1 text-sm">{item.admission}</p>
                </div>
              </div>
              <div className="mt-3 border-l-2 border-blue-400 pl-3">
                <p className="text-xs font-bold text-slate-700">Mengapa ditandai?</p>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{item.reason}</p>
              </div>
              <div className="mt-4 flex gap-2">
                <Button
                  size="sm"
                  variant="success"
                  onClick={() => updateDiscrepancy(item.id, "Terkonfirmasi")}
                >
                  <Check className="size-4" aria-hidden="true" />
                  Konfirmasi
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => updateDiscrepancy(item.id, "Diedit")}
                >
                  <Edit3 className="size-4" aria-hidden="true" />
                  Edit
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Safety flags section */}
      {(safetyFlags.length > 0 || safetyLoading || DATA_MODE !== "live") && (
        <section className="space-y-3">
          <SectionHeading as="h2" title="Flag keamanan obat" description="ISMP high-alert · NTI · Beers PIM — semua adalah kandidat, bukan kesalahan terkonfirmasi." />
          {safetyLoading && (
            <p className="text-sm text-slate-500">Memeriksa flag keamanan…</p>
          )}
          {!safetyLoading && DATA_MODE === "live" && safetyFlags.length === 0 && patient.medications.length > 0 && (
            <Card>
              <p className="text-sm text-slate-600">
                Tidak ada flag keamanan ditemukan untuk daftar obat ini pada basis data lookup.
              </p>
            </Card>
          )}
          {DATA_MODE !== "live" && patient.medications.length > 0 && (
            <Card className="border-amber-200 bg-amber-50">
              <div className="flex gap-3">
                <AlertTriangle className="size-5 shrink-0 text-amber-700" />
                <p className="text-sm text-amber-900">
                  Mode sintetis — flag ISMP/NTI/Beers hanya tersedia saat terhubung ke backend (
                  <code className="rounded bg-amber-100 px-1 font-mono text-xs">VITE_DATA_MODE=live</code>
                  ).
                </p>
              </div>
            </Card>
          )}
          {safetyFlags.length > 0 && (
            <div className="grid gap-3 xl:grid-cols-2">
              {safetyFlags.map((flag, idx) => {
                const toneMap: Record<string, "danger" | "warning" | "info"> = {
                  ISMP_HIGH_ALERT: "danger",
                  NTI_DRUG:        "warning",
                  BEERS_PIM:       "info",
                }
                const labelMap: Record<string, string> = {
                  ISMP_HIGH_ALERT: "ISMP High-Alert",
                  NTI_DRUG:        "Narrow Therapeutic Index",
                  BEERS_PIM:       "Beers PIM (≥65 th)",
                }
                return (
                  <Card key={idx} className="border-l-4 border-l-red-500">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <Badge tone={toneMap[flag.flag_type] ?? "warning"}>
                        {labelMap[flag.flag_type] ?? flag.flag_type}
                      </Badge>
                      <span className="font-clinical-mono text-[0.6875rem] text-slate-400">CANDIDATE</span>
                    </div>
                    <h3 className="mt-3 text-sm font-bold text-slate-900 capitalize">{flag.drug_name}</h3>
                    {flag.beers_note && (
                      <p className="mt-2 text-sm text-slate-600">{flag.beers_note}</p>
                    )}
                    <dl className="mt-3 space-y-1 text-xs text-slate-500">
                      {flag.category && (
                        <div className="flex gap-2">
                          <dt className="font-bold">Kategori:</dt>
                          <dd>{flag.category}</dd>
                        </div>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <dt className="font-bold">Sumber:</dt>
                        <dd>
                          <a
                            href={flag.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 underline"
                          >
                            {flag.source} ({flag.source_version})
                          </a>
                        </dd>
                      </div>
                    </dl>
                  </Card>
                )
              })}
            </div>
          )}
        </section>
      )}

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <SectionHeading as="h2" title="Interaksi obat" description="Entri basis pengetahuan demo, bukan pemeriksaan referensi lengkap." />
          <Button
            variant="secondary"
            onClick={() => setReferenceOpen(true)}
          >
            <BookOpenCheck className="size-4" aria-hidden="true" />
            Daftar yang perlu dicek di referensi Anda
          </Button>
        </div>
        {patient.interactions.length === 0 ? (
          <Card className="border-amber-200 bg-amber-50">
            <div className="flex gap-3">
              <ShieldAlert className="size-5 shrink-0 text-amber-700" />
              <div>
                <h3 className="text-sm font-bold text-amber-900">Tidak ada entri pada basis pengetahuan demo</h3>
                <p className="mt-1 text-sm text-amber-900">
                  Ini bukan jaminan tidak ada interaksi. Periksa obat dan pasangan berisiko pada referensi institusi Anda.
                </p>
              </div>
            </div>
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {patient.interactions.map((item) => (
              <Card key={item.id}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <Badge tone={item.severity === "Tinggi" ? "danger" : "warning"}>
                      Keparahan: {item.severity}
                    </Badge>
                    <h3 className="mt-3 text-sm font-bold text-slate-900">{item.drugs}</h3>
                  </div>
                  <Badge tone={item.status === "REVIEWED" ? "success" : "warning"}>
                    {item.status}
                  </Badge>
                </div>
                <dl className="mt-4 space-y-3 text-sm">
                  <div>
                    <dt className="font-bold text-slate-700">Alasan ringkas</dt>
                    <dd className="mt-1 text-slate-600">{item.reason}</dd>
                  </div>
                  <div>
                    <dt className="font-bold text-slate-700">Parameter pemantauan</dt>
                    <dd className="mt-1 text-slate-600">{item.monitoring}</dd>
                  </div>
                  <div>
                    <dt className="font-bold text-slate-700">Sumber</dt>
                    <dd className="mt-1 flex items-center gap-2 text-blue-700">
                      {item.source}
                      <ExternalLink className="size-3" />
                    </dd>
                  </div>
                </dl>
                <div className="mt-4 flex gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => window.open(item.sourceUrl, "_blank", "noopener,noreferrer")}
                  >
                    Buka sumber
                  </Button>
                  <Button
                    size="sm"
                    variant="success"
                    onClick={() =>
                      onUpdatePatient({
                        ...patient,
                        interactions: patient.interactions.map((entry) =>
                          entry.id === item.id ? { ...entry, status: "REVIEWED" as const } : entry,
                        ),
                      })
                    }
                  >
                    Tandai reviewed
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      <Card className="border-t-4 border-t-blue-600">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <SectionHeading as="h2" title="Draf dokumentasi SBAR" description="Periksa setiap bagian terhadap rekam medis dan sumber asli." />
          <div className="flex items-center gap-2">
            {/* Req 5.6, 17.5: AiDraftNotice alongside AI-generated content */}
            <AiDraftNotice source="template" />
            <Button
              size="sm"
              variant="secondary"
              onClick={copySbar}
            >
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              {copied ? "Tersalin" : "Salin SBAR"}
            </Button>
          </div>
        </div>
        <div className="mt-5 grid gap-3 xl:grid-cols-2">
          {[
            ["S", "Situation", patient.sbar.situation],
            ["B", "Background", patient.sbar.background],
            ["A", "Assessment", patient.sbar.assessment],
            ["R", "Pertanyaan konfirmasi", patient.sbar.recommendation],
          ].map(([letter, label, text]) => (
            <div
              key={letter}
              className={`rounded-lg border p-4 ${
                letter === "R" ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-slate-50"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="flex size-7 items-center justify-center rounded bg-blue-700 font-bold text-white">
                  {letter}
                </span>
                <p className="text-sm font-bold">{label}</p>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-700">{text}</p>
            </div>
          ))}
        </div>
        <Field
          className="mt-5"
          label="Rekomendasi Apoteker"
          htmlFor="rekomendasi-apoteker"
          hint="Diisi manual oleh apoteker; tidak dibuat oleh AI."
        >
          <Textarea
            id="rekomendasi-apoteker"
            value={recommendation}
            onChange={(event) => setRecommendation(event.target.value)}
            placeholder="Tulis rekomendasi klinis Anda setelah verifikasi…"
          />
        </Field>
      </Card>

      <Card className="sticky bottom-3 z-20 border-slate-300 shadow-lg">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <Field label="Catatan keputusan" htmlFor="catatan-keputusan" className="w-full min-w-0 flex-1 sm:min-w-[18rem]">
            <Input
              id="catatan-keputusan"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Catatan opsional untuk audit log"
            />
          </Field>
          <div className="grid w-full grid-cols-1 gap-2 sm:flex sm:w-auto sm:flex-wrap">
            <Button
              className="w-full sm:w-auto"
              size="lg"
              variant="success"
              onClick={() => setDecision("APPROVE")}
            >
              <CheckCircle2 className="size-5" aria-hidden="true" />
              APPROVE
            </Button>
            <Button
              className="w-full sm:w-auto"
              size="lg"
              variant="secondary"
              onClick={() => setDecision("EDIT")}
            >
              <Edit3 className="size-5" aria-hidden="true" />
              EDIT
            </Button>
            <Button
              className="w-full sm:w-auto"
              size="lg"
              variant="danger"
              onClick={() => setDecision("REJECT")}
            >
              <XCircle className="size-5" aria-hidden="true" />
              REJECT
            </Button>
          </div>
        </div>
      </Card>

      <Modal
        open={referenceOpen}
        title="Checklist referensi manual"
        onClose={() => setReferenceOpen(false)}
        footer={
          <Button onClick={() => setReferenceOpen(false)}>Selesai</Button>
        }
      >
        <p className="text-sm text-slate-600">
          Periksa item berikut langsung di Martindale, Micromedex, atau referensi institusi.
        </p>
        <div className="mt-4 space-y-2">
          {[
            ...patient.interactions.map((item) => item.drugs),
            ...patient.medications
              .filter((item) => item.name)
              .map((item) => `${item.name} — dosis, rute, dan frekuensi`),
          ].map((item) => (
            <Checkbox key={item} label={item} />
          ))}
        </div>
      </Modal>

      <Modal
        open={Boolean(decision)}
        title={`Konfirmasi keputusan ${decision ?? ""}`}
        onClose={() => setDecision(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDecision(null)}>
              Batal
            </Button>
            <Button
              variant={
                decision === "REJECT"
                  ? "danger"
                  : decision === "APPROVE"
                    ? "success"
                    : "primary"
              }
              onClick={() => {
                if (decision) onDecision(decision, note)
                setDecision(null)
                onNavigate("audit")
              }}
            >
              Konfirmasi keputusan apoteker
            </Button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-slate-700">
          Keputusan ini dibuat oleh apoteker, bukan oleh model atau AI. Tindakan akan dicatat pada Audit Log.
        </p>
        {note && (
          <div className="mt-4 rounded-md bg-slate-50 p-3 text-sm">
            <strong>Catatan:</strong> {note}
          </div>
        )}
      </Modal>
    </div>
  )
}
