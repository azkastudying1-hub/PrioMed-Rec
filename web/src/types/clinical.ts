export type PageId = "queue" | "command_center" | "worklist" | "tutorial" | "bpmh" | "analysis" | "audit" | "settings"
export type ViewState = "ready" | "loading" | "empty" | "error"
export type RiskLevel = "HIGH" | "MEDIUM" | "LOW"
export type WorkflowStatus =
  | "Menunggu BPMH"
  | "BPMH Lengkap"
  | "Dalam Analisis"
  | "Menunggu Telaah"
  | "Draft Telaah"
  | "Selesai Disetujui"
  | "Selesai Diedit"
  | "Ditolak"
  | "Eskalasi"
  | "Retriage"
  // Legacy statuses (UI display)
  | "Siap dianalisis"
  | "Perlu verifikasi"
  | "Disetujui"
export type Disposition = "Dilanjutkan" | "Ditunda" | "Diganti" | "Dihentikan" | ""
export type ActionType = "APPROVE" | "REJECT" | "EDIT" | "ESCALATE" | "DRAFT_REVIEW"

export interface RiskContribution {
  label: string
  value: number
  detail: string
}

export interface Medication {
  id: string
  name: string
  dose: string
  unit: string
  frequency: string
  route: string
  source: string
  disposition: Disposition
  reason: string
}

export interface Discrepancy {
  id: string
  type: "POTENTIAL_UNDOCUMENTED_OMISSION" | "POSSIBLE_SUBSTITUTION" | "POTENTIAL_DUPLICATION" | "UNRESOLVED_MATCH"
  medication: string
  home: string
  admission: string
  reason: string
  status: "Perlu konfirmasi" | "Terkonfirmasi" | "Diedit"
}

export interface DrugInteraction {
  id: string
  drugs: string
  severity: "Sedang" | "Tinggi"
  reason: string
  monitoring: string
  source: string
  sourceUrl: string
  status: "NEEDS_PHARMACIST_REVIEW" | "REVIEWED"
}

export interface SbarDraft {
  situation: string
  background: string
  assessment: string
  recommendation: string
}

export interface Patient {
  id: string
  admissionId: string
  ward: string
  age: number
  admittedAt: string
  riskScore: number
  riskLevel: RiskLevel
  status: WorkflowStatus
  highAlertCount: number
  topReason: string
  contributions: RiskContribution[]
  medications: Medication[]
  discrepancies: Discrepancy[]
  interactions: DrugInteraction[]
  sbar: SbarDraft
}

export interface AuditEntry {
  id: string
  patientId: string
  action: ActionType
  pharmacist: string
  timestamp: string
  note: string
  source: string
}

// v1 worklist item (from /api/v1/worklist)
export interface WorklistItemV1 {
  encounter_id: string
  patient_id: string
  patient_name: string | null
  ward: string | null
  workflow_status: string
  latest_tier: RiskLevel | null
  ml_score: number | null
  priority_reasons: Array<{ source: string; reason: string; tier: string }>
  admitted_at: string
  sla_hours_elapsed: number | null
  claimed_by: string | null
  claimed_at: string | null
  row_version: number
  dpjp_name: string | null
}

export interface HighAlertMedication {
  id: string
  name: string
  category: string
  source: string
  version: string
  verified: boolean
}

export interface WardCapacity {
  ward: string
  capacity: number
  allocated: number
}
