import { useState, type ReactNode } from "react"
import {
  Activity,
  BarChart3,
  BookOpen,
  ClipboardCheck,
  ClipboardList,
  FileClock,
  FlaskConical,
  HeartPulse,
  Menu,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  UserRound,
  X,
} from "lucide-react"
import type {
  PageId,
  Patient,
  RiskLevel,
  ViewState,
  WorkflowStatus,
} from "../types/clinical"
import { Badge, Button, Card, Heading, IconButton, Select } from "./ui"

export function PriorityBadge({
  level,
  score,
  compact = false,
}: {
  level: RiskLevel
  score?: number
  compact?: boolean
}) {
  const tone =
    level === "HIGH" ? "danger" : level === "MEDIUM" ? "warning" : "success"
  return (
    <Badge tone={tone} className="whitespace-nowrap">
      <span aria-hidden="true">
        {level === "HIGH" ? "▲" : level === "MEDIUM" ? "◆" : "●"}
      </span>
      {level}
      {!compact && score !== undefined ? ` · ${score.toFixed(2)}` : ""}
    </Badge>
  )
}

export function StatusBadge({ status }: { status: WorkflowStatus }) {
  const tone =
    status === "Menunggu BPMH"
      ? "neutral"
      : status === "Siap dianalisis"
        ? "info"
        : status === "Perlu verifikasi"
          ? "warning"
          : status === "Disetujui"
            ? "success"
            : "danger"
  return <Badge tone={tone}>{status}</Badge>
}

export function VerificationNotice({
  kind,
  compact = false,
}: {
  kind: "ml" | "rule" | "ai"
  compact?: boolean
}) {
  const config = {
    ml: { icon: BarChart3, title: "Prediksi ML", text: "wajib diverifikasi" },
    rule: {
      icon: SlidersHorizontal,
      title: "Flag rule engine",
      text: "perlu konfirmasi apoteker",
    },
    ai: {
      icon: Sparkles,
      title: "Draf AI",
      text: "wajib diverifikasi sebelum digunakan",
    },
  }[kind]
  const Icon = config.icon
  return (
    <div
      className={`flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 text-amber-950 ${
        compact ? "px-2.5 py-1.5 text-[0.6875rem]" : "p-3 text-xs"
      }`}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>
        <strong>{config.title}</strong> · {config.text}
      </span>
    </div>
  )
}

export function KpiCard({
  label,
  value,
  detail,
  tone = "default",
  icon,
}: {
  label: string
  value: string
  detail: string
  tone?: "default" | "danger" | "warning" | "info"
  icon: ReactNode
}) {
  const tones = {
    default: "border-slate-200",
    danger: "border-l-red-600 border-l-4",
    warning: "border-l-amber-500 border-l-4",
    info: "border-l-blue-600 border-l-4",
  }
  return (
    <Card variant="compact" className={tones[tone]}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="mt-1 font-mono text-2xl font-bold text-slate-950">
            {value}
          </p>
          <p className="mt-1 text-xs text-slate-500">{detail}</p>
        </div>
        <div className="rounded-md bg-slate-100 p-2 text-slate-600">{icon}</div>
      </div>
    </Card>
  )
}

export function PatientSummary({
  patient,
  compact = false,
}: {
  patient: Patient
  compact?: boolean
}) {
  return (
    <div
      className={`grid gap-4 ${
        compact ? "grid-cols-2" : "sm:grid-cols-2 xl:grid-cols-5"
      }`}
    >
      {[
        ["Pasien", patient.id],
        ["Bangsal", patient.ward],
        ["Usia", `${patient.age} tahun`],
        ["Admisi", patient.admittedAt],
      ].map(([label, value]) => (
        <div key={label}>
          <p className="text-[0.6875rem] font-bold uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
        </div>
      ))}
      {!compact && (
        <div>
          <p className="text-[0.6875rem] font-bold uppercase tracking-wide text-slate-500">
            Prioritas
          </p>
          <div className="mt-1">
            <PriorityBadge
              level={patient.riskLevel}
              score={patient.riskScore}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export function RiskContributionChart({ patient }: { patient: Patient }) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Heading level={2}>Kontribusi terhadap skor</Heading>
          <p className="mt-1 text-sm text-slate-600">
            Faktor yang meningkatkan atau menurunkan estimasi risiko pada model
            demo.
          </p>
        </div>
        <VerificationNotice kind="ml" compact />
      </div>
      <div className="mt-6 space-y-4">
        {patient.contributions.map((item) => {
          const width = `${Math.min(Math.abs(item.value) / 0.25, 1) * 48}%`
          return (
            <div
              key={item.label}
              className="grid gap-1 md:grid-cols-[12rem_1fr_4rem] md:items-center"
            >
              <div>
                <p className="text-sm font-semibold text-slate-800">
                  {item.label}
                </p>
                <p className="text-xs text-slate-500">{item.detail}</p>
              </div>
              <div className="relative h-7 rounded bg-slate-100">
                <div className="absolute inset-y-0 left-1/2 w-px bg-slate-400" />
                <div
                  className={`absolute top-1 h-5 rounded-sm ${
                    item.value >= 0
                      ? "left-1/2 bg-blue-600"
                      : "right-1/2 bg-cyan-600"
                  }`}
                  style={{ width }}
                />
              </div>
              <p
                className={`font-mono text-sm font-bold ${
                  item.value >= 0 ? "text-blue-700" : "text-cyan-800"
                }`}
              >
                {item.value > 0 ? "+" : ""}
                {item.value.toFixed(2)}
              </p>
            </div>
          )
        })}
      </div>
      <div className="mt-5 flex flex-wrap gap-4 border-t border-slate-200 pt-4 text-xs text-slate-600">
        <span>
          <span className="mr-1 inline-block size-2.5 bg-blue-600" />{" "}
          Meningkatkan estimasi
        </span>
        <span>
          <span className="mr-1 inline-block size-2.5 bg-cyan-600" /> Menurunkan
          estimasi
        </span>
        <span className="font-semibold text-slate-700">
          Kontribusi statistik, bukan alasan medis pasti.
        </span>
      </div>
    </Card>
  )
}

const navigation: Array<{
  id: PageId
  label: string
  icon: typeof ClipboardList
}> = [
  { id: "queue", label: "Antrean Farmasi", icon: Sparkles },
  { id: "command_center", label: "Command Center", icon: Activity },
  { id: "worklist", label: "Worklist", icon: ClipboardList },
  { id: "tutorial", label: "Tutorial", icon: BookOpen },
  { id: "bpmh", label: "Form BPMH", icon: ClipboardCheck },
  { id: "analysis", label: "Detail & Analisis", icon: FlaskConical },
  { id: "audit", label: "Audit Log", icon: FileClock },
  { id: "settings", label: "Pengaturan", icon: Settings },
]

const HOSPITAL_SIDEBAR_IMAGE =
  "/hospital-sidebar.png"

export function AppShell({
  page,
  onNavigate,
  viewState,
  onViewState,
  children,
}: {
  page: PageId
  onNavigate: (page: PageId) => void
  viewState: ViewState
  onViewState: (state: ViewState) => void
  children: ReactNode
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const activeLabel = navigation.find((item) => item.id === page)?.label
  return (
    <div className="min-h-screen bg-slate-100">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col overflow-hidden border-r border-blue-900/40 bg-[#0A1F44] text-white shadow-2xl lg:flex">
        {/* Background hospital image + elegant layered blue gradient overlay */}
        <div className="pointer-events-none absolute inset-0" aria-hidden="true">
          <img
            src={HOSPITAL_SIDEBAR_IMAGE}
            alt=""
            className="size-full object-cover object-[55%_center] brightness-105 saturate-105 contrast-105"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-[#071633]/40 via-[#0A1F44]/18 to-[#061329]/65" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#061A3A]/38 via-transparent to-[#0A1F44]/15" />
          <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-[#061329]/70 to-transparent" />
        </div>

        <div className="relative z-10 border-b border-cyan-100/30 bg-[#061329]/40 px-5 py-5 backdrop-blur-sm">
          <div className="flex items-center gap-3.5">
            <div className="relative flex size-11 shrink-0 items-center justify-center rounded-xl border border-cyan-100/80 bg-gradient-to-br from-white via-cyan-50 to-cyan-200 text-blue-800 shadow-lg shadow-slate-950/40">
              <HeartPulse className="size-6" strokeWidth={2.3} />
              <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full border-2 border-[#0A1F44] bg-emerald-400 text-[0.625rem] font-black leading-none text-[#0A1F44]">
                +
              </span>
            </div>
            <div>
              <p className="font-['Plus_Jakarta_Sans'] text-[1.15rem] font-extrabold tracking-[-0.025em] text-white drop-shadow-sm">
                Prio<span className="text-cyan-300">Med</span>
                <span className="font-semibold text-blue-100">-Rec</span>
              </p>
              <p className="mt-0.5 text-[0.625rem] font-semibold uppercase tracking-[0.13em] text-cyan-200/95">
                Medication Safety
              </p>
            </div>
          </div>
        </div>
        <div className="relative z-10 mx-3 mt-4 flex items-center justify-between rounded-md bg-[#061329]/70 px-3 py-2 text-[0.6875rem] font-extrabold uppercase tracking-[0.16em] text-cyan-100 shadow-sm ring-1 ring-white/15 backdrop-blur-sm">
          <span>Menu utama</span>
          <span className="h-px w-12 bg-gradient-to-r from-cyan-300/50 to-transparent" />
        </div>
        <nav
          className="relative z-10 flex-1 space-y-1.5 px-3 py-2.5"
          aria-label="Navigasi utama"
        >
          {navigation.map((item) => {
            const Icon = item.icon
            const isActive = page === item.id
            return (
              <Button
                key={item.id}
                variant="ghost"
                onClick={() => onNavigate(item.id)}
                className={`w-full justify-start rounded-lg border-0 border-l-4 text-sm font-semibold tracking-wide transition-all duration-150 ${
                  isActive
                    ? "border-l-cyan-300 bg-gradient-to-r from-[#1F6FEB]/95 via-blue-600/90 to-cyan-500/80 text-white shadow-lg shadow-blue-950/50 ring-1 ring-white/20 backdrop-blur-sm hover:from-[#1F6FEB] hover:to-cyan-500/90"
                    : "border-l-transparent bg-gradient-to-r from-[#061329]/80 via-[#061A3A]/68 to-[#0A1F44]/52 text-white shadow-sm ring-1 ring-white/20 backdrop-blur-[2px] hover:border-l-cyan-300/75 hover:from-[#0A2A57]/90 hover:via-[#0A2A57]/80 hover:to-[#0A2A57]/65 hover:text-white hover:ring-cyan-200/35"
                }`}
                icon={
                  <Icon
                    className={`size-4 transition-colors ${
                      isActive ? "text-cyan-200" : "text-cyan-200/85"
                    }`}
                  />
                }
              >
                {item.label}
              </Button>
            )
          })}
        </nav>
        <div className="relative z-10 border-t border-cyan-200/20 bg-slate-950/35 p-4 backdrop-blur-md">
          <div className="rounded-lg border border-cyan-200/25 bg-gradient-to-br from-white/15 to-blue-900/30 p-3 text-xs leading-relaxed text-blue-50 shadow-inner">
            <div className="mb-1.5 flex items-center gap-1.5 font-semibold text-cyan-200">
              <ShieldCheck className="size-4 shrink-0 text-cyan-300" />
              <span>Standar Keselamatan</span>
            </div>
            Bukan triase medis darurat. Keputusan klinis tetap oleh apoteker.
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 overflow-hidden border-b border-blue-950/30 bg-gradient-to-r from-[#071A3A] via-[#124B96] to-[#087EA4] text-white shadow-[0_8px_24px_rgba(10,31,68,0.16)]">
          <div className="pointer-events-none absolute -right-16 -top-24 size-64 rounded-full bg-cyan-300/15 blur-3xl" />
          <div className="pointer-events-none absolute left-1/3 top-0 h-px w-1/2 bg-gradient-to-r from-transparent via-cyan-200/60 to-transparent" />
          <div className="relative z-10 flex min-h-16 items-center justify-between gap-3 px-4 md:px-6">
            <div className="flex items-center gap-3">
              <IconButton
                label="Buka menu navigasi"
                className="border border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white lg:hidden"
                onClick={() => setMobileMenuOpen(true)}
              >
                <Menu className="size-5" />
              </IconButton>
              <div>
                <p className="text-[0.6875rem] font-bold uppercase tracking-[0.14em] text-cyan-100/90">
                  Ruang kerja klinis
                </p>
                <p className="font-['Plus_Jakarta_Sans'] font-bold text-white">
                  {activeLabel}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone="cyan">
                <FlaskConical className="size-3" />
                <span className="hidden sm:inline">Mode data: </span>Sintetis
              </Badge>
              <div className="hidden items-center gap-2 border-l border-white/20 pl-3 md:flex">
                <div className="flex size-8 items-center justify-center rounded-full bg-white/15 ring-1 ring-white/20">
                  <UserRound className="size-4" />
                </div>
                <div className="text-xs">
                  <p className="font-bold text-white">Apt. Maya R.</p>
                  <p className="text-blue-100">Farmasi Klinik</p>
                </div>
              </div>
            </div>
          </div>
          <div className="relative z-10 flex flex-wrap items-center justify-between gap-2 border-t border-white/15 bg-[#061329]/35 px-4 py-2 text-xs text-blue-50 backdrop-blur-md md:px-6">
            <div className="flex items-center gap-2.5">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-cyan-300/15 text-cyan-200 ring-1 ring-cyan-200/30">
                <ShieldCheck className="size-4" />
              </span>
              <span>
                <strong className="text-white">Verifikasi klinis wajib</strong>
                <span className="hidden text-blue-100 sm:inline">
                  {" "}
                  · Prototipe decision-support, keputusan akhir tetap oleh tenaga
                  kesehatan.
                </span>
              </span>
            </div>
            <label className="flex items-center gap-2 font-semibold text-blue-100">
              Tampilan
              <Select
                aria-label="Preview state halaman"
                className="min-h-8 w-28 border-white/25 bg-white/95 py-0 text-xs text-slate-800"
                value={viewState}
                onChange={(event) =>
                  onViewState(event.target.value as ViewState)
                }
                options={[
                  { value: "ready", label: "Ready" },
                  { value: "loading", label: "Loading" },
                  { value: "empty", label: "Empty" },
                  { value: "error", label: "Error" },
                ]}
              />
            </label>
          </div>
        </header>
        <main className="mx-auto max-w-[100rem] p-3 sm:p-4 md:p-6">{children}</main>
      </div>
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-[2px] lg:hidden"
          role="presentation"
          onMouseDown={(event) =>
            event.target === event.currentTarget && setMobileMenuOpen(false)
          }
        >
          <div className="relative flex h-full w-[min(86vw,20rem)] flex-col overflow-hidden bg-[#0A1F44] p-4 text-white shadow-2xl">
            {/* Mobile drawer background hospital image + blue gradient overlay */}
            <div className="pointer-events-none absolute inset-0" aria-hidden="true">
              <img
                src={HOSPITAL_SIDEBAR_IMAGE}
                alt=""
                className="size-full object-cover object-[55%_center] brightness-105 saturate-105 contrast-105"
              />
              <div className="absolute inset-0 bg-gradient-to-b from-[#071633]/40 via-[#0A1F44]/18 to-[#061329]/65" />
              <div className="absolute inset-0 bg-gradient-to-r from-[#061A3A]/38 via-transparent to-[#0A1F44]/15" />
              <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-[#061329]/70 to-transparent" />
            </div>

            <div className="relative z-10 flex items-center justify-between rounded-lg border-b border-cyan-100/30 bg-[#061329]/45 p-2.5 backdrop-blur-sm">
              <div className="flex items-center gap-3">
                <div className="relative flex size-10 shrink-0 items-center justify-center rounded-xl border border-cyan-100/80 bg-gradient-to-br from-white via-cyan-50 to-cyan-200 text-blue-800 shadow-md">
                  <HeartPulse className="size-5" strokeWidth={2.3} />
                  <span className="absolute -right-1 -top-1 flex size-3.5 items-center justify-center rounded-full border-2 border-[#0A1F44] bg-emerald-400 text-[0.55rem] font-black leading-none text-[#0A1F44]">
                    +
                  </span>
                </div>
                <div>
                  <p className="font-['Plus_Jakarta_Sans'] font-extrabold text-white">
                    Prio<span className="text-cyan-300">Med</span>
                    <span className="text-blue-100">-Rec</span>
                  </p>
                  <p className="text-[0.625rem] font-semibold uppercase tracking-widest text-cyan-200">
                    Medication Safety
                  </p>
                </div>
              </div>
              <IconButton
                label="Tutup menu navigasi"
                className="text-white hover:bg-white/15 hover:text-white"
                onClick={() => setMobileMenuOpen(false)}
              >
                <X className="size-5" />
              </IconButton>
            </div>
            <div className="relative z-10 mt-4 flex items-center justify-between rounded-md bg-[#061329]/70 px-3 py-2 text-[0.6875rem] font-extrabold uppercase tracking-[0.16em] text-cyan-100 shadow-sm ring-1 ring-white/15 backdrop-blur-sm">
              <span>Menu utama</span>
              <span className="h-px w-10 bg-gradient-to-r from-cyan-300/50 to-transparent" />
            </div>
            <nav
              className="relative z-10 mt-2.5 flex-1 space-y-1.5"
              aria-label="Navigasi mobile"
            >
              {navigation.map((item) => {
                const Icon = item.icon
                const isActive = page === item.id
                return (
                  <Button
                    key={item.id}
                    className={`w-full justify-start rounded-lg border-0 border-l-4 font-semibold ${
                      isActive
                        ? "border-l-cyan-300 bg-gradient-to-r from-[#1F6FEB]/95 via-blue-600/90 to-cyan-500/80 text-white shadow-md ring-1 ring-white/20"
                        : "border-l-transparent bg-gradient-to-r from-[#061329]/80 via-[#061A3A]/68 to-[#0A1F44]/52 text-white shadow-sm ring-1 ring-white/20 backdrop-blur-[2px] hover:border-l-cyan-300/75 hover:from-[#0A2A57]/90 hover:via-[#0A2A57]/80 hover:to-[#0A2A57]/65 hover:text-white hover:ring-cyan-200/35"
                    }`}
                    variant="ghost"
                    icon={
                      <Icon
                        className={`size-5 ${
                          isActive ? "text-cyan-200" : "text-cyan-200/85"
                        }`}
                      />
                    }
                    onClick={() => {
                      onNavigate(item.id)
                      setMobileMenuOpen(false)
                    }}
                  >
                    {item.label}
                  </Button>
                )
              })}
            </nav>
            <div className="relative z-10 rounded-lg border border-cyan-200/25 bg-gradient-to-br from-white/15 to-blue-900/35 p-3 text-xs leading-5 text-blue-50 backdrop-blur-sm">
              <div className="mb-1 flex items-center gap-1.5 font-semibold text-cyan-200">
                <ShieldCheck className="size-4 shrink-0 text-cyan-300" />
                <span>Standar Keselamatan</span>
              </div>
              Semua output sistem wajib diverifikasi apoteker.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function Drawer({
  open,
  onClose,
  children,
}: {
  open: boolean
  onClose: () => void
  children: ReactNode
}) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 bg-slate-950/45"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Ringkasan pasien"
        className="absolute inset-y-0 right-0 w-[min(92vw,32rem)] overflow-y-auto border-l border-slate-200 bg-white shadow-2xl"
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4">
          <Heading level={2}>Ringkasan pasien</Heading>
          <IconButton label="Tutup panel" onClick={onClose}>
            <X className="size-5" />
          </IconButton>
        </div>
        {children}
      </div>
    </div>
  )
}
