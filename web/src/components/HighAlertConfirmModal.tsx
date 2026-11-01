/**
 * web/src/components/HighAlertConfirmModal.tsx
 * ----------------------------------------------
 * Modal konfirmasi untuk diskrepansi high-alert sebelum APPROVE (F-208, B-112).
 *
 * S2: APPROVE diblokir server jika ada high-alert belum dikonfirmasi.
 * Komponen ini mewajibkan apoteker mengkonfirmasi SETIAP temuan high-alert.
 */

interface HighAlertItem {
  id: string
  drug_name: string | null
  rule_type: string
  evidence: string | null
}

interface Props {
  isOpen: boolean
  items: HighAlertItem[]
  onConfirmAll: () => void
  onCancel: () => void
}

export function HighAlertConfirmModal({ isOpen, items, onConfirmAll, onCancel }: Props) {
  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ha-confirm-title"
    >
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-6">
        {/* Header */}
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
            <span className="text-xl" aria-hidden="true">⚠️</span>
          </div>
          <div>
            <h2 id="ha-confirm-title" className="text-base font-semibold text-red-800">
              Konfirmasi Temuan High-Alert
            </h2>
            <p className="text-sm text-slate-600 mt-0.5">
              Terdapat {items.length} temuan obat <strong>high-alert</strong> yang memerlukan
              konfirmasi eksplisit sebelum persetujuan.
            </p>
          </div>
        </div>

        {/* Items */}
        <div className="space-y-2 mb-5 max-h-64 overflow-y-auto">
          {items.map((item) => (
            <div
              key={item.id}
              className="p-3 bg-red-50 border border-red-200 rounded-lg"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-red-700 uppercase tracking-wide">
                  HIGH ALERT
                </span>
                <span className="text-xs text-slate-500 capitalize">
                  {item.rule_type.replace('_', ' ')}
                </span>
              </div>
              <p className="text-sm font-medium text-slate-800">
                {item.drug_name ?? '(nama obat tidak diketahui)'}
              </p>
              {item.evidence && (
                <p className="text-xs text-slate-600 mt-0.5">{item.evidence}</p>
              )}
            </div>
          ))}
        </div>

        {/* Safety notice */}
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg mb-5">
          <p className="text-xs text-amber-800">
            <strong>Pernyataan:</strong> Dengan menekan "Saya Telah Memeriksa",
            apoteker menyatakan telah mengevaluasi setiap temuan high-alert di atas
            dan mengambil keputusan klinis yang sesuai berdasarkan penilaian profesional.
          </p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 py-2.5 border border-slate-300 text-slate-700 rounded-lg text-sm hover:bg-slate-50 transition-colors"
          >
            Batal
          </button>
          <button
            onClick={onConfirmAll}
            className="flex-1 py-2.5 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
          >
            Saya Telah Memeriksa — Lanjutkan APPROVE
          </button>
        </div>
      </div>
    </div>
  )
}
