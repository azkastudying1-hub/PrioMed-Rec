/*
 * web/src/uiux/layout.tsx
 * ---------------------------------------------------------------------------
 * Kerangka aplikasi (AppShell) untuk seluruh halaman PrioMed-Rec.
 *
 * Struktur:
 *  - Sidebar navy gelap: navigasi per kelompok kerja + pengingat keselamatan.
 *  - Topbar putih: konteks halaman, mode data, status demo (khusus dev), user.
 *  - Strip keselamatan: pengingat bahwa keputusan tetap di tangan apoteker.
 *
 * Props sengaja dibuat sama dengan AppShell lama di components/clinical.tsx
 * supaya App.tsx bisa mengganti import tanpa mengubah seluruh halaman lain.
 */

import { useEffect, useState, type ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import {
  Activity,
  BookOpen,
  ClipboardCheck,
  ClipboardList,
  FileClock,
  FlaskConical,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react"
import { DATA_MODE } from "../api/client"
import { useAuthStore } from "../lib/auth"
import type { PageId, ViewState } from "../types/clinical"
import { Badge, IconButton, Select, SkipLink, cn } from "./primitives"
import { initials } from "./clinical"

interface NavItem {
  id: PageId
  label: string
  hint: string
  icon: LucideIcon
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Operasional",
    items: [
      { id: "queue", label: "Antrean Farmasi", hint: "Prioritas & SLA", icon: Sparkles },
      { id: "worklist", label: "Worklist Telaah", hint: "Kasus aktif", icon: ClipboardList },
      { id: "command_center", label: "Command Center", hint: "Beban & kapasitas", icon: Activity },
    ],
  },
  {
    label: "Telaah klinis",
    items: [
      { id: "bpmh", label: "Form BPMH", hint: "Riwayat obat", icon: ClipboardCheck },
      { id: "analysis", label: "Analisis Kasus", hint: "Temuan & SBAR", icon: FlaskConical },
    ],
  },
  {
    label: "Tata kelola",
    items: [
      { id: "audit", label: "Jejak Audit", hint: "Hash-chain", icon: FileClock },
      { id: "settings", label: "Pengaturan", hint: "Konfigurasi", icon: Settings },
    ],
  },
  {
    label: "Bantuan",
    items: [{ id: "tutorial", label: "Panduan Pengguna", hint: "Alur kerja", icon: BookOpen }],
  },
]

const ROLE_LABELS: Record<string, string> = {
  PHARMACIST: "Apoteker klinis",
  COORDINATOR: "Koordinator farmasi",
  ADMIN: "Administrator",
  AUDITOR: "Auditor",
  TECHNICIAN: "Teknisi farmasi",
}

export interface AppShellProps {
  page: PageId
  onNavigate: (page: PageId) => void
  viewState: ViewState
  onViewState: (state: ViewState) => void
  children: ReactNode
}

function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 text-white shadow-lg shadow-blue-950/40">
        <HeartPulse className="size-5" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="truncate font-display text-base font-extrabold tracking-tight text-white">
          PrioMed<span className="text-cyan-300">-Rec</span>
        </p>
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-200/75">
          Medication Safety
        </p>
      </div>
    </div>
  )
}

function SafetyNote() {
  return (
    <div className="rounded-lg border border-cyan-300/15 bg-cyan-300/5 p-3">
      <div className="flex items-center gap-2 text-[11px] font-bold text-cyan-200">
        <ShieldCheck className="size-3.5" aria-hidden="true" />
        Decision support
      </div>
      <p className="mt-1 text-[11px] leading-relaxed text-slate-300">
        Sistem membantu prioritas telaah, bukan menggantikan keputusan klinis apoteker.
      </p>
    </div>
  )
}

function NavList({
  page,
  onNavigate,
  onAfterNavigate,
}: {
  page: PageId
  onNavigate: (page: PageId) => void
  onAfterNavigate?: () => void
}) {
  return (
    <nav aria-label="Navigasi utama" className="space-y-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          <p className="px-3 pb-1.5 text-[9px] font-bold uppercase tracking-[0.2em] text-slate-400/70">
            {group.label}
          </p>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const active = page === item.id
              const Icon = item.icon
              return (
                <button
                  key={item.id}
                  type="button"
                  aria-current={active ? "page" : undefined}
                  onClick={() => {
                    onNavigate(item.id)
                    onAfterNavigate?.()
                  }}
                  className={cn(
                    "group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300",
                    active
                      ? "bg-white/10 text-white ring-1 ring-white/15"
                      : "text-slate-300 hover:bg-white/5 hover:text-white",
                  )}
                >
                  <Icon
                    className={cn(
                      "size-4 shrink-0",
                      active ? "text-cyan-300" : "text-slate-400 group-hover:text-cyan-200",
                    )}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-semibold">{item.label}</span>
                    <span className="block truncate text-[10px] text-slate-400/80">{item.hint}</span>
                  </span>
                  {active && <span className="size-1.5 rounded-full bg-cyan-300" aria-hidden="true" />}
                </button>
              )
            })}
          </div>
        </div>
      ))}
    </nav>
  )
}

export function AppShell({ page, onNavigate, viewState, onViewState, children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)

  const active = NAV_GROUPS.flatMap((group) => group.items).find((item) => item.id === page)
  const displayName = user?.username ?? "Apoteker"
  const roleLabel = ROLE_LABELS[user?.role ?? ""] ?? "Apoteker klinis"

  useEffect(() => {
    setMobileOpen(false)
  }, [page])

  useEffect(() => {
    if (!mobileOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [mobileOpen])

  return (
    <div className="min-h-screen bg-[var(--pmr-bg)]">
      <SkipLink />

      {/* Sidebar desktop */}
      <aside className="pmr-sidebar-surface fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-white/10 lg:flex">
        <div className="flex h-[var(--pmr-header-h)] items-center border-b border-white/10 px-4">
          <Brand />
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-4">
          <NavList page={page} onNavigate={onNavigate} />
        </div>
        <div className="space-y-3 border-t border-white/10 p-3">
          <SafetyNote />
          <div className="flex items-center gap-2 px-1">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/10 font-display text-[11px] font-bold text-cyan-200">
              {initials(displayName)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-white">{displayName}</p>
              <p className="truncate text-[10px] text-slate-400">{roleLabel}</p>
            </div>
            <IconButton
              label="Keluar"
              icon={<LogOut className="size-4" />}
              onClick={logout}
              className="text-slate-300 hover:bg-white/10 hover:text-white"
            />
          </div>
        </div>
      </aside>

      {/* Drawer mobile */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-950/55 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <div className="pmr-sidebar-surface pmr-enter absolute inset-y-0 left-0 flex w-[min(20rem,86vw)] flex-col shadow-2xl">
            <div className="flex h-[var(--pmr-header-h)] items-center justify-between border-b border-white/10 px-4">
              <Brand />
              <IconButton
                label="Tutup menu"
                icon={<X className="size-4" />}
                onClick={() => setMobileOpen(false)}
                className="text-slate-300 hover:bg-white/10 hover:text-white"
              />
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-4">
              <NavList
                page={page}
                onNavigate={onNavigate}
                onAfterNavigate={() => setMobileOpen(false)}
              />
            </div>
            <div className="space-y-3 border-t border-white/10 p-3">
              <SafetyNote />
              <button
                type="button"
                onClick={logout}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-xs font-semibold text-slate-300 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
              >
                <LogOut className="size-4" aria-hidden="true" />
                Keluar dari akun
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Area konten */}
      <div className="min-h-screen lg:pl-64">
        <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
          <div className="flex h-[var(--pmr-header-h)] items-center gap-3 px-4 sm:px-6 lg:px-8">
            <IconButton
              label="Buka menu"
              icon={<Menu className="size-5" />}
              onClick={() => setMobileOpen(true)}
              className="lg:hidden"
            />

            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-400">
                Ruang kerja
              </p>
              <p className="truncate font-display text-sm font-bold text-slate-900">
                {active?.label ?? "PrioMed-Rec"}
              </p>
            </div>

            <div className="flex items-center gap-2">
              {import.meta.env.DEV && (
                <label className="hidden items-center gap-1.5 text-[10px] font-semibold text-slate-500 xl:flex">
                  Status demo
                  <Select
                    value={viewState}
                    onChange={(event) => onViewState(event.target.value as ViewState)}
                    className="min-h-8 w-28 py-1 text-xs"
                    aria-label="Status demo halaman"
                  >
                    <option value="ready">Siap</option>
                    <option value="loading">Memuat</option>
                    <option value="empty">Kosong</option>
                    <option value="error">Gagal</option>
                  </Select>
                </label>
              )}

              <Badge
                tone={DATA_MODE === "live" ? "success" : "neutral"}
                dot
                className="hidden sm:inline-flex"
                title={
                  DATA_MODE === "live"
                    ? "Terhubung ke API live"
                    : "Menggunakan data sintetis untuk demo"
                }
              >
                {DATA_MODE === "live" ? "Data live" : "Data sintetis"}
              </Badge>

              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white py-1 pl-1 pr-1 shadow-sm">
                <div className="flex size-8 items-center justify-center rounded-md bg-gradient-to-br from-teal-500 to-blue-700 font-display text-[11px] font-extrabold text-white">
                  {initials(displayName)}
                </div>
                <div className="hidden min-w-0 pr-1 md:block">
                  <p className="max-w-32 truncate text-xs font-semibold text-slate-800">
                    {displayName}
                  </p>
                  <p className="max-w-32 truncate text-[10px] text-slate-500">{roleLabel}</p>
                </div>
                <IconButton
                  label="Keluar"
                  icon={<LogOut className="size-4" />}
                  onClick={logout}
                  compact
                />
              </div>
            </div>
          </div>

          <div className="border-t border-blue-100 bg-blue-50/70">
            <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 sm:px-6 lg:px-8">
              <p className="flex items-center gap-2 text-[11px] leading-relaxed text-blue-950">
                <ShieldCheck className="size-3.5 shrink-0 text-blue-700" aria-hidden="true" />
                <span>
                  <strong>Keputusan klinis tetap di tangan apoteker.</strong> Sistem hanya
                  memprioritaskan telaah dan menandai kandidat diskrepansi.
                </span>
              </p>
              <p className="hidden font-clinical-mono text-[9px] uppercase tracking-wider text-blue-800/70 md:block">
                WHO FIRST · WHAT TO CHECK · WHAT TO DO
              </p>
            </div>
          </div>
        </header>

        <main
          id="pmr-main"
          tabIndex={-1}
          className="mx-auto w-full max-w-[1600px] px-4 py-5 sm:px-6 lg:px-8"
        >
          {children}
        </main>

        <footer className="mx-auto w-full max-w-[1600px] px-4 pb-6 text-[10px] leading-relaxed text-slate-400 sm:px-6 lg:px-8">
          PrioMed-Rec · Alat bantu keputusan farmasi · Bukan pengganti penilaian klinis.
        </footer>
      </div>
    </div>
  )
}
