/**
 * web/src/api/queue.ts
 * ---------------------
 * Klien API Antrean Farmasi & Command Center (QUEUE_PLAN §6–§8).
 *
 *   GET  /api/v1/queue                 daftar antrean (keyset)
 *   GET  /api/v1/queue/mine            Antrean Saya (klaim aktif + pratinjau)
 *   POST /api/v1/queue/next            Ambil pasien berikutnya (atomik, lease 15 mnt)
 *   POST /api/v1/queue/:id/heartbeat   perpanjang lease
 *   POST /api/v1/queue/:id/release     lepas klaim
 *   POST /api/v1/queue/:id/resume      kembalikan kasus PARKED_DPJP
 *   GET  /api/v1/queue/command-center  data koordinator
 *   GET  /api/v1/events/queue          SSE (fetch-stream agar bisa membawa Bearer token)
 *
 * Semua panggilan memakai `apiGet/apiPost` (Bearer JWT + auto-refresh).
 * ADR-20: tidak ada LLM/Langflow di jalur antrean.
 */

import { apiGet, apiPost } from '../lib/apiClient'
import { useAuthStore } from '../lib/auth'

// ---------------------------------------------------------------------------
// Types — mengikuti kontrak backend (api/routes/v1/queue.py)
// ---------------------------------------------------------------------------

export type QueueTier = 'HIGH' | 'MEDIUM' | 'LOW'
export type TierSource = 'RULE' | 'ML' | 'SLA'
export type QueueType = 'BPMH' | 'REVIEW'
export type QueueState = 'OPEN' | 'CLAIMED' | 'PARKED_DPJP' | 'CLOSED'

export interface PriorityReason {
  source: string
  reason: string
  tier: string
}

export interface QueueEntry {
  encounter_id: string
  queue_type: QueueType
  ward: string
  state: QueueState
  tier_rank: number
  tier_source: TierSource
  priority_score: number
  ml_percentile: number | null
  depth_level: number
  admitted_at: string
  sla_due_at: string | null
  next_due_at: string | null
  discharge_planned_at: string | null
  claimed_by: string | null
  claim_expires_at: string | null
  queue_version: number
  // pengayaan
  tier: QueueTier
  patient_id: string | null
  patient_name: string | null
  dpjp_name: string | null
  ml_score: number | null
  workflow_status: string | null
  row_version: number
  priority_reasons: PriorityReason[]
  hours_waiting: number | null
  sla_target_hours: number | null
  sla_ratio: number | null
  claimed_by_name: string | null
  lease_seconds_left: number | null
  why: string[]
}

export interface QueueListResponse {
  items: QueueEntry[]
  has_next: boolean
  next_cursor: string | null
  count: number
  total: number
}

export interface MyQueueResponse {
  claimed: QueueEntry[]
  upcoming: QueueEntry[]
}

export interface QueueListParams {
  queue_type?: QueueType
  ward?: string
  tier?: QueueTier
  state?: QueueState
  search?: string
  after_cursor?: string
  limit?: number
}

export function getQueueList(p: QueueListParams = {}): Promise<QueueListResponse> {
  const q = new URLSearchParams()
  if (p.queue_type) q.set('queue_type', p.queue_type)
  if (p.ward) q.set('ward', p.ward)
  if (p.tier) q.set('tier', p.tier)
  if (p.state) q.set('state', p.state)
  if (p.search?.trim()) q.set('search', p.search.trim())
  if (p.after_cursor) q.set('after_cursor', p.after_cursor)
  q.set('limit', String(p.limit ?? 50))
  return apiGet<QueueListResponse>(`/queue?${q}`)
}

export const getMyQueue = () => apiGet<MyQueueResponse>('/queue/mine')

/** Ambil pasien berikutnya. `null` bila antrean kosong / tidak ada yang sesuai cakupan. */
export async function claimNext(
  queueType: QueueType,
  wardScope?: string[],
): Promise<QueueEntry | null> {
  const q = new URLSearchParams({ queue_type: queueType })
  if (wardScope?.length) q.set('ward_scope', wardScope.join(','))
  const res = await apiPost<QueueEntry | { message: string }>(`/queue/next?${q}`, {})
  return 'encounter_id' in res ? res : null
}

export const heartbeatEntry = (encounterId: string) =>
  apiPost<{ encounter_id: string; claim_expires_at: string }>(
    `/queue/${encounterId}/heartbeat`, {})

export const releaseEntry = (encounterId: string) =>
  apiPost<{ encounter_id: string; state: string }>(`/queue/${encounterId}/release`, {})

export const resumeEntry = (encounterId: string) =>
  apiPost<{ encounter_id: string; state: string }>(`/queue/${encounterId}/resume`, {})

// ---------------------------------------------------------------------------
// Command Center
// ---------------------------------------------------------------------------

export interface AtRiskItem {
  encounter_id: string
  patient_id: string | null
  patient_name: string | null
  ward: string
  tier: QueueTier
  tier_source: TierSource
  queue_type: QueueType
  state: QueueState
  hours_waiting: number
  sla_target_hours: number
  sla_ratio: number
  claimed_by: string | null
}

export interface CommandCenterData {
  as_of: string
  queue_version: number
  simulated_label: string
  totals: {
    open_total: number
    review_open: number
    bpmh_open: number
    claimed: number
    parked_dpjp: number
    high_open: number
  }
  heatmap: {
    wards: string[]
    tiers: QueueTier[]
    cells: Record<string, Record<QueueTier, number>>
  }
  aging: { buckets: string[]; by_tier: Record<QueueTier, number[]> }
  at_risk: { total: number; items: AtRiskItem[] }
  capacity: {
    pharmacists_on_duty: number
    shift_minutes: number
    productive_pct: number
    capacity_minutes: number
    demand_minutes: number
    pipeline_minutes: number
    load_ratio: number
    extra_pharmacist_hours: number
    review_minutes: Record<QueueTier, number>
    assumption_note: string
  }
  surge: {
    active: boolean
    reasons: string[]
    recommendations: string[]
    thresholds: { load_ratio: number; backlog: number; high_p90_pct_of_sla: number }
    note: string
  }
  flow: {
    bpmh_open: number
    review_open: number
    claimed: number
    parked_dpjp: number
    closed_total: number
    events_24h: Record<string, number>
  }
  safety: {
    sla_high_pct: number | null
    age_distribution: Record<
      QueueTier,
      { p50_hours: number | null; p90_hours: number | null; p99_hours: number | null }
    >
    missed_reconciliations: { today: number; total: number }
    expired_claims: number
    tier_source_ratio: Record<string, number>
  }
}

export function getCommandCenter(pharmacists?: number): Promise<CommandCenterData> {
  const q = pharmacists ? `?pharmacists=${pharmacists}` : ''
  return apiGet<CommandCenterData>(`/queue/command-center${q}`)
}

// ---------------------------------------------------------------------------
// SSE — fetch-stream (EventSource tidak bisa mengirim header Authorization)
// ---------------------------------------------------------------------------

export type SseStatus = 'connecting' | 'live' | 'reconnecting' | 'offline'

export interface QueueSseEvent {
  id: string | null
  event: string
  data: Record<string, unknown>
}

/**
 * Berlangganan `/events/queue?from_now=true`.
 * - Sambung ulang otomatis (backoff 1→15 dtk) dengan `Last-Event-ID`.
 * - `onStatus('live')` dipanggil pada setiap frame (termasuk heartbeat 15 dtk).
 * - Mengembalikan fungsi cleanup.
 */
export function subscribeQueueEvents(
  onEvent: (e: QueueSseEvent) => void,
  onStatus: (s: SseStatus) => void,
): () => void {
  const ctrl = new AbortController()
  let lastId: string | null = null
  let attempt = 0
  let stopped = false

  const run = async () => {
    while (!stopped) {
      onStatus(attempt === 0 ? 'connecting' : 'reconnecting')
      try {
        const token = useAuthStore.getState().accessToken
        const headers: Record<string, string> = { Accept: 'text/event-stream' }
        if (token) headers.Authorization = `Bearer ${token}`
        if (lastId) headers['Last-Event-ID'] = lastId

        const url = lastId ? '/api/v1/events/queue' : '/api/v1/events/queue?from_now=true'
        const res = await fetch(url, { headers, signal: ctrl.signal })

        if (res.status === 401) {
          const ok = await useAuthStore.getState().refreshAccessToken()
          if (!ok) throw new Error('unauthorized')
          continue
        }
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

        attempt = 0
        onStatus('live')
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''
        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          let idx: number
          while ((idx = buf.indexOf('\n\n')) >= 0) {
            const frame = buf.slice(0, idx)
            buf = buf.slice(idx + 2)
            const ev = parseFrame(frame)
            if (!ev) continue
            if (ev.id) lastId = ev.id
            onStatus('live')
            onEvent(ev)
          }
        }
      } catch (err) {
        if (stopped || (err as Error).name === 'AbortError') return
      }
      attempt += 1
      onStatus(attempt > 3 ? 'offline' : 'reconnecting')
      await new Promise((r) => setTimeout(r, Math.min(1000 * 2 ** attempt, 15000)))
    }
  }
  void run()

  return () => {
    stopped = true
    ctrl.abort()
  }
}

function parseFrame(frame: string): QueueSseEvent | null {
  let id: string | null = null
  let event = 'message'
  const data: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue
    if (line.startsWith('id:')) id = line.slice(3).trim()
    else if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trim())
  }
  if (!data.length) return null
  try {
    return { id, event, data: JSON.parse(data.join('\n')) }
  } catch {
    return null
  }
}
