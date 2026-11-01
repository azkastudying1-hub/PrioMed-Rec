/**
 * web/src/components/queue/WardQueuePanel.tsx
 * -------------------------------------------
 * Panel daftar antrean bangsal dengan filter (Bangsal, Tier, Tipe Antrean),
 * pencarian nama/encounter, dan render baris antrean.
 */

import React, { useState } from 'react'
import type { QueueEntry, QueueTier, QueueType } from '../../api/queue'
import { QueueEntryRow } from './QueueEntryRow'
import { Filter, Search, Layers, RefreshCw } from 'lucide-react'

interface Props {
  entries: QueueEntry[]
  totalCount: number
  loading: boolean
  onClaim: (entry: QueueEntry) => void
  onRefresh: () => void
  selectedWard: string
  onSelectWard: (ward: string) => void
  selectedTier: string
  onSelectTier: (tier: string) => void
  selectedType: QueueType
  onSelectType: (type: QueueType) => void
}

const WARDS = [
  'Semua Bangsal',
  'IGD',
  'ICU',
  'PENYAKIT_DALAM',
  'BEDAH',
  'JANTUNG',
  'SARAF',
  'ANAK',
  'KEBIDANAN',
  'ONKOLOGI',
]

const TIERS = ['Semua Prioritas', 'HIGH', 'MEDIUM', 'LOW']

export function WardQueuePanel({
  entries,
  totalCount,
  loading,
  onClaim,
  onRefresh,
  selectedWard,
  onSelectWard,
  selectedTier,
  onSelectTier,
  selectedType,
  onSelectType,
}: Props) {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredEntries = entries.filter((e) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      e.encounter_id.toLowerCase().includes(q) ||
      (e.patient_id ?? '').toLowerCase().includes(q) ||
      (e.patient_name && e.patient_name.toLowerCase().includes(q))
    )
  })

  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-sm">
      {/* Filters header */}
      <div className="p-4 border-b border-slate-200 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-slate-500" />
            <h3 className="text-base font-bold text-slate-800">
              Antrean Bangsal ({totalCount})
            </h3>
            {loading && <RefreshCw className="w-4 h-4 text-sky-600 animate-spin" />}
          </div>

          {/* Antrean Type Tabs (REVIEW vs BPMH) */}
          <div className="flex bg-slate-100 p-0.5 rounded-lg text-xs font-semibold">
            <button
              type="button"
              onClick={() => onSelectType('REVIEW')}
              className={`px-3 py-1.5 rounded-md transition ${
                selectedType === 'REVIEW'
                  ? 'bg-white text-indigo-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Telaah Resep (Apoteker)
            </button>
            <button
              type="button"
              onClick={() => onSelectType('BPMH')}
              className={`px-3 py-1.5 rounded-md transition ${
                selectedType === 'BPMH'
                  ? 'bg-white text-indigo-700 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Rekonsiliasi Masuk (TTK)
            </button>
          </div>
        </div>

        {/* Filter dropdowns + search */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-1">
          {/* Ward filter */}
          <div>
            <select
              value={selectedWard}
              onChange={(e) => onSelectWard(e.target.value)}
              className="w-full text-xs font-medium border border-slate-200 rounded-md py-1.5 px-2.5 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              {WARDS.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>

          {/* Tier filter */}
          <div>
            <select
              value={selectedTier}
              onChange={(e) => onSelectTier(e.target.value)}
              className="w-full text-xs font-medium border border-slate-200 rounded-md py-1.5 px-2.5 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              {TIERS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          {/* Search input */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Cari ID / Nama Pasien..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs pl-8 pr-3 py-1.5 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-sky-500"
            />
          </div>
        </div>
      </div>

      {/* Entry List */}
      <div className="p-3 space-y-2 max-h-[600px] overflow-y-auto">
        {filteredEntries.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-sm">
            {loading ? 'Memuat daftar antrean...' : 'Tidak ada pasien dalam antrean ini.'}
          </div>
        ) : (
          filteredEntries.map((entry) => (
            <QueueEntryRow key={entry.encounter_id} entry={entry} onClaim={onClaim} />
          ))
        )}
      </div>
    </div>
  )
}
