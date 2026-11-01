/**
 * web/src/pages/AuditLogPage.tsx
 *
 * Task 10.1: Migrated from legacy components to uiux/ design system.
 * Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7
 */

import { useMemo, useState } from "react"
import { CheckCircle2, Pencil, Search, X, XCircle } from "lucide-react"
import type { AuditEntry, ViewState } from "../types/clinical"
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Select,
  Skeleton,
  Input,
} from "../uiux/primitives"
import { SectionHeading } from "../uiux/clinical"

// Req 8.2: Action badges with icon + text + color
function ActionBadge({ action }: { action: string }) {
  switch (action) {
    case "APPROVE":
      return (
        <Badge tone="success" icon={<CheckCircle2 className="size-3.5" aria-hidden="true" />}>
          APPROVE
        </Badge>
      )
    case "REJECT":
      return (
        <Badge tone="danger" icon={<XCircle className="size-3.5" aria-hidden="true" />}>
          REJECT
        </Badge>
      )
    case "EDIT":
      return (
        <Badge tone="info" icon={<Pencil className="size-3.5" aria-hidden="true" />}>
          EDIT
        </Badge>
      )
    default:
      return <Badge tone="neutral">{action}</Badge>
  }
}

export function AuditLogPage({
  entries,
  viewState,
  onViewState,
}: {
  entries: AuditEntry[]
  viewState: ViewState
  onViewState: (state: ViewState) => void
}) {
  const [search, setSearch] = useState("")
  const [action, setAction] = useState("Semua")

  const filtered = useMemo(
    () =>
      entries
        .filter((item) => action === "Semua" || item.action === action)
        .filter((item) =>
          `${item.patientId} ${item.pharmacist}`
            .toLowerCase()
            .includes(search.toLowerCase()),
        ),
    [action, entries, search],
  )

  const reset = () => {
    setSearch("")
    setAction("Semua")
  }

  // Req 8.3: Skeleton for loading state
  if (viewState === "loading")
    return (
      <div className="space-y-5">
        <SectionHeading as="h1" title="Audit Log" />
        <Card className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <Skeleton className="w-28 h-4" />
              <Skeleton className="w-16 h-5 rounded-full" />
              <Skeleton className="h-4 flex-1" />
              <Skeleton className="h-4 w-24" />
            </div>
          ))}
        </Card>
      </div>
    )

  if (viewState === "error")
    return (
      <ErrorState
        description="Audit Log tidak dapat dimuat."
        onRetry={() => onViewState("ready")}
      />
    )

  // Req 8.4: EmptyState from primitives for empty state
  if (viewState === "empty")
    return (
      <EmptyState
        title="Belum ada aktivitas tercatat"
        description="Keputusan APPROVE, REJECT, atau EDIT dari apoteker akan muncul di sini."
        action={
          <Button onClick={() => onViewState("ready")}>
            Tampilkan audit demo
          </Button>
        }
      />
    )

  return (
    <div className="space-y-5">
      {/* Req 8.1: SectionHeading from clinical.tsx */}
      <SectionHeading
        as="h1"
        title="Audit Log"
        description="Jejak keputusan apoteker yang dapat ditelusuri. Output sistem tidak dicatat sebagai keputusan final."
      />

      <Card padded={false} className="p-3">
        <div className="grid gap-3 lg:grid-cols-[1fr_12rem_11rem_11rem_auto]">
          <label className="relative">
            <span className="sr-only">Cari pasien atau apoteker</span>
            <Search className="pointer-events-none absolute left-3 top-3 size-4 text-slate-400" />
            <Input
              className="pl-9"
              placeholder="Cari pasien atau apoteker"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <Input aria-label="Tanggal awal" type="date" />
          <Input aria-label="Tanggal akhir" type="date" />
          {/* Req 8.7: Convert legacy Select options prop to children <option> elements */}
          <Select
            aria-label="Jenis aksi"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          >
            <option value="Semua">Semua aksi</option>
            <option value="APPROVE">APPROVE</option>
            <option value="REJECT">REJECT</option>
            <option value="EDIT">EDIT</option>
          </Select>
          <Button
            variant="ghost"
            onClick={reset}
          >
            <X className="size-4" aria-hidden="true" />
            Reset
          </Button>
        </div>
      </Card>

      {/* Req 8.4: EmptyState with reset filter action when no entries match */}
      {filtered.length === 0 ? (
        <EmptyState
          title="Tidak ada audit sesuai filter"
          description="Ubah rentang tanggal, jenis aksi, atau kata pencarian."
          action={
            <Button variant="secondary" onClick={reset}>
              Reset filter
            </Button>
          }
        />
      ) : (
        <Card className="overflow-hidden p-0">
          {/* Mobile card layout */}
          <div className="divide-y divide-slate-200 md:hidden">
            {filtered.map((item) => (
              <div key={item.id} className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-bold text-slate-950">{item.patientId}</p>
                    {/* Req 8.6: font-clinical-mono for timestamps */}
                    <p className="mt-1 font-clinical-mono text-xs text-slate-500">{item.timestamp}</p>
                  </div>
                  {/* Req 8.2: Action badges with icon + color */}
                  <ActionBadge action={item.action} />
                </div>
                <div className="grid grid-cols-2 gap-3 rounded-md bg-slate-50 p-3 text-xs">
                  <div>
                    <p className="font-bold uppercase text-slate-500">Apoteker</p>
                    <p className="mt-1 font-semibold text-slate-800">{item.pharmacist}</p>
                  </div>
                  <div>
                    <p className="font-bold uppercase text-slate-500">Sumber</p>
                    <p className="mt-1 text-slate-700">{item.source}</p>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-bold uppercase text-slate-500">Catatan</p>
                  <p className="mt-1 text-sm leading-5 text-slate-700">{item.note || "Tidak ada catatan"}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Desktop table layout */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[58rem] text-left text-sm">
              <thead className="bg-slate-50 text-[0.6875rem] uppercase tracking-wide text-slate-500">
                <tr>
                  {["Waktu", "Pasien", "Aksi", "Apoteker", "Catatan", "Sumber"].map((col) => (
                    <th key={col} className="px-4 py-3 font-bold">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {filtered.map((item) => (
                  <tr key={item.id} className="align-top hover:bg-slate-50">
                    {/* Req 8.6: font-clinical-mono for timestamps */}
                    <td className="whitespace-nowrap px-4 py-4 font-clinical-mono text-xs text-slate-600">
                      {item.timestamp}
                    </td>
                    <td className="px-4 py-4 font-bold">{item.patientId}</td>
                    {/* Req 8.2, 8.5: Action badge with icon + text + color */}
                    <td className="px-4 py-4">
                      <ActionBadge action={item.action} />
                    </td>
                    <td className="px-4 py-4">{item.pharmacist}</td>
                    <td className="max-w-md px-4 py-4 text-slate-600">
                      {item.note || "Tidak ada catatan"}
                    </td>
                    <td className="px-4 py-4 text-xs text-slate-500">
                      {item.source}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
