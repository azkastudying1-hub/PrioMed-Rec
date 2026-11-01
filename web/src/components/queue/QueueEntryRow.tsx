/**
 * web/src/components/queue/QueueEntryRow.tsx
 * -----------------------------------------
 * Baris antrean interaktif yang menampilkan identitas pasien, bangsal,
 * tier + sumber (RULE/ML/SLA), countdown SLA, aging strip, dan tombol aksi.
 */

import React from 'react'
import type { QueueEntry } from '../../api/queue'
import { AgingStrip } from './AgingStrip'
import { TierSourceBadge } from './TierSourceBadge'
import { Clock, User, Building, ShieldAlert } from 'lucide-react'

interface Props {
  entry: QueueEntry
  isClaimedByMe?: boolean
  onClaim?: (entry: QueueEntry) => void
  onOpen?: (entry: QueueEntry) => void
}

function formatElapsed(hours: number | null): string {
  if (hours == null) return '-'
  if (hours < 1) return `${Math.round(hours * 60)} mnt`
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return m > 0 ? `${h}j ${m}m` : `${h}j`
}

export function QueueEntryRow({ entry, isClaimedByMe = false, onClaim, onOpen }: Props) {
  const isClaimedByOther = !!entry.claimed_by && !isClaimedByMe

  return (
    <div
      className={`group relative flex items-center gap-3 p-3.5 bg-white border rounded-lg transition hover:shadow-md ${
        isClaimedByMe
          ? 'border-indigo-400 bg-indigo-50/20'
          : isClaimedByOther
          ? 'border-slate-200 bg-slate-50 opacity-75'
          : 'border-slate-200 hover:border-slate-300'
      }`}
    >
      {/* Aging strip on the left edge */}
      <AgingStrip hoursElapsed={entry.hours_waiting} tier={entry.tier} />

      {/* Main details */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <TierSourceBadge tier={entry.tier} source={entry.tier_source} size="sm" />
          <span className="text-xs font-mono font-medium text-slate-500">
            {entry.encounter_id.slice(0, 8)}
          </span>
          <span className="text-sm font-semibold text-slate-800 truncate">
            {entry.patient_name || `Pasien ${(entry.patient_id ?? entry.encounter_id).slice(0, 8)}`}
          </span>
          {entry.ml_score != null && (
            <span
              className="text-[11px] font-mono text-slate-400"
              title={`Skor ML: ${(entry.ml_score * 100).toFixed(0)}%`}
            >
              ML: {(entry.ml_score * 100).toFixed(0)}%
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1">
            <Building className="w-3.5 h-3.5 text-slate-400" />
            {entry.ward || 'Umum'}
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            Tunggu: {formatElapsed(entry.hours_waiting)}
          </span>
          {entry.dpjp_name && (
            <span className="inline-flex items-center gap-1">
              <User className="w-3.5 h-3.5 text-slate-400" />
              DPJP: {entry.dpjp_name}
            </span>
          )}
          {entry.claimed_by && (
            <span className="inline-flex items-center gap-1 text-indigo-600 font-medium">
              Diklaim: {entry.claimed_by}
            </span>
          )}
        </div>
      </div>

      {/* Right side: Priority score & Action button */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="text-right hidden sm:block">
          <div className="text-xs text-slate-400">Skor Prioritas</div>
          <div className="text-sm font-bold text-slate-700 font-mono">
            {entry.priority_score.toFixed(1)}
          </div>
        </div>

        {isClaimedByMe ? (
          <button
            type="button"
            onClick={() => onOpen?.(entry)}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-md shadow-sm transition"
          >
            Lanjutkan Telaah
          </button>
        ) : isClaimedByOther ? (
          <span className="px-2.5 py-1 bg-slate-200 text-slate-500 text-xs rounded font-medium">
            Sedang Ditelaah
          </span>
        ) : (
          <button
            type="button"
            onClick={() => onClaim?.(entry)}
            className="px-3 py-1.5 bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold rounded-md shadow-sm transition"
          >
            Ambil Kasus
          </button>
        )}
      </div>
    </div>
  )
}
