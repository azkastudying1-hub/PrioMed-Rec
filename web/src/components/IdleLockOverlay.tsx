/**
 * web/src/components/IdleLockOverlay.tsx
 * ----------------------------------------
 * Overlay yang muncul saat sesi idle > 30 menit (F-201).
 * Apoteker perlu memasukkan password lagi untuk membuka kunci.
 */

import { useState, FormEvent } from 'react'
import { useAuthStore } from '../lib/auth'
import { loginApi, ApiError } from '../lib/apiClient'

export function IdleLockOverlay() {
  const { user, isLocked, unlock, logout } = useAuthStore()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (!isLocked) return null

  async function handleUnlock(e: FormEvent) {
    e.preventDefault()
    if (!user?.username) return
    setError(null)
    setLoading(true)
    try {
      const res = await loginApi(user.username, password)
      unlock(res.access_token)
      setPassword('')
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Gagal memverifikasi. Coba lagi.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 backdrop-blur-sm">
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-6">
          <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <span className="text-2xl">🔒</span>
          </div>
          <h2 className="text-lg font-semibold text-slate-800">Sesi Dikunci</h2>
          <p className="text-sm text-slate-500 mt-1">
            Sesi idle selama 30 menit. Masukkan password untuk melanjutkan.
          </p>
          {user && (
            <p className="text-xs text-blue-600 mt-1 font-medium">{user.username}</p>
          )}
        </div>

        <form onSubmit={handleUnlock} className="space-y-4">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Password"
            autoFocus
            required
          />

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Memverifikasi...' : 'Buka Kunci'}
          </button>

          <button
            type="button"
            onClick={logout}
            className="w-full py-2 text-sm text-slate-500 hover:text-slate-700 transition-colors"
          >
            Logout & Keluar
          </button>
        </form>
      </div>
    </div>
  )
}
