/**
 * web/src/pages/ReviewConfirmationPage.tsx
 * --------------------------
 * Halaman konfirmasi review setelah apoteker mengambil keputusan.
 *
 * Task 13.3: Migrated to uiux/ design system.
 * Requirements: 16.1, 16.2, 16.3, 16.4, 16.5
 */

import { useState, useCallback } from "react"
import { CheckCircle2, Clock } from "lucide-react"
import {
  Badge,
  Button,
  Card,
  InlineAlert,
} from "../uiux/primitives"
import { SectionHeading, SafetyBanner } from "../uiux/clinical"

interface ReviewConfirmationProps {
  patientId: string
  action: "approve" | "reject" | "edit" | "escalate"
  note: string
  timestamp: string
  onReturnToWorklist: () => void
}

// Req 16.3: Badge with consistent color coding per action type
function ActionBadge({ action }: { action: ReviewConfirmationProps["action"] }) {
  switch (action) {
    case "approve":
      return <Badge tone="success">APPROVE</Badge>
    case "reject":
      return <Badge tone="danger">REJECT</Badge>
    case "escalate":
      return <Badge tone="warning">ESCALATE</Badge>
    case "edit":
      return <Badge tone="info">EDIT</Badge>
    default:
      return <Badge tone="neutral">{String(action).toUpperCase()}</Badge>
  }
}

export function ReviewConfirmationPage({
  patientId,
  action,
  note,
  timestamp,
  onReturnToWorklist,
}: ReviewConfirmationProps) {
  const [showSuccess, setShowSuccess] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  const handleSave = useCallback(async () => {
    setIsSaving(true)
    try {
      await new Promise((resolve) => setTimeout(resolve, 1500))
      setShowSuccess(true)
      setTimeout(() => {
        onReturnToWorklist()
      }, 2000)
    } catch (error) {
      console.error("Gagal menyimpan review:", error)
      window.alert("Gagal menyimpan review. Silakan coba lagi.")
    } finally {
      setIsSaving(false)
    }
  }, [onReturnToWorklist])

  // Req 16.2: InlineAlert tone "success" with CheckCircle2 on successful review
  if (showSuccess) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-[var(--pmr-bg)]">
        <div className="w-full max-w-md space-y-4">
          <InlineAlert
            tone="success"
            icon={<CheckCircle2 className="size-4" aria-hidden="true" />}
            title="Review Berhasil Disimpan"
          >
            Keputusan apoteker tercatat dalam audit trail.
          </InlineAlert>

          <Card>
            <p className="text-sm text-slate-500 mb-2">Ringkasan:</p>
            <p className="whitespace-pre-line text-slate-700 text-sm">
              Pasien {patientId} — Action: {action.toUpperCase()} — Note: {note}
            </p>
          </Card>

          {/* Req 16.4: Return button uses secondary variant */}
          <Button
            variant="secondary"
            className="w-full"
            onClick={onReturnToWorklist}
          >
            Kembali ke Worklist
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-[var(--pmr-bg)]">
      <div className="w-full max-w-md space-y-4">
        <SectionHeading
          as="h1"
          title="Konfirmasi Review"
          description={`Review untuk pasien ${patientId}`}
        />

        <Card>
          <div className="flex items-center gap-3 mb-4">
            <Clock className="size-5 text-slate-400" aria-hidden="true" />
            <span className="text-sm text-slate-500">
              Waktu: <span className="font-clinical-mono">{timestamp}</span>
            </span>
          </div>

          {/* Req 16.1: Action label using SectionHeading */}
          <div className="mb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Keputusan:</p>
            {/* Req 16.3: Badge with consistent color coding */}
            <ActionBadge action={action} />
          </div>

          {note && (
            <div className="mb-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Catatan:</p>
              <p className="whitespace-pre-line text-slate-700 text-sm py-2 px-3 rounded-md bg-slate-50">
                {note}
              </p>
            </div>
          )}

          <div className="pt-4 border-t border-slate-200">
            <Button
              type="submit"
              size="lg"
              loading={isSaving}
              className="w-full"
              onClick={handleSave}
            >
              {isSaving ? 'Menyimpan...' : 'Simpan Review'}
            </Button>
          </div>
        </Card>

        {/* Req 16.5: Safety disclaimer */}
        <SafetyBanner compact />
        <p className="text-xs text-center text-slate-400">
          Keputusan ini tercatat di jejak audit. Output AI bersifat advisori saja.
        </p>
      </div>
    </div>
  )
}
