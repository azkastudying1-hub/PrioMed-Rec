/**
 * web/src/pages/QueuePage.tsx
 * -----------------------------
 * Halaman Antrean Farmasi (QUEUE_PLAN Q-008).
 *
 * Fitur:
 * - Tombol "Ambil pasien berikutnya" (POST /queue/next) + pintasan keyboard `N`
 * - "Antrean Saya": klaim aktif + countdown lease, heartbeat, lepas klaim
 * - Antrean Bangsal: filter tier/status/bangsal + pencarian, keyset "Muat lagi"
 * - Aging strip per baris (usia tunggu relatif SLA) + badge sumber tier
 * - Status koneksi SSE + banner "N pembaruan — muat ulang urutan"
 * - Indikator "Data simulasi"
 *
 * Keselamatan:
 * - ADR-20: tidak ada panggilan LLM di jalur antrean.
 * - S11: label "Prioritas Telaah Farmasi", bukan "risiko pasien".
 * - Tombol klaim hanya tersedia bagi pengguna terautentikasi (JWT).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import { Helmet } from "react-helmet-async"
import {
  AlarmClock,
  ArrowRight,
  Check,
  CheckCircle2,
  CircleHelp,
  LoaderCircle,
  RefreshCw,
  Stethoscope,
  Users,
  Wifi,
  WifiOff,
} from "lucide-react"

import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Heading,
  Input,
  Modal,
  PageSkeleton,
  Select,
} from "../components/ui"
import { TierBadge } from "../components/TierBadge"
import { SimulationPanel } from "../components/SimulationPanel"
import { LoginPage } from "./LoginPage"
import { useAuthStore } from "../lib/auth"
import type { WorklistItemV1 } from "../lib/apiClient"
import {
  claimNext,
  getMyQueue,
  getQueueList,
  heartbeatEntry,
  releaseEntry,
  subscribeQueueEvents,
  type MyQueueResponse,
  type QueueEntry,
  type QueueTier,
  type SseStatus,
  type TierSource,
} from "../api/queue"

const SIMULATED_LABEL =
  "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"

const TIER_OPTIONS = [
  { value: "", label: "Semua prioritas" },
  { value: "HIGH", label: "Tinggi" },
  { value: "MEDIUM", label: "Sedang" },
  { value: "LOW", label: "Rendah" },
]

const SOURCE_LABEL: Record<TierSource, string> = {
  RULE: "aturan",
  ML: "ML",
  SLA: "SLA",
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatHours(hours: number | null): string {
  if (hours == null) return "—"
  if (hours < 1) return `${Math.round(hours * 60)} mnt`
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return m > 0 ? `${h} j ${m} mnt` : `${h} j`
}

function toWorklistItem(entry: QueueEntry): WorklistItemV1 {
  return {
    encounter_id: entry.encounter_id,
    patient_id: entry.patient_id ?? entry.encounter_id,
    patient_name: entry.patient_name,
    ward: entry.ward,
    workflow_status:
      entry.workflow_status ??
      (entry.state === "CLAIMED" ? "DRAFT_REVIEW" : "MENUNGGU_TELAAH"),
    latest_tier: entry.tier,
    ml_score: entry.ml_score,
    priority_reasons: entry.priority_reasons ?? [],
    admitted_at: entry.admitted_at,
    sla_hours_elapsed: entry.hours_waiting,
    claimed_by: entry.claimed_by,
    claimed_at: null,
    row_version: entry.row_version,
    dpjp_name: entry.dpjp_name,
  }
}

function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(id)
  }, [value, delay])
  return debounced
}

/** Bar usia tunggu relatif terhadap SLA (0–100%+). */
function SlaBar({ ratio }: { ratio: number | null }) {
  const pct = ratio == null ? 0 : Math.min(Math.max(ratio * 100, 0), 100)
  const tone =
    ratio == null
      ? "bg-slate-300"
      : ratio >= 0.9
        ? "bg-red-600"
        : ratio >= 0.7
          ? "bg-amber-500"
          : ratio >= 0.4
            ? "bg-yellow-400"
            : "bg-emerald-500"
  return (
    <div
      className="h-1.5 w-full min-w-24 overflow-hidden rounded-full bg-slate-200"
      role="img"
      aria-label={
        ratio == null
          ? "Usia tunggu tidak diketahui"
          : `Usia tunggu ${Math.round(ratio * 100)} persen dari target SLA`
      }
    >
      <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

function TierSourceBadge({ entry }: { entry: QueueEntry }) {
  const label = SOURCE_LABEL[entry.tier_source] ?? entry.tier_source
  const tone =
    entry.tier_source === "RULE"
      ? "danger"
      : entry.tier_source === "ML"
        ? "warning"
        : "info"
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <TierBadge tier={entry.tier} size="md" />
      <Badge tone={tone}>
        {entry.tier_source === "RULE" ? "aturan" : label.toUpperCase()}
      </Badge>
      {entry.ml_percentile != null && entry.tier_source === "ML" && (
        <span className="text-[0.6875rem] text-slate-500">
          p{Math.round(entry.ml_percentile)}%
        </span>
      )}
    </span>
  )
}

/** Countdown masa sewa klaim (lease). */
function LeaseCountdown({
  expiresAt,
  onExpired,
}: {
  expiresAt: string | null
  onExpired?: () => void
}) {
  const [now, setNow] = useState(() => Date.now())
  const firedRef = useRef(false)

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  const secondsLeft = useMemo(() => {
    if (!expiresAt) return null
    return Math.max(0, Math.floor((new Date(expiresAt).getTime() - now) / 1000))
  }, [expiresAt, now])

  useEffect(() => {
    if (secondsLeft === 0 && !firedRef.current) {
      firedRef.current = true
      onExpired?.()
    }
  }, [secondsLeft, onExpired])

  if (secondsLeft == null) {
    return <span className="text-xs text-slate-500">Lease tidak diketahui</span>
  }

  const mm = String(Math.floor(secondsLeft / 60)).padStart(2, "0")
  const ss = String(secondsLeft % 60).padStart(2, "0")
  const critical = secondsLeft <= 120

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-semibold tabular-nums ${critical
        ? "border-red-300 bg-red-50 text-red-700"
        : "border-slate-300 bg-slate-50 text-slate-700"
        }`}
      aria-label={`Sisa masa sewa klaim ${mm} menit ${ss} detik`}
    >
      <AlarmClock className="size-3.5" aria-hidden="true" />
      {mm}:{ss}
    </span>
  )
}

function SseIndicator({ status }: { status: SseStatus }) {
  const config: Record<SseStatus, { label: string; cls: string; icon: ReactNode }> = {
    live: {
      label: "Live",
      cls: "border-emerald-300 bg-emerald-50 text-emerald-800",
      icon: <Wifi className="size-3.5" aria-hidden="true" />,
    },
    connecting: {
      label: "Menghubungkan",
      cls: "border-slate-300 bg-slate-50 text-slate-600",
      icon: <LoaderCircle className="size-3.5 animate-spin" aria-hidden="true" />,
    },
    reconnecting: {
      label: "Menyambung ulang",
      cls: "border-amber-300 bg-amber-50 text-amber-800",
      icon: <RefreshCw className="size-3.5 animate-spin" aria-hidden="true" />,
    },
    offline: {
      label: "Offline",
      cls: "border-red-300 bg-red-50 text-red-800",
      icon: <WifiOff className="size-3.5" aria-hidden="true" />,
    },
  }
  const c = config[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[0.6875rem] font-bold ${c.cls}`}
      role="status"
    >
      {c.icon}
      {c.label}
    </span>
  )
}

function StatCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string
  value: number | string
  hint?: string
  tone?: "default" | "danger" | "info"
}) {
  const tones = {
    default: "border-slate-200 bg-white",
    danger: "border-red-200 bg-red-50/60",
    info: "border-blue-200 bg-blue-50/50",
  }
  return (
    <div className={`rounded-lg border p-4 ${tones[tone]}`}>
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-slate-950">
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function QueuePage(props: { onOpenCase?: (item: WorklistItemV1) => void }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  if (!isAuthenticated) {
    return <LoginPage onSuccess={() => undefined} />
  }

  return <QueueWorkspace onOpenCase={props.onOpenCase} />
}

function QueueWorkspace({
  onOpenCase,
}: {
  onOpenCase?: (item: WorklistItemV1) => void
}) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  // Filters
  const [ward, setWard] = useState("")
  const [tier, setTier] = useState("")
  const [search, setSearch] = useState("")
  const debouncedSearch = useDebounced(search)

  // Ward queue
  const [entries, setEntries] = useState<QueueEntry[]>([])
  const [total, setTotal] = useState(0)
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  // My queue
  const [mine, setMine] = useState<MyQueueResponse | null>(null)
  const [mineError, setMineError] = useState<string | null>(null)
  const [claimingId, setClaimingId] = useState<string | null>(null)

  // Claim next
  const [claimLoading, setClaimLoading] = useState(false)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // SSE
  const [sseStatus, setSseStatus] = useState<SseStatus>("connecting")
  const [pendingUpdates, setPendingUpdates] = useState(0)

  // "Mengapa pasien ini?"
  const [whyEntry, setWhyEntry] = useState<QueueEntry | null>(null)

  const reload = useCallback(() => setReloadKey((k) => k + 1), [])

  // --- Ward queue ---------------------------------------------------------
  useEffect(() => {
    if (!isAuthenticated) return
    let cancelled = false
    setLoading(true)
    setError(null)
    getQueueList({
      queue_type: "REVIEW",
      state: "OPEN",
      ward: ward || undefined,
      tier: (tier || undefined) as QueueTier | undefined,
      search: debouncedSearch || undefined,
      limit: 50,
    })
      .then((res) => {
        if (cancelled) return
        setEntries(res.items ?? [])
        setTotal(res.total ?? res.items?.length ?? 0)
        setCursor(res.next_cursor ?? null)
        setHasNext(Boolean(res.has_next))
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [isAuthenticated, ward, tier, debouncedSearch, reloadKey])

  // --- My queue -----------------------------------------------------------
  const refreshMine = useCallback(async () => {
    if (!isAuthenticated) return
    try {
      const res = await getMyQueue()
      setMine(res)
      setMineError(null)
    } catch (err) {
      setMineError(err instanceof Error ? err.message : String(err))
    }
  }, [isAuthenticated])

  useEffect(() => {
    void refreshMine()
  }, [refreshMine, reloadKey])

  // --- SSE ----------------------------------------------------------------
  useEffect(() => {
    if (!isAuthenticated) return
    return subscribeQueueEvents(
      () => setPendingUpdates((n) => n + 1),
      (status) => setSseStatus(status),
    )
  }, [isAuthenticated])

  // --- Actions ------------------------------------------------------------
  const applyUpdates = useCallback(() => {
    setPendingUpdates(0)
    reload()
    void refreshMine()
  }, [reload, refreshMine])

  // Auto-refresh setelah SSE tenang ~1,2 dtk agar demo terasa real-time
  // tanpa mengacak urutan pada setiap event tunggal.
  useEffect(() => {
    if (pendingUpdates === 0) return
    const id = window.setTimeout(() => {
      setPendingUpdates(0)
      reload()
      void refreshMine()
    }, 1200)
    return () => window.clearTimeout(id)
  }, [pendingUpdates, reload, refreshMine])

  const handleClaimNext = useCallback(async () => {
    if (claimLoading) return
    setClaimLoading(true)
    setActionError(null)
    setActionMessage(null)
    try {
      const entry = await claimNext("REVIEW", ward ? [ward] : undefined)
      if (!entry) {
        setActionMessage(
          "Tidak ada pasien telaah dalam cakupan Anda saat ini. Antrean mungkin kosong atau sudah diklaim apoteker lain.",
        )
        await refreshMine()
        return
      }
      setPendingUpdates(0)
      await Promise.all([refreshMine(), Promise.resolve(reload())])
      onOpenCase?.(toWorklistItem(entry))
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setClaimLoading(false)
    }
  }, [claimLoading, ward, onOpenCase, refreshMine, reload])

  // Keyboard shortcut `N`
  useEffect(() => {
    if (!isAuthenticated) return
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const tag = target?.tagName
      if (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        target?.isContentEditable
      ) {
        return
      }
      if (
        (event.key === "n" || event.key === "N") &&
        !event.ctrlKey &&
        !event.metaKey &&
        !event.altKey
      ) {
        event.preventDefault()
        void handleClaimNext()
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [isAuthenticated, handleClaimNext])

  async function handleHeartbeat(entry: QueueEntry) {
    setClaimingId(entry.encounter_id)
    setActionError(null)
    try {
      await heartbeatEntry(entry.encounter_id)
      setActionMessage(
        `Masa sewa ${entry.patient_name ?? entry.encounter_id} diperpanjang.`,
      )
      await Promise.all([refreshMine(), Promise.resolve(reload())])
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setClaimingId(null)
    }
  }

  async function handleRelease(entry: QueueEntry) {
    setClaimingId(entry.encounter_id)
    setActionError(null)
    try {
      await releaseEntry(entry.encounter_id)
      setActionMessage(
        `Klaim ${entry.patient_name ?? entry.encounter_id} dilepas kembali ke antrean.`,
      )
      await Promise.all([refreshMine(), Promise.resolve(reload())])
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setClaimingId(null)
    }
  }

  async function handleLoadMore() {
    if (!cursor || loadingMore) return
    setLoadingMore(true)
    try {
      const res = await getQueueList({
        queue_type: "REVIEW",
        state: "OPEN",
        ward: ward || undefined,
        tier: (tier || undefined) as QueueTier | undefined,
        search: debouncedSearch || undefined,
        after_cursor: cursor,
        limit: 50,
      })
      setEntries((prev) => [...prev, ...(res.items ?? [])])
      setCursor(res.next_cursor ?? null)
      setHasNext(Boolean(res.has_next))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingMore(false)
    }
  }

  // --- Derived ------------------------------------------------------------
  const claimed = mine?.claimed ?? []
  const upcoming = mine?.upcoming ?? []
  const highCount = entries.filter((entry) => entry.tier === "HIGH").length
  const wards = useMemo(() => {
    const set = new Set<string>()
    entries.forEach((entry) => entry.ward && set.add(entry.ward))
    claimed.forEach((entry) => entry.ward && set.add(entry.ward))
    return Array.from(set).sort()
  }, [entries, claimed])

  return (
    <div className="space-y-5 pb-10">
      <Helmet>
        <title>Antrean Farmasi — PrioMed-Rec</title>
        <meta
          name="description"
          content="Antrean telaah farmasi: ambil pasien berikutnya, pantau klaim dan SLA."
        />
      </Helmet>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Heading level={1}>Antrean Farmasi</Heading>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            Prioritas Telaah Farmasi diurutkan dari aturan klinis, model ML, dan
            tekanan SLA. Ambil pasien berikutnya lalu telaah di Case Workspace.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SseIndicator status={sseStatus} />
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className="size-4" />}
            onClick={applyUpdates}
          >
            Muat ulang
          </Button>
        </div>
      </div>

      {/* Simulasi */}
      <div
        className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
        role="note"
      >
        <span aria-hidden="true">⚠</span>
        <span>
          <strong className="font-semibold">Data simulasi.</strong>{" "}
          {SIMULATED_LABEL.replace("Data simulasi — ", "")}
        </span>
      </div>

      {/* Kontrol simulasi replay CSV */}
      <SimulationPanel onChange={applyUpdates} />

      {/* Update banner */}
      {pendingUpdates > 0 && (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-blue-300 bg-blue-50 px-3 py-2 text-sm text-blue-900"
          role="status"
        >
          <span>
            <strong className="font-semibold">
              {pendingUpdates} pembaruan baru
            </strong>{" "}
            — urutan tidak melompat otomatis.
          </span>
          <Button size="sm" variant="primary" onClick={applyUpdates}>
            Muat ulang urutan
          </Button>
        </div>
      )}

      {/* Action messages */}
      {actionError && (
        <div
          className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          {actionError}
        </div>
      )}
      {actionMessage && !actionError && (
        <div
          className="flex items-start justify-between gap-3 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900"
          role="status"
        >
          <span className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {actionMessage}
          </span>
          <button
            type="button"
            className="text-xs font-semibold underline"
            onClick={() => setActionMessage(null)}
          >
            Tutup
          </button>
        </div>
      )}

      {/* Stats + claim-next */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Terbuka (Review)"
          value={total}
          hint={`${highCount} prioritas tinggi di halaman ini`}
        />
        <StatCard
          label="Diklaim Saya"
          value={claimed.length}
          hint="Lease 15 menit — perpanjang bila perlu"
          tone="info"
        />
        <StatCard
          label="Pratinjau Berikutnya"
          value={upcoming.length}
          hint="5 entri teratas sesuai cakupan"
        />
        <Card variant="emphasized" className="flex flex-col justify-between">
          <div className="text-xs font-semibold uppercase tracking-wide text-blue-800">
            Aksi cepat
          </div>
          <Button
            className="mt-2 w-full"
            size="lg"
            loading={claimLoading}
            icon={<Stethoscope className="size-4" />}
            onClick={() => void handleClaimNext()}
          >
            Ambil pasien berikutnya
          </Button>
          <p className="mt-2 text-xs text-blue-900/80">
            Pintasan keyboard{" "}
            <kbd className="rounded border border-blue-300 bg-white px-1 font-mono text-[0.6875rem]">
              N
            </kbd>
            {ward ? ` · bangsal ${ward}` : " · semua bangsal"}
          </p>
        </Card>
      </div>

      {/* Antrean Saya */}
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Heading level={2}>Antrean Saya</Heading>
          <span className="text-xs text-slate-500">
            {claimed.length} klaim aktif · {upcoming.length} berikutnya
          </span>
        </div>

        {mineError && (
          <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            Antrean Saya tidak tersedia untuk peran ini: {mineError}
          </p>
        )}

        {claimed.length === 0 ? (
          <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
            Belum ada kasus yang Anda klaim. Gunakan tombol{" "}
            <strong>Ambil pasien berikutnya</strong> atau tekan{" "}
            <kbd className="rounded border border-slate-300 bg-white px-1 font-mono text-xs">
              N
            </kbd>
            .
          </p>
        ) : (
          <ul className="grid gap-2 lg:grid-cols-2">
            {claimed.map((entry) => (
              <li
                key={entry.encounter_id}
                className="rounded-lg border border-blue-200 bg-blue-50/40 p-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <TierSourceBadge entry={entry} />
                      <LeaseCountdown
                        expiresAt={entry.claim_expires_at}
                        onExpired={() => void refreshMine()}
                      />
                    </div>
                    <div className="mt-1 truncate text-sm font-semibold text-slate-900">
                      {entry.patient_name ?? entry.patient_id ?? "Pasien"}
                    </div>
                    <div className="text-xs text-slate-600">
                      {entry.ward} · menunggu{" "}
                      {formatHours(entry.hours_waiting)}
                      {entry.sla_target_hours != null
                        ? ` / target ${entry.sla_target_hours} j`
                        : ""}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="primary"
                      icon={<ArrowRight className="size-4" />}
                      onClick={() => onOpenCase?.(toWorklistItem(entry))}
                    >
                      Telaah
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={claimingId === entry.encounter_id}
                      onClick={() => void handleHeartbeat(entry)}
                    >
                      Perpanjang
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={claimingId === entry.encounter_id}
                      onClick={() => void handleRelease(entry)}
                    >
                      Lepas
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}

        {upcoming.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Berikutnya untuk Anda
            </div>
            <ol className="space-y-1">
              {upcoming.map((entry, index) => (
                <li
                  key={entry.encounter_id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="w-5 shrink-0 text-xs font-bold text-slate-400">
                      {index + 1}
                    </span>
                    <TierBadge tier={entry.tier} size="sm" />
                    <span className="truncate font-medium text-slate-800">
                      {entry.patient_name ?? entry.patient_id ?? "Pasien"}
                    </span>
                    <span className="shrink-0 text-xs text-slate-500">
                      {entry.ward}
                    </span>
                  </span>
                  <span className="text-xs text-slate-500">
                    {formatHours(entry.hours_waiting)} menunggu
                  </span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </Card>

      {/* Antrean Bangsal */}
      <Card className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <Heading level={2}>Antrean Bangsal — Telaah</Heading>
            <p className="mt-0.5 text-xs text-slate-500">
              Hanya entri berstatus <strong>OPEN</strong> · {total} entri cocok ·
              urut prioritas
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Cari nama / ID pasien"
              aria-label="Cari pasien di antrean"
              className="w-56"
            />
            <Select
              aria-label="Filter bangsal"
              value={ward}
              onChange={(e) => setWard(e.target.value)}
              options={[
                { value: "", label: "Semua bangsal" },
                ...wards.map((w) => ({ value: w, label: w })),
              ]}
              className="w-44"
            />
            <Select
              aria-label="Filter prioritas"
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              options={TIER_OPTIONS}
              className="w-44"
            />
          </div>
        </div>

        {loading && entries.length === 0 ? (
          <PageSkeleton type="table" />
        ) : error ? (
          <ErrorState retry={reload} />
        ) : entries.length === 0 ? (
          <EmptyState
            title="Antrean telaah kosong"
            description="Tidak ada pasien menunggu telaah untuk filter ini. Antrean akan bertambah saat BPMH selesai atau pasien baru masuk."
            action={
              <Button variant="secondary" onClick={reload}>
                Muat ulang
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table
              className="w-full min-w-[880px] text-sm"
              aria-label="Daftar antrean telaah farmasi"
            >
              <thead className="sticky top-0 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th scope="col" className="px-3 py-2">
                    Prioritas
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Pasien
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Bangsal
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Usia tunggu
                  </th>
                  <th scope="col" className="px-3 py-2 min-w-40">
                    Tekanan SLA
                  </th>
                  <th scope="col" className="px-3 py-2">
                    Mengapa?
                  </th>
                  <th scope="col" className="px-3 py-2 text-right">
                    Aksi
                  </th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr
                    key={entry.encounter_id}
                    className="border-t border-slate-100 align-top hover:bg-slate-50/70"
                  >
                    <td className="px-3 py-3">
                      <TierSourceBadge entry={entry} />
                    </td>
                    <td className="px-3 py-3">
                      <div className="font-medium text-slate-900">
                        {entry.patient_name ?? entry.patient_id ?? "Pasien"}
                      </div>
                      <div className="text-xs text-slate-400">
                        {entry.patient_id ?? entry.encounter_id}
                      </div>
                      {entry.dpjp_name && (
                        <div className="text-xs text-slate-500">
                          DPJP {entry.dpjp_name}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-slate-700">
                      {entry.ward}
                      <div className="text-xs text-slate-400">
                        {entry.queue_type}
                      </div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap text-slate-700">
                      {formatHours(entry.hours_waiting)}
                      <div className="text-xs text-slate-400">
                        {entry.sla_target_hours != null
                          ? `target ${entry.sla_target_hours} j`
                          : "tanpa target"}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <SlaBar ratio={entry.sla_ratio} />
                      <div className="mt-1 text-xs text-slate-500 tabular-nums">
                        {entry.sla_ratio == null
                          ? "—"
                          : `${Math.round(entry.sla_ratio * 100)}% SLA`}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <button
                        type="button"
                        onClick={() => setWhyEntry(entry)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
                        aria-label={`Lihat alasan prioritas ${entry.patient_name ?? entry.encounter_id}`}
                      >
                        <CircleHelp className="size-3.5" aria-hidden="true" />
                        Mengapa?
                      </button>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="flex flex-col items-end gap-1">
                        {entry.claimed_by ? (
                          <span className="text-xs text-slate-500">
                            Diklaim{" "}
                            {entry.claimed_by_name ??
                              entry.claimed_by.slice(0, 8)}
                          </span>
                        ) : (
                          <Button
                            size="sm"
                            variant="primary"
                            loading={claimLoading}
                            onClick={() => void handleClaimNext()}
                            title="Ambil & klaim entri teratas antrean"
                          >
                            Ambil
                          </Button>
                        )}
                        <button
                          type="button"
                          onClick={() => onOpenCase?.(toWorklistItem(entry))}
                          className="text-xs font-semibold text-blue-700 underline-offset-2 hover:underline"
                        >
                          Buka
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {hasNext && !loading && !error && (
          <div className="flex justify-center">
            <Button
              variant="secondary"
              loading={loadingMore}
              icon={<Users className="size-4" />}
              onClick={() => void handleLoadMore()}
            >
              Muat 50 entri lagi
            </Button>
          </div>
        )}
      </Card>

      {/* Why modal */}
      <Modal
        open={whyEntry !== null}
        title="Mengapa pasien ini diprioritaskan?"
        onClose={() => setWhyEntry(null)}
        footer={
          <Button variant="secondary" onClick={() => setWhyEntry(null)}>
            Tutup
          </Button>
        }
      >
        {whyEntry && (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <TierSourceBadge entry={whyEntry} />
              <span className="text-slate-600">
                Skor prioritas{" "}
                <strong className="tabular-nums text-slate-900">
                  {whyEntry.priority_score.toFixed(2)}
                </strong>
              </span>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Ringkasan
              </div>
              {whyEntry.why.length === 0 ? (
                <p className="mt-1 text-slate-600">
                  Tidak ada catatan tambahan dari mesin antrean.
                </p>
              ) : (
                <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-700">
                  {whyEntry.why.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Faktor penentu
              </div>
              {whyEntry.priority_reasons.length === 0 ? (
                <p className="mt-1 text-slate-600">
                  Belum ada faktor terperinci untuk entri ini.
                </p>
              ) : (
                <ul className="mt-1 space-y-1">
                  {whyEntry.priority_reasons.map((reason, index) => (
                    <li
                      key={`${reason.source}-${index}`}
                      className="rounded-md border border-slate-200 px-2 py-1.5"
                    >
                      <span className="mr-1 font-semibold text-slate-700">
                        {reason.source}
                      </span>
                      <Badge tone="neutral">{reason.tier}</Badge>
                      <div className="mt-1 text-slate-600">{reason.reason}</div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <p className="rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-500">
              <Check className="mr-1 inline size-3.5" aria-hidden="true" />
              Prioritas telaah farmasi bukan diagnosis dan tidak menggantikan
              keputusan klinis apoteker.
            </p>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default QueuePage
