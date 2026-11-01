/**
 * src/api/client.ts
 * -----------------
 * Thin fetch wrapper for PrioMed-Rec FastAPI backend.
 *
 * In development (vite dev server), requests to /api/* are proxied to
 * http://localhost:8000 via vite.config.ts proxy rules.
 *
 * DATA MODE:
 *   VITE_DATA_MODE=synthetic (default) — uses mock data from clinicalData.ts
 *   VITE_DATA_MODE=live               — hits real FastAPI endpoints
 *
 * LANGFLOW MODE:
 *   When VITE_LANGFLOW_URL is set and Langflow is reachable, analyzePatient
 *   and submitReview are routed through Langflow first (full orchestration).
 *   If Langflow is unavailable, both fall back to direct FastAPI calls.
 *
 * The mode is read from import.meta.env.VITE_DATA_MODE.
 * Set it in web/.env.local for local development.
 */

import { parseApiError } from './errors'
import { langflowAnalyze, langflowReview } from './langflow'
import { useAuthStore } from '../lib/auth'

const BASE = '/api'

export const DATA_MODE: 'synthetic' | 'live' =
  (import.meta.env.VITE_DATA_MODE as 'synthetic' | 'live') ?? 'synthetic'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = (import.meta.env.VITE_API_KEY as string) || ''
  const store = useAuthStore.getState();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> ?? {}),
    ...(store.accessToken ? { 'Authorization': `Bearer ${store.accessToken}` } : {}),
  }
  if (apiKey) {
    headers['X-API-Key'] = apiKey
  }
  
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch (networkErr) {
    const err = parseApiError(0, String(networkErr))
    throw new Error(err.message)
  }
  
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText)
    const err = parseApiError(res.status, detail)
    throw new Error(err.message)
  }
  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------
export interface HealthResponse {
  status: string
  model_version: string
  rule_version: string
  api_version: string
}
export const getHealth = () => apiFetch<HealthResponse>('/health')

// ---------------------------------------------------------------------------
// Patient
// ---------------------------------------------------------------------------
export interface EncounterSummary {
  encounter_id: string
  encounter_start: string
  encounter_end: string
  encounter_class: string
  encounter_type: string
  age: number | null
  gender: string
}
export interface PatientResponse {
  patient_id: string
  encounter_count: number
  encounters: EncounterSummary[]
  latest_admission: EncounterSummary | null
}
export const getPatient = (patientId: string) =>
  apiFetch<PatientResponse>(`/patient/${encodeURIComponent(patientId)}`)

export const getSamplePatients = (limit = 10) =>
  apiFetch<{ patient_ids: string[]; count: number }>(`/patients/sample?limit=${limit}`)

// ---------------------------------------------------------------------------
// Prioritization
// ---------------------------------------------------------------------------
export interface TopFeature {
  feature: string
  value: number
  shap_value: number
  direction: string
}
export interface PrioritizeResponse {
  risk_probability: number
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
  model_version: string
  threshold_version: string
  top_features: TopFeature[]
}

export interface RankedPatient {
  rank: number
  patient_id: string
  encounter_id: string
  discrepancy_likelihood: number
  review_priority: 'HIGH' | 'MEDIUM' | 'LOW'
  age: number | null
  gender: string | null
  encounter_class: string | null
  encounter_start: string | null
  pre_admission_med_count: number
  admission_med_count: number
  high_alert_count: number
  polypharmacy_flag: number
  top_risk_driver: string
}
export interface BatchPrioritizeResponse {
  total_analyzed: number
  high_priority_count: number
  medium_priority_count: number
  low_priority_count: number
  ranked_patients: RankedPatient[]
}
export const getBatchWorklist = (limit = 50, priorityFilter?: string) =>
  apiFetch<BatchPrioritizeResponse>('/prioritize/batch', {
    method: 'POST',
    body: JSON.stringify({ limit, priority_filter: priorityFilter ?? null }),
  })

// ---------------------------------------------------------------------------
// Analysis (one-shot: ML + rule engine + SBAR)
// ---------------------------------------------------------------------------
export interface DiscrepancyFlag {
  flag_type: string
  severity: string
  medication_code: string | null
  medication_name: string | null
  evidence: string
  verification_required: boolean
  rule_id: string
}
export interface AnalyzeResponse {
  patient_id: string
  encounter_id: string
  discrepancy_likelihood: number
  review_priority: 'HIGH' | 'MEDIUM' | 'LOW'
  model_version: string
  top_features: TopFeature[]
  flags: DiscrepancyFlag[]
  rule_version: string
  report: string
  report_available: boolean
  risk_probability: number
  priority: 'HIGH' | 'MEDIUM' | 'LOW'
}
/**
 * analyzePatient — Langflow-first with FastAPI fallback.
 *
 * 1. Tries Langflow orchestrator flow (full ML + rules + LLM pipeline).
 * 2. Falls back to direct POST /analyze if Langflow is unreachable.
 */
export async function analyzePatient(
  patientId: string,
  encounterId?: string,
  question?: string,
): Promise<AnalyzeResponse> {
  // Try AI Gateway first (ADR-02: browser never calls Langflow directly)
  try {
    const lf = await langflowAnalyze(patientId, encounterId)
    // Cast — AI Gateway returns same shape as /analyze
    return lf as unknown as AnalyzeResponse
  } catch {
    // AI Gateway unavailable or errored — fall back to FastAPI directly
  }
  return apiFetch<AnalyzeResponse>('/analyze', {
    method: 'POST',
    body: JSON.stringify({
      patient_id: patientId,
      encounter_id: encounterId ?? '',
      question: question ?? null,
    }),
  })
}

// ---------------------------------------------------------------------------
// Review (audit trail)
// ---------------------------------------------------------------------------
export interface ReviewRequest {
  case_id: string
  pharmacist_id: string
  ai_result: Record<string, unknown>
  action: 'APPROVE' | 'REJECT' | 'EDIT' | 'ESCALATE' | 'DRAFT_REVIEW'
  pharmacist_note?: string
  edited_result?: Record<string, unknown> | null
}
export interface ReviewResponse {
  review_id: string
  case_id: string
  action: string
  timestamp: string
  pharmacist_id: string
  model_version: string | null
  rule_version: string | null
  final_result: Record<string, unknown>
}
/**
 * submitReview — Langflow-first with FastAPI fallback.
 *
 * 1. Tries Langflow review flow (routes APPROVE/REJECT/EDIT through Langflow).
 * 2. Falls back to direct POST /review if Langflow is unavailable.
 */
export async function submitReview(req: ReviewRequest): Promise<ReviewResponse> {
  // Try Langflow review flow first
  try {
    const lf = await langflowReview(req as unknown as Record<string, unknown>)
    return lf as unknown as ReviewResponse
  } catch {
    // Langflow unavailable — fall back to FastAPI directly
  }
  return apiFetch<ReviewResponse>('/review', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

// ---------------------------------------------------------------------------
// BPMH — Best Possible Medication History
// ---------------------------------------------------------------------------
export interface BpmhMedItem {
  medication_code: string | null
  medication_name: string
  dose_value: string | null
  dose_unit: string | null
  frequency: string | null
  route: string | null
  source_of_info: string | null
  disposition: 'DILANJUTKAN' | 'DITUNDA' | 'DIGANTI' | 'DIHENTIKAN' | null
  disposition_reason: string | null
}
export interface BpmhRequest {
  encounter_id: string
  medications: BpmhMedItem[]
  pharmacist_id?: string
}
export interface BpmhResponse {
  patient_id: string
  encounter_id: string
  medication_count: number
  submitted_at: string
  status: string
}
export const submitBpmh = (patientId: string, req: BpmhRequest) =>
  apiFetch<BpmhResponse>(`/bpmh/${encodeURIComponent(patientId)}`, {
    method: 'POST',
    body: JSON.stringify(req),
  })

// ---------------------------------------------------------------------------
// Safety flags (Stage 2: ISMP high-alert / NTI / Beers PIM)
// ---------------------------------------------------------------------------
export interface SafetyFlag {
  flag_type: 'ISMP_HIGH_ALERT' | 'NTI_DRUG' | 'BEERS_PIM'
  drug_name: string
  category: string
  route: string
  source: string
  source_version: string
  source_url: string
  status: 'CANDIDATE'
  verification_required: true
  beers_note?: string
  age_threshold?: number
}
export interface SafetyFlagsResponse {
  flags: SafetyFlag[]
  high_alert_count: number
  nti_count: number
  beers_pim_count: number
  total_flag_count: number
  lookup_version: string
  source_versions: Record<string, unknown>
}
export interface SafetyFlagsRequest {
  medications: { medication_name: string }[]
  patient_age?: number | null
}
/** POST /interactions/safety — check admission med list for high-alert/NTI/Beers flags */
export const checkSafetyFlags = (req: SafetyFlagsRequest) =>
  apiFetch<SafetyFlagsResponse>('/interactions/safety', {
    method: 'POST',
    body: JSON.stringify(req),
  })

// ---------------------------------------------------------------------------
// Worklist (real-time)
// ---------------------------------------------------------------------------
export interface WorklistPatient {
  patient_id: string
  encounter_id: string
  workflow_status: string
  updated_at: string
  updated_by: string
}
export const getWorklist = (limit = 50) =>
  apiFetch<{ patients: WorklistPatient[]; count: number }>(`/worklist?limit=${limit}`)

// ---------------------------------------------------------------------------
// Audit Log
// ---------------------------------------------------------------------------
export interface AuditLogEntry {
  review_id: string
  case_id: string
  patient_id: string
  pharmacist_id: string
  action: string
  timestamp: string
  note: string
  model_version: string
  rule_version: string
}
export const getAuditLog = (params?: {
  patient_id?: string
  action?: string
  date_from?: string
  date_to?: string
  limit?: number
}) => {
  const q = new URLSearchParams()
  if (params?.patient_id) q.set('patient_id', params.patient_id)
  if (params?.action) q.set('action', params.action)
  if (params?.date_from) q.set('date_from', params.date_from)
  if (params?.date_to) q.set('date_to', params.date_to)
  if (params?.limit) q.set('limit', String(params.limit))
  return apiFetch<{ entries: AuditLogEntry[]; count: number }>(`/audit?${q.toString()}`)
}

// ---------------------------------------------------------------------------
// Settings - High Alert
// ---------------------------------------------------------------------------
export const getHighAlerts = () =>
  apiFetch<{ drugs: { drug_name: string; category: string }[] }>('/settings/high-alert')

export const updateHighAlerts = (drugs: { drug_name: string; category: string }[]) =>
  apiFetch<{ message: string; count: number }>('/settings/high-alert', {
    method: 'POST',
    body: JSON.stringify({ drugs }),
  })
