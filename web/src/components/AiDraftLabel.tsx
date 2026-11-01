/**
 * web/src/components/AiDraftLabel.tsx
 * -------------------------------------
 * Label permanen "Draf AI - wajib diverifikasi apoteker" (S12, F-207).
 * WAJIB ditampilkan pada setiap teks yang dihasilkan AI/LLM.
 */

import { Sparkles } from 'lucide-react'

interface Props {
  source?: string  // langflow | llm | template
  className?: string
}

export function AiDraftLabel({ source, className = '' }: Props) {
  const sourceLabel = source === 'template'
    ? 'Draf Otomatis (Template)'
    : source === 'langflow' || source === 'llm'
      ? 'Draf AI'
      : 'Draf AI'

  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-1 bg-amber-50 border border-amber-300 rounded text-xs text-amber-800 ${className}`}
      role="note"
      aria-label="Peringatan: teks ini adalah draf AI yang memerlukan verifikasi apoteker"
    >
      <Sparkles className="size-3.5 shrink-0" aria-hidden="true" />
      <span>
        <strong>{sourceLabel}</strong> — wajib diverifikasi apoteker sebelum digunakan
      </span>
    </div>
  )
}
