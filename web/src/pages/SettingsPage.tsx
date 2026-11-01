/**
 * web/src/pages/SettingsPage.tsx
 *
 * Task 13.1: Migrated from legacy components to uiux/ design system.
 * Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
 */

import { useState } from "react"
import {
  CheckCircle2,
  FileUp,
  FlaskConical,
  Pencil,
  Save,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react"
import type {
  HighAlertMedication,
  ViewState,
  WardCapacity,
} from "../types/clinical"
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  Skeleton,
} from "../uiux/primitives"
import { SectionHeading } from "../uiux/clinical"

export function SettingsPage({
  highAlerts,
  capacities,
  viewState,
  onViewState,
  onHighAlerts,
  onCapacities,
}: {
  highAlerts: HighAlertMedication[]
  capacities: WardCapacity[]
  viewState: ViewState
  onViewState: (state: ViewState) => void
  onHighAlerts: (items: HighAlertMedication[]) => void
  onCapacities: (items: WardCapacity[]) => void
}) {
  const [editItem, setEditItem] = useState<HighAlertMedication | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [imported, setImported] = useState(false)

  // Req 14.1: Skeleton for loading state
  if (viewState === "loading")
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card className="space-y-4">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </Card>
        <Card className="space-y-4">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </Card>
      </div>
    )

  if (viewState === "error")
    return (
      <ErrorState
        description="Pengaturan tidak dapat dimuat"
        onRetry={() => onViewState("ready")}
      />
    )

  if (viewState === "empty")
    return (
      <EmptyState
        title="Daftar high-alert belum dikonfigurasi"
        description="Impor atau tambahkan daftar obat high-alert institusi sebelum dipakai untuk penandaan."
        action={
          <Button onClick={() => onViewState("ready")}>
            Gunakan data demo
          </Button>
        }
      />
    )

  return (
    <div className="space-y-6">
      {/* Req 14.2: SectionHeading from clinical.tsx */}
      <SectionHeading
        as="h1"
        title="Pengaturan"
        description="Konfigurasi prototype lokal. Perubahan aktif selama sesi browser ini."
      />

      <Card className="border-l-4 border-l-cyan-500">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="rounded-md bg-cyan-100 p-2 text-cyan-900">
              <FlaskConical className="size-5" aria-hidden="true" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Mode data: sintetis</h3>
              <p className="mt-1 text-sm text-slate-600">
                Tidak ada data pasien nyata. Semua perubahan disimpan hanya di
                memori browser dan reset saat halaman dimuat ulang.
              </p>
            </div>
          </div>
          <Badge tone="teal">
            <ShieldCheck className="size-3" aria-hidden="true" /> Prototype lokal
          </Badge>
        </div>
      </Card>

      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <SectionHeading
            as="h2"
            title="Daftar obat high-alert"
            description="Daftar institusi demo yang dipakai untuk indikator pada Worklist."
          />
          <Button
            variant="secondary"
            onClick={() => setImportOpen(true)}
          >
            <FileUp className="size-4" aria-hidden="true" />
            Impor daftar
          </Button>
        </div>
        <Card className="overflow-hidden p-0">
          <div className="divide-y divide-slate-200 md:hidden">
            {highAlerts.map((item) => (
              <div key={item.id} className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-bold text-slate-950">{item.name}</p>
                    <p className="mt-1 text-sm text-slate-600">{item.category}</p>
                  </div>
                  {/* Req 14.6: Icons on verification status badges (color + text) */}
                  <Badge
                    tone={item.verified ? "success" : "warning"}
                    icon={
                      item.verified
                        ? <CheckCircle2 className="size-3.5" aria-hidden="true" />
                        : <TriangleAlert className="size-3.5" aria-hidden="true" />
                    }
                  >
                    {item.verified ? "Terverifikasi" : "Perlu verifikasi"}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-3 rounded-md bg-slate-50 p-3 text-xs">
                  <div>
                    <p className="font-bold uppercase text-slate-500">Sumber</p>
                    <p className="mt-1 text-slate-700">{item.source}</p>
                  </div>
                  <div>
                    <p className="font-bold uppercase text-slate-500">Versi</p>
                    <p className="mt-1 font-clinical-mono text-slate-700">{item.version}</p>
                  </div>
                </div>
                <Button
                  className="w-full"
                  size="sm"
                  variant="secondary"
                  onClick={() => setEditItem(item)}
                >
                  <Pencil className="size-4" aria-hidden="true" />
                  Edit obat
                </Button>
              </div>
            ))}
          </div>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <thead className="bg-slate-50 text-[0.6875rem] uppercase tracking-wide text-slate-500">
                <tr>
                  {["Nama obat", "Kategori", "Sumber", "Versi", "Status verifikasi", ""].map((col) => (
                    <th key={col} className="px-4 py-3 font-bold">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {highAlerts.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-4 font-bold">{item.name}</td>
                    <td className="px-4 py-4">{item.category}</td>
                    <td className="px-4 py-4 text-slate-600">{item.source}</td>
                    <td className="px-4 py-4 font-clinical-mono text-xs">{item.version}</td>
                    <td className="px-4 py-4">
                      {/* Req 14.6: Icon + text label for verification status */}
                      <Badge
                        tone={item.verified ? "success" : "warning"}
                        icon={
                          item.verified
                            ? <CheckCircle2 className="size-3.5" aria-hidden="true" />
                            : <TriangleAlert className="size-3.5" aria-hidden="true" />
                        }
                      >
                        {item.verified ? "Terverifikasi" : "Perlu verifikasi"}
                      </Badge>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setEditItem(item)}
                      >
                        <Pencil className="size-4" aria-hidden="true" />
                        Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      <section className="space-y-3">
        <SectionHeading
          as="h2"
          title="Kapasitas apoteker per bangsal"
          description="Perubahan kapasitas langsung diperbarui pada KPI Worklist."
        />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {capacities.map((item) => (
            <Card key={item.ward}>
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900">{item.ward}</h3>
                <Badge tone="info">
                  {item.allocated}/{item.capacity} teralokasi
                </Badge>
              </div>
              {/* Req 14.3: htmlFor/id association */}
              <Field
                className="mt-4"
                label="Kapasitas review/hari"
                htmlFor={`capacity-${item.ward}`}
                required
              >
                <Input
                  id={`capacity-${item.ward}`}
                  type="number"
                  min={1}
                  value={item.capacity}
                  onChange={(event) =>
                    onCapacities(
                      capacities.map((entry) =>
                        entry.ward === item.ward
                          ? { ...entry, capacity: Number(event.target.value) }
                          : entry,
                      ),
                    )
                  }
                />
              </Field>
            </Card>
          ))}
        </div>
      </section>

      {/* Req 14.5: Modal from primitives with Escape-to-close, scroll-lock, and focus management */}
      <Modal
        open={Boolean(editItem)}
        title="Edit obat high-alert"
        onClose={() => setEditItem(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditItem(null)}>
              Batal
            </Button>
            <Button
              onClick={() => {
                if (editItem)
                  onHighAlerts(
                    highAlerts.map((item) =>
                      item.id === editItem.id ? editItem : item,
                    ),
                  )
                setEditItem(null)
              }}
            >
              <Save className="size-4" aria-hidden="true" />
              Simpan perubahan
            </Button>
          </>
        }
      >
        {editItem && (
          <div className="space-y-4">
            {/* Req 14.3: htmlFor/id associations */}
            <Field label="Nama obat" htmlFor="edit-name" required>
              <Input
                id="edit-name"
                value={editItem.name}
                onChange={(event) =>
                  setEditItem({ ...editItem, name: event.target.value })
                }
              />
            </Field>
            <Field label="Kategori" htmlFor="edit-category" required>
              <Input
                id="edit-category"
                value={editItem.category}
                onChange={(event) =>
                  setEditItem({ ...editItem, category: event.target.value })
                }
              />
            </Field>
            <Field label="Sumber" htmlFor="edit-source" required>
              <Input
                id="edit-source"
                value={editItem.source}
                onChange={(event) =>
                  setEditItem({ ...editItem, source: event.target.value })
                }
              />
            </Field>
            <Button
              variant={editItem.verified ? "success" : "secondary"}
              onClick={() =>
                setEditItem({ ...editItem, verified: !editItem.verified })
              }
            >
              <CheckCircle2 className="size-4" aria-hidden="true" />
              {editItem.verified ? "Terverifikasi" : "Tandai terverifikasi"}
            </Button>
          </div>
        )}
      </Modal>

      <Modal
        open={importOpen}
        title="Impor daftar high-alert"
        onClose={() => {
          setImportOpen(false)
          setImported(false)
        }}
        footer={
          <Button
            onClick={() => {
              setImported(true)
            }}
          >
            <FileUp className="size-4" aria-hidden="true" />
            Validasi file demo
          </Button>
        }
      >
        <p className="text-sm text-slate-600">
          Pilih CSV atau XLSX. Prototype hanya memvalidasi nama file dan tidak
          mengunggah data ke server.
        </p>
        <Field label="Pilih file" htmlFor="import-file" className="mt-4">
          <Input id="import-file" type="file" accept=".csv,.xlsx" />
        </Field>
        {imported && (
          <div className="mt-4 rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-900">
            Validasi simulasi selesai. Tidak ada file yang dikirim atau disimpan.
          </div>
        )}
      </Modal>
    </div>
  )
}
