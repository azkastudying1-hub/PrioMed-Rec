/**
 * web/src/lib/apiClient.ts
 * -------------------------
 * Authenticated API client for /api/v1 endpoints (F-202).
 *
 * - Adds Bearer token from auth store to every request
 * - Retries once with refreshed token on 401
 * - Returns structured errors with PrioMed error envelope support
 *
 * ADR-02: Browser NEVER calls Langflow/LLM directly.
 * All AI calls go through: UI → FastAPI AI Gateway → Langflow/LLM
 */

import { useAuthStore } from './auth'

const API_BASE = '/api/v1'

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// ---------------------------------------------------------------------------
// Core fetch with auto-refresh
// ---------------------------------------------------------------------------
async function apiFetch<T>(
  path: string,
  init?: RequestInit & { skipAuth?: boolean },
  _retry = true,
): Promise<T> {
  const store = useAuthStore.getState()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> ?? {}),
  }

  if (!init?.skipAuth && store.accessToken) {
    headers['Authorization'] = `Bearer ${store.accessToken}`
  }

  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers })
  } catch (networkErr) {
    throw new ApiError(0, 'NETWORK_ERROR', `Koneksi ke server gagal: ${networkErr}`)
  }

  // Auto-refresh on 401, but skip for login endpoint
  if (res.status === 401 && _retry) {
    // Skip auto-refresh for /auth/login endpoint - preserve original backend error message
    const isLoginEndpoint = path === '/auth/login'
    
    if (!isLoginEndpoint) {
      const refreshed = await store.refreshAccessToken()
      if (refreshed) {
        return apiFetch<T>(path, init, false)
      }
      store.logout()
      throw new ApiError(401, 'UNAUTHORIZED', 'Sesi habis. Silakan login kembali.')
    }
  }

  if (!res.ok) {
    let errorBody: { code?: string; message?: string; details?: unknown } = {}
    try {
      errorBody = await res.json()
    } catch {
      errorBody = { message: res.statusText }
    }
    throw new ApiError(
      res.status,
      errorBody.code ?? `HTTP_${res.status}`,
      errorBody.message ?? `Error ${res.status}`,
      errorBody.details,
    )
  }

  return res.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------
export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  role: string
  username: string
  user_id: string
}

export async function loginApi(username: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
    skipAuth: true,
  })
}

export async function logoutApi(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' })
}

export interface UserProfile {
  user_id: string
  username: string
  full_name: string
  role: string
  actor_type: string
}

export const getMe = () => apiFetch<UserProfile>('/auth/me')

// ---------------------------------------------------------------------------
// Worklist endpoints  (B-114)
// ---------------------------------------------------------------------------
export interface WorklistItemV1 {
  encounter_id: string
  patient_id: string
  patient_name: string | null
  ward: string | null
  workflow_status: string
  latest_tier: 'HIGH' | 'MEDIUM' | 'LOW' | null
  ml_score: number | null
  priority_reasons: Array<{ source: string; reason: string; tier: string }>
  admitted_at: string
  sla_hours_elapsed: number | null
  claimed_by: string | null
  claimed_at: string | null
  row_version: number
  dpjp_name: string | null
}

export interface WorklistResponseV1 {
  items: WorklistItemV1[]
  total: number
  page: number
  page_size: number
  has_next: boolean
}

export interface WorklistFilters {
  tier?: 'HIGH' | 'MEDIUM' | 'LOW'
  status?: string
  ward?: string
  assigned_to_me?: boolean
  search?: string
  page?: number
  page_size?: number
}

export function getWorklistV1(filters?: WorklistFilters): Promise<WorklistResponseV1> {
  const q = new URLSearchParams()
  if (filters?.tier) q.set('tier', filters.tier)
  if (filters?.status) q.set('status', filters.status)
  if (filters?.ward) q.set('ward', filters.ward)
  if (filters?.assigned_to_me) q.set('assigned_to_me', 'true')
  if (filters?.search) q.set('search', filters.search)
  if (filters?.page) q.set('page', String(filters.page))
  if (filters?.page_size) q.set('page_size', String(filters.page_size))
  return apiFetch<WorklistResponseV1>(`/worklist?${q.toString()}`)
}

export function claimEncounterV1(encounterId: string, rowVersion?: number) {
  const headers: Record<string, string> = {}
  if (rowVersion !== undefined) headers['If-Match'] = String(rowVersion)
  return apiFetch<{ status: string; encounter_id: string; claimed_by: string; row_version: number }>(
    `/worklist/${encounterId}/claim`,
    { method: 'POST', headers },
  )
}

export function releaseEncounterV1(encounterId: string) {
  return apiFetch<{ status: string; encounter_id: string; claimed_by: null }>(
    `/worklist/${encounterId}/release`,
    { method: 'POST' },
  )
}

// ---------------------------------------------------------------------------
// Review endpoint (B-108)
// ---------------------------------------------------------------------------
export type ReviewAction = 'APPROVE' | 'EDIT' | 'REJECT' | 'ESCALATE' | 'DRAFT_REVIEW'

export interface ReviewRequestV1 {
  action: ReviewAction
  reason?: string
  note?: string
  ai_snapshot?: Record<string, unknown>
}

export interface ReviewResponseV1 {
  status: string
  encounter_id: string
  action: string
  new_workflow_status: string
  row_version: number
  audit_entry_id: string
  idempotent: boolean
}

export function submitReviewV1(
  encounterId: string,
  body: ReviewRequestV1,
  opts?: { idempotencyKey?: string; ifMatch?: number },
): Promise<ReviewResponseV1> {
  const headers: Record<string, string> = {}
  if (opts?.idempotencyKey) headers['Idempotency-Key'] = opts.idempotencyKey
  if (opts?.ifMatch !== undefined) headers['If-Match'] = String(opts.ifMatch)
  return apiFetch<ReviewResponseV1>(`/encounters/${encounterId}/review`, {
    method: 'POST',
    body: JSON.stringify(body),
    headers,
  })
}

export function getReviewHistoryV1(encounterId: string) {
  return apiFetch<{ encounter_id: string; current_status: string; history: unknown[] }>(
    `/encounters/${encounterId}/review/history`,
  )
}

// ---------------------------------------------------------------------------
// Audit chain verify  (B-107)
// ---------------------------------------------------------------------------
export interface AuditVerifyResult {
  valid: boolean
  count: number
  first_broken_seq: number | null
  message: string
}

export function verifyAuditChain(full = false): Promise<AuditVerifyResult> {
  return apiFetch<AuditVerifyResult>(`/audit/verify?full=${full}`)
}

// ---------------------------------------------------------------------------
// Health  (v1)
// ---------------------------------------------------------------------------
export interface HealthV1 {
  status: string
  api_version: string
  model_version: string
  rule_version: string
  db_status: string
  timestamp: string
}

export const getHealthV1 = () => apiFetch<HealthV1>('/health')

// ---------------------------------------------------------------------------
// Generic helpers (for use outside apiClient, e.g. langflow.ts → AI gateway)
// ---------------------------------------------------------------------------

/**
 * Generic authenticated GET — path is relative to /api/v1 (e.g. '/ai/health').
 * For absolute paths like '/api/v1/ai/sbar', strip the '/api/v1' prefix first.
 */
export function apiGet<T>(path: string): Promise<T> {
  const normalised = path.startsWith('/api/v1') ? path.slice('/api/v1'.length) : path
  return apiFetch<T>(normalised)
}

/**
 * Generic authenticated POST — path is relative to /api/v1.
 */
export function apiPost<T>(path: string, body: unknown): Promise<T> {
  const normalised = path.startsWith('/api/v1') ? path.slice('/api/v1'.length) : path
  return apiFetch<T>(normalised, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
