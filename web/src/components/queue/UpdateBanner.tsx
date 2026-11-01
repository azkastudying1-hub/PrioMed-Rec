/**
 * web/src/components/queue/UpdateBanner.tsx
 * -----------------------------------------
 * Banner notifikasi real-time saat SSE mendeteksi versi antrean baru.
 */

import React from 'react'
import { RefreshCw, ArrowUpCircle } from 'lucide-react'

interface Props {
  hasUpdate: boolean
  pendingChangesCount?: number
  onRefresh: () => void
}

export function UpdateBanner({ hasUpdate, pendingChangesCount = 1, onRefresh }: Props) {
  if (!hasUpdate) return null

  return (
    <div className="bg-sky-50 border border-sky-200 text-sky-800 px-4 py-2.5 rounded-lg flex items-center justify-between shadow-sm animate-fade-in mb-4">
      <div className="flex items-center gap-2">
        <ArrowUpCircle className="w-5 h-5 text-sky-600 animate-bounce" />
        <span className="text-sm font-medium">
          Ada pembaruan antrean baru ({pendingChangesCount} perubahan terdeteksi dari SSE).
        </span>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        className="inline-flex items-center gap-1.5 px-3 py-1 bg-sky-600 hover:bg-sky-700 text-white text-xs font-semibold rounded-md shadow transition"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Perbarui Tampilan
      </button>
    </div>
  )
}
