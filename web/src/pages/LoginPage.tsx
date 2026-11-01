/**
 * web/src/pages/LoginPage.tsx
 * ----------------------------
 * Halaman login sederhana untuk hackathon PrioMed-Rec.
 * - Username + password → POST /api/v1/auth/login
 * - Menyimpan token ke auth store
 * - Redirect ke worklist setelah berhasil
 * - Mengikuti desain system: Inter font, warna prioritas, kontras WCAG AA
 *
 * Task 3.1: Migrated from plain HTML to uiux/ design system primitives.
 * Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
 */
import { useState, FormEvent } from 'react'
import { HeartPulse } from 'lucide-react'
import { useAuthStore } from '../lib/auth'
import { loginApi, ApiError } from '../lib/apiClient'
import {
  Button,
  Field,
  Input,
  InlineAlert,
  SkipLink,
} from '../uiux/primitives'
import { SafetyBanner } from '../uiux/clinical'

interface Props {
  onSuccess: () => void
}

export function LoginPage({ onSuccess }: Props) {
  const login = useAuthStore((s) => s.login)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await loginApi(username, password)
      login(res.access_token, res.refresh_token)
      onSuccess()
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Gagal terhubung ke server. Periksa koneksi Anda.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Req 1.7: SkipLink at top of page */}
      <SkipLink />

      <div className="min-h-screen flex items-center justify-center bg-[var(--pmr-bg)]">
        <div className="w-full max-w-sm bg-white rounded-2xl shadow-md p-8">
          {/* Header — Req 1.1, 1.2 */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-2 mb-3">
              {/* Req 1.2: HeartPulse icon matching AppShell Brand */}
              <div className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 text-white shadow-lg">
                <HeartPulse className="size-5" />
              </div>
              <h1 className="font-display text-xl font-bold text-slate-900">PrioMed-Rec</h1>
            </div>
            <p className="text-sm text-slate-500">
              Sistem Prioritas Telaah Farmasi
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Rekonsiliasi Obat Admisi Rawat Inap
            </p>
          </div>

          <form id="pmr-main" onSubmit={handleSubmit} className="space-y-4">
            {/* Req 1.3: Field + Input with htmlFor/id associations */}
            <Field label="Username" htmlFor="login-username" required>
              <Input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="apoteker1"
                autoComplete="username"
              />
            </Field>

            <Field label="Password" htmlFor="login-password" required>
              <Input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </Field>

            {/* Req 1.5: InlineAlert with tone "danger" for errors */}
            {error && (
              <InlineAlert tone="danger" title="Gagal masuk">
                {error}
              </InlineAlert>
            )}

            {/* Req 1.6, 1.8: Button with lg size (min-h-12) and loading prop */}
            <Button
              type="submit"
              size="lg"
              loading={loading}
              className="w-full"
            >
              Masuk
            </Button>
          </form>

          {/* Demo credentials hint */}
          <div className="mt-6 p-3 bg-slate-50 rounded-lg border border-slate-200">
            <p className="text-xs text-slate-500 font-medium mb-2">Akun Demo:</p>
            <div className="space-y-1 text-xs text-slate-600 font-mono">
              <div>apoteker1 / demo1234 <span className="text-blue-600">(PHARMACIST)</span></div>
              <div>ttk1 / demo1234 <span className="text-blue-600">(TECHNICIAN)</span></div>
              <div>koordinator1 / demo1234 <span className="text-blue-600">(COORDINATOR)</span></div>
              <div>admin / admin1234 <span className="text-blue-600">(ADMIN)</span></div>
            </div>
          </div>

          {/* Req 1.4: SafetyBanner below the form */}
          <div className="mt-4">
            <SafetyBanner compact />
          </div>
        </div>
      </div>
    </>
  )
}
