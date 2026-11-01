/**
 * src/api/hooks.ts
 * -----------------
 * React hooks for PrioMed-Rec FastAPI backend.
 *
 * Pattern: each hook returns { data, loading, error, refetch }
 * When VITE_DATA_MODE=synthetic (default), hooks return mock data immediately.
 * When VITE_DATA_MODE=live, hooks call the real FastAPI endpoints.
 */

import { useCallback, useEffect, useState } from 'react'
import {
  DATA_MODE,
  analyzePatient,
  getBatchWorklist,
  getHealth,
  submitReview,
  type AnalyzeResponse,
  type BatchPrioritizeResponse,
  type HealthResponse,
  type ReviewRequest,
  type ReviewResponse,
} from './client'

// ---------------------------------------------------------------------------
// Generic async hook
// ---------------------------------------------------------------------------

interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
  skip = false,
): AsyncState<T> & { refetch: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: !skip, error: null })

  const run = useCallback(() => {
    if (skip) return
    setState((s) => ({ ...s, loading: true, error: null }))
    fn()
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((err: Error) => setState({ data: null, loading: false, error: err.message }))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, skip])

  useEffect(() => { run() }, [run])

  return { ...state, refetch: run }
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

export function useHealth() {
  return useAsync<HealthResponse>(() => getHealth(), [])
}

// ---------------------------------------------------------------------------
// Worklist (batch prioritization)
// ---------------------------------------------------------------------------

export function useWorklist(limit = 50, priorityFilter?: string) {
  return useAsync<BatchPrioritizeResponse>(
    () => getBatchWorklist(limit, priorityFilter),
    [limit, priorityFilter],
    DATA_MODE === 'synthetic',
  )
}

// ---------------------------------------------------------------------------
// Patient analysis
// ---------------------------------------------------------------------------

export function useAnalysis(patientId: string, encounterId?: string) {
  return useAsync<AnalyzeResponse>(
    () => analyzePatient(patientId, encounterId),
    [patientId, encounterId],
    DATA_MODE === 'synthetic' || !patientId,
  )
}

// ---------------------------------------------------------------------------
// Submit review action (imperative — not a mount-time fetch)
// ---------------------------------------------------------------------------

export function useSubmitReview() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ReviewResponse | null>(null)

  const submit = useCallback(async (req: ReviewRequest) => {
    if (DATA_MODE === 'synthetic') {
      // Mock success in synthetic mode
      const mock: ReviewResponse = {
        review_id: `rev-${Date.now()}`,
        case_id: req.case_id,
        action: req.action,
        timestamp: new Date().toISOString(),
        pharmacist_id: req.pharmacist_id,
        model_version: null,
        rule_version: null,
        final_result: req.edited_result ?? req.ai_result,
      }
      setResult(mock)
      return mock
    }

    setLoading(true)
    setError(null)
    try {
      const res = await submitReview(req)
      setResult(res)
      return res
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  return { submit, loading, error, result }
}
