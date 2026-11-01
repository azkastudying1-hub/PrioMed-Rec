import { useEffect, useState } from "react"
import { AppShell } from "./uiux/layout"
import { CasePage, WorklistPage, NotFoundState } from "./uiux/pages"
import {
  DATA_MODE,
  getBatchWorklist,
  getAuditLog,
  submitReview,
  type RankedPatient,
} from "./api/client"
import {
  initialAuditEntries,
  initialHighAlertMedications,
  initialPatients,
  initialWardCapacities,
} from "./data/clinicalData"
import { AuditLogPage } from "./pages/AuditLogPage"
import { AuditLogPageV2 } from "./pages/AuditLogPageV2"
import { BpmhPage } from "./pages/BpmhPage"
import { PatientAnalysisPage } from "./pages/PatientAnalysisPage"
import { SettingsPage } from "./pages/SettingsPage"
import { TutorialPage } from "./pages/TutorialPage"
import { QueuePage } from "./pages/QueuePage"
import { CommandCenterPage } from "./pages/CommandCenterPage"
import { DashboardPage } from "./pages/DashboardPage"
import { LoginPage } from "./pages/LoginPage"
import { IdleLockOverlay } from "./components/IdleLockOverlay"
import { useAuthStore, initIdleListener, cleanupIdleListener } from "./lib/auth"
import { PatientFlowProvider, usePatientFlow } from "./contexts/PatientFlowContext"
import type {
  ActionType,
  Medication,
  PageId,
  Patient,
  ViewState,
  WorklistItemV1,
} from "./types/clinical"

const initialViewStates: Record<PageId, ViewState> = {
  queue: "ready",
  command_center: "ready",
  worklist: "ready",
  tutorial: "ready",
  bpmh: "ready",
  analysis: "ready",
  audit: "ready",
  settings: "ready",
}

/** Map a RankedPatient from the API to the local Patient shape (mock fields filled in). */
function rankToPatient(r: RankedPatient): import("./types/clinical").Patient {
  const template = initialPatients[0]
  return {
    ...template,
    id: r.patient_id,
    admissionId: r.encounter_id,
    ward: r.encounter_class ?? "—",
    age: r.age ?? 0,
    admittedAt: r.encounter_start ?? "—",
    riskScore: r.discrepancy_likelihood,
    riskLevel: r.review_priority,
    status: "Menunggu BPMH",
    highAlertCount: r.high_alert_count,
    topReason: r.top_risk_driver,
    contributions: [
      { label: r.top_risk_driver, value: r.discrepancy_likelihood, detail: "Top driver dari model ML" },
    ],
    medications: [],
    discrepancies: [],
    interactions: [],
    sbar: template.sbar,
  }
}

export default function App() {
  const { isAuthenticated } = useAuthStore()
  const [page, setPage] = useState<PageId>("worklist")
  const [patients, setPatients] = useState(initialPatients)
  const [activePatientId, setActivePatientId] = useState(initialPatients[0].id)
  const [auditEntries, setAuditEntries] = useState(initialAuditEntries)
  const [highAlerts, setHighAlerts] = useState(initialHighAlertMedications)
  const [capacities, setCapacities] = useState(initialWardCapacities)
  const [viewStates, setViewStates] = useState(initialViewStates)
  // V2 state: selected v1 encounter for Case Workspace
  const [selectedV1Item, setSelectedV1Item] = useState<WorklistItemV1 | null>(null)

  // Idle lock listener (F-201)
  useEffect(() => {
    if (isAuthenticated) {
      initIdleListener()
      return () => cleanupIdleListener()
    }
  }, [isAuthenticated])

  // Live mode: load worklist from FastAPI on mount
  useEffect(() => {
    if (DATA_MODE !== "live" || !isAuthenticated) return
    setViewStates((s) => ({ ...s, worklist: "loading" }))
    getBatchWorklist(50)
      .then((res) => {
        if (res.ranked_patients.length === 0) {
          setViewStates((s) => ({ ...s, worklist: "empty" }))
          return
        }
        setPatients(res.ranked_patients.map(rankToPatient))
        setActivePatientId(res.ranked_patients[0].patient_id)
        setViewStates((s) => ({ ...s, worklist: "ready" }))
      })
      .catch(() => setViewStates((s) => ({ ...s, worklist: "error" })))
  }, [isAuthenticated])

  // Live mode: load persistent audit log on mount / page change to audit
  useEffect(() => {
    if (DATA_MODE !== "live" || !isAuthenticated) return
    getAuditLog({ limit: 50 })
      .then((res) => {
        if (res.entries && res.entries.length > 0) {
          const mapped = res.entries.map((e) => ({
            id: e.review_id,
            patientId: e.patient_id || e.case_id,
            action: (e.action === "APPROVE" ? "APPROVE" : e.action === "REJECT" ? "REJECT" : "EDIT") as ActionType,
            pharmacist: e.pharmacist_id || "Apoteker",
            timestamp: e.timestamp.replace("T", " ").slice(0, 16),
            note: e.note || "Tidak ada catatan.",
            source: `Model ${e.model_version} · Rule ${e.rule_version}`,
          }))
          setAuditEntries(mapped)
        }
      })
      .catch((err) => console.warn("Could not load audit log from API", err))
  }, [page, isAuthenticated])

  // Show login page if not authenticated (AUTH_REQUIRED mode) or when DATA_MODE=live.
  // Keep this after every hook so hook order stays stable across auth changes.
  const requireAuth = DATA_MODE === 'live'
  if (!isAuthenticated) {
    return <LoginPage onSuccess={() => setPage("worklist")} />
  }

  const activePatient =
    patients.find((patient) => patient.id === activePatientId) ?? patients[0]
  const updatePatient = (patient: Patient) => {
    setPatients((current) =>
      current.map((item) => (item.id === patient.id ? patient : item)),
    )
  }
  const saveBpmh = (medications: Medication[]) => {
    updatePatient({ ...activePatient, medications, status: "Siap dianalisis" })
  }
  const recordDecision = (action: ActionType, note: string) => {
    const status =
      action === "APPROVE"
        ? "Disetujui"
        : action === "REJECT"
          ? "Ditolak"
          : "Perlu verifikasi"
    updatePatient({ ...activePatient, status })
    setAuditEntries((current) => [
      {
        id: `audit-${Date.now()}`,
        patientId: activePatient.id,
        action,
        pharmacist: "Apt. Maya R.",
        timestamp: `Hari ini, ${new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`,
        note: note || "Tidak ada catatan tambahan.",
        source: "Keputusan apoteker",
      },
      ...current,
    ])

    if (DATA_MODE === "live") {
      submitReview({
        case_id: activePatient.id,
        action,
        pharmacist_note: note,
        pharmacist_id: "Apt. Maya R.",
        ai_result: {
          patient_id: activePatient.id,
          model_version: "1.0.0",
          rule_version: "1.0.0",
        },
      }).catch((err) => console.warn("Failed to persist review action", err))
    }
  }
  const navigate = (nextPage: PageId) => setPage(nextPage)

  return (
    <PatientFlowProvider>
      <>
        <IdleLockOverlay />
        <AppShell
          page={page}
          onNavigate={navigate}
          viewState={viewStates[page]}
          onViewState={(state) =>
            setViewStates((current) => ({ ...current, [page]: state }))
          }
        >
          {page === "queue" && !selectedV1Item && (
            <QueuePage
              onOpenCase={(item) => setSelectedV1Item(item)}
            />
          )}
          {page === "queue" && selectedV1Item && (
            <CasePage
              item={selectedV1Item}
              onBack={() => setSelectedV1Item(null)}
            />
          )}
          {page === "command_center" && (
            <CommandCenterPage />
          )}
          {page === "worklist" && !selectedV1Item && (
            <WorklistPage
              onSelectEncounter={(item) => {
                setSelectedV1Item(item)
                const patient = patients.find(
                  (candidate) =>
                    candidate.id === item.patient_id ||
                    candidate.admissionId === item.encounter_id,
                )
                if (patient) setActivePatientId(patient.id)
              }}
            />
          )}
          {page === "worklist" && selectedV1Item && (
            <CasePage
              item={selectedV1Item}
              onBack={() => setSelectedV1Item(null)}
            />
          )}
          {page === "tutorial" && (
            <TutorialPage
              viewState={viewStates.tutorial}
              onViewState={(state) =>
                setViewStates((current) => ({ ...current, tutorial: state }))
              }
              onNavigate={navigate}
            />
          )}
          {page === "bpmh" && (
            <BpmhPage
              key={activePatient.id}
              patient={activePatient}
              viewState={viewStates.bpmh}
              onViewState={(state) =>
                setViewStates((current) => ({ ...current, bpmh: state }))
              }
              onSave={saveBpmh}
              onNavigate={navigate}
            />
          )}
          {page === "analysis" && (
            <PatientAnalysisPage
              patient={activePatient}
              viewState={viewStates.analysis}
              onViewState={(state) =>
                setViewStates((current) => ({ ...current, analysis: state }))
              }
              onNavigate={navigate}
              onUpdatePatient={updatePatient}
              onDecision={recordDecision}
            />
          )}
          {page === "audit" && (
            DATA_MODE === "live" ? (
              <AuditLogPageV2
                entries={auditEntries}
                viewState={viewStates.audit}
                onViewState={(state) =>
                  setViewStates((current) => ({ ...current, audit: state }))
                }
              />
            ) : (
              <AuditLogPage
                entries={auditEntries}
                viewState={viewStates.audit}
                onViewState={(state) =>
                  setViewStates((current) => ({ ...current, audit: state }))
                }
              />
            )
          )}
          {page === "settings" && (
            <SettingsPage
              highAlerts={highAlerts}
              capacities={capacities}
              viewState={viewStates.settings}
              onViewState={(state) =>
                setViewStates((current) => ({ ...current, settings: state }))
              }
              onHighAlerts={setHighAlerts}
              onCapacities={setCapacities}
            />
          )}
          {/* Task 12.1: Req 9.4 - NotFoundState fallback for invalid page state */}
          {!["queue", "command_center", "worklist", "tutorial", "bpmh", "analysis", "audit", "settings"].includes(page) && (
            <NotFoundState onReturn={() => setPage("worklist")} />
          )}
        </AppShell>
      </>
    </PatientFlowProvider>
  )
}
