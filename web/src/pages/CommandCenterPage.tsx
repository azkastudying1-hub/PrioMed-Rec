/**
 * web/src/pages/CommandCenterPage.tsx
 * -------------------------------------
 * Command Center (Pusat Kendali) — QUEUE_PLAN Q-009.
 *
 * Isi:
 * - Gauge permintaan vs kapasitas (+ what-if jumlah apoteker bertugas)
 * - Peta panas bangsal × tier
 * - Histogram usia menunggu per tier
 * - Daftar berisiko SLA
 * - Banner mode lonjakan (rekomendasi saja, tidak menurunkan tier HIGH)
 * - Alur 24 jam + indikator keselamatan
 * - Label "Data simulasi"
 *
 * Sumber: GET /api/v1/queue/command-center (Bearer JWT).
 * ADR-20: tidak ada panggilan LLM di jalur ini.
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import React from "react"
import { Helmet } from "react-helmet-async"
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Gauge,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
  Users,
  Wifi,
  WifiOff,
} from "lucide-react"

/**
 * Task 13.2: Migrated from legacy components to uiux/ design system.
 * Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6
 * - Replaced Heading, Badge, Button, Card, EmptyState, ErrorState, Input, PageSkeleton
 *   with uiux/primitives equivalents
 * - Replaced TierBadge with PriorityBadge from uiux/clinical
 * - Replaced PageSkeleton with Skeleton components approximating layout
 * - Preserved all SSE, what-if, simulation panel functionality
 */
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Input,
  Skeleton,
} from "../uiux/primitives"
import { PriorityBadge, SectionHeading } from "../uiux/clinical"
// Keep legacy Heading alias for internal use (non-exported, used below)
const Heading = ({ level, children, className }: { level?: number; children: React.ReactNode; className?: string }) => {
  const Tag = (level === 1 ? 'h1' : level === 3 ? 'h3' : 'h2') as 'h1' | 'h2' | 'h3'
  return <Tag className={`font-display font-bold tracking-tight text-slate-900 ${level === 1 ? 'text-xl sm:text-2xl' : level === 3 ? 'text-sm' : 'text-lg'} ${className ?? ''}`}>{children}</Tag>
}
import { SimulationPanel } from "../components/SimulationPanel"
import { useAuthStore } from "../lib/auth"
import {
  getCommandCenter,
  subscribeQueueEvents,
  type CommandCenterData,
  type QueueTier,
  type SseStatus,
} from "../api/queue"

const SIMULATED_LABEL =
  "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"

const TIERS: QueueTier[] = ["HIGH", "MEDIUM", "LOW"]

const TIER_TEXT: Record<QueueTier, string> = {
  HIGH: "Tinggi",
  MEDIUM: "Sedang",
  LOW: "Rendah",
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatMinutes(minutes: number | null | undefined): string {
  if (minutes == null || Number.isNaN(minutes)) return "—"
  if (minutes < 60) return `${Math.round(minutes)} mnt`
  const hours = minutes / 60
  return `${hours.toFixed(hours >= 10 ? 0 : 1)} j`
}

function pct(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return "—"
  return `${(value * 100).toFixed(digits)}%`
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

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
}

function KpiButton({
  label,
  value,
  hint,
  targetId,
  tone = "default",
}: {
  label: string
  value: number | string
  hint?: string
  targetId: string
  tone?: "default" | "danger" | "info" | "warning"
}) {
  const tones = {
    default: "border-slate-200 bg-white hover:border-slate-300",
    danger: "border-red-200 bg-red-50/60 hover:border-red-300",
    info: "border-blue-200 bg-blue-50/50 hover:border-blue-300",
    warning: "border-amber-200 bg-amber-50/60 hover:border-amber-300",
  }
  return (
    <button
      type="button"
      onClick={() => scrollToId(targetId)}
      className={`rounded-lg border p-4 text-left transition-colors ${tones[tone]}`}
      title={`Lihat rincian: ${label}`}
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold tabular-nums text-slate-950">
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
      <div className="mt-1 inline-flex items-center gap-1 text-[0.6875rem] font-semibold text-blue-700">
        Rincian <ArrowRight className="size-3" aria-hidden="true" />
      </div>
    </button>
  )
}

function heatTone(count: number, max: number): string {
  if (count === 0) return "bg-slate-50 text-slate-400 border-slate-200"
  const ratio = max > 0 ? count / max : 0
  if (ratio >= 0.75) return "bg-red-600 text-white border-red-700"
  if (ratio >= 0.5) return "bg-red-400 text-white border-red-500"
  if (ratio >= 0.3) return "bg-amber-300 text-amber-950 border-amber-400"
  if (ratio >= 0.15) return "bg-yellow-100 text-yellow-950 border-yellow-300"
  return "bg-emerald-50 text-emerald-900 border-emerald-200"
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function CommandCenterPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  return <CommandCenterWorkspace />
}

function CommandCenterWorkspace() {
  const [data, setData] = useState<CommandCenterData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  // What-if kapasitas
  const [pharmacistsInput, setPharmacistsInput] = useState("")
  const [appliedPharmacists, setAppliedPharmacists] = useState<number | undefined>(
    undefined,
  )

  const [sseStatus, setSseStatus] = useState<SseStatus>("connecting")
  const [pendingUpdates, setPendingUpdates] = useState(0)

  const reload = useCallback(() => setReloadKey((k) => k + 1), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getCommandCenter(appliedPharmacists)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [reloadKey, appliedPharmacists])

  useEffect(() => {
    return subscribeQueueEvents(
      () => setPendingUpdates((n) => n + 1),
      (status) => setSseStatus(status),
    )
  }, [])

  // Auto-refresh setelah SSE tenang ~1,2 dtk (demo real-time).
  useEffect(() => {
    if (pendingUpdates === 0) return
    const id = window.setTimeout(() => {
      setPendingUpdates(0)
      reload()
    }, 1200)
    return () => window.clearTimeout(id)
  }, [pendingUpdates, reload])

  const heatmapMax = useMemo(() => {
    if (!data) return 0
    let max = 0
    for (const ward of data.heatmap.wards) {
      for (const tier of data.heatmap.tiers) {
        const value = data.heatmap.cells[ward]?.[tier] ?? 0
        if (value > max) max = value
      }
    }
    return max
  }, [data])

  const agingMax = useMemo(() => {
    if (!data) return 0
    let max = 0
    for (const tier of TIERS) {
      for (const value of data.aging.by_tier[tier] ?? []) {
        if (value > max) max = value
      }
    }
    return max
  }, [data])

  if (loading && !data) {
    return (
      <div className="space-y-5">
        <Helmet>
          <title>Command Center — Memuat · PrioMed-Rec</title>
        </Helmet>
        <Heading level={1}>Command Center</Heading>
        {/* Req 15.2: Skeleton approximating detail layout */}
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            {[...Array(6)].map((_, i) => (
              <Card key={i} className="space-y-2">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-7 w-16" />
                <Skeleton className="h-3 w-32" />
              </Card>
            ))}
          </div>
          <Card className="space-y-3">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
          </Card>
        </div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="space-y-5">
        <Helmet>
          <title>Command Center — Kesalahan · PrioMed-Rec</title>
        </Helmet>
        <Heading level={1}>Command Center</Heading>
        <ErrorState onRetry={reload} description="Command Center tidak dapat dimuat" />
        <p className="text-center text-xs text-slate-500">{error}</p>
      </div>
    )
  }

  if (!data) {
    return (
      <EmptyState
        title="Belum ada data"
        description="Command Center belum menerima data antrean."
        action={<Button onClick={reload}>Muat ulang</Button>}
      />
    )
  }

  const { capacity, surge, safety, flow, totals, at_risk: atRisk } = data
  const loadRatio = capacity.load_ratio
  const loadPct = Math.min(Math.max(loadRatio * 100, 0), 200)

  return (
    <div className="space-y-5 pb-10">
      <Helmet>
        <title>Command Center — PrioMed-Rec</title>
        <meta
          name="description"
          content="Pusat kendali antrean farmasi: kapasitas, peta panas bangsal, risiko SLA."
        />
      </Helmet>

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Heading level={1}>Command Center</Heading>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">
            Ringkasan beban kerja, kapasitas, dan risiko SLA antrean telaah
            farmasi. Angka kapasitas adalah asumsi yang dapat dikonfigurasi.
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Diperbarui{" "}
            {new Date(data.as_of).toLocaleString("id-ID", {
              dateStyle: "medium",
              timeStyle: "short",
            })}{" "}
            · versi antrean {data.queue_version}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SseIndicator status={sseStatus} />
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className="size-4" />}
            loading={loading}
            onClick={reload}
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
      <SimulationPanel onChange={reload} />

      {/* Update banner */}
      {pendingUpdates > 0 && (
        <div
          className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-blue-300 bg-blue-50 px-3 py-2 text-sm text-blue-900"
          role="status"
        >
          <span>
            <strong className="font-semibold">
              {pendingUpdates} pembaruan antrean
            </strong>{" "}
            — angka belum disegarkan.
          </span>
          <Button
            size="sm"
            onClick={() => {
              setPendingUpdates(0)
              reload()
            }}
          >
            Muat ulang
          </Button>
        </div>
      )}

      {/* Surge banner */}
      {surge.active ? (
        <Card className="border-amber-400 bg-amber-50 border">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-700" aria-hidden="true" />
            <div className="space-y-1">
              <Heading level={3} className="text-amber-900">
                Mode lonjakan aktif — rekomendasi saja
              </Heading>
              {surge.reasons.length > 0 && (
                <ul className="list-disc pl-5 text-sm text-amber-900">
                  {surge.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              )}
              {surge.recommendations.length > 0 && (
                <ul className="list-disc pl-5 text-sm font-medium text-amber-950">
                  {surge.recommendations.map((rec) => (
                    <li key={rec}>{rec}</li>
                  ))}
                </ul>
              )}
              <p className="pt-1 text-xs text-amber-800">
                Tier HIGH tidak pernah diturunkan oleh mode lonjakan. {surge.note}
              </p>
            </div>
          </div>
        </Card>
      ) : (
        <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
          <span className="font-semibold text-slate-800">
            Mode lonjakan tidak aktif.
          </span>{" "}
          Ambang: load ratio ≥ {surge.thresholds.load_ratio}×, backlog ≥{" "}
          {surge.thresholds.backlog}, HIGH p90 ≥{" "}
          {pct(surge.thresholds.high_p90_pct_of_sla)} SLA. {surge.note}
        </div>
      )}

      {/* KPI */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiButton
          label="Antrean terbuka"
          value={totals.open_total}
          hint={`${totals.review_open} telaah · ${totals.bpmh_open} BPMH`}
          targetId="section-heatmap"
        />
        <KpiButton
          label="Prioritas tinggi"
          value={totals.high_open}
          hint="Tier HIGH terbuka"
          tone={totals.high_open > 0 ? "danger" : "default"}
          targetId="section-sla-risk"
        />
        <KpiButton
          label="Diklaim"
          value={totals.claimed}
          hint="Sedang dikerjakan apoteker"
          tone="info"
          targetId="section-sla-risk"
        />
        <KpiButton
          label="Ditunda DPJP"
          value={totals.parked_dpjp}
          hint="Menunggu keputusan DPJP"
          targetId="section-flow"
        />
        <KpiButton
          label="Risiko SLA"
          value={atRisk.total}
          hint="≥ 75% target SLA"
          tone={atRisk.total > 0 ? "warning" : "default"}
          targetId="section-sla-risk"
        />
        <KpiButton
          label="Beban kapasitas"
          value={`${pct(loadRatio)}`}
          hint={
            loadRatio > 1
              ? `Kurang ${formatMinutes(
                capacity.demand_minutes - capacity.capacity_minutes,
              )}`
              : "Dalam kapasitas"
          }
          tone={loadRatio > 1 ? "danger" : "default"}
          targetId="section-capacity"
        />
      </div>

      {/* Capacity */}
      <Card className="space-y-4" id="section-capacity">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Gauge className="size-5 text-blue-700" aria-hidden="true" />
            <Heading level={2}>Kapasitas: permintaan vs kapasitas</Heading>
          </div>
          <Badge tone={loadRatio > 1 ? "danger" : loadRatio >= 0.8 ? "warning" : "success"}>
            {loadRatio > 1 ? "Kelebihan beban" : loadRatio >= 0.8 ? "Mendekati batas" : "Aman"}
          </Badge>
        </div>

        <div>
          <div className="mb-1 flex flex-wrap items-end justify-between gap-2 text-sm">
            <span className="font-semibold text-slate-800 tabular-nums">
              {pct(loadRatio)} dari kapasitas
            </span>
            <span className="text-xs text-slate-500">
              {formatMinutes(capacity.demand_minutes)} kebutuhan ·{" "}
              {formatMinutes(capacity.capacity_minutes)} kapasitas
            </span>
          </div>
          <div
            className="h-4 w-full overflow-hidden rounded-full bg-slate-200"
            role="img"
            aria-label={`Beban kapasitas ${pct(loadRatio)}`}
          >
            <div
              className={`h-full ${loadRatio > 1
                  ? "bg-red-600"
                  : loadRatio >= 0.8
                    ? "bg-amber-500"
                    : "bg-emerald-600"
                }`}
              style={{ width: `${Math.min(loadPct, 100)}%` }}
            />
          </div>
          <div className="mt-1 text-xs text-slate-500">
            Skala penuh = 100% kapasitas; kelebihan ditandai angka di atas.
          </div>
        </div>

        <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-md border border-slate-200 p-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Apoteker bertugas
            </dt>
            <dd className="mt-1 text-lg font-bold tabular-nums text-slate-900">
              {capacity.pharmacists_on_duty}
            </dd>
            <dd className="text-xs text-slate-500">
              shift {capacity.shift_minutes} mnt · produktif{" "}
              {pct(capacity.productive_pct)}
            </dd>
          </div>
          <div className="rounded-md border border-slate-200 p-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Menit telaah
            </dt>
            <dd className="mt-2 space-y-0.5 text-xs text-slate-700 tabular-nums">
              {TIERS.map((tier) => (
                <div key={tier} className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1">
                    {/* Req 15.2: PriorityBadge from uiux/clinical (not legacy TierBadge) */}
                    <PriorityBadge tier={tier} compact />
                  </span>
                  <span>{capacity.review_minutes[tier] ?? "—"} mnt</span>
                </div>
              ))}
            </dd>
          </div>
          <div className="rounded-md border border-slate-200 p-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Pipeline menunggu
            </dt>
            <dd className="mt-1 text-lg font-bold tabular-nums text-slate-900">
              {formatMinutes(capacity.pipeline_minutes)}
            </dd>
            <dd className="text-xs text-slate-500">
              termasuk antrean BPMH
            </dd>
          </div>
          <div className="rounded-md border border-slate-200 p-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Kebutuhan tambahan
            </dt>
            <dd className="mt-1 text-lg font-bold tabular-nums text-slate-900">
              {capacity.extra_pharmacist_hours > 0
                ? `${capacity.extra_pharmacist_hours.toFixed(1)} jam`
                : "Tidak perlu"}
            </dd>
            <dd className="text-xs text-slate-500">
              jam apoteker untuk menutup beban
            </dd>
          </div>
        </dl>

        {/* What-if */}
        <form
          className="flex flex-wrap items-end gap-2 rounded-md border border-blue-200 bg-blue-50/50 p-3"
          onSubmit={(event) => {
            event.preventDefault()
            const parsed = Number.parseInt(pharmacistsInput, 10)
            setAppliedPharmacists(
              Number.isFinite(parsed) && parsed > 0 ? parsed : undefined,
            )
          }}
        >
          <label className="grid gap-1 text-xs font-semibold text-slate-700">
            What-if: jumlah apoteker bertugas
            <Input
              type="number"
              min={1}
              max={100}
              inputMode="numeric"
              placeholder={String(capacity.pharmacists_on_duty)}
              value={pharmacistsInput}
              onChange={(event) => setPharmacistsInput(event.target.value)}
              className="w-40"
            />
          </label>
          <Button type="submit" size="sm" variant="primary">
            Hitung ulang
          </Button>
          {appliedPharmacists !== undefined && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => {
                setPharmacistsInput("")
                setAppliedPharmacists(undefined)
              }}
            >
              Kembali ke asumsi awal
            </Button>
          )}
          <p className="w-full text-xs text-slate-600">{capacity.assumption_note}</p>
        </form>
      </Card>

      {/* Heatmap */}
      <Card className="space-y-3" id="section-heatmap">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Users className="size-5 text-blue-700" aria-hidden="true" />
            <Heading level={2}>Peta panas bangsal × prioritas</Heading>
          </div>
          <span className="text-xs text-slate-500">
            Jumlah entri terbuka · warna makin pekat = makin padat
          </span>
        </div>

        {data.heatmap.wards.length === 0 ? (
          <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
            Belum ada entri terbuka pada bangsal mana pun.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table
              className="w-full min-w-[520px] border-separate border-spacing-1 text-sm"
              aria-label="Peta panas antrean per bangsal dan prioritas"
            >
              <thead>
                <tr>
                  <th scope="col" className="px-2 py-1 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Bangsal
                  </th>
                  {data.heatmap.tiers.map((tier) => (
                    <th
                      key={tier}
                      scope="col"
                      className="px-2 py-1 text-center text-xs font-semibold uppercase tracking-wide text-slate-500"
                    >
                      {TIER_TEXT[tier]}
                    </th>
                  ))}
                  <th scope="col" className="px-2 py-1 text-center text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.heatmap.wards.map((ward) => {
                  const rowTotal = data.heatmap.tiers.reduce(
                    (sum, tier) => sum + (data.heatmap.cells[ward]?.[tier] ?? 0),
                    0,
                  )
                  return (
                    <tr key={ward}>
                      <th scope="row" className="whitespace-nowrap px-2 py-1 text-left text-xs font-semibold text-slate-700">
                        {ward}
                      </th>
                      {data.heatmap.tiers.map((tier) => {
                        const count = data.heatmap.cells[ward]?.[tier] ?? 0
                        return (
                          <td key={tier} className="p-0">
                            <div
                              className={`flex h-9 min-w-16 items-center justify-center rounded border text-xs font-bold tabular-nums ${heatTone(
                                count,
                                heatmapMax,
                              )}`}
                              title={`${ward} · ${TIER_TEXT[tier]}: ${count} entri`}
                            >
                              {count}
                            </div>
                          </td>
                        )
                      })}
                      <td className="px-2 py-1 text-center text-xs font-bold tabular-nums text-slate-700">
                        {rowTotal}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Aging histogram */}
      <Card className="space-y-3" id="section-aging">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-5 text-blue-700" aria-hidden="true" />
            <Heading level={2}>Histogram usia menunggu</Heading>
          </div>
          <span className="text-xs text-slate-500">
            Distribusi entri per bucket usia (jam)
          </span>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          {TIERS.map((tier) => {
            const buckets = data.aging.by_tier[tier] ?? []
            const tierTotal = buckets.reduce((sum, v) => sum + v, 0)
            return (
              <div key={tier} className="rounded-md border border-slate-200 p-3">
                <div className="flex items-center justify-between gap-2">
                  {/* Req 15.2: PriorityBadge from uiux/clinical */}
                  <PriorityBadge tier={tier} />
                  <span className="text-xs text-slate-500 tabular-nums">
                    {tierTotal} entri
                  </span>
                </div>
                <div
                  className="mt-3 flex h-28 items-end gap-1.5"
                  role="img"
                  aria-label={`Histogram usia menunggu prioritas ${TIER_TEXT[tier]}`}
                >
                  {buckets.length === 0 ? (
                    <p className="text-xs text-slate-500">Tidak ada data.</p>
                  ) : (
                    buckets.map((value, index) => {
                      const height =
                        agingMax > 0 ? Math.max((value / agingMax) * 100, value > 0 ? 6 : 2) : 2
                      return (
                        <div key={index} className="flex flex-1 flex-col items-center gap-1">
                          <span className="text-[0.625rem] tabular-nums text-slate-500">
                            {value}
                          </span>
                          <div
                            className={`w-full rounded-t ${tier === "HIGH"
                                ? "bg-red-500"
                                : tier === "MEDIUM"
                                  ? "bg-amber-400"
                                  : "bg-emerald-500"
                              }`}
                            style={{ height: `${height}%` }}
                          />
                          <span className="whitespace-nowrap text-[0.625rem] text-slate-500">
                            {data.aging.buckets[index] ?? ""}
                          </span>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            )
          })}
        </div>

        <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
          {TIERS.map((tier) => {
            const dist = safety.age_distribution[tier]
            return (
              <div key={tier} className="rounded-md bg-slate-50 px-3 py-2">
                <span className="font-semibold text-slate-800">
                  {TIER_TEXT[tier]}
                </span>{" "}
                · p50 {dist?.p50_hours ?? "—"} j · p90 {dist?.p90_hours ?? "—"} j ·
                p99 {dist?.p99_hours ?? "—"} j
              </div>
            )
          })}
        </div>
      </Card>

      {/* SLA risk list */}
      <Card className="space-y-3" id="section-sla-risk">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-5 text-amber-700" aria-hidden="true" />
            <Heading level={2}>Daftar berisiko SLA</Heading>
          </div>
          <span className="text-xs text-slate-500">
            {atRisk.total} entri ≥ 75% target · HIGH mendekati jatuh tempo
          </span>
        </div>

        {atRisk.items.length === 0 ? (
          <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500">
            Tidak ada entri yang mendekati batas SLA. 👍
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full min-w-[760px] text-sm" aria-label="Daftar entri berisiko SLA">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th scope="col" className="px-3 py-2">Prioritas</th>
                  <th scope="col" className="px-3 py-2">Pasien</th>
                  <th scope="col" className="px-3 py-2">Bangsal</th>
                  <th scope="col" className="px-3 py-2">Antrean</th>
                  <th scope="col" className="px-3 py-2">Usia / target</th>
                  <th scope="col" className="px-3 py-2">SLA</th>
                  <th scope="col" className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {atRisk.items.map((item) => (
                  <tr key={item.encounter_id} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1">
                        {/* Req 15.2: PriorityBadge (not legacy TierBadge) */}
                        <PriorityBadge tier={item.tier} compact />
                        <span className="text-[0.625rem] uppercase text-slate-500">
                          {item.tier_source}
                        </span>
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-900">
                        {item.patient_name ?? "Pasien"}
                      </div>
                      <div className="text-xs text-slate-400">
                        {item.patient_id ?? item.encounter_id}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-slate-700">{item.ward}</td>
                    <td className="px-3 py-2 text-xs text-slate-600">
                      {item.queue_type}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap text-slate-700 tabular-nums">
                      {item.hours_waiting.toFixed(1)} j / {item.sla_target_hours} j
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`font-semibold tabular-nums ${item.sla_ratio >= 1
                            ? "text-red-700"
                            : item.sla_ratio >= 0.9
                              ? "text-amber-700"
                              : "text-slate-700"
                          }`}
                      >
                        {pct(item.sla_ratio)}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <Badge tone={item.state === "CLAIMED" ? "info" : "neutral"}>
                        {item.state}
                      </Badge>
                      {item.claimed_by && (
                        <div className="mt-0.5 text-[0.625rem] text-slate-500">
                          oleh {item.claimed_by.slice(0, 8)}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Flow + Safety */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3" id="section-flow">
          <div className="flex items-center gap-2">
            <Activity className="size-5 text-blue-700" aria-hidden="true" />
            <Heading level={2}>Alur antrean</Heading>
          </div>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            {[
              ["BPMH terbuka", flow.bpmh_open],
              ["Telaah terbuka", flow.review_open],
              ["Diklaim", flow.claimed],
              ["Ditunda DPJP", flow.parked_dpjp],
            ].map(([label, value]) => (
              <div key={label} className="rounded-md border border-slate-200 p-2">
                <dt className="text-xs text-slate-500">{label}</dt>
                <dd className="text-lg font-bold tabular-nums text-slate-900">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Total selesai: {flow.closed_total}
            </div>
            <div className="mt-2 space-y-1">
              {Object.entries(flow.events_24h).length === 0 ? (
                <p className="text-xs text-slate-500">
                  Belum ada event dalam 24 jam terakhir.
                </p>
              ) : (
                Object.entries(flow.events_24h)
                  .sort((a, b) => b[1] - a[1])
                  .map(([event, count]) => {
                    const max = Math.max(
                      ...Object.values(flow.events_24h),
                      1,
                    )
                    return (
                      <div key={event} className="flex items-center gap-2 text-xs">
                        <span className="w-40 truncate text-slate-600" title={event}>
                          {event}
                        </span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-blue-500"
                            style={{ width: `${Math.max((count / max) * 100, 3)}%` }}
                          />
                        </div>
                        <span className="w-8 text-right tabular-nums text-slate-700">
                          {count}
                        </span>
                      </div>
                    )
                  })
              )}
            </div>
            <p className="mt-2 text-[0.6875rem] text-slate-500">Event 24 jam terakhir.</p>
          </div>
        </Card>

        <Card className="space-y-3" id="section-safety">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-emerald-700" aria-hidden="true" />
            <Heading level={2}>Indikator keselamatan</Heading>
          </div>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-md border border-slate-200 p-2">
              <dt className="text-xs text-slate-500">HIGH dalam SLA</dt>
              <dd className="text-lg font-bold tabular-nums text-slate-900">
                {safety.sla_high_pct == null
                  ? "—"
                  : `${safety.sla_high_pct.toFixed(1)}%`}
              </dd>
            </div>
            <div
              className={`rounded-md border p-2 ${safety.missed_reconciliations.today > 0
                  ? "border-red-300 bg-red-50"
                  : "border-slate-200"
                }`}
            >
              <dt className="text-xs text-slate-500">Missed reconciliation</dt>
              <dd className="text-lg font-bold tabular-nums text-slate-900">
                {safety.missed_reconciliations.today}
                <span className="ml-1 text-xs font-normal text-slate-500">
                  hari ini · {safety.missed_reconciliations.total} total
                </span>
              </dd>
            </div>
            <div className="rounded-md border border-slate-200 p-2">
              <dt className="text-xs text-slate-500">Klaim kedaluwarsa</dt>
              <dd className="text-lg font-bold tabular-nums text-slate-900">
                {safety.expired_claims}
              </dd>
            </div>
            <div className="rounded-md border border-slate-200 p-2">
              <dt className="text-xs text-slate-500">Sumber tier</dt>
              <dd className="mt-1 flex flex-wrap gap-1">
                {Object.entries(safety.tier_source_ratio).map(([source, ratio]) => (
                  <Badge
                    key={source}
                    tone={
                      source === "RULE" ? "danger" : source === "ML" ? "warning" : "info"
                    }
                  >
                    {source} {pct(ratio)}
                  </Badge>
                ))}
              </dd>
            </div>
          </dl>
          <p className="rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-900">
            <ShieldCheck className="mr-1 inline size-3.5" aria-hidden="true" />
            Tier HIGH berbasis aturan tidak pernah diturunkan otomatis. Semua
            keputusan telaah tetap berada pada apoteker.
          </p>
        </Card>
      </div>
    </div>
  )
}

export default CommandCenterPage
