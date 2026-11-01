/**
 * web/src/components/SlaCountdown.tsx
 * --------------------------------------
 * Countdown SLA dengan warna merah/kuning/hijau (F-203).
 * Menampilkan sisa waktu atau status breach.
 */

import type { RiskLevel } from '../types/clinical'

interface Props {
  hoursElapsed: number | null | undefined
  tier: RiskLevel | null | undefined
  size?: 'sm' | 'md'
}

const SLA_TARGETS: Record<RiskLevel, { target: number; warning: number }> = {
  HIGH:   { target: 2,  warning: 1 },
  MEDIUM: { target: 8,  warning: 4 },
  LOW:    { target: 24, warning: 16 },
}

function formatHours(h: number): string {
  if (h < 1) return `${Math.round(h * 60)}m`
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  return mm > 0 ? `${hh}j ${mm}m` : `${hh}j`
}

export function SlaCountdown({ hoursElapsed, tier, size = 'md' }: Props) {
  if (hoursElapsed == null || !tier) {
    return <span className="text-xs text-slate-400">—</span>
  }

  const cfg = SLA_TARGETS[tier] ?? SLA_TARGETS.MEDIUM
  const remaining = cfg.target - hoursElapsed

  const textSize = size === 'sm' ? 'text-xs' : 'text-xs font-medium'

  if (hoursElapsed >= cfg.target) {
    // SLA Breach
    return (
      <span
        className={`inline-flex items-center gap-1 ${textSize} text-red-700 bg-red-50 px-1.5 py-0.5 rounded border border-red-200`}
        title={`SLA Breach: melewati ${cfg.target}j (sudah ${formatHours(hoursElapsed)})`}
        aria-label={`SLA breach: sudah ${formatHours(hoursElapsed)}`}
      >
        <span aria-hidden="true">⚠️</span>
        Breach +{formatHours(hoursElapsed - cfg.target)}
      </span>
    )
  }

  if (hoursElapsed >= cfg.warning) {
    // SLA Warning
    return (
      <span
        className={`inline-flex items-center gap-1 ${textSize} text-yellow-700 bg-yellow-50 px-1.5 py-0.5 rounded border border-yellow-200`}
        title={`SLA Warning: sisa ${formatHours(remaining)} dari target ${cfg.target}j`}
        aria-label={`SLA warning: sisa ${formatHours(remaining)}`}
      >
        <span aria-hidden="true">⏰</span>
        Sisa {formatHours(remaining)}
      </span>
    )
  }

  // OK
  return (
    <span
      className={`inline-flex items-center gap-1 ${textSize} text-slate-500`}
      title={`Sisa waktu SLA: ${formatHours(remaining)} dari target ${cfg.target}j`}
    >
      <span aria-hidden="true">⏱</span>
      {formatHours(remaining)}
    </span>
  )
}
