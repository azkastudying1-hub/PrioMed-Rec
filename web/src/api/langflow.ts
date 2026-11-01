/**
 * src/api/langflow.ts
 * --------------------
 * AI Gateway client — semua panggilan AI dialihkan melalui FastAPI (ADR-02, S7).
 *
 * Browser TIDAK PERNAH memanggil Langflow/LLM secara langsung.
 * Alur: React UI → POST /api/v1/ai/* → FastAPI AI Gateway → Langflow/LLM
 *
 * Versi lama yang memanggil Langflow langsung TELAH DIHAPUS (A-301).
 * Gunakan apiClient di lib/apiClient.ts untuk panggilan terautentikasi.
 */

import { apiGet, apiPost } from '../lib/apiClient'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SbarResponse {
  encounter_id: string
  sbar_text: string
  source: 'gemini' | 'groq' | 'watsonx' | 'ollama' | 'template' | string
  guardrail_version: string
  ai_draft_label: string  // "Draf AI — wajib diverifikasi apoteker"
  warnings: string[]
}

export interface CopilotResponse {
  answer: string
  source: string
  guardrail_version: string
  ai_draft_label: string
  warnings: string[]
}

export interface AiHealthStatus {
  providers: Record<string, { available: boolean; model?: string; error?: string }>
  guardrail_version: string
  guardrail_metrics: Record<string, number>
  fallback_order: string[]
  prompt_versions: Record<string, string>
}

// ---------------------------------------------------------------------------
// AI Gateway endpoints (via FastAPI — NEVER direct to Langflow)
// ---------------------------------------------------------------------------

/**
 * Minta draf SBAR dari AI Gateway untuk encounter tertentu.
 * Browser → POST /api/v1/ai/sbar → FastAPI → LLM chain → guardrail
 */
export async function requestSbar(
  encounterId: string,
  contextOverride?: Record<string, unknown>,
): Promise<SbarResponse> {
  return apiPost<SbarResponse>('/api/v1/ai/sbar', {
    encounter_id: encounterId,
    context_override: contextOverride ?? null,
  })
}

/**
 * Kirim pertanyaan ke copilot AI tentang kasus.
 * Browser → POST /api/v1/ai/copilot → FastAPI → LLM chain → guardrail
 */
export async function askCopilot(
  question: string,
  encounterId?: string,
  contextOverride?: Record<string, unknown>,
): Promise<CopilotResponse> {
  return apiPost<CopilotResponse>('/api/v1/ai/copilot', {
    encounter_id: encounterId ?? null,
    question,
    context_override: contextOverride ?? null,
  })
}

/**
 * Periksa status semua provider LLM.
 */
export async function getAiHealth(): Promise<AiHealthStatus> {
  return apiGet<AiHealthStatus>('/api/v1/ai/health')
}

// ---------------------------------------------------------------------------
// Legacy health check — kept for backward compat, now checks AI Gateway
// ---------------------------------------------------------------------------

/** Periksa apakah AI Gateway tersedia (bukan Langflow langsung). */
export async function langflowIsHealthy(): Promise<boolean> {
  try {
    const health = await getAiHealth()
    return Object.values(health.providers).some((p) => p.available)
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// Legacy stubs — dialihkan ke AI Gateway (A-301)
// ---------------------------------------------------------------------------

/**
 * @deprecated Gunakan requestSbar() — memanggil AI Gateway, bukan Langflow langsung.
 */
export async function langflowAnalyze(
  patientId: string,
  encounterId?: string,
): Promise<Record<string, unknown>> {
  const result = await requestSbar(encounterId ?? patientId, { patient_id: patientId })
  return { report: result.sbar_text, source: result.source, _source: result.source }
}

/**
 * @deprecated Gunakan POST /api/v1/review melalui apiClient — bukan Langflow langsung.
 */
export async function langflowReview(
  reviewPayload: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  // Redirect to the v1 review endpoint via the authenticated API client
  return apiPost<Record<string, unknown>>('/api/v1/review', reviewPayload)
}
