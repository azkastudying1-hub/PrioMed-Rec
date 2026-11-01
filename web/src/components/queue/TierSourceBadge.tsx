/**
 * web/src/components/queue/TierSourceBadge.tsx
 * --------------------------------------------
 * Badge tier prioritas antrean dengan asal sumber penentu (RULE vs ML vs SLA).
 *
 * Contoh:
 *   HIGH (ATURAN)  — dipicu temuan aturan klinis (lantai tidak boleh turun)
 *   HIGH (ML)      — dipicu prediksi model Machine Learning
 *   MED (SLA)      — dipromosikan karena penuaan waktu tunggu
 */

import React from 'react'
import type { QueueTier, TierSource } from '../../api/queue'

interface Props {
  tier: QueueTier
  source?: TierSource
  size?: 'sm' | 'md' | 'lg'
}

const TIER_COLORS: Record<QueueTier, { bg: string; text: string; border: string }> = {
  HIGH: {
    bg: 'bg-red-50 text-red-700 border-red-200',
    text: 'text-red-700',
    border: 'border-red-200',
  },
  MEDIUM: {
    bg: 'bg-amber-50 text-amber-700 border-amber-200',
    text: 'text-amber-700',
    border: 'border-amber-200',
  },
  LOW: {
    bg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    text: 'text-emerald-700',
    border: 'border-emerald-200',
  },
}

const SOURCE_LABELS: Record<TierSource, { label: string; badgeBg: string }> = {
  RULE: { label: 'ATURAN', badgeBg: 'bg-purple-100 text-purple-800 border-purple-300' },
  ML:   { label: 'ML', badgeBg: 'bg-blue-100 text-blue-800 border-blue-300' },
  SLA:  { label: 'SLA', badgeBg: 'bg-orange-100 text-orange-800 border-orange-300' },
}

export function TierSourceBadge({ tier, source = 'ML', size = 'md' }: Props) {
  const tierStyle = TIER_COLORS[tier] || TIER_COLORS.MEDIUM
  const sourceInfo = SOURCE_LABELS[source] || SOURCE_LABELS.ML

  const padding = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-0.5 text-xs font-medium'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border ${tierStyle.bg} ${padding}`}>
      <span className="font-semibold">{tier}</span>
      <span
        className={`px-1 py-0.2 rounded text-[10px] font-bold border tracking-wider ${sourceInfo.badgeBg}`}
        title={`Sumber penentuan tier: ${sourceInfo.label}`}
      >
        {sourceInfo.label}
      </span>
    </span>
  )
}
