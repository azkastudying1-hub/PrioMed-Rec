/**
 * web/src/components/ReviewActionBar.tsx
 * ----------------------------------------
 * Bilah aksi sticky untuk keputusan telaah apoteker (F-208).
 *
 * Aksi: APPROVE | EDIT | REJECT | ESCALATE | DRAFT_REVIEW
 * - Alasan wajib untuk EDIT, REJECT, ESCALATE
 * - APPROVE memerlukan konfirmasi high-alert jika ada
 * - Undo tersedia 10 detik setelah submit
 *
 * S1: Keputusan akhir HANYA dari apoteker
 * S12: Label "Draf AI — wajib diverifikasi apoteker" ditampilkan
 */

import { useState, useEffect, useCallback } from 'react'
import type { ActionType } from '../types/clinical'

interface Props {
  encounterId: string
  rowVersion: number
  hasUnconfirmedHighAlert: boolean
  highAlertCount: number
  onAction: (action: ActionType, reason?: string, note?: string) => Promise<void>
  onHighAlertConfirmNeeded: () => void
  isSubmitting?: boolean
}

const ACTION_CONFIG: Record<ActionType, {
  label: string; color: string; requiresReason: boolean; confirmMsg?: string
}> = {
  APPROVE: {
    label: '✓ Setujui',
    color: 'bg-green-600 hover:bg-green-700 text-white',
    requiresReason: false,
  },
  EDIT: {
    label: '✏️ Edit & Setujui',
    color: 'bg-blue-600 hover:bg-blue-700 text-white',
    requiresReason: true,
  },
  REJECT: {
    label: '✗ Tolak',
    color: 'bg-slate-600 hover:bg-slate-700 text-white',
    requiresReason: true,
    confirmMsg: 'Apakah Anda yakin ingin menolak telaah ini?',
  },
  ESCALATE: {
    label: '↑ Eskalasi',
    color: 'bg-orange-500 hover:bg-orange-600 text-white',
    requiresReason: true,
  },
  DRAFT_REVIEW: {
    label: '💾 Simpan Draf',
    color: 'bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300',
    requiresReason: false,
  },
}

export function ReviewActionBar({
  encounterId,
  rowVersion,
  hasUnconfirmedHighAlert,
  highAlertCount,
  onAction,
  onHighAlertConfirmNeeded,
  isSubmitting = false,
}: Props) {
  const [selectedAction, setSelectedAction] = useState<ActionType | null>(null)
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [undoTimer, setUndoTimer] = useState<ReturnType<typeof setTimeout> | null>(null)
  const [undoCountdown, setUndoCountdown] = useState(0)
  const [pendingAction, setPendingAction] = useState<{
    action: ActionType; reason?: string; note?: string
  } | null>(null)

  const cancelUndo = useCallback(() => {
    if (undoTimer) clearTimeout(undoTimer)
    setUndoTimer(null)
    setUndoCountdown(0)
    setPendingAction(null)
  }, [undoTimer])

  useEffect(() => {
    return () => { if (undoTimer) clearTimeout(undoTimer) }
  }, [undoTimer])

  function handleActionClick(action: ActionType) {
    // APPROVE + high-alert check
    if (action === 'APPROVE' && hasUnconfirmedHighAlert) {
      onHighAlertConfirmNeeded()
      return
    }

    const cfg = ACTION_CONFIG[action]
    if (cfg.requiresReason && !reason.trim()) {
      setSelectedAction(action)
      return
    }

    // Confirm destructive actions
    if (cfg.confirmMsg && !window.confirm(cfg.confirmMsg)) return

    initiateSubmit(action, reason.trim() || undefined, note.trim() || undefined)
  }

  function initiateSubmit(action: ActionType, actionReason?: string, actionNote?: string) {
    setPendingAction({ action, reason: actionReason, note: actionNote })
    setUndoCountdown(10)

    let count = 10
    const interval = setInterval(() => {
      count -= 1
      setUndoCountdown(count)
      if (count <= 0) {
        clearInterval(interval)
        executeAction(action, actionReason, actionNote)
      }
    }, 1000)

    setUndoTimer(interval as unknown as ReturnType<typeof setTimeout>)
  }

  async function executeAction(action: ActionType, actionReason?: string, actionNote?: string) {
    setUndoTimer(null)
    setUndoCountdown(0)
    setPendingAction(null)
    setSelectedAction(null)
    setReason('')
    setNote('')
    await onAction(action, actionReason, actionNote)
  }

  // If reason required and action selected, show reason form
  if (selectedAction && ACTION_CONFIG[selectedAction].requiresReason) {
    return (
      <div className="sticky bottom-0 bg-white border-t border-slate-200 p-4 shadow-lg">
        <div className="max-w-2xl mx-auto">
          <p className="text-sm font-medium text-slate-700 mb-2">
            Alasan {ACTION_CONFIG[selectedAction].label} (wajib):
          </p>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            rows={2}
            placeholder="Tulis alasan keputusan klinis..."
            autoFocus
            aria-label="Alasan keputusan"
          />
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => {
                if (!reason.trim()) return
                initiateSubmit(selectedAction, reason, note || undefined)
              }}
              disabled={!reason.trim() || isSubmitting}
              className={`flex-1 py-2 rounded-lg text-sm font-medium disabled:opacity-50 ${ACTION_CONFIG[selectedAction].color}`}
            >
              Konfirmasi {ACTION_CONFIG[selectedAction].label}
            </button>
            <button
              onClick={() => { setSelectedAction(null); setReason('') }}
              className="px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
            >
              Batal
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Undo countdown overlay
  if (pendingAction && undoCountdown > 0) {
    return (
      <div className="sticky bottom-0 bg-amber-50 border-t border-amber-300 p-4 shadow-lg">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-amber-800">
              Mengirim: <strong>{ACTION_CONFIG[pendingAction.action].label}</strong>
            </span>
            <span className="text-xs text-amber-700 ml-2">dalam {undoCountdown}d...</span>
          </div>
          <button
            onClick={cancelUndo}
            className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700"
          >
            ↩ Urungkan
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="sticky bottom-0 bg-white border-t border-slate-200 p-4 shadow-lg">
      {/* High-alert warning */}
      {hasUnconfirmedHighAlert && (
        <div className="max-w-2xl mx-auto mb-3 p-2 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
          <span className="text-sm" aria-hidden="true">⚠️</span>
          <p className="text-xs text-red-700">
            <strong>{highAlertCount} temuan high-alert</strong> belum dikonfirmasi.
            Konfirmasi diperlukan sebelum APPROVE dapat diproses.
          </p>
        </div>
      )}

      {/* Note field */}
      <div className="max-w-2xl mx-auto mb-3">
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs text-slate-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="Catatan opsional apoteker..."
          aria-label="Catatan opsional"
        />
      </div>

      {/* Action buttons */}
      <div className="max-w-2xl mx-auto flex flex-wrap gap-2">
        {(['DRAFT_REVIEW', 'APPROVE', 'EDIT', 'REJECT', 'ESCALATE'] as ActionType[]).map((action) => (
          <button
            key={action}
            onClick={() => handleActionClick(action)}
            disabled={isSubmitting}
            className={`flex-1 min-w-[80px] py-2 px-3 rounded-lg text-xs font-medium disabled:opacity-50 transition-colors ${ACTION_CONFIG[action].color}`}
            aria-label={ACTION_CONFIG[action].label}
          >
            {ACTION_CONFIG[action].label}
          </button>
        ))}
      </div>

      {/* S1 reminder */}
      <p className="max-w-2xl mx-auto mt-2 text-center text-xs text-slate-400">
        Keputusan akhir adalah tanggung jawab apoteker yang bersangkutan.
      </p>
    </div>
  )
}
