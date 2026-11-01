/**
 * web/src/lib/auth.ts
 * --------------------
 * JWT auth store + token management (F-201).
 *
 * - Tokens stored in memory (access) + localStorage (refresh)
 * - Idle lock after 30 minutes of inactivity (configurable)
 * - Identity from decoded JWT payload — never from backend body
 *
 * S7: Semua panggilan ke backend melalui apiFetch yang menambahkan Bearer token
 */

import { create } from 'zustand'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface TokenPayload {
  sub: string       // user_id
  username: string
  role: string      // PHARMACIST | TECHNICIAN | COORDINATOR | ADMIN | AUDITOR
  actor_type: string
  exp: number
}

export interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: TokenPayload | null
  isAuthenticated: boolean
  isLocked: boolean  // idle lock
}

export interface AuthActions {
  login: (accessToken: string, refreshToken: string) => void
  logout: () => void
  lock: () => void
  unlock: (accessToken: string) => void
  refreshAccessToken: () => Promise<boolean>
}

// ---------------------------------------------------------------------------
// JWT decode (no verification — server already verified)
// ---------------------------------------------------------------------------
function decodeJwt(token: string): TokenPayload | null {
  try {
    const payload = token.split('.')[1]
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
    return decoded as TokenPayload
  } catch {
    return null
  }
}

function isExpired(payload: TokenPayload): boolean {
  return Date.now() / 1000 > payload.exp
}

// ---------------------------------------------------------------------------
// Zustand store
// ---------------------------------------------------------------------------
export const useAuthStore = create<AuthState & AuthActions>((set, get) => ({
  accessToken: null,
  refreshToken: localStorage.getItem('priomed_refresh_token'),
  user: null,
  isAuthenticated: false,
  isLocked: false,

  login(accessToken, refreshToken) {
    const user = decodeJwt(accessToken)
    localStorage.setItem('priomed_refresh_token', refreshToken)
    set({ accessToken, refreshToken, user, isAuthenticated: true, isLocked: false })
  },

  logout() {
    localStorage.removeItem('priomed_refresh_token')
    set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false, isLocked: false })
  },

  lock() {
    set({ isLocked: true })
  },

  unlock(accessToken) {
    const user = decodeJwt(accessToken)
    set({ accessToken, user, isLocked: false })
  },

  async refreshAccessToken() {
    const { refreshToken } = get()
    if (!refreshToken) return false
    try {
      const res = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) {
        get().logout()
        return false
      }
      const data = await res.json() as { access_token: string }
      const user = decodeJwt(data.access_token)
      set({ accessToken: data.access_token, user, isAuthenticated: true, isLocked: false })
      return true
    } catch {
      get().logout()
      return false
    }
  },
}))

// ---------------------------------------------------------------------------
// Idle lock timer
// ---------------------------------------------------------------------------
const IDLE_MINUTES = 30

let _idleTimer: ReturnType<typeof setTimeout> | null = null

export function resetIdleTimer() {
  if (_idleTimer) clearTimeout(_idleTimer)
  _idleTimer = setTimeout(() => {
    const state = useAuthStore.getState()
    if (state.isAuthenticated) {
      state.lock()
    }
  }, IDLE_MINUTES * 60 * 1000)
}

export function initIdleListener() {
  const events = ['mousemove', 'keydown', 'mousedown', 'touchstart', 'scroll']
  events.forEach(e => document.addEventListener(e, resetIdleTimer, { passive: true }))
  resetIdleTimer()
}

export function cleanupIdleListener() {
  const events = ['mousemove', 'keydown', 'mousedown', 'touchstart', 'scroll']
  events.forEach(e => document.removeEventListener(e, resetIdleTimer))
  if (_idleTimer) clearTimeout(_idleTimer)
}
