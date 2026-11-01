/**
 * web/src/components/queue/AgingStrip.tsx
 * ---------------------------------------
 * Indikator visual usia tunggu pasien vs target SLA.
 * Garis tepi/bar vertikal warna-warni yang menunjukkan urgensi penuaan (aging).
 *
 * Hijau  : < 50% SLA
 * Kuning : 50% - 75% SLA
 * Oranye : 75% - 100% SLA (warning)
 * Merah  : >= 100% SLA (breach)
 */

import React from 'react'
import type { QueueTier } from '../../api/queue'

interface Props {
  hoursElapsed: number | null | undefined
  tier: QueueTier
  className?: string
}

const SLA_TARGETS: Record<QueueTier, number> = {
  HIGH: 2,     // 2 jam
  MEDIUM: 8,   // 8 jam
  LOW: 24,     // 24 jam
}

export function AgingStrip({ hoursElapsed, tier, className = '' }: Props) {
  const elapsed = hoursElapsed ?? 0
  const target = SLA_TARGETS[tier] ?? 8
  const ratio = target > 0 ? elapsed / target : 0

  let colorClass = 'bg-emerald-500'
  let label = 'SLA Aman'

  if (ratio >= 1.0) {
    colorClass = 'bg-red-600 animate-pulse'
    label = 'SLA Lewat (Breach)'
  } else if (ratio >= 0.75) {
    colorClass = 'bg-amber-500'
    label = 'SLA Kritis (>75%)'
  } else if (ratio >= 0.5) {
    colorClass = 'bg-yellow-400'
    label = 'SLA Waspada (>50%)'
  }

  return (
    <div
      className={`w-1.5 h-full rounded-full self-stretch shrink-0 ${colorClass} ${className}`}
      title={`${label}: ${elapsed.toFixed(1)}j / ${target}j target`}
      aria-label={`${label}`}
    />
  )
}
