/**
 * web/src/pages/AuditLogPageV2.tsx
 * ----------------------------------
 * Audit Log v2 dengan tombol verifikasi rantai hash (F-212).
 *
 * Task 10.2: Migrated from legacy/inline styles to uiux/ design system.
 * Requirement: 8.8
 */

import { useState } from 'react'
import { CheckCircle2, Pencil, ShieldCheck, XCircle } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { verifyAuditChain, type AuditVerifyResult } from '../lib/apiClient'
import { useAuthStore } from '../lib/auth'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  InlineAlert,
  Skeleton,
} from '../uiux/primitives'
import { SectionHeading } from '../uiux/clinical'

interface AuditEntry {
  id: string
  patientId: string
  action: string
  pharmacist: string
  timestamp: string
  note: string
  source: string
}

interface Props {
  entries: AuditEntry[]
  viewState: 'ready' | 'loading' | 'empty' | 'error'
  onViewState: (state: 'ready' | 'loading' | 'empty' | 'error') => void
}

// Req 8.8: Replace ACTION_COLORS map with Badge tones + icons
function ActionBadge({ action }: { action: string }) {
  switch (action) {
    case 'APPROVE':
      return (
        <Badge tone="success" icon={<CheckCircle2 className="size-3.5" aria-hidden="true" />}>
          APPROVE
        </Badge>
      )
    case 'EDIT':
      return (
        <Badge tone="info" icon={<Pencil className="size-3.5" aria-hidden="true" />}>
          EDIT
        </Badge>
      )
    case 'REJECT':
      return (
        <Badge tone="danger" icon={<XCircle className="size-3.5" aria-hidden="true" />}>
          REJECT
        </Badge>
      )
    case 'ESCALATE':
      return <Badge tone="warning">{action}</Badge>
    case 'DRAFT_REVIEW':
      return <Badge tone="neutral">{action}</Badge>
    case 'CLAIM':
      return <Badge tone="info">{action}</Badge>
    default:
      return <Badge tone="neutral">{action}</Badge>
  }
}

export function AuditLogPageV2({ entries, viewState, onViewState }: Props) {
  const { user } = useAuthStore()
  const isAdminOrAuditor = user?.role === 'ADMIN' || user?.role === 'AUDITOR'

  const [verifyResult, setVerifyResult] = useState<AuditVerifyResult | null>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)

  // Preserve verifyAuditChain mutation (no API change)
  const verifyMutation = useMutation({
    mutationFn: () => verifyAuditChain(true),
    onSuccess: (data) => {
      setVerifyResult(data)
      setVerifyError(null)
    },
    onError: (err) => {
      setVerifyError(err instanceof Error ? err.message : 'Verifikasi gagal.')
      setVerifyResult(null)
    },
  })

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <SectionHeading
          as="h1"
          title="Log Audit"
          description={`Jejak audit append-only · ${entries.length} entri ditampilkan`}
        />

        {/* Verify Chain button — only for ADMIN/AUDITOR */}
        {isAdminOrAuditor && (
          <Button
            variant="secondary"
            size="sm"
            loading={verifyMutation.isPending}
            onClick={() => verifyMutation.mutate()}
            aria-label="Verifikasi integritas rantai hash audit"
          >
            <ShieldCheck className="size-4" aria-hidden="true" />
            Verifikasi Rantai Hash
          </Button>
        )}
      </div>

      {/* Req 8.8: Verify result with InlineAlert */}
      {verifyResult && (
        <InlineAlert
          tone={verifyResult.valid ? 'success' : 'danger'}
          title={verifyResult.valid ? 'Rantai Hash Valid' : 'Rantai Hash Rusak'}
        >
          {verifyResult.message}
          {verifyResult.first_broken_seq != null && (
            <span className="ml-2 text-xs">(rusak mulai seq #{verifyResult.first_broken_seq})</span>
          )}
          <span className="ml-2 text-xs text-slate-500">{verifyResult.count} entri diperiksa</span>
        </InlineAlert>
      )}

      {verifyError && (
        <InlineAlert tone="danger" title="Verifikasi gagal">
          {verifyError}
        </InlineAlert>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {/* Req 8.8: Skeleton for loading */}
        {viewState === 'loading' && (
          <Card className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="w-28 h-4" />
                <Skeleton className="w-16 h-5 rounded-full" />
                <Skeleton className="h-4 flex-1" />
              </div>
            ))}
          </Card>
        )}

        {/* Req 8.8: ErrorState for error */}
        {viewState === 'error' && (
          <ErrorState
            description="Gagal memuat log audit."
            onRetry={() => onViewState('ready')}
          />
        )}

        {/* Req 8.8: EmptyState for empty */}
        {viewState !== 'loading' && viewState !== 'error' && entries.length === 0 && (
          <EmptyState
            title="Belum ada entri audit"
            description="Keputusan apoteker akan muncul di sini setelah disimpan."
          />
        )}

        {viewState !== 'loading' && entries.length > 0 && (
          <Card className="overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label="Log audit telaah farmasi">
                <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                  <tr>
                    <th scope="col" className="px-4 py-2 text-left text-xs font-medium text-slate-500">Waktu</th>
                    <th scope="col" className="px-4 py-2 text-left text-xs font-medium text-slate-500">Aksi</th>
                    <th scope="col" className="px-4 py-2 text-left text-xs font-medium text-slate-500">Pasien</th>
                    <th scope="col" className="px-4 py-2 text-left text-xs font-medium text-slate-500">Apoteker</th>
                    <th scope="col" className="px-4 py-2 text-left text-xs font-medium text-slate-500">Catatan</th>
                    <th scope="col" className="px-4 py-2 text-left text-xs font-medium text-slate-500">Sumber</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      {/* Req 8.8: font-clinical-mono for timestamps */}
                      <td className="px-4 py-3 font-clinical-mono text-xs text-slate-500 whitespace-nowrap">
                        {entry.timestamp}
                      </td>
                      {/* Req 8.8: Badge with tone + icon for actions */}
                      <td className="px-4 py-3">
                        <ActionBadge action={entry.action} />
                      </td>
                      <td className="px-4 py-3 text-slate-700 font-clinical-mono text-xs">
                        {entry.patientId}
                      </td>
                      <td className="px-4 py-3 text-slate-700 text-xs">
                        {entry.pharmacist}
                      </td>
                      <td className="px-4 py-3 text-slate-600 text-xs max-w-xs truncate">
                        {entry.note || '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-xs">
                        {entry.source}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
