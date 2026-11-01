/**
 * web/src/components/TierBadge.tsx
 * ----------------------------------
 * Badge warna + ikon + teks untuk tier prioritas telaah farmasi (F-203).
 *
 * S11: Label "Prioritas Telaah Farmasi" — BUKAN "risiko pasien" atau "triase"
 */

import type { RiskLevel } from '../types/clinical'

interface Props {
  tier: RiskLevel | null | undefined
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

const TIER_CONFIG: Record<RiskLevel, {
  bg: string; text: string; border: string; icon: string; label: string
}> = {
  HIGH: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    border: 'border-red-300',
    icon: '🔴',
    label: 'Prioritas Tinggi',
  },
  MEDIUM: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-800',
    border: 'border-yellow-300',
    icon: '🟡',
    label: 'Prioritas Sedang',
  },
  LOW: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-300',
    icon: '🟢',
    label: 'Prioritas Rendah',
  },
}

const SIZE_CLASSES = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2 py-1 text-xs font-medium',
  lg: 'px-3 py-1.5 text-sm font-semibold',
}

export function TierBadge({ tier, size = 'md', showLabel = false }: Props) {
  if (!tier) {
    return (
      <span className={`inline-flex items-center gap-1 rounded border ${SIZE_CLASSES[size]} bg-slate-100 text-slate-500 border-slate-200`}>
        —
      </span>
    )
  }

  const cfg = TIER_CONFIG[tier]

  return (
    <span
      className={`inline-flex items-center gap-1 rounded border ${SIZE_CLASSES[size]} ${cfg.bg} ${cfg.text} ${cfg.border}`}
      title={cfg.label}
      aria-label={`Prioritas telaah farmasi: ${cfg.label}`}
    >
      <span aria-hidden="true">{cfg.icon}</span>
      {showLabel ? cfg.label : tier}
    </span>
  )
}
