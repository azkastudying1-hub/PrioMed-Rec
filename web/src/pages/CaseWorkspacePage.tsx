/**
 * web/src/pages/CaseWorkspacePage.tsx
 * ---------------------------------------
 * Case Workspace v2 — satu layar telaah farmasi (F-204, F-205, F-206, F-207, F-208, F-214).
 *
 * Fitur:
 * - Header sticky: info pasien + tier badge + SLA countdown
 * - Tab: Bandingkan (BPMH vs admisi) | Temuan (diskrepansi tier) | SBAR | Riwayat
 * - Bilah aksi sticky: APPROVE/EDIT/REJECT/ESCALATE/DRAFT_REVIEW
 * - HighAlertConfirmModal sebelum APPROVE jika ada HA belum konfirmasi
 * - Undo 10 detik
 * - Label "Draf AI" pada teks SBAR
 * - Copilot AI Drawer (tombol pojok kanan bawah) — A-304
 *
 * S1: Keputusan akhir hanya dari apoteker
 * S11: Label "Prioritas Telaah Farmasi"
 * S12: AiDraftLabel pada setiap teks AI
 * ADR-02: Browser TIDAK memanggil Langflow/LLM langsung
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { TierBadge } from '../components/TierBadge'
import { SlaCountdown } from '../components/SlaCountdown'
import { AiDraftLabel } from '../components/AiDraftLabel'
import { ReviewActionBar } from '../components/ReviewActionBar'
import { HighAlertConfirmModal } from '../components/HighAlertConfirmModal'
import {
  getReviewHistoryV1,
  submitReviewV1,
  type WorklistItemV1,
  type ReviewAction,
} from '../lib/apiClient'
import type { ActionType } from '../types/clinical'
import { CopilotDrawer } from '../components/CopilotDrawer'

interface Props {
  item: WorklistItemV1
  onBack: () => void
}

type TabId = 'compare' | 'findings' | 'sbar' | 'history'

const TABS: { id: TabId; label: string }[] = [
  { id: 'compare',  label: '📋 Bandingkan' },
  { id: 'findings', label: '🔍 Temuan' },
  { id: 'sbar',     label: '📄 SBAR' },
  { id: 'history',  label: '🕐 Riwayat' },
]

const WORKFLOW_STATUS_LABELS: Record<string, string> = {
  MENUNGGU_BPMH:   'Menunggu BPMH',
  BPMH_LENGKAP:    'BPMH Lengkap',
  DALAM_ANALISIS:  'Dalam Analisis',
  MENUNGGU_TELAAH: 'Menunggu Telaah',
  DRAFT_REVIEW:    'Draft Telaah',
  SELESAI_APPROVE: 'Disetujui ✓',
  SELESAI_EDIT:    'Diedit & Disetujui ✓',
  DITOLAK:         'Ditolak',
  ESKALASI:        'Eskalasi',
}

export function CaseWorkspacePage({ item, onBack }: Props) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<TabId>('findings')
  const [showHighAlertModal, setShowHighAlertModal] = useState(false)
  const [showCopilot, setShowCopilot] = useState(false)
  const [sbarText, setSbarText] = useState({
    situation: '',
    background: '',
    assessment: '',
    recommendation: '',
  })
  const [sbarCopied, setSbarCopied] = useState(false)

  // Load review history
  const { data: historyData } = useQuery({
    queryKey: ['review-history', item.encounter_id],
    queryFn: () => getReviewHistoryV1(item.encounter_id),
  })

  // Submit review mutation
  const reviewMutation = useMutation({
    mutationFn: (payload: { action: ReviewAction; reason?: string; note?: string }) =>
      submitReviewV1(item.encounter_id, payload, {
        idempotencyKey: `${item.encounter_id}-${payload.action}-${Date.now()}`,
        ifMatch: item.row_version,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worklist'] })
      queryClient.invalidateQueries({ queryKey: ['review-history', item.encounter_id] })
    },
  })

  // High-alert items (from priority_reasons where tier=HIGH + source=rules)
  const highAlertItems = item.priority_reasons
    .filter((r) => r.source === 'rules' && r.reason.toLowerCase().includes('high-alert'))
    .map((r, i) => ({
      id: `ha-${i}`,
      drug_name: r.reason.split(':')[1]?.trim() ?? null,
      rule_type: 'high-alert',
      evidence: r.reason,
    }))

  const hasUnconfirmedHighAlert = highAlertItems.length > 0 &&
    item.workflow_status !== 'SELESAI_APPROVE' &&
    item.workflow_status !== 'SELESAI_EDIT'

  async function handleAction(action: ActionType, reason?: string, note?: string) {
    try {
      await reviewMutation.mutateAsync({
        action: action as ReviewAction,
        reason,
        note,
      })
    } catch (err) {
      alert(`Error: ${err instanceof Error ? err.message : String(err)}`)
    }
  }

  function copySbar() {
    const text = [
      'SITUATION:', sbarText.situation || '(belum diisi)',
      '\nBACKGROUND:', sbarText.background || '(belum diisi)',
      '\nASSESSMENT:', sbarText.assessment || '(belum diisi)',
      '\nRECOMMENDATION:', sbarText.recommendation || '(belum diisi)',
    ].join('\n')
    navigator.clipboard.writeText(text).then(() => {
      setSbarCopied(true)
      setTimeout(() => setSbarCopied(false), 2000)
    })
  }

  const isTerminal = ['SELESAI_APPROVE', 'SELESAI_EDIT', 'DITOLAK'].includes(item.workflow_status)

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Sticky Header */}
      <header className="sticky top-0 z-20 bg-white border-b border-slate-200 px-4 py-3 shadow-sm">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={onBack}
              className="text-sm text-blue-600 hover:text-blue-800 transition-colors"
              aria-label="Kembali ke worklist"
            >
              ← Worklist
            </button>
            <div className="h-4 w-px bg-slate-200" aria-hidden="true" />
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-semibold text-slate-800">
                  {item.patient_name ?? item.patient_id}
                </h1>
                <TierBadge tier={item.latest_tier} size="sm" />
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {item.patient_id} · {item.ward ?? '—'} · {item.dpjp_name ? `Dr. ${item.dpjp_name}` : ''}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <SlaCountdown hoursElapsed={item.sla_hours_elapsed} tier={item.latest_tier} />
            <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded">
              {WORKFLOW_STATUS_LABELS[item.workflow_status] ?? item.workflow_status}
            </span>
          </div>
        </div>

        {/* Tab nav */}
        <nav className="flex gap-1 mt-3" role="tablist" aria-label="Tab workspace">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4 pb-32">

        {/* ── Tab: BANDINGKAN ── */}
        {activeTab === 'compare' && (
          <CompareTab item={item} />
        )}

        {/* ── Tab: TEMUAN ── */}
        {activeTab === 'findings' && (
          <FindingsTab item={item} />
        )}

        {/* ── Tab: SBAR ── */}
        {activeTab === 'sbar' && (
          <div className="max-w-2xl mx-auto">
            <div className="mb-3">
              <AiDraftLabel source="template" />
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
              {(['situation', 'background', 'assessment', 'recommendation'] as const).map((field) => (
                <div key={field}>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    {field === 'situation' ? 'S — Situation' :
                     field === 'background' ? 'B — Background' :
                     field === 'assessment' ? 'A — Assessment' : 'R — Recommendation'}
                  </label>
                  <textarea
                    value={sbarText[field]}
                    onChange={(e) => setSbarText((prev) => ({ ...prev, [field]: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                    rows={field === 'recommendation' ? 4 : 3}
                    placeholder={`Isi bagian ${field.toUpperCase()} SBAR...`}
                    aria-label={`SBAR bagian ${field}`}
                  />
                </div>
              ))}

              <button
                onClick={copySbar}
                className="w-full py-2 border border-slate-300 text-sm text-slate-600 rounded-lg hover:bg-slate-50 transition-colors"
                aria-label="Salin teks SBAR untuk CPPT"
              >
                {sbarCopied ? '✓ Disalin!' : '📋 Salin SBAR untuk CPPT'}
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-400 text-center">
              Teks SBAR harus diedit dan diverifikasi oleh apoteker sebelum diserahkan ke DPJP.
            </p>
          </div>
        )}

        {/* ── Tab: RIWAYAT ── */}
        {activeTab === 'history' && (
          <HistoryTab history={(historyData?.history ?? []) as HistoryEntry[]} />
        )}
      </div>

      {/* Sticky Action Bar (hidden for terminal states) */}
      {!isTerminal && (
        <>
          <ReviewActionBar
            encounterId={item.encounter_id}
            rowVersion={item.row_version}
            hasUnconfirmedHighAlert={hasUnconfirmedHighAlert}
            highAlertCount={highAlertItems.length}
            onAction={handleAction}
            onHighAlertConfirmNeeded={() => setShowHighAlertModal(true)}
            isSubmitting={reviewMutation.isPending}
          />

          <HighAlertConfirmModal
            isOpen={showHighAlertModal}
            items={highAlertItems}
            onConfirmAll={() => {
              setShowHighAlertModal(false)
              handleAction('APPROVE')
            }}
            onCancel={() => setShowHighAlertModal(false)}
          />
        </>
      )}

      {isTerminal && (
        <div className="sticky bottom-0 bg-green-50 border-t border-green-200 px-4 py-3 text-center">
          <p className="text-sm text-green-700 font-medium">
            {WORKFLOW_STATUS_LABELS[item.workflow_status]} — Kasus ini telah diselesaikan.
          </p>
        </div>
      )}

      {/* Copilot FAB — floating action button (A-304) */}
      {!showCopilot && (
        <button
          onClick={() => setShowCopilot(true)}
          className="fixed bottom-20 right-5 z-20 flex items-center gap-2 px-4 py-3 bg-violet-600 text-white rounded-full shadow-lg hover:bg-violet-700 transition-all hover:scale-105 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2"
          aria-label="Buka AI Copilot Farmasi"
          title="AI Copilot — tanya tentang kasus ini"
        >
          <span aria-hidden="true">🤖</span>
          <span className="text-sm font-medium">Copilot</span>
        </button>
      )}

      {/* Copilot Drawer (slide-in from right) */}
      <CopilotDrawer
        encounterId={item.encounter_id}
        isOpen={showCopilot}
        onClose={() => setShowCopilot(false)}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CompareTab({ item }: { item: WorklistItemV1 }) {
  return (
    <div className="max-w-3xl mx-auto">
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="grid grid-cols-2 border-b border-slate-200">
          <div className="px-4 py-3 bg-blue-50 border-r border-slate-200">
            <p className="text-xs font-semibold text-blue-700 uppercase tracking-wider">
              Obat di Rumah (BPMH)
            </p>
          </div>
          <div className="px-4 py-3 bg-slate-50">
            <p className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
              Pesanan Admisi
            </p>
          </div>
        </div>

        {/* Placeholder rows — akan diisi dari AnalysisRun discrepancies */}
        {item.priority_reasons.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-slate-400">
            Tidak ada data perbandingan tersedia.
            <br />
            <span className="text-xs">Jalankan analisis untuk melihat perbandingan BPMH vs pesanan admisi.</span>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {item.priority_reasons.map((reason, i) => (
              <div key={i} className="grid grid-cols-2">
                <div className="px-4 py-3 text-sm text-slate-700 border-r border-slate-100">
                  <span className="text-xs text-slate-400">Alasan: </span>
                  {reason.reason}
                </div>
                <div className="px-4 py-3 text-sm text-slate-500">
                  <TierBadge tier={reason.tier as 'HIGH' | 'MEDIUM' | 'LOW'} size="sm" />
                  <span className="ml-2 text-xs">{reason.source}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const SEVERITY_TIER_LABEL: Record<number, { label: string; color: string }> = {
  1: { label: 'Tier 1 — Kritis', color: 'bg-red-100 text-red-800 border-red-200' },
  2: { label: 'Tier 2 — Perlu Perhatian', color: 'bg-yellow-100 text-yellow-800 border-yellow-200' },
  3: { label: 'Tier 3 — Informasional', color: 'bg-slate-100 text-slate-700 border-slate-200' },
}

function FindingsTab({ item }: { item: WorklistItemV1 }) {
  const [showTier3, setShowTier3] = useState(false)

  // Synthesize finding rows from priority_reasons
  const findings = item.priority_reasons.map((r, i) => ({
    id: `finding-${i}`,
    tier: r.reason.includes('Tier-1') || r.reason.includes('high-alert') || r.tier === 'HIGH' ? 1 :
          r.reason.includes('Tier-2') || r.tier === 'MEDIUM' ? 2 : 3,
    source: r.source,
    reason: r.reason,
    tier_label: r.tier,
  }))

  const tier1 = findings.filter((f) => f.tier === 1)
  const tier2 = findings.filter((f) => f.tier === 2)
  const tier3 = findings.filter((f) => f.tier === 3)

  if (findings.length === 0) {
    return (
      <div className="max-w-2xl mx-auto text-center py-12">
        <span className="text-4xl" aria-hidden="true">✅</span>
        <p className="mt-3 text-sm text-slate-500">Tidak ada diskrepansi signifikan terdeteksi.</p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Tier 1 (always visible) */}
      {tier1.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-red-700 uppercase tracking-wider mb-2">
            🔴 Tier 1 — Kritis ({tier1.length})
          </h3>
          <div className="space-y-2">
            {tier1.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </div>
        </section>
      )}

      {/* Tier 2 */}
      {tier2.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-yellow-700 uppercase tracking-wider mb-2">
            🟡 Tier 2 — Perlu Perhatian ({tier2.length})
          </h3>
          <div className="space-y-2">
            {tier2.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </div>
        </section>
      )}

      {/* Tier 3 (collapsed by default) */}
      {tier3.length > 0 && (
        <section>
          <button
            onClick={() => setShowTier3(!showTier3)}
            className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2"
            aria-expanded={showTier3}
          >
            <span>{showTier3 ? '▾' : '▸'}</span>
            🟢 Tier 3 — Informasional ({tier3.length})
          </button>
          {showTier3 && (
            <div className="space-y-2">
              {tier3.map((f) => (
                <FindingCard key={f.id} finding={f} />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function FindingCard({ finding }: {
  finding: { id: string; tier: number; source: string; reason: string; tier_label: string }
}) {
  const cfg = SEVERITY_TIER_LABEL[finding.tier] ?? SEVERITY_TIER_LABEL[2]
  return (
    <div className={`p-3 rounded-lg border ${cfg.color}`}>
      <div className="flex items-center justify-between mb-1">
        <span className={`text-xs font-medium ${cfg.color.split(' ')[1]}`}>
          {cfg.label}
        </span>
        <span className="text-xs text-slate-400 capitalize">{finding.source}</span>
      </div>
      <p className="text-sm text-slate-700">{finding.reason}</p>
    </div>
  )
}

interface HistoryEntry {
  audit_entry_id: string
  action: string
  actor_id: string | null
  actor_type: string
  note: string | null
  timestamp: string
}

const ACTION_LABEL: Record<string, { icon: string; color: string }> = {
  APPROVE:      { icon: '✓', color: 'text-green-700' },
  EDIT:         { icon: '✏️', color: 'text-blue-700' },
  REJECT:       { icon: '✗', color: 'text-slate-600' },
  ESCALATE:     { icon: '↑', color: 'text-orange-600' },
  DRAFT_REVIEW: { icon: '💾', color: 'text-slate-500' },
  CLAIM:        { icon: '🔒', color: 'text-slate-500' },
  RELEASE:      { icon: '🔓', color: 'text-slate-400' },
}

function HistoryTab({ history }: { history: HistoryEntry[] }) {
  if (!history.length) {
    return (
      <div className="max-w-2xl mx-auto text-center py-12 text-sm text-slate-400">
        Belum ada riwayat untuk kasus ini.
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto">
      <ol className="relative border-l border-slate-200 space-y-4 ml-2">
        {history.map((entry) => {
          const cfg = ACTION_LABEL[entry.action] ?? { icon: '•', color: 'text-slate-500' }
          return (
            <li key={entry.audit_entry_id} className="ml-4">
              <span className="absolute -left-2 w-4 h-4 bg-white border border-slate-200 rounded-full flex items-center justify-center text-xs">
                {cfg.icon}
              </span>
              <div className="bg-white rounded-lg border border-slate-200 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-semibold ${cfg.color}`}>{entry.action}</span>
                  <span className="text-xs text-slate-400">
                    {entry.timestamp?.replace('T', ' ').slice(0, 16)}
                  </span>
                </div>
                <p className="text-xs text-slate-500">
                  {entry.actor_type === 'agent_via_mcp' ? '🤖 MCP Agent' : `👤 ${entry.actor_id ?? 'sistem'}`}
                </p>
                {entry.note && (
                  <p className="text-sm text-slate-700 mt-1">{entry.note}</p>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
