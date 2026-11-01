/**
 * web/src/components/SimulationPanel.tsx
 * ---------------------------------------
 * Panel kontrol demo: replay CSV satu pasien per interval.
 *
 * - Mulai / hentikan simulation engine (APScheduler di backend)
 * - Tambah 1 pasien manual
 * - Menampilkan skor XGBoost, tier akhir, temuan aturan, dan eskalasi SLA
 * - Polling status ringan (1,5 dtk saat berjalan)
 *
 * Data yang ditampilkan adalah data simulasi.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Database,
  LoaderCircle,
  Play,
  Plus,
  Square,
} from 'lucide-react'

import { Badge, Button, Card, Input, Select } from './ui'
import {
  getSimulationStatus,
  startSimulation,
  stepSimulation,
  stopSimulation,
  type SimulationStatus,
} from '../api/simulation'

interface Props {
  /** Dipanggil setelah start/step agar halaman memuat ulang antrean. */
  onChange?: () => void
  className?: string
}

const SLA_OPTIONS = [
  { value: '0.0025', label: 'Demo cepat (1 jam SLA ≈ 9 dtk)' },
  { value: '0.01', label: 'Demo sedang (1 jam SLA ≈ 36 dtk)' },
  { value: '1', label: 'Produksi (SLA dalam jam)' },
]

function statusTone(status: SimulationStatus | null): {
  label: string
  tone: 'neutral' | 'info' | 'warning' | 'success' | 'danger'
} {
  if (!status) return { label: 'Memuat', tone: 'neutral' }
  if (status.preparing) return { label: 'Menyiapkan dataset', tone: 'info' }
  if (status.draining) return { label: 'Menunggu eskalasi SLA', tone: 'warning' }
  if (status.running) return { label: 'Berjalan', tone: 'success' }
  if (status.finished) return { label: 'Selesai', tone: 'info' }
  if (status.errors > 0) return { label: 'Berhenti dengan error', tone: 'danger' }
  return { label: 'Berhenti', tone: 'neutral' }
}

export function SimulationPanel({ onChange, className = '' }: Props) {
  const [status, setStatus] = useState<SimulationStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<'start' | 'stop' | 'step' | null>(null)

  const [intervalSeconds, setIntervalSeconds] = useState('6')
  const [maxPatients, setMaxPatients] = useState('60')
  const [slaScale, setSlaScale] = useState('0.0025')

  const timer = useRef<number | null>(null)
  const mounted = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const next = await getSimulationStatus()
      if (!mounted.current) return
      setStatus(next)
      setError(null)
    } catch (err) {
      if (!mounted.current) return
      setError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    return () => {
      mounted.current = false
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [refresh])

  useEffect(() => {
    const active = Boolean(status?.running || status?.preparing)
    const delay = active ? 1500 : 5000
    timer.current = window.setTimeout(() => {
      void refresh()
    }, delay)
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
  }, [status, refresh])

  const handleStart = useCallback(async () => {
    setBusy('start')
    setError(null)
    try {
      const res = await startSimulation({
        interval_seconds: Number(intervalSeconds) || 6,
        max_patients: Number(maxPatients) || 60,
        sla_scale: Number(slaScale) || 0.0025,
        fresh_ids: true,
      })
      setStatus(res.status)
      onChange?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }, [intervalSeconds, maxPatients, slaScale, onChange])

  const handleStop = useCallback(async () => {
    setBusy('stop')
    setError(null)
    try {
      const res = await stopSimulation()
      setStatus(res.status)
      onChange?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }, [onChange])

  const handleStep = useCallback(async () => {
    setBusy('step')
    setError(null)
    try {
      const res = await stepSimulation(1)
      setStatus(res.status)
      onChange?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }, [onChange])

  const badge = statusTone(status)
  const last = status?.last_patient
  const running = Boolean(status?.running)
  const preparing = Boolean(status?.preparing)

  return (
    <Card className={className} variant="emphasized">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <Activity className="mt-0.5 size-5 text-blue-700" aria-hidden="true" />
          <div>
            <h2 className="text-sm font-semibold text-slate-900">
              Simulasi Replay CSV — XGBoost + Rule Engine
            </h2>
            <p className="mt-0.5 max-w-2xl text-xs text-slate-600">
              Setiap tick mengambil satu baris <code>model_ready.csv</code>,
              menjalankan prediksi XGBoost dan aturan diskrepansi asli, lalu
              menulis ke antrean. Dashboard diperbarui lewat SSE.
            </p>
          </div>
        </div>
        <Badge tone={badge.tone}>{badge.label}</Badge>
      </div>

      {/* Kontrol */}
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs font-medium text-slate-600">
          Interval (detik)
          <Input
            type="number"
            min={1}
            max={120}
            value={intervalSeconds}
            onChange={(e) => setIntervalSeconds(e.target.value)}
            disabled={running || preparing}
            className="mt-1"
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          Jumlah pasien
          <Input
            type="number"
            min={1}
            max={5000}
            value={maxPatients}
            onChange={(e) => setMaxPatients(e.target.value)}
            disabled={running || preparing}
            className="mt-1"
          />
        </label>
        <label className="text-xs font-medium text-slate-600">
          Kecepatan SLA
          <Select
            options={SLA_OPTIONS}
            value={slaScale}
            onChange={(e) => setSlaScale(e.target.value)}
            disabled={running || preparing}
            className="mt-1"
          />
        </label>
        <div className="flex items-end gap-2">
          {running || preparing ? (
            <Button
              variant="danger"
              icon={<Square className="size-4" />}
              loading={busy === 'stop'}
              onClick={() => void handleStop()}
            >
              Hentikan
            </Button>
          ) : (
            <Button
              variant="primary"
              icon={
                busy === 'start' ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <Play className="size-4" />
                )
              }
              loading={busy === 'start'}
              onClick={() => void handleStart()}
            >
              Mulai simulasi
            </Button>
          )}
          <Button
            variant="secondary"
            icon={<Plus className="size-4" />}
            loading={busy === 'step'}
            onClick={() => void handleStep()}
            disabled={busy !== null}
          >
            1 pasien
          </Button>
        </div>
      </div>

      {/* Metrik */}
      {status && (
        <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4 lg:grid-cols-7">
          <Metric label="Pasien masuk" value={status.admitted} />
          <Metric label="BPMH selesai" value={status.bpmh_completed} />
          <Metric label="Eskalasi SLA" value={status.escalated} />
          <Metric label="Menunggu BPMH" value={status.pending_bpmh} />
          <Metric label="Error" value={status.errors} danger={status.errors > 0} />
          <Metric
            label={status.draining ? 'Sisa drain' : 'Tick'}
            value={status.draining ? status.drain_remaining : status.tick_count}
          />
          <Metric
            label="Dataset"
            value={`${status.next_index}/${status.dataset_rows}`}
          />
        </div>
      )}

      {/* Pasien terakhir */}
      {last && last.encounter_id && (
        <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="inline-flex items-center gap-1 font-medium text-slate-900">
              <Database className="size-3.5" aria-hidden="true" />
              Pasien terakhir
            </span>
            <span>
              ID: <code>{last.source_encounter_id ?? last.encounter_id}</code>
            </span>
            <span>Bangsal: {last.ward ?? '—'}</span>
            <span>
              Skor ML:{' '}
              <strong>{last.ml_score != null ? last.ml_score.toFixed(3) : '—'}</strong>
            </span>
            <span>
              Tier akhir: <strong>{last.final_tier ?? '—'}</strong>
            </span>
            <span>Temuan aturan: {last.rule_findings ?? 0}</span>
            {last.mutation_type && <span>Kasus: {last.mutation_type}</span>}
          </div>
          {last.rule_types && last.rule_types.length > 0 && (
            <p className="mt-1 text-[11px] text-slate-500">
              {last.rule_types.join(' · ')}
            </p>
          )}
        </div>
      )}

      {status?.last_error && (
        <p className="mt-2 flex items-start gap-1 text-xs text-red-700" role="alert">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {status.last_error}
        </p>
      )}
      {error && (
        <p className="mt-2 flex items-start gap-1 text-xs text-red-700" role="alert">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}

      <p className="mt-3 text-[11px] text-slate-500">
        {status?.label ??
          'Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS'}
        {status?.model_version ? ` · model ${status.model_version}` : ''}
        {status?.load_seconds ? ` · muat ${status.load_seconds}s` : ''}
      </p>
    </Card>
  )
}

function Metric({
  label,
  value,
  danger = false,
}: {
  label: string
  value: number | string
  danger?: boolean
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-2 py-1.5">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p
        className={`text-base font-semibold ${
          danger ? 'text-red-700' : 'text-slate-900'
        }`}
      >
        {value}
      </p>
    </div>
  )
}
