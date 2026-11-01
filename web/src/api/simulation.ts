/**
 * web/src/api/simulation.ts
 * --------------------------
 * Klien kontrol simulation engine replay CSV.
 *
 *   POST /api/v1/simulation/start
 *   POST /api/v1/simulation/stop
 *   POST /api/v1/simulation/step
 *   GET  /api/v1/simulation/status
 */

import { apiGet, apiPost } from '../lib/apiClient'

export interface SimulationLastPatient {
  event: string
  encounter_id: string
  source_encounter_id?: string
  patient_id?: string
  ward?: string
  ml_score?: number
  model_priority?: string
  final_tier?: string
  rules_floor?: string
  rule_findings?: number
  rule_types?: string[]
  mutation_type?: string
  admitted_at?: string
}

export interface SimulationStatus {
  running: boolean
  finished: boolean
  preparing: boolean
  started_at: string | null
  stopped_at: string | null
  interval_seconds: number
  max_patients: number
  sla_scale: number
  drain_ticks: number
  drain_remaining: number
  draining: boolean
  dataset_path: string
  dataset_rows: number
  next_index: number
  admitted: number
  bpmh_completed: number
  escalated: number
  errors: number
  tick_count: number
  pending_bpmh: number
  last_patient: SimulationLastPatient | null
  last_error: string | null
  model_version: string | null
  label: string
  load_seconds: number
}

export interface SimulationStartInput {
  interval_seconds?: number
  max_patients?: number
  sla_scale?: number
  dataset_path?: string | null
  cases_path?: string | null
  fresh_ids?: boolean
  drain_ticks?: number
}

export function getSimulationStatus(): Promise<SimulationStatus> {
  return apiGet<SimulationStatus>('/simulation/status')
}

export function startSimulation(
  input: SimulationStartInput = {},
): Promise<{ ok: boolean; status: SimulationStatus }> {
  return apiPost('/simulation/start', input)
}

export function stopSimulation(): Promise<{ ok: boolean; status: SimulationStatus }> {
  return apiPost('/simulation/stop', {})
}

export function stepSimulation(
  count = 1,
): Promise<{ ok: boolean; stepped: number; last: SimulationLastPatient | null; status: SimulationStatus }> {
  return apiPost('/simulation/step', { count })
}
