/**
 * web/src/pages/PatientDetailPage.tsx
 * ----------------------------
 * Halaman detail pasien untuk apoteker memahami kasus dan mengambil keputusan.
 */

import { useState } from "react"
import { ClipboardList, Shield } from "lucide-react"
import { Card, Button, Badge, Textarea, Heading } from "../components/ui"
import { Accordion, AccordionItem, AccordionItemTrigger, AccordionItemContent } from "../components/ui/accordion"
import { Tabs, Tab } from "../components/ui/tabs"
import type { Patient, Medication, Discrepancy } from "../types/clinical"

interface PatientDetailProps {
  patient: Patient
  discrepancies: Discrepancy[]
  onAction: (action: "approve" | "reject" | "edit" | "escalate", note: string) => void
  onGenerateSBAR: () => void
  onEscalate: () => void
}

export function PatientDetailPage({
  patient,
  discrepancies,
  onAction,
  onGenerateSBAR,
  onEscalate,
}: PatientDetailProps) {
  const [activeTab, setActiveTab] = useState("comparison")
  const [showRiskDetails, setShowRiskDetails] = useState(false)
  const [sbarDraft, setSBarDraft] = useState<string | null>(null)
  const [isLoadingSBAR, setIsLoadingSBAR] = useState(false)
  const [reviewNote, setReviewNote] = useState("")

  const handleGenerateSBAR = async () => {
    setIsLoadingSBAR(true)
    try {
      const draft = generateStaticSBAR(patient)
      setSBarDraft(draft)
      setActiveTab("sbar")
    } catch (error) {
      console.error("Generate SBAR gagal:", error)
    } finally {
      setIsLoadingSBAR(false)
    }
  }

  const generateStaticSBAR = (patient: Patient): string => {
    const { age, ward, medications, sbar } = patient
    const primaryMeds = medications?.slice(0, 5) || []

    return `SBAR DRAFT — AI GENERATED

S: Pasien ${age} tahun, dirawat di ${ward}, masuk dari IGD dan akan dirawat inap.

B: Menggunakan ${primaryMeds.map((m: Medication) => m.name).join(", ")} sebelum admisi. Dosis terakhir belum dikonfirmasi.

A: Potensi omission obat-obatan vital. Risiko komplikasi bila obat rutin terlewat.

R: Mohon konfirmasi dosis terakhir obat-obatan. Verifikasi ke keluarga/apotek/rekam medis. Komunikasikan temuan ke DPJP.

AI-generated draft. Wajib diverifikasi apoteker.
Keputusan terapi akhir oleh DPJP.`
  }

  const getSeverityColor = (severity: string): string => {
    const map: Record<string, string> = {
      CRITICAL: "text-red-600",
      HIGH: "text-amber-600",
      MEDIUM: "text-amber-300",
      LOW: "text-green-600",
      REVIEW: "text-orange-600",
      NEW: "text-blue-600",
      MATCHED: "text-green-600",
      OMISSION: "text-amber-600",
    }
    return map[severity] || "text-slate-500"
  }

  return (
    <div className="min-h-screen p-4">
      {/* Header pasien */}
      <div className="border-b border-slate-200 mb-6 pb-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <Heading level={1}>
              Patient {patient.id} | {patient.age} tahun | {patient.ward}
            </Heading>
            <p className="text-sm text-slate-500 mt-1">
              Admission {patient.admissionId} | Risk: {patient.riskScore.toFixed(2)} | {patient.riskLevel} | Admitted: {patient.admittedAt}
            </p>
          </div>

          <Badge tone="info" className="text-sm">
            AI-generated draft
          </Badge>
        </div>
      </div>

      {/* Tabs navigasi */}
      <Tabs defaultValue="comparison" onValueChange={setActiveTab}>
        <Tab value="comparison">Medication Comparison</Tab>
        <Tab value="risk">Risk Explanation</Tab>
        <Tab value="sbar">SBAR</Tab>
        <Tab value="audit">Audit Trail</Tab>
      </Tabs>

      {/* Tab content */}
      {activeTab === "comparison" && (
        <Card className="mb-4">
          <div className="flex flex-row items-center justify-between mb-4">
            <Heading level={2}>Medication Comparison</Heading>
            <Button
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={() => setShowRiskDetails(!showRiskDetails)}
            >
              {showRiskDetails ? "Menyembunyikan detail SHAP teknis..." : "Lihat detail SHAP & teknis"}
            </Button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="px-4 py-3 text-left font-bold text-slate-700">Medication</th>
                  <th className="px-4 py-3 text-left font-bold text-slate-700">Dose</th>
                  <th className="px-4 py-3 text-left font-bold text-slate-700">Unit</th>
                  <th className="px-4 py-3 text-left font-bold text-slate-700">Frequency</th>
                  <th className="px-4 py-3 text-left font-bold text-slate-700">Route</th>
                  <th className="px-4 py-3 text-left font-bold text-slate-700">Source</th>
                </tr>
              </thead>
              <tbody>
                {patient.medications?.map((med: Medication, index: number) => (
                  <tr key={index} className="border-b border-slate-100">
                    <td className="px-4 py-3">{med.name}</td>
                    <td className="px-4 py-3">{med.dose}</td>
                    <td className="px-4 py-3">{med.unit}</td>
                    <td className="px-4 py-3">{med.frequency}</td>
                    <td className="px-4 py-3">{med.route}</td>
                    <td className="px-4 py-3">{med.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Progressive disclosure: SHAP details */}
          {showRiskDetails && (
            <div className="mt-4">
              <Accordion>
                {patient.medications?.map((med: Medication, i: number) => (
                  <AccordionItem key={i} value={`item-${i}`}>
                    <AccordionItemTrigger value={`trigger-${i}`}>
                      <span className="font-medium text-slate-700">
                        {med.name} detail
                      </span>
                    </AccordionItemTrigger>
                    <AccordionItemContent>
                      <p className="text-sm text-slate-600">
                        Disposition: {med.disposition}
                      </p>
                      <p className="mt-2 text-sm text-slate-500">
                        Reason: {med.reason || "none specified"}
                      </p>
                    </AccordionItemContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          )}
        </Card>
      )}

      {activeTab === "risk" && (
        <Card className="mb-4">
          <Heading level={2} className="mb-4">Risk Explanation</Heading>
          <div className="space-y-3">
            {discrepancies?.map((disc: Discrepancy, i: number) => (
              <div key={i} className="border rounded-lg p-3">
                <p className="font-medium text-slate-700">{disc.medication}</p>
                <p className="text-sm text-slate-600 mt-1">{disc.reason}</p>
                <p className="mt-2 text-xs text-slate-500">Type: {disc.type} | Status: {disc.status}</p>
              </div>
            ))}
            {discrepancies?.length === 0 && (
              <p className="text-sm text-slate-500">
                Tidak ada discrepancy ditemukan. Semua obat sudah dicek dan sesuai protokol administrasi.
              </p>
            )}
          </div>
        </Card>
      )}

      {activeTab === "sbar" && (
        <Card className="mb-4">
          <Heading level={2} className="mb-4">SBAR Panel</Heading>
          <div className="bg-slate-50 rounded-lg p-4 mb-4">
            <p className="text-xs font-bold text-amber-600 mb-2">
              SBAR DRAFT — AI GENERATED
            </p>
            <p className="text-slate-800 whitespace-pre-wrap">
              {sbarDraft || "Generating SBAR draft..."}
            </p>
            <div className="mt-3 pt-3 border-t border-slate-200">
              <small className="text-xs text-slate-500">
                AI-generated draft. Wajib diverifikasi apoteker. Keputusan terapi akhir oleh DPJP.
              </small>
            </div>
          </div>

          <div className="flex gap-3 mt-4">
            <Button variant="secondary" size="sm" onClick={onGenerateSBAR}>
              Regenerate SBAR
            </Button>
            <Button size="sm" onClick={onEscalate} className="bg-amber-50 text-amber-800">
              Escalate to DPJP
            </Button>
          </div>
        </Card>
      )}

      {activeTab === "audit" && (
        <Card className="mb-4">
          <Heading level={2} className="mb-4">Audit Trail</Heading>
          <div className="h-64 bg-slate-50 rounded-lg p-4 flex items-center justify-center">
            <p className="text-slate-400 text-center">
              Riwayat review dan perubahan obat
            </p>
          </div>
          <small className="mt-3 text-xs text-slate-500 block">
            Audit log akan muncul di sini setelah review disimpan
          </small>
        </Card>
      )}

      {/* Review Form - Selalu di bagian bawah */}
      <Card>
        <div className="flex flex-col sm:flex-row justify-between items-center gap-3 mb-4">
          <Heading level={2}>Pharmacist Review</Heading>
          <small className="text-xs text-slate-500">
            {activeTab === "sbar" ? "SBAR Draft" : "Medication Review"}
          </small>
        </div>

        <div className="space-y-4">
          {/* Action buttons */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <Button variant="secondary" size="sm" onClick={() => onAction("approve", reviewNote)}>
              APPROVE
            </Button>
            <Button variant="secondary" size="sm" onClick={() => onAction("reject", reviewNote)}>
              REJECT
            </Button>
            <Button variant="secondary" size="sm" onClick={() => onAction("edit", reviewNote)}>
              EDIT
            </Button>
            <Button size="sm" onClick={() => onAction("escalate", reviewNote)}>
              ESCALATE
            </Button>
          </div>

          {/* Note input */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Note
            </label>
            <Textarea
              placeholder="____________________________________________"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 h-24 resize-y"
              value={reviewNote}
              onChange={(e) => setReviewNote(e.target.value)}
            />
          </div>

          {/* Save button - prominent single button */}
          <div className="pt-3 border-t border-slate-200">
            <Button
              className="w-full py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              onClick={() => onAction("approve", reviewNote)}
            >
              [Save Review]
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}