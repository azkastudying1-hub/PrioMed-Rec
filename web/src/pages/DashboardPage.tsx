/**
 * web/src/pages/DashboardPage.tsx
 * ---------------------------------
 * Dashboard ringkasan KPI + system health (F-210).
 *
 * Task 4.1: Migrated from legacy components to uiux/ design system.
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
 */

import { useQuery } from '@tanstack/react-query'
import { getWorklistV1, getHealthV1, type WorklistItemV1 } from '../lib/apiClient'
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Skeleton,
} from '../uiux/primitives'
import {
  KpiCard,
  PriorityBadge,
  SectionHeading,
  SLA_TARGETS,
  isSlaBreached,
  slaTargetHours,
} from '../uiux/clinical'

// Req 2.6: SystemHealthDot renders both color AND text label (not color alone)
function SystemHealthDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-700">
      <Badge
        tone={ok ? 'success' : 'danger'}
        dot
        aria-label={`${label}: ${ok ? 'OK' : 'Error'}`}
      >
        {label}
      </Badge>
      <span className={`text-xs font-semibold ${ok ? 'text-emerald-600' : 'text-red-600'}`}>
        {ok ? 'OK' : 'Error'}
      </span>
    </div>
  )
}

export function DashboardPage() {
  const {
    data: worklistData,
    isLoading: worklistLoading,
    isError: worklistError,
    refetch: refetchWorklist,
  } = useQuery({
    queryKey: ['worklist-dashboard'],
    queryFn: () => getWorklistV1({ page_size: 100 }),
    refetchInterval: 60_000,
  })

  const {
    data: healthData,
    isLoading: healthLoading,
  } = useQuery({
    queryKey: ['health-v1'],
    queryFn: getHealthV1,
    refetchInterval: 60_000,
  })

  const items: WorklistItemV1[] = worklistData?.items ?? []
  const total = worklistData?.total ?? 0
  const highCount  = items.filter((i) => i.latest_tier === 'HIGH').length
  const medCount   = items.filter((i) => i.latest_tier === 'MEDIUM').length
  const lowCount   = items.filter((i) => i.latest_tier === 'LOW').length

  // Req 2.7: Use SLA_TARGETS from clinical.tsx (HIGH:4h, MEDIUM:12h, LOW:24h)
  const breachCount = items.filter((i) =>
    isSlaBreached(i.sla_hours_elapsed, i.latest_tier as 'HIGH' | 'MEDIUM' | 'LOW' | null | undefined),
  ).length

  const warnCount = items.filter((i) => {
    if (!i.latest_tier || i.sla_hours_elapsed == null) return false
    const tier = i.latest_tier as keyof typeof SLA_TARGETS
    const target = SLA_TARGETS[tier]
    if (!target) return false
    return (
      i.sla_hours_elapsed >= target.warningHours &&
      i.sla_hours_elapsed < target.targetHours
    )
  }).length

  const unhandled = items.filter((i) =>
    i.workflow_status === 'MENUNGGU_BPMH' || i.workflow_status === 'MENUNGGU_TELAAH'
  ).length

  const dbOk     = healthData?.db_status === 'ok'
  const apiOk    = !!healthData
  const modelOk  = healthData?.model_version !== 'unknown' && !!healthData?.model_version
  const rulesOk  = healthData?.rule_version !== 'unknown' && !!healthData?.rule_version

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Req 2.1: SectionHeading from clinical.tsx */}
      <SectionHeading
        title="Dashboard Farmasi"
        description="Pembaruan otomatis setiap 60 detik"
        as="h1"
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetchWorklist()}
          >
            ↻ Refresh
          </Button>
        }
        className="mb-6"
      />

      {/* KPI Grid */}
      {worklistLoading ? (
        // Req 2.4: Skeleton from primitives (not animate-pulse divs)
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="space-y-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-7 w-16" />
              <Skeleton className="h-3 w-32" />
            </Card>
          ))}
        </div>
      ) : worklistError ? (
        // Req 2.5: ErrorState from primitives with onRetry
        <div className="mb-6">
          <ErrorState
            description="Gagal memuat data worklist."
            onRetry={() => refetchWorklist()}
          />
        </div>
      ) : (
        // Req 2.2: KpiCard from uiux/clinical.tsx
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <KpiCard label="Kasus Aktif" value={total} hint="semua tier" tone="info" />
          <KpiCard
            label="Prioritas Tinggi"
            value={highCount}
            hint="HIGH"
            tone={highCount > 0 ? 'critical' : 'success'}
          />
          <KpiCard label="Prioritas Sedang" value={medCount} hint="MEDIUM" tone={medCount > 5 ? 'warning' : 'neutral'} />
          <KpiCard label="Prioritas Rendah" value={lowCount} hint="LOW" />
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        {/* SLA Panel */}
        <Card>
          <SectionHeading as="h2" title="Status SLA" className="mb-3" />
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">SLA Breach</span>
              <span className={`text-sm font-bold ${breachCount > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                {breachCount}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">SLA Warning</span>
              <span className={`text-sm font-bold ${warnCount > 0 ? 'text-amber-500' : 'text-emerald-600'}`}>
                {warnCount}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600">Kasus tanpa penanganan</span>
              <span className={`text-sm font-bold ${unhandled > 0 ? 'text-amber-500' : 'text-emerald-600'}`}>
                {unhandled}
              </span>
            </div>
          </div>

          {/* Req 2.7: SLA bar with design system colors */}
          {total > 0 && (
            <div className="mt-3 h-3 bg-slate-100 rounded-full overflow-hidden flex">
              <div
                className="bg-red-600 h-full transition-all"
                style={{ width: `${(breachCount / total) * 100}%` }}
                aria-label={`${breachCount} breach`}
              />
              <div
                className="bg-amber-500 h-full transition-all"
                style={{ width: `${(warnCount / total) * 100}%` }}
                aria-label={`${warnCount} warning`}
              />
              <div
                className="bg-emerald-600 h-full transition-all"
                style={{ width: `${((total - breachCount - warnCount) / total) * 100}%` }}
                aria-label="ok"
              />
            </div>
          )}
        </Card>

        {/* System Health */}
        <Card>
          <SectionHeading as="h2" title="Kesehatan Sistem" className="mb-3" />
          {healthLoading ? (
            // Req 2.4: Skeleton for health loading
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-5 w-full" />
              ))}
            </div>
          ) : (
            // Req 2.6: SystemHealthDot with both color and text label
            <div className="space-y-2">
              <SystemHealthDot ok={apiOk} label="API / Backend" />
              <SystemHealthDot ok={dbOk} label="Database" />
              <SystemHealthDot ok={modelOk} label={`Model ML (${healthData?.model_version ?? '—'})`} />
              <SystemHealthDot ok={rulesOk} label={`Rule Engine (${healthData?.rule_version ?? '—'})`} />
            </div>
          )}

          {healthData && (
            <p className="mt-3 text-xs text-slate-400">
              API v{healthData.api_version} ·{' '}
              {healthData.timestamp ? new Date(healthData.timestamp).toLocaleTimeString('id-ID') : '—'}
            </p>
          )}
        </Card>
      </div>

      {/* Req 2.3: PriorityBadge from uiux/clinical.tsx (not legacy TierBadge) */}
      {items.length > 0 && (
        <Card>
          <SectionHeading as="h2" title="Distribusi Prioritas Telaah" className="mb-3" />
          <div className="flex flex-wrap gap-2">
            {(['HIGH', 'MEDIUM', 'LOW'] as const).map((t) => {
              const count = items.filter((i) => i.latest_tier === t).length
              return (
                <div key={t} className="flex items-center gap-2">
                  <PriorityBadge tier={t} />
                  <span className="text-sm font-semibold text-slate-700">{count}</span>
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}
