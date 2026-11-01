/**
 * web/src/pages/WorklistPageV2.tsx
 * ----------------------------------
 * Worklist Telaah Farmasi v2 (F-203).
 *
 * Fitur:
 * - Fetch dari GET /api/v1/worklist (TanStack Query)
 * - Tier badges HIGH/MEDIUM/LOW
 * - SLA countdown per item
 * - Chip alasan prioritas (dari priority_reasons[])
 * - Klaim encounter
 * - Filter tier + pencarian
 * - Polling setiap 30 detik
 * - Loading/empty/error states dengan tombol "Coba Lagi"
 *
 * S11: Label "Prioritas Telaah Farmasi" — bukan "risiko" / "triase"
 */

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { TierBadge } from '../components/TierBadge'
import { SlaCountdown } from '../components/SlaCountdown'
import { getWorklistV1, claimEncounterV1, type WorklistItemV1 } from '../lib/apiClient'
import type { RiskLevel } from '../types/clinical'

interface Props {
  onSelectEncounter?: (item: WorklistItemV1) => void
}

const STATUS_LABELS: Record<string, string> = {
  MENUNGGU_BPMH:    'Menunggu BPMH',
  BPMH_LENGKAP:     'BPMH Lengkap',
  DALAM_ANALISIS:   'Dalam Analisis',
  MENUNGGU_TELAAH:  'Menunggu Telaah',
  DRAFT_REVIEW:     'Draft Telaah',
  SELESAI_APPROVE:  'Selesai ✓',
  SELESAI_EDIT:     'Selesai (Edit) ✓',
  DITOLAK:          'Ditolak',
  ESKALASI:         'Eskalasi',
  RETRIAGE:         'Retriage',
}

function WorklistRow({
  item,
  currentUserId,
  onSelect,
  onClaim,
}: {
  item: WorklistItemV1
  currentUserId?: string
  onSelect: () => void
  onClaim: (item: WorklistItemV1) => void
}) {
  const isMine = item.claimed_by === currentUserId
  const isClaimed = !!item.claimed_by && !isMine

  return (
    <tr
      className={`border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors ${isMine ? 'bg-blue-50' : ''}`}
      onClick={onSelect}
    >
      {/* Tier */}
      <td className="px-3 py-3 w-32">
        <TierBadge tier={item.latest_tier} size="md" />
      </td>

      {/* Patient */}
      <td className="px-3 py-3">
        <div className="font-medium text-slate-800 text-sm">
          {item.patient_name || item.patient_id}
        </div>
        <div className="text-xs text-slate-400 mt-0.5">{item.patient_id}</div>
      </td>

      {/* Ward */}
      <td className="px-3 py-3 text-sm text-slate-600">
        {item.ward || '—'}
      </td>

      {/* Status */}
      <td className="px-3 py-3">
        <span className="text-xs text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
          {STATUS_LABELS[item.workflow_status] ?? item.workflow_status}
        </span>
      </td>

      {/* SLA */}
      <td className="px-3 py-3">
        <SlaCountdown
          hoursElapsed={item.sla_hours_elapsed}
          tier={item.latest_tier}
          size="sm"
        />
      </td>

      {/* Priority reason chips */}
      <td className="px-3 py-3 max-w-xs">
        <div className="flex flex-wrap gap-1">
          {item.priority_reasons.slice(0, 2).map((r, i) => (
            <span
              key={i}
              className="text-xs bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded truncate max-w-[140px]"
              title={r.reason}
            >
              {r.reason}
            </span>
          ))}
          {item.priority_reasons.length > 2 && (
            <span className="text-xs text-slate-400">
              +{item.priority_reasons.length - 2}
            </span>
          )}
        </div>
      </td>

      {/* Claim */}
      <td className="px-3 py-3 text-right">
        {isMine ? (
          <span className="text-xs text-blue-600 font-medium">✓ Diklaim Anda</span>
        ) : isClaimed ? (
          <span className="text-xs text-slate-400">Diklaim</span>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); onClaim(item) }}
            className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            Klaim
          </button>
        )}
      </td>
    </tr>
  )
}

export function WorklistPageV2({ onSelectEncounter }: Props) {
  const queryClient = useQueryClient()
  const [tierFilter, setTierFilter] = useState<RiskLevel | ''>('')
  const [search, setSearch] = useState('')
  const [claimingId, setClaimingId] = useState<string | null>(null)

  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['worklist', tierFilter, search],
    queryFn: () => getWorklistV1({
      tier: tierFilter || undefined,
      search: search || undefined,
      page_size: 50,
    }),
    refetchInterval: 30_000,  // Poll every 30s
    staleTime: 15_000,
  })

  async function handleClaim(item: WorklistItemV1) {
    setClaimingId(item.encounter_id)
    try {
      await claimEncounterV1(item.encounter_id, item.row_version)
      queryClient.invalidateQueries({ queryKey: ['worklist'] })
    } catch (err) {
      alert(`Gagal klaim: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setClaimingId(null)
    }
  }

  const items = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-lg font-bold text-slate-800">
              Worklist Prioritas Telaah Farmasi
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              {total} kasus aktif • Diperbarui setiap 30 detik
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="text-xs px-3 py-1.5 border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors text-slate-600"
            aria-label="Refresh worklist"
          >
            ↻ Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <div className="flex gap-1">
            {(['', 'HIGH', 'MEDIUM', 'LOW'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTierFilter(t)}
                className={`text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
                  tierFilter === t
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                }`}
              >
                {t === '' ? 'Semua' : t === 'HIGH' ? '🔴 Tinggi' : t === 'MEDIUM' ? '🟡 Sedang' : '🟢 Rendah'}
              </button>
            ))}
          </div>

          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari pasien atau ID..."
            className="flex-1 min-w-[180px] px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Cari pasien"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-48">
            <div className="text-sm text-slate-500 animate-pulse">Memuat worklist...</div>
          </div>
        )}

        {isError && (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <p className="text-sm text-red-600">Gagal memuat worklist dari server.</p>
            <button
              onClick={() => refetch()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
            >
              Coba Lagi
            </button>
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 gap-2">
            <span className="text-3xl">✅</span>
            <p className="text-sm text-slate-500">Tidak ada kasus yang menunggu telaah.</p>
          </div>
        )}

        {!isLoading && !isError && items.length > 0 && (
          <table className="w-full text-sm" role="grid" aria-label="Daftar kasus telaah farmasi">
            <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
              <tr>
                <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-slate-500">Prioritas</th>
                <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-slate-500">Pasien</th>
                <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-slate-500">Bangsal</th>
                <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-slate-500">Status</th>
                <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-slate-500">SLA</th>
                <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-slate-500">Alasan</th>
                <th scope="col" className="px-3 py-2 text-right text-xs font-medium text-slate-500">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <WorklistRow
                  key={item.encounter_id}
                  item={item}
                  onSelect={() => onSelectEncounter?.(item)}
                  onClaim={handleClaim}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Footer summary */}
      {items.length > 0 && (
        <div className="p-3 border-t border-slate-100 bg-slate-50 flex gap-4 text-xs text-slate-500">
          {(['HIGH', 'MEDIUM', 'LOW'] as RiskLevel[]).map((t) => {
            const count = items.filter((i) => i.latest_tier === t).length
            return count > 0 ? (
              <span key={t}>
                <TierBadge tier={t} size="sm" /> {count}
              </span>
            ) : null
          })}
        </div>
      )}
    </div>
  )
}
