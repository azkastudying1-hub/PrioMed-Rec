/**
 * web/src/components/queue/MyClaimedPanel.tsx
 * -------------------------------------------
 * Panel kasus yang sedang aktif diklaim oleh apoteker login.
 * Menampilkan countdown masa sewa (lease timer), tombol heartbeat, lepas klaim,
 * dan buka ruang kerja telaah (Case Workspace).
 */

import React, { useEffect, useState } from 'react'
import type { QueueEntry } from '../../api/queue'
import { heartbeatEntry, releaseEntry } from '../../api/queue'
import { TierSourceBadge } from './TierSourceBadge'
import { Clock, ShieldCheck, Play, XCircle, RefreshCw } from 'lucide-react'

interface Props {
  claimedEntries: QueueEntry[]
  onOpenCase: (entry: QueueEntry) => void
  onClaimReleased: (entryId: string) => void
}

export function MyClaimedPanel({ claimedEntries, onOpenCase, onClaimReleased }: Props) {
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [heartbeatSuccess, setHeartbeatSuccess] = useState<string | null>(null)

  // Auto-heartbeat every 4 minutes (lease is typically 15-30m)
  useEffect(() => {
    if (claimedEntries.length === 0) return

    const interval = setInterval(() => {
      claimedEntries.forEach((entry) => {
        heartbeatEntry(entry.encounter_id).catch((err) =>
          console.warn(`Heartbeat gagal untuk ${entry.encounter_id}:`, err)
        )
      })
    }, 4 * 60 * 1000)

    return () => clearInterval(interval)
  }, [claimedEntries])

  const handleRelease = async (entry: QueueEntry) => {
    if (!confirm(`Lepas klaim untuk ${entry.encounter_id.slice(0, 8)}? Kasus akan kembali ke antrean umum.`)) return
    setLoadingId(entry.encounter_id)
    try {
      await releaseEntry(entry.encounter_id)
      onClaimReleased(entry.encounter_id)
    } catch (err) {
      alert(`Gagal melepas klaim: ${err}`)
    } finally {
      setLoadingId(null)
    }
  }

  const handleManualHeartbeat = async (entry: QueueEntry) => {
    setLoadingId(entry.encounter_id)
    try {
      await heartbeatEntry(entry.encounter_id)
      setHeartbeatSuccess(entry.encounter_id)
      setTimeout(() => setHeartbeatSuccess(null), 2500)
    } catch (err) {
      alert(`Gagal memperpanjang sewa: ${err}`)
    } finally {
      setLoadingId(null)
    }
  }

  if (claimedEntries.length === 0) {
    return (
      <div className="bg-slate-50 border border-dashed border-slate-200 rounded-lg p-5 text-center text-slate-500">
        <ShieldCheck className="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <div className="text-sm font-medium">Belum ada kasus yang diklaim</div>
        <p className="text-xs text-slate-400 mt-1">
          Klik tombol <strong>"Ambil Berikutnya"</strong> untuk mulai menelaah pasien prioritas tertinggi.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
          <span>Antrean Saya</span>
          <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-full">
            {claimedEntries.length} aktif
          </span>
        </h3>
        <span className="text-xs text-slate-400">Auto-heartbeat aktif (tiap 4 mnt)</span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {claimedEntries.map((entry) => (
          <div
            key={entry.encounter_id}
            className="bg-white border-2 border-indigo-200 rounded-lg p-3.5 shadow-sm hover:border-indigo-300 transition"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div>
                <div className="flex items-center gap-1.5 mb-1">
                  <TierSourceBadge tier={entry.tier} source={entry.tier_source} size="sm" />
                  <span className="text-xs font-mono font-medium text-slate-600">
                    {entry.encounter_id.slice(0, 8)}
                  </span>
                </div>
                <div className="text-sm font-bold text-slate-800">
                  {entry.patient_name || `Pasien ${(entry.patient_id ?? entry.encounter_id).slice(0, 8)}`}
                </div>
                <div className="text-xs text-slate-500">Bangsal: {entry.ward || 'Umum'}</div>
              </div>

              <div className="text-right">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold rounded">
                  <Clock className="w-3 h-3" />
                  Sewa Aktif
                </span>
                {heartbeatSuccess === entry.encounter_id && (
                  <div className="text-[10px] text-emerald-600 font-medium mt-1">
                    ✓ Diperpanjang
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-100 mt-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleManualHeartbeat(entry)}
                  disabled={loadingId === entry.encounter_id}
                  title="Perpanjang masa sewa klaim (heartbeat)"
                  className="p-1.5 text-slate-400 hover:text-indigo-600 rounded hover:bg-indigo-50 transition"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingId === entry.encounter_id ? 'animate-spin' : ''}`} />
                </button>
                <button
                  type="button"
                  onClick={() => handleRelease(entry)}
                  disabled={loadingId === entry.encounter_id}
                  className="inline-flex items-center gap-1 text-xs text-rose-600 hover:text-rose-700 font-medium hover:underline"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Lepas
                </button>
              </div>

              <button
                type="button"
                onClick={() => onOpenCase(entry)}
                className="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded shadow-sm transition"
              >
                <Play className="w-3 h-3 fill-current" />
                Buka Kasus
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
