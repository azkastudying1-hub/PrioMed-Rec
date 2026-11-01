/**
 * web/src/pages/WorklistPage.tsx
 * ----------------------------
 * Halaman worklist prio-rec dengan desain yang dioptimalkan untuk scan apoteker.
 * - Maksimal 5 kolom utama
 * - Badge warna untuk priority
 * - Alasan singkat (bukan SHAP penuh)
 * - Tombol utama satu: Review
 * - Filter: All, HIGH, MEDIUM, LOW, High Alert, SLA Breached
 */

import { useMemo, useState } from "react"
import { ChevronRight, Search, X } from "lucide-react"
import type { Patient } from "../types/clinical"
import { Button, Card, EmptyState, Select } from "../components/ui"
import { PriorityBadge, StatusBadge } from "../components/clinical"

export function WorklistPage({
  patients,
  onSelectPatient,
  onNavigate,
}: {
  patients: Patient[]
  onSelectPatient: (patient: Patient) => void
  onNavigate: (page: string) => void
}) {
  const [search, setSearch] = useState("")
  const [priority, setPriority] = useState("All")

  const filtered = useMemo(
    () =>
      patients
        .filter((patient) =>
          `${patient.id} ${patient.ward}`
            .toLowerCase()
            .includes(search.toLowerCase()),
        )
        .filter(
          (patient) => priority === "All" || patient.riskLevel === priority,
        )
        .sort((a, b) => b.riskScore - a.riskScore),
    [patients, priority, search],
  )

  const reset = () => {
    setSearch("")
    setPriority("All")
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-800">
            PrioMed-Rec | Admission MedRec Worklist
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Urutan review berdasarkan predicted discrepancy likelihood. Ini bukan
            urutan kegawatan medis.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Select
            aria-label="Filter prioritas"
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
            options={["All", "HIGH", "MEDIUM", "LOW", "High Alert", "SLA Breached"].map(
              (item) => ({
                value: item,
                label: item === "All" ? "Semua" : item === "High Alert" ? "High Alert" : `Prioritas ${item}`,
              }),
            )}
          />
          <Button
            variant="ghost"
            size="sm"
            icon={<X className="size-4" />}
            onClick={reset}
          >
            Reset
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <h3 className="text-sm font-semibold text-slate-600">Total pasien</h3>
          <p className="text-2xl font-bold text-slate-900">{patients.length}</p>
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-slate-600">Prioritas HIGH</h3>
          <p className="text-2xl font-bold text-slate-900">
            {patients.filter((item) => item.riskLevel === "HIGH").length}
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-slate-600">High Alert</h3>
          <p className="text-2xl font-bold text-slate-900">
            {patients.filter((item) => item.highAlertCount > 0).length}
          </p>
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-slate-600">SLA Breached</h3>
          <p className="text-2xl font-bold text-slate-900">
            {patients.filter((item) => item.highAlertCount > 0).length}
          </p>
        </Card>
      </div>

      {/* Search */}
      <Card className="overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <p className="text-sm font-bold text-slate-800">
            Pasien admisi terurut berdasarkan risiko
          </p>
          <p className="text-xs text-slate-500">
            {filtered.length} dari {patients.length} pasien
          </p>
        </div>

        <div className="p-4">
          <label className="relative block">
            <span className="sr-only">Cari pasien atau ID admisi</span>
            <Search className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400" />
            <input
              className="w-full pl-9 min-h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
              placeholder="Cari pasien atau ID admisi"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        </div>

        {/* Worklist Grid - maksimal 5 "kolom" utama */}
        {filtered.length === 0 ? (
          <EmptyState
            title="Belum ada pasien yang memerlukan review"
            description="Worklist akan terisi ketika data admisi tersedia. Tidak ada pasien high-alert saat ini."
            action={
              <Button onClick={() => onNavigate("analysis")}>
                Tampilkan data demo
              </Button>
            }
          />
        ) : (
          <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
            {filtered.map((patient) => (
              <div
                key={patient.id}
                className="group border rounded-md bg-slate-50 p-3 hover:bg-slate-50/80 transition-colors cursor-pointer"
                onClick={() => onSelectPatient(patient)}
              >
                {/* Patient info - 3 kolom utama */}
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-slate-950 text-sm line-clamp-1">
                    {patient.id}
                  </p>
                  <p className="text-[0.8125rem] text-slate-500 line-clamp-1">
                    {patient.ward}
                  </p>
                </div>

                {/* Risk score & priority */}
                <div className="flex items-center gap-2 mt-2">
                  <span className="font-mono text-base font-bold text-slate-900">
                    {patient.riskScore.toFixed(2)}
                  </span>
                  <PriorityBadge
                    level={patient.riskLevel}
                    compact
                  />
                </div>

                {/* Waiting time */}
                <p className="text-[0.75rem] text-slate-500 line-clamp-1 mt-2">
                  Admitted: {patient.admittedAt}
                </p>

                {/* Reasons - 1 kolom, singkat */}
                <p className="text-[0.75rem] text-slate-500 line-clamp-1 mt-2">
                  {patient.topReason}
                </p>

                {/* Review button - satu tombol utama */}
                <Button
                  size="sm"
                  className="w-full mt-3"
                  onClick={() => onSelectPatient(patient)}
                >
                  Review
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}