import { useEffect, useState } from "react"
import {
  ClipboardPaste,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Table2,
  Trash2,
} from "lucide-react"
import type { Medication, PageId, Patient, ViewState } from "../types/clinical"
import { DATA_MODE, submitBpmh, type BpmhMedItem } from "../api/client"
import { PatientIdentity } from "../uiux/clinical"
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  InlineAlert,
  Input,
  Select,
  Skeleton,
  Textarea,
} from "../uiux/primitives"

const blankMedication = (): Medication => ({
  id: `m-${Date.now()}-${Math.random()}`,
  name: "",
  dose: "",
  unit: "",
  frequency: "",
  route: "",
  source: "",
  disposition: "",
  reason: "",
})

export function BpmhPage({
  patient,
  viewState,
  onViewState,
  onSave,
  onNavigate,
}: {
  patient: Patient
  viewState: ViewState
  onViewState: (state: ViewState) => void
  onSave: (medications: Medication[]) => void
  onNavigate: (page: PageId) => void
}) {
  const [mode, setMode] = useState<"table" | "paste">("table")
  const [medications, setMedications] = useState<Medication[]>(
    patient.medications.length ? patient.medications : [blankMedication()],
  )
  const [pasteText, setPasteText] = useState(
    "Warfarin 2 mg 1x sehari oral\nMetformin 500 mg 2x sehari oral\nAmlodipine 5 mg 1x sehari",
  )
  const [saveLabel, setSaveLabel] = useState("Tersimpan otomatis pukul 10:22")
  const [parsed, setParsed] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    setSaveLabel("Menyimpan…")
    const timer = window.setTimeout(() => {
      setSaveLabel(
        `Tersimpan otomatis pukul ${new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`,
      )
    }, 650)
    return () => window.clearTimeout(timer)
  }, [medications, pasteText])

  const updateMedication = (
    id: string,
    field: keyof Medication,
    value: string,
  ) => {
    setMedications((current) =>
      current.map((item) =>
        item.id === id ? { ...item, [field]: value } : item,
      ),
    )
  }
  const parseText = () => {
    const parsedRows = pasteText
      .split("\n")
      .filter(Boolean)
      .map((line, index) => {
        const parts = line.trim().split(/\s+/)
        const doseIndex = parts.findIndex((part) => /^\d/.test(part))
        return {
          ...blankMedication(),
          id: `parsed-${index}`,
          name: doseIndex > 0 ? parts.slice(0, doseIndex).join(" ") : line,
          dose: doseIndex > 0 ? parts[doseIndex] : "",
          unit: parts[doseIndex + 1]?.toLowerCase() === "mg" ? "mg" : "",
          frequency:
            parts.find((part) => part.toLowerCase().includes("x")) ?? "",
          route: line.toLowerCase().includes("oral") ? "Oral" : "",
          source: "Teks yang ditempel",
        }
      })
    setMedications(parsedRows.length ? parsedRows : [blankMedication()])
    setParsed(true)
    setMode("table")
  }
  const incompleteCount = medications.filter(
    (item) => item.name && (!item.dose || !item.frequency || !item.disposition),
  ).length
  const canSubmit = medications.some((item) => item.name.trim())

  if (viewState === "loading") return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-48" />
      <Card className="space-y-3">
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-10 w-full" />
      </Card>
    </div>
  )
  if (viewState === "error")
    return (
      <ErrorState
        description="Riwayat BPMH tidak dapat dimuat"
        onRetry={() => onViewState("ready")}
      />
    )
  if (viewState === "empty") {
    return (
      <EmptyState
        title="Belum ada obat pada BPMH"
        description="Mulai dengan menambahkan obat satu per satu atau tempel daftar obat dari sumber lain untuk dikoreksi."
        action={
          <Button
            onClick={() => onViewState("ready")}
            icon={<Plus className="size-4" />}
          >
            Mulai input BPMH
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onNavigate("worklist")}
          >
            ← Kembali ke Worklist
          </Button>
          <h1 className="font-display text-xl font-bold text-slate-900 mt-2">Form BPMH</h1>
          <p className="mt-1 text-sm text-slate-600">
            Best Possible Medication History · hanya nama obat yang wajib diisi.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
          <Save className="size-4 text-emerald-700" /> {saveLabel}
        </div>
      </div>

      <Card>
        <PatientIdentity
          name={patient.id}
          patientId={patient.id}
          ward={patient.ward}
        />
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid w-full grid-cols-2 rounded-lg border border-slate-300 bg-white p-1 sm:inline-flex sm:w-auto">
          <Button
            size="sm"
            variant={mode === "table" ? "primary" : "ghost"}
            onClick={() => setMode("table")}
            icon={<Table2 className="size-4" />}
          >
            Mode Tabel
          </Button>
          <Button
            size="sm"
            variant={mode === "paste" ? "primary" : "ghost"}
            onClick={() => setMode("paste")}
            icon={<ClipboardPaste className="size-4" />}
          >
            Mode Tempel Teks
          </Button>
        </div>
        <Badge tone="info">Nama obat wajib · field lain opsional</Badge>
      </div>

      {mode === "paste" ? (
        <Card>
          <h2 className="text-lg font-bold text-slate-900">Tempel daftar obat</h2>
          <p className="mt-1 text-sm text-slate-600">
            Satu obat per baris. Hasil parsing adalah draf dan harus dikoreksi
            sebelum submit.
          </p>
          <Field
            className="mt-5"
            label="Teks sumber"
            htmlFor="bpmh-paste-text"
            required
            hint="Contoh: Warfarin 2 mg 1x sehari oral"
          >
            <Textarea
              id="bpmh-paste-text"
              className="min-h-64 font-mono"
              value={pasteText}
              onChange={(event) => setPasteText(event.target.value)}
            />
          </Field>
          <div className="mt-4 flex justify-end">
            <Button icon={<Sparkles className="size-4" />} onClick={parseText}>
              Parse ke tabel
            </Button>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {parsed && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Hasil parse adalah draf — wajib diperiksa apoteker sebelum submit.
            </div>
          )}
          <Card className="overflow-hidden p-0">
            {/* Mobile card layout */}
            <div className="space-y-3 p-3 md:hidden">
              {medications.map((medication, index) => (
                <div key={medication.id} className="rounded-lg border border-slate-200 bg-white p-4">
                  <div className="mb-4 flex items-center justify-between">
                    <p className="text-sm font-bold text-slate-900">Obat {index + 1}</p>
                    <IconButton
                      label={`Hapus ${medication.name || "baris obat"}`}
                      icon={<Trash2 className="size-4" />}
                      onClick={() =>
                        setMedications((current) =>
                          current.filter((item) => item.id !== medication.id),
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-4">
                    <Field label="Nama obat" htmlFor={`mob-name-${medication.id}`} required>
                      <Input
                        id={`mob-name-${medication.id}`}
                        value={medication.name}
                        onChange={(event) =>
                          updateMedication(medication.id, "name", event.target.value)
                        }
                        placeholder="Cari nama obat"
                      />
                    </Field>
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Dosis" htmlFor={`mob-dose-${medication.id}`}>
                        <Input
                          id={`mob-dose-${medication.id}`}
                          value={medication.dose}
                          onChange={(event) =>
                            updateMedication(medication.id, "dose", event.target.value)
                          }
                        />
                      </Field>
                      <Field label="Satuan" htmlFor={`mob-unit-${medication.id}`}>
                        <Select
                          id={`mob-unit-${medication.id}`}
                          value={medication.unit}
                          onChange={(event) =>
                            updateMedication(medication.id, "unit", event.target.value)
                          }
                        >
                          <option value="">—</option>
                          <option value="mg">mg</option>
                          <option value="mcg">mcg</option>
                          <option value="g">g</option>
                          <option value="unit">unit</option>
                          <option value="mL">mL</option>
                        </Select>
                      </Field>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Frekuensi" htmlFor={`mob-freq-${medication.id}`}>
                        <Input
                          id={`mob-freq-${medication.id}`}
                          value={medication.frequency}
                          onChange={(event) =>
                            updateMedication(medication.id, "frequency", event.target.value)
                          }
                          placeholder="2× sehari"
                        />
                      </Field>
                      <Field label="Rute" htmlFor={`mob-route-${medication.id}`}>
                        <Select
                          id={`mob-route-${medication.id}`}
                          value={medication.route}
                          onChange={(event) =>
                            updateMedication(medication.id, "route", event.target.value)
                          }
                        >
                          <option value="">—</option>
                          <option value="Oral">Oral</option>
                          <option value="IV">IV</option>
                          <option value="SC">SC</option>
                          <option value="Inhalasi">Inhalasi</option>
                        </Select>
                      </Field>
                    </div>
                    <Field label="Sumber informasi" htmlFor={`mob-src-${medication.id}`}>
                      <Input
                        id={`mob-src-${medication.id}`}
                        value={medication.source}
                        onChange={(event) =>
                          updateMedication(medication.id, "source", event.target.value)
                        }
                      />
                    </Field>
                    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                      <Field label="Disposisi" htmlFor={`mob-disp-${medication.id}`}>
                        <Select
                          id={`mob-disp-${medication.id}`}
                          className="border-blue-300 font-semibold"
                          value={medication.disposition}
                          onChange={(event) =>
                            updateMedication(medication.id, "disposition", event.target.value)
                          }
                        >
                          <option value="">Pilih disposisi</option>
                          <option value="Dilanjutkan">Dilanjutkan</option>
                          <option value="Ditunda">Ditunda</option>
                          <option value="Diganti">Diganti</option>
                          <option value="Dihentikan">Dihentikan</option>
                        </Select>
                      </Field>
                    </div>
                    <Field label="Alasan" htmlFor={`mob-reason-${medication.id}`}>
                      <Input
                        id={`mob-reason-${medication.id}`}
                        value={medication.reason}
                        onChange={(event) =>
                          updateMedication(medication.id, "reason", event.target.value)
                        }
                      />
                    </Field>
                  </div>
                </div>
              ))}
            </div>
            {/* Desktop table layout */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[84rem] border-collapse text-left text-sm">
                <thead className="bg-slate-50 text-[0.6875rem] uppercase tracking-wide text-slate-500">
                  <tr>
                    {[
                      "Nama obat *",
                      "Dosis",
                      "Satuan",
                      "Frekuensi",
                      "Rute",
                      "Sumber info",
                      "Disposisi",
                      "Alasan",
                      "",
                    ].map((label) => (
                      <th
                        key={label}
                        className={`px-3 py-3 font-bold ${
                          label === "Disposisi"
                            ? "bg-blue-50 text-blue-800"
                            : ""
                        }`}
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {medications.map((medication) => (
                    <tr key={medication.id} className="align-top">
                      <td className="w-52 p-2">
                        <Input
                          aria-label="Nama obat"
                          required
                          value={medication.name}
                          onChange={(event) =>
                            updateMedication(
                              medication.id,
                              "name",
                              event.target.value,
                            )
                          }
                          placeholder="Cari nama obat"
                        />
                      </td>
                      <td className="w-24 p-2">
                        <Input
                          aria-label="Dosis"
                          value={medication.dose}
                          onChange={(event) =>
                            updateMedication(
                              medication.id,
                              "dose",
                              event.target.value,
                            )
                          }
                        />
                      </td>
                      <td className="w-24 p-2">
                        <Select
                          aria-label="Satuan"
                          value={medication.unit}
                          onChange={(event) =>
                            updateMedication(
                              medication.id,
                              "unit",
                              event.target.value,
                            )
                          }
                        >
                          <option value="">—</option>
                          <option value="mg">mg</option>
                          <option value="mcg">mcg</option>
                          <option value="g">g</option>
                          <option value="unit">unit</option>
                          <option value="mL">mL</option>
                        </Select>
                      </td>
                      <td className="w-36 p-2">
                        <Input
                          aria-label="Frekuensi"
                          value={medication.frequency}
                          onChange={(event) =>
                            updateMedication(
                              medication.id,
                              "frequency",
                              event.target.value,
                            )
                          }
                          placeholder="mis. 2× sehari"
                        />
                      </td>
                      <td className="w-28 p-2">
                        <Select
                          aria-label="Rute"
                          value={medication.route}
                          onChange={(event) =>
                            updateMedication(
                              medication.id,
                              "route",
                              event.target.value,
                            )
                          }
                        >
                          <option value="">—</option>
                          <option value="Oral">Oral</option>
                          <option value="IV">IV</option>
                          <option value="SC">SC</option>
                          <option value="Inhalasi">Inhalasi</option>
                        </Select>
                      </td>
                      <td className="w-44 p-2">
                        <Input
                          aria-label="Sumber informasi"
                          value={medication.source}
                          onChange={(event) =>
                            updateMedication(
                              medication.id,
                              "source",
                              event.target.value,
                            )
                          }
                        />
                      </td>
                      <td className="w-44 bg-blue-50/60 p-2">
                        <Select
                          aria-label="Disposisi"
                          className="border-blue-300 font-semibold"
                          value={medication.disposition}
                          onChange={(event) =>
                            updateMedication(
                              medication.id,
                              "disposition",
                              event.target.value,
                            )
                          }
                        >
                          <option value="">Pilih disposisi</option>
                          <option value="Dilanjutkan">Dilanjutkan</option>
                          <option value="Ditunda">Ditunda</option>
                          <option value="Diganti">Diganti</option>
                          <option value="Dihentikan">Dihentikan</option>
                        </Select>
                      </td>
                      <td className="w-56 p-2">
                        <Input
                          aria-label="Alasan disposisi"
                          value={medication.reason}
                          onChange={(event) =>
                            updateMedication(
                              medication.id,
                              "reason",
                              event.target.value,
                            )
                          }
                        />
                      </td>
                      <td className="p-2">
                        <IconButton
                          label={`Hapus ${medication.name || "baris obat"}`}
                          icon={<Trash2 className="size-4" />}
                          onClick={() =>
                            setMedications((current) =>
                              current.filter(
                                (item) => item.id !== medication.id,
                              ),
                            )
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-slate-200 bg-slate-50 p-3">
              <Button
                variant="secondary"
                size="sm"
                icon={<Plus className="size-4" />}
                onClick={() =>
                  setMedications((current) => [...current, blankMedication()])
                }
              >
                Tambah obat
              </Button>
            </div>
          </Card>
        </div>
      )}

      {submitted && !canSubmit && (
        <InlineAlert tone="warning" title="Minimal satu nama obat diperlukan">
          Isi minimal satu nama obat sebelum melanjutkan.
        </InlineAlert>
      )}
      {incompleteCount > 0 && canSubmit && (
        <InlineAlert tone="warning" title={`${incompleteCount} obat belum lengkap`}>
          Anda tetap dapat submit; apoteker dapat melengkapinya saat verifikasi.
        </InlineAlert>
      )}

      {submitError && (
        <InlineAlert tone="danger" title="Gagal menyimpan ke server">
          {submitError}. Data tetap tersimpan lokal.
        </InlineAlert>
      )}

      <div className="flex flex-wrap justify-end gap-3 border-t border-slate-300 pt-5">
        <Button variant="secondary" onClick={() => onNavigate("worklist")}>
          Simpan dan kembali
        </Button>
        <Button
          size="lg"
          disabled={submitting}
          icon={submitting ? <Loader2 className="size-4 animate-spin" /> : undefined}
          onClick={async () => {
            setSubmitted(true)
            if (!canSubmit) return
            const validMeds = medications.filter((item) => item.name.trim())
            onSave(validMeds)

            // Live mode: persist BPMH to backend
            if (DATA_MODE === "live") {
              setSubmitting(true)
              setSubmitError(null)
              const payload: BpmhMedItem[] = validMeds.map((m) => ({
                medication_code: null,
                medication_name: m.name.trim(),
                dose_value: m.dose || null,
                dose_unit: m.unit || null,
                frequency: m.frequency || null,
                route: m.route || null,
                source_of_info: m.source || null,
                disposition: (m.disposition?.toUpperCase() || null) as BpmhMedItem["disposition"],
                disposition_reason: m.reason || null,
              }))
              try {
                await submitBpmh(patient.id, {
                  encounter_id: patient.admissionId,
                  medications: payload,
                  pharmacist_id: "self",
                })
              } catch (err) {
                setSubmitError(err instanceof Error ? err.message : "Unknown error")
                // Don't block navigation — local state is already saved
              } finally {
                setSubmitting(false)
              }
            }

            onNavigate("analysis")
          }}
        >
          Submit BPMH untuk analisis
        </Button>
      </div>
    </div>
  )
}
