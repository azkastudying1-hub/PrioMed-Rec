/*
 * web/src/uiux/pages.tsx
 * ---------------------------------------------------------------------------
 * Dua layar utama yang menutup alur kerja apoteker:
 *
 *  1. WorklistPage  - memilih kasus, melihat prioritas/SLA, mengklaim kasus.
 *  2. CasePage      - menelaah temuan, membandingkan BPMH vs order admisi,
 *                     menyunting SBAR, melihat riwayat, lalu menyimpan keputusan.
 *
 * Halaman ini memakai API yang sudah ada:
 *   getWorklistV1 / claimEncounterV1 / submitReviewV1 / getReviewHistoryV1
 *
 * Pada mode `synthetic`, data diambil dari clinicalData.ts dan keputusan tidak
 * dikirim ke server. Pada mode `live`, semua aksi tetap melalui apiClient
 * sehingga audit trail dan hard-stop server tetap berlaku.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Clock,
  Compass,
  Copy,
  FileClock,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  TriangleAlert,
  UserRound,
  X,
} from "lucide-react"
import { DATA_MODE } from "../api/client"
import { subscribeQueueEvents } from "../api/queue"
import { initialPatients } from "../data/clinicalData"
import {
  claimEncounterV1,
  getReviewHistoryV1,
  getWorklistV1,
  submitReviewV1,
  type ReviewAction,
  type WorklistItemV1,
} from "../lib/apiClient"
import { useAuthStore } from "../lib/auth"
import type { Discrepancy, Patient, RiskLevel, SbarDraft } from "../types/clinical"
import { CopilotDrawer } from "../components/CopilotDrawer"
import {
  AiDraftNotice,
  AuditTimeline,
  FindingCard,
  HighAlertDialog,
  KpiCard,
  PatientIdentity,
  PriorityBadge,
  ReasonChip,
  RiskScoreBar,
  SectionHeading,
  SlaIndicator,
  SourceTag,
  WorkflowStatusBadge,
  formatDateTime,
  initials,
  isSlaBreached,
  isTerminalStatus,
  type AuditTimelineEntry,
  type FindingTier,
  type HighAlertItem,
} from "./clinical"
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
  Kbd,
  Modal,
  SegmentedControl,
  Select,
  Skeleton,
  Tabs,
  Textarea,
  cn,
  cleanText,
  type ButtonVariant,
} from "./primitives"

/* -------------------------------------------------------------------------- */
/* Tipe & helper data                                                         */
/* -------------------------------------------------------------------------- */

interface Finding {
  id: string
  tier: FindingTier
  title: string
  source: string
  why: string
  action: string
  home?: string
  admission?: string
}

type Feedback = {
  tone: "success" | "danger" | "warning"
  text: string
}

const DISCREPANCY_LABEL: Record<Discrepancy["type"], string> = {
  POTENTIAL_UNDOCUMENTED_OMISSION: "Potensi obat terlewat",
  POSSIBLE_SUBSTITUTION: "Kemungkinan substitusi",
  POTENTIAL_DUPLICATION: "Potensi duplikasi",
  UNRESOLVED_MATCH: "Padanan belum pasti",
}

const DISCREPANCY_TIER: Record<Discrepancy["type"], FindingTier> = {
  POTENTIAL_UNDOCUMENTED_OMISSION: 1,
  POSSIBLE_SUBSTITUTION: 2,
  POTENTIAL_DUPLICATION: 1,
  UNRESOLVED_MATCH: 3,
}

const DISCREPANCY_ACTION: Record<Discrepancy["type"], string> = {
  POTENTIAL_UNDOCUMENTED_OMISSION:
    "Konfirmasi ke DPJP apakah obat rumah sengaja dihentikan. Jika tidak, lengkapi order atau dokumentasikan alasan penghentian.",
  POSSIBLE_SUBSTITUTION:
    "Pastikan substitusi disengaja, sesuai kesetaraan dosis, dan terdokumentasi di catatan terapi.",
  POTENTIAL_DUPLICATION:
    "Periksa kandungan aktif dan total dosis harian. Hentikan salah satu order jika duplikasi terkonfirmasi.",
  UNRESOLVED_MATCH:
    "Minta klarifikasi sumber BPMH atau cocokkan dengan resep/obat yang dibawa pasien sebelum melanjutkan.",
}

const ACTION_META: Record<
  ReviewAction,
  { label: string; title: string; description: string; variant: ButtonVariant; requiresReason: boolean }
> = {
  APPROVE: {
    label: "Setujui",
    title: "Setujui hasil telaah",
    description:
      "Menyetujui berarti seluruh temuan sudah diverifikasi dan dokumentasi siap difinalkan.",
    variant: "success",
    requiresReason: false,
  },
  EDIT: {
    label: "Edit & setujui",
    title: "Edit lalu setujui",
    description: "Gunakan bila rekomendasi perlu diperbaiki sebelum disetujui.",
    variant: "primary",
    requiresReason: true,
  },
  REJECT: {
    label: "Tolak",
    title: "Tolak hasil telaah",
    description: "Gunakan bila temuan tidak valid atau order tidak dapat dipertanggungjawabkan.",
    variant: "danger",
    requiresReason: true,
  },
  ESCALATE: {
    label: "Eskalasi",
    title: "Eskalasi ke DPJP",
    description: "Gunakan bila diperlukan keputusan dokter sebelum telaah dapat diselesaikan.",
    // Task 8.1 Req 6.1: ESCALATE uses warning variant (amber) from task 1.1
    variant: "warning",
    requiresReason: true,
  },
  DRAFT_REVIEW: {
    label: "Simpan draf",
    title: "Simpan draf telaah",
    description: "Draf dapat dilanjutkan nanti tanpa menutup kasus.",
    variant: "secondary",
    requiresReason: false,
  },
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? cleanText(error.message) : "Terjadi kesalahan yang tidak diketahui."
}

function findDemoPatient(item: WorklistItemV1): Patient | undefined {
  return initialPatients.find(
    (patient) => patient.id === item.patient_id || patient.admissionId === item.encounter_id,
  )
}

function toSyntheticItems(): WorklistItemV1[] {
  const slaDemo = [5.4, 3.1, 7.2, 2.4, 13.5, 4.0]
  const dpjpDemo = [
    "dr. Budi Santoso, Sp.PD",
    "dr. Siti Rahma, Sp.An",
    "dr. Andi Wijaya, Sp.JP",
    "dr. Maya Putri, Sp.PD",
    "dr. Rizky Pratama, Sp.EM",
    "dr. Nina Kartika, Sp.PD",
  ]

  return initialPatients.map((patient, index) => {
    const workflowStatus =
      patient.status === "Disetujui"
        ? "SELESAI_APPROVE"
        : patient.status === "Ditolak"
          ? "DITOLAK"
          : patient.status === "Perlu verifikasi"
            ? "MENUNGGU_TELAAH"
            : "MENUNGGU_BPMH"

    return {
      encounter_id: patient.admissionId,
      patient_id: patient.id,
      patient_name: patient.id,
      ward: patient.ward,
      workflow_status: workflowStatus,
      latest_tier: patient.riskLevel,
      ml_score: patient.riskScore,
      priority_reasons: [
        ...patient.discrepancies.map((discrepancy) => ({
          source: "RULE",
          reason: `${DISCREPANCY_LABEL[discrepancy.type]} · ${cleanText(discrepancy.medication)}`,
          tier: patient.riskLevel,
        })),
        ...(patient.highAlertCount > 0
          ? [
              {
                source: "RULE",
                reason: `High-alert: ${patient.highAlertCount} obat perlu verifikasi`,
                tier: "HIGH",
              },
            ]
          : []),
        ...(patient.riskScore >= 0.7
          ? [
              {
                source: "ML",
                reason: `Probabilitas diskrepansi ${Math.round(patient.riskScore * 100)}%`,
                tier: patient.riskLevel,
              },
            ]
          : []),
      ],
      admitted_at: patient.admittedAt,
      sla_hours_elapsed: slaDemo[index % slaDemo.length],
      claimed_by: null,
      claimed_at: null,
      row_version: 1,
      dpjp_name: dpjpDemo[index % dpjpDemo.length],
    }
  })
}

function buildFindings(item: WorklistItemV1): Finding[] {
  const demo = findDemoPatient(item)

  if (demo && demo.discrepancies.length > 0) {
    return demo.discrepancies.map((discrepancy) => ({
      id: discrepancy.id,
      tier: DISCREPANCY_TIER[discrepancy.type],
      title: `${DISCREPANCY_LABEL[discrepancy.type]} · ${cleanText(discrepancy.medication)}`,
      source: "RULE",
      why: discrepancy.reason,
      action: DISCREPANCY_ACTION[discrepancy.type],
      home: discrepancy.home,
      admission: discrepancy.admission,
    }))
  }

  return item.priority_reasons.map((reason, index) => ({
    id: `${item.encounter_id}-reason-${index}`,
    tier: reason.tier === "HIGH" ? 1 : reason.tier === "MEDIUM" ? 2 : 3,
    title: cleanText(reason.reason),
    source: reason.source,
    why: "Alasan ini berasal dari mesin prioritas. Buka rekam BPMH dan order admisi untuk memverifikasi konteks klinis.",
    action:
      "Konfirmasi ke DPJP, periksa dokumentasi obat, lalu tentukan apakah temuan valid sebelum menyimpan keputusan.",
  }))
}

function buildHighAlerts(item: WorklistItemV1): HighAlertItem[] {
  const demo = findDemoPatient(item)
  const collected = new Map<string, HighAlertItem>()

  demo?.interactions
    .filter((interaction) => interaction.severity === "Tinggi")
    .forEach((interaction) => {
      collected.set(interaction.id, {
        id: interaction.id,
        label: interaction.drugs,
        detail: `${interaction.reason} Monitoring: ${interaction.monitoring}`,
      })
    })

  item.priority_reasons
    .filter((reason) => /high[- ]?alert/i.test(reason.reason))
    .forEach((reason, index) => {
      const label = cleanText(reason.reason)
      collected.set(`reason-${index}-${label}`, {
        id: `reason-${index}-${label}`,
        label,
        detail: "Temuan high-alert dari mesin aturan. Verifikasi dosis, rute, frekuensi, dan monitoring.",
      })
    })

  if (collected.size === 0 && demo && demo.highAlertCount > 0) {
    collected.set("high-alert-count", {
      id: "high-alert-count",
      label: `${demo.highAlertCount} order high-alert`,
      detail: "Daftar obat high-alert belum tersedia di worklist. Periksa tab Bandingkan dan rekam BPMH.",
    })
  }

  return Array.from(collected.values())
}

function buildSbar(item: WorklistItemV1, findings: Finding[]): SbarDraft {
  const demo = findDemoPatient(item)
  if (demo?.sbar) {
    return {
      situation: cleanText(demo.sbar.situation),
      background: cleanText(demo.sbar.background),
      assessment: cleanText(demo.sbar.assessment),
      recommendation: cleanText(demo.sbar.recommendation),
    }
  }

  const patient = cleanText(item.patient_name ?? item.patient_id)
  const reasons = item.priority_reasons.map((reason) => cleanText(reason.reason)).join("; ")

  return {
    situation: `${patient} di ${cleanText(item.ward)} dengan prioritas ${
      item.latest_tier ?? "belum dinilai"
    } dan ${findings.length} kandidat temuan.`,
    background: `Admisi ${formatDateTime(item.admitted_at)}. ${
      reasons || "Belum ada alasan prioritas yang tercatat."
    }`,
    assessment: findings.length
      ? `${findings.length} temuan perlu verifikasi: ${findings
          .slice(0, 3)
          .map((finding) => finding.title)
          .join("; ")}.`
      : "Belum ada temuan yang perlu diverifikasi.",
    recommendation:
      "Konfirmasi temuan ke DPJP, lengkapi dokumentasi, lalu simpan keputusan telaah.",
  }
}

/* -------------------------------------------------------------------------- */
/* Komponen kecil bersama                                                     */
/* -------------------------------------------------------------------------- */

function FeedbackBanner({
  feedback,
  onClose,
}: {
  feedback: Feedback | null
  onClose: () => void
}) {
  if (!feedback) return null
  const title =
    feedback.tone === "success"
      ? "Berhasil"
      : feedback.tone === "warning"
        ? "Perlu diperhatikan"
        : "Terjadi kesalahan"

  return (
    <InlineAlert
      tone={feedback.tone}
      title={title}
      action={
        <IconButton
          label="Tutup pesan"
          icon={<X className="size-4" />}
          onClick={onClose}
          className="size-8"
        />
      }
    >
      {feedback.text}
    </InlineAlert>
  )
}

function WorklistSkeleton() {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <Card key={item} className="space-y-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-7 w-16" />
            <Skeleton className="h-3 w-32" />
          </Card>
        ))}
      </div>
      <Card className="space-y-3">
        {[0, 1, 2, 3, 4].map((item) => (
          <div key={item} className="flex items-center gap-4">
            <Skeleton className="size-9 rounded-lg" />
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-8 w-24" />
          </div>
        ))}
      </Card>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Worklist                                                                   */
/* -------------------------------------------------------------------------- */

export interface WorklistPageProps {
  onSelectEncounter: (item: WorklistItemV1) => void
}

export function WorklistPage({ onSelectEncounter }: WorklistPageProps) {
  const [tier, setTier] = useState<"ALL" | RiskLevel>("ALL")
  const [ward, setWard] = useState("ALL")
  const [search, setSearch] = useState("")
  const [claimingId, setClaimingId] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const currentUserId = useAuthStore((state) => state.user?.sub)

  const live = DATA_MODE === "live"
  const syntheticItems = useMemo(toSyntheticItems, [])

  const worklistQuery = useQuery({
    queryKey: ["worklist"],
    queryFn: () => getWorklistV1({ page_size: 100 }),
    enabled: live,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  // SSE: segarkan worklist segera setelah antrean berubah (debounce 1,2 dtk).
  useEffect(() => {
    if (!live) return
    let timer: number | null = null
    const unsubscribe = subscribeQueueEvents(
      () => {
        if (timer) window.clearTimeout(timer)
        timer = window.setTimeout(() => {
          timer = null
          void queryClient.invalidateQueries({ queryKey: ["worklist"] })
        }, 1200)
      },
      () => {
        /* status koneksi ditampilkan di halaman antrean */
      },
    )
    return () => {
      if (timer) window.clearTimeout(timer)
      unsubscribe()
    }
  }, [live, queryClient])

  const allItems = live ? (worklistQuery.data?.items ?? []) : syntheticItems

  const wards = useMemo(
    () =>
      Array.from(
        new Set(
          allItems
            .map((item) => item.ward)
            .filter((value): value is string => Boolean(value)),
        ),
      ).sort(),
    [allItems],
  )

  const filteredItems = useMemo(() => {
    const term = search.trim().toLowerCase()

    return allItems.filter((item) => {
      if (isTerminalStatus(item.workflow_status)) return false
      if (tier !== "ALL" && item.latest_tier !== tier) return false
      if (ward !== "ALL" && item.ward !== ward) return false
      if (!term) return true

      const haystack = [
        item.patient_name,
        item.patient_id,
        item.encounter_id,
        item.ward,
        item.dpjp_name,
        ...item.priority_reasons.map((reason) => reason.reason),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()

      return haystack.includes(term)
    })
  }, [allItems, search, tier, ward])

  const counts = useMemo(() => {
    const active = allItems.filter((item) => !isTerminalStatus(item.workflow_status))
    return {
      total: active.length,
      high: active.filter((item) => item.latest_tier === "HIGH").length,
      medium: active.filter((item) => item.latest_tier === "MEDIUM").length,
      low: active.filter((item) => item.latest_tier === "LOW").length,
      breach: active.filter((item) => isSlaBreached(item.sla_hours_elapsed, item.latest_tier)).length,
      highAlert: active.filter((item) =>
        item.priority_reasons.some((reason) => /high[- ]?alert/i.test(reason.reason)),
      ).length,
    }
  }, [allItems])

  const claimAndOpen = useCallback(
    async (item: WorklistItemV1) => {
      if (!live) {
        onSelectEncounter(item)
        return
      }

      if (item.claimed_by && item.claimed_by !== currentUserId) {
        setFeedback({
          tone: "warning",
          text: `Kasus sedang diklaim oleh ${item.claimed_by}. Anda dapat membuka untuk melihat, tetapi keputusan sebaiknya dikoordinasikan.`,
        })
        onSelectEncounter(item)
        return
      }

      if (!item.claimed_by) {
        setClaimingId(item.encounter_id)
        try {
          const claimed = await claimEncounterV1(item.encounter_id, item.row_version)
          await queryClient.invalidateQueries({ queryKey: ["worklist"] })
          setClaimingId(null)
          onSelectEncounter({
            ...item,
            claimed_by: claimed.claimed_by,
            claimed_at: new Date().toISOString(),
            row_version: claimed.row_version,
          })
          return
        } catch (error) {
          setFeedback({ tone: "danger", text: `Klaim gagal: ${errorMessage(error)}` })
          setClaimingId(null)
          return
        }
      }

      onSelectEncounter(item)
    },
    [currentUserId, live, onSelectEncounter, queryClient],
  )

  const claimNext = useCallback(() => {
    const next = filteredItems.find(
      (item) =>
        !isTerminalStatus(item.workflow_status) &&
        (!item.claimed_by || item.claimed_by === currentUserId),
    )

    if (!next) {
      setFeedback({
        tone: "warning",
        text: "Tidak ada kasus aktif yang dapat diambil pada filter ini.",
      })
      return
    }

    void claimAndOpen(next)
  }, [claimAndOpen, currentUserId, filteredItems])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return
      }

      if (event.key === "/") {
        event.preventDefault()
        searchRef.current?.focus()
      }

      if (
        event.key.toLowerCase() === "n" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey
      ) {
        event.preventDefault()
        claimNext()
      }
    }

    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [claimNext])

  const isLoading = live && worklistQuery.isLoading
  const isError = live && worklistQuery.isError

  return (
    <div className="space-y-5">
      <SectionHeading
        eyebrow="Operasional farmasi"
        title="Worklist Prioritas Telaah"
        description="Mulai dari kasus dengan risiko diskrepansi dan tekanan SLA tertinggi. Urutan menggabungkan model ML, aturan klinis, dan waktu tunggu."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                if (live) void worklistQuery.refetch()
              }}
              disabled={!live}
              loading={live && worklistQuery.isFetching}
              icon={<RefreshCw className="size-4" />}
              title={live ? "Muat ulang worklist" : "Mode sintetis tidak memerlukan muat ulang"}
            >
              Muat ulang
            </Button>
            <Button onClick={claimNext} loading={claimingId !== null} icon={<ArrowRight className="size-4" />}>
              Ambil berikutnya <Kbd>N</Kbd>
            </Button>
          </>
        }
      />

      <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Kasus aktif"
          value={counts.total}
          hint="Belum selesai pada antrean saat ini"
          tone="info"
          icon={<ClipboardList className="size-4" />}
        />
        <KpiCard
          label="Prioritas tinggi"
          value={counts.high}
          hint="Target telaah 4 jam"
          tone="critical"
          icon={<TriangleAlert className="size-4" />}
        />
        <KpiCard
          label="Lewat SLA"
          value={counts.breach}
          hint="Perlu eskalasi atau penambahan kapasitas"
          tone="danger"
          icon={<Clock className="size-4" />}
        />
        <KpiCard
          label="High-alert"
          value={counts.highAlert}
          hint="Wajib konfirmasi sebelum persetujuan"
          tone="warning"
          icon={<ShieldAlert className="size-4" />}
        />
      </div>

      <Card padded={false} className="p-3">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
          <div className="relative min-w-0 flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <Input
              ref={searchRef}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Cari pasien, encounter, bangsal, atau alasan..."
              aria-label="Cari worklist"
              className="pl-9"
            />
          </div>

          <SegmentedControl
            items={[
              { value: "ALL", label: "Semua", count: counts.total },
              { value: "HIGH", label: "Tinggi", count: counts.high },
              { value: "MEDIUM", label: "Sedang", count: counts.medium },
              { value: "LOW", label: "Rendah", count: counts.low },
            ]}
            value={tier}
            onChange={setTier}
            ariaLabel="Filter prioritas"
          />

          <Select
            value={ward}
            onChange={(event) => setWard(event.target.value)}
            aria-label="Filter bangsal"
            className="w-full xl:w-52"
          >
            <option value="ALL">Semua bangsal</option>
            {wards.map((value) => (
              <option key={value} value={value}>
                {cleanText(value)}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {isLoading ? (
        <WorklistSkeleton />
      ) : isError ? (
        <ErrorState
          description="Worklist tidak dapat dimuat. Periksa koneksi ke API lalu coba lagi."
          onRetry={() => void worklistQuery.refetch()}
          retrying={worklistQuery.isFetching}
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={<ClipboardList className="size-5" />}
          title="Tidak ada kasus pada filter ini"
          description="Ubah filter prioritas atau bangsal, atau hapus kata kunci pencarian."
          action={
            <Button
              variant="secondary"
              onClick={() => {
                setTier("ALL")
                setWard("ALL")
                setSearch("")
              }}
            >
              Reset filter
            </Button>
          }
        />
      ) : (
        <>
          <div className="hidden lg:block">
            <WorklistTable
              items={filteredItems}
              live={live}
              claimingId={claimingId}
              onOpen={(item) => void claimAndOpen(item)}
            />
          </div>
          <div className="grid gap-3 lg:hidden">
            {filteredItems.map((item) => (
              <WorklistCard
                key={item.encounter_id}
                item={item}
                live={live}
                claiming={claimingId === item.encounter_id}
                onOpen={() => void claimAndOpen(item)}
              />
            ))}
          </div>
        </>
      )}

      <p className="text-[10px] leading-relaxed text-slate-500">
        {live
          ? "Worklist diperbarui otomatis setiap 30 detik. "
          : "Mode data sintetis: keputusan tidak dikirim ke server. "}
        Tekan <Kbd>/</Kbd> untuk mencari dan <Kbd>N</Kbd> untuk mengambil kasus berikutnya.
      </p>
    </div>
  )
}

function WorklistTable({
  items,
  live,
  claimingId,
  onOpen,
}: {
  items: WorklistItemV1[]
  live: boolean
  claimingId: string | null
  onOpen: (item: WorklistItemV1) => void
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1040px] text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr className="text-[10px] uppercase tracking-wider text-slate-500">
              <th scope="col" className="px-4 py-3 font-bold">Prioritas</th>
              <th scope="col" className="px-4 py-3 font-bold">Pasien</th>
              <th scope="col" className="px-4 py-3 font-bold">Bangsal / DPJP</th>
              <th scope="col" className="px-4 py-3 font-bold">Status</th>
              <th scope="col" className="px-4 py-3 font-bold">SLA</th>
              <th scope="col" className="px-4 py-3 font-bold">Alasan prioritas</th>
              <th scope="col" className="px-4 py-3 text-right font-bold">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {items.map((item) => {
              const reasons = item.priority_reasons.slice(0, 2)
              const remaining = item.priority_reasons.length - reasons.length

              return (
                <tr
                  key={item.encounter_id}
                  tabIndex={0}
                  onClick={() => onOpen(item)}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      onOpen(item)
                    }
                  }}
                  aria-label={`Buka telaah ${cleanText(item.patient_name ?? item.patient_id)}`}
                  className="cursor-pointer transition hover:bg-blue-50/40 focus-visible:bg-blue-50/40 focus-visible:outline-none"
                >
                  <td className="px-4 py-3 align-top">
                    <PriorityBadge tier={item.latest_tier} score={item.ml_score} compact />
                    {/* Task 5.1 Req 3.4: High-alert indicator badge with AlertTriangle icon */}
                    {(() => {
                      const highAlertCount = item.priority_reasons.filter((r) =>
                        /high[- ]?alert/i.test(r.reason)
                      ).length
                      return highAlertCount > 0 ? (
                        <Badge
                          tone="critical"
                          icon={<TriangleAlert className="size-3.5" aria-hidden="true" />}
                          className="mt-1"
                        >
                          {highAlertCount} high-alert
                        </Badge>
                      ) : null
                    })()}
                  </td>
                  <td className="px-4 py-3 align-top">
                    <PatientIdentity
                      compact
                      name={item.patient_name}
                      patientId={item.patient_id}
                      encounterId={item.encounter_id}
                    />
                  </td>
                  <td className="px-4 py-3 align-top">
                    <p className="text-xs font-semibold text-slate-800">{cleanText(item.ward)}</p>
                    <p className="mt-0.5 text-[10px] text-slate-500">DPJP: {cleanText(item.dpjp_name)}</p>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <WorkflowStatusBadge status={item.workflow_status} />
                  </td>
                  <td className="px-4 py-3 align-top">
                    <SlaIndicator
                      compact
                      hoursElapsed={item.sla_hours_elapsed}
                      tier={item.latest_tier}
                    />
                  </td>
                  <td className="max-w-[280px] px-4 py-3 align-top">
                    <div className="flex flex-wrap gap-1">
                      {reasons.length === 0 ? (
                        <span className="text-[11px] text-slate-500">Belum ada alasan tercatat</span>
                      ) : (
                        reasons.map((reason, index) => (
                          <ReasonChip
                            key={`${item.encounter_id}-reason-${index}`}
                            reason={reason.reason}
                            source={reason.source}
                            tier={item.latest_tier}
                          />
                        ))
                      )}
                      {remaining > 0 && (
                        <Badge tone="neutral">+{remaining} lainnya</Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right align-top">
                    <Button
                      size="sm"
                      variant={item.latest_tier === "HIGH" ? "primary" : "secondary"}
                      loading={claimingId === item.encounter_id}
                      onClick={(event) => {
                        event.stopPropagation()
                        onOpen(item)
                      }}
                    >
                      {live && !item.claimed_by ? "Klaim & buka" : "Buka telaah"}
                    </Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function WorklistCard({
  item,
  live,
  claiming,
  onOpen,
}: {
  item: WorklistItemV1
  live: boolean
  claiming: boolean
  onOpen: () => void
}) {
  return (
    <Card className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <PriorityBadge tier={item.latest_tier} score={item.ml_score} />
        <SlaIndicator hoursElapsed={item.sla_hours_elapsed} tier={item.latest_tier} compact />
      </div>

      <PatientIdentity
        name={item.patient_name}
        patientId={item.patient_id}
        encounterId={item.encounter_id}
        ward={item.ward}
        dpjp={item.dpjp_name}
      />

      <div className="flex flex-wrap items-center gap-2">
        <WorkflowStatusBadge status={item.workflow_status} />
        {item.priority_reasons.slice(0, 2).map((reason, index) => (
          <ReasonChip
            key={`${item.encounter_id}-mobile-reason-${index}`}
            reason={reason.reason}
            source={reason.source}
            tier={item.latest_tier}
          />
        ))}
        {item.priority_reasons.length > 2 && (
          <Badge tone="neutral">+{item.priority_reasons.length - 2}</Badge>
        )}
      </div>

      <Button
        className="w-full"
        variant={item.latest_tier === "HIGH" ? "primary" : "secondary"}
        loading={claiming}
        onClick={onOpen}
        iconRight={<ArrowRight className="size-4" />}
      >
        {live && !item.claimed_by ? "Klaim & buka telaah" : "Buka telaah"}
      </Button>
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/* Case workspace                                                             */
/* -------------------------------------------------------------------------- */

export interface CasePageProps {
  item: WorklistItemV1
  onBack: () => void
}

export function CasePage({ item, onBack }: CasePageProps) {
  const [tab, setTab] = useState("findings")
  const [pendingAction, setPendingAction] = useState<ReviewAction | null>(null)
  const [reason, setReason] = useState("")
  const [note, setNote] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [finalStatus, setFinalStatus] = useState<string | null>(null)
  const [rowVersion, setRowVersion] = useState(item.row_version)
  const [highAlertOpen, setHighAlertOpen] = useState(false)
  const [copilotOpen, setCopilotOpen] = useState(false)
  const [sbarCopied, setSbarCopied] = useState(false)
  const [sbar, setSbar] = useState<SbarDraft>(() =>
    buildSbar(item, buildFindings(item)),
  )
  const copyTimer = useRef<number | null>(null)
  const queryClient = useQueryClient()

  const live = DATA_MODE === "live"
  const findings = useMemo(() => buildFindings(item), [item])
  const highAlerts = useMemo(() => buildHighAlerts(item), [item])
  const demo = useMemo(() => findDemoPatient(item), [item])
  const completed = finalStatus ? isTerminalStatus(finalStatus) : isTerminalStatus(item.workflow_status)
  const displayStatus = finalStatus ?? item.workflow_status

  useEffect(() => {
    setTab("findings")
    setFinalStatus(null)
    setFeedback(null)
    setPendingAction(null)
    setReason("")
    setNote("")
    setRowVersion(item.row_version)
    setSbar(buildSbar(item, buildFindings(item)))
  }, [item])

  useEffect(() => {
    return () => {
      if (copyTimer.current) window.clearTimeout(copyTimer.current)
    }
  }, [])

  const historyQuery = useQuery({
    queryKey: ["review-history", item.encounter_id],
    queryFn: () => getReviewHistoryV1(item.encounter_id),
    enabled: live && tab === "history",
    retry: false,
  })

  const historyEntries = useMemo<AuditTimelineEntry[]>(() => {
    const raw = historyQuery.data?.history ?? []
    return raw.map((entry, index) => {
      const record = (entry ?? {}) as Record<string, unknown>
      return {
        id: String(record.audit_entry_id ?? record.id ?? `history-${index}`),
        action: String(record.action ?? record.new_status ?? "DRAFT"),
        actor: record.actor_id
          ? String(record.actor_id)
          : record.actor
            ? String(record.actor)
            : "Sistem",
        actorType: record.actor_type ? String(record.actor_type) : null,
        timestamp: record.created_at
          ? String(record.created_at)
          : record.timestamp
            ? String(record.timestamp)
            : null,
        note: record.reason
          ? String(record.reason)
          : record.note
            ? String(record.note)
            : null,
      }
    })
  }, [historyQuery.data])

  const activeAction = pendingAction ? ACTION_META[pendingAction] : null
  const canSubmit = !activeAction?.requiresReason || reason.trim().length >= 10

  function openAction(action: ReviewAction) {
    if (completed) {
      setFeedback({ tone: "warning", text: "Kasus sudah selesai. Buka kembali dari worklist bila perlu telaah ulang." })
      return
    }

    if (action === "APPROVE" && highAlerts.length > 0) {
      setHighAlertOpen(true)
      return
    }

    setReason("")
    setNote("")
    setPendingAction(action)
  }

  function confirmHighAlert() {
    setHighAlertOpen(false)
    setReason(
      `High-alert diperiksa: ${highAlerts.map((alert) => cleanText(alert.label)).join("; ")}`,
    )
    setNote("")
    setPendingAction("APPROVE")
  }

  async function submitAction() {
    if (!pendingAction || !activeAction) return

    if (!canSubmit) {
      setFeedback({ tone: "warning", text: "Alasan klinis minimal 10 karakter agar dapat diaudit." })
      return
    }

    setSubmitting(true)
    try {
      let nextStatus: string

      if (live) {
        const response = await submitReviewV1(
          item.encounter_id,
          {
            action: pendingAction,
            reason: reason.trim() || undefined,
            note: note.trim() || undefined,
            ai_snapshot: {
              tier: item.latest_tier,
              ml_score: item.ml_score,
              priority_reasons: item.priority_reasons,
            },
          },
          {
            idempotencyKey: `${item.encounter_id}-${pendingAction}-${Date.now()}`,
            ifMatch: rowVersion,
          },
        )
        setRowVersion(response.row_version)
        nextStatus = response.new_workflow_status
        await queryClient.invalidateQueries({ queryKey: ["worklist"] })
        await queryClient.invalidateQueries({
          queryKey: ["review-history", item.encounter_id],
        })
      } else {
        nextStatus =
          pendingAction === "APPROVE"
            ? "SELESAI_APPROVE"
            : pendingAction === "EDIT"
              ? "SELESAI_EDIT"
              : pendingAction === "REJECT"
                ? "DITOLAK"
                : pendingAction === "ESCALATE"
                  ? "ESKALASI"
                  : "DRAFT_TELAAH"
      }

      setFinalStatus(nextStatus)
      setFeedback({
        tone: "success",
        text: `${activeAction.label} tersimpan dan tercatat di jejak audit.`,
      })
      setPendingAction(null)
      setReason("")
      setNote("")
    } catch (error) {
      setFeedback({
        tone: "danger",
        text: `Gagal menyimpan keputusan: ${errorMessage(error)}`,
      })
    } finally {
      setSubmitting(false)
    }
  }

  async function copySbar() {
    const text = [
      `S: ${sbar.situation}`,
      `B: ${sbar.background}`,
      `A: ${sbar.assessment}`,
      `R: ${sbar.recommendation}`,
    ].join("\n")

    try {
      await navigator.clipboard.writeText(text)
      setSbarCopied(true)
      if (copyTimer.current) window.clearTimeout(copyTimer.current)
      copyTimer.current = window.setTimeout(() => setSbarCopied(false), 2000)
    } catch {
      setFeedback({
        tone: "danger",
        text: "Clipboard tidak tersedia di browser ini. Salin SBAR secara manual.",
      })
    }
  }

  const tabs = [
    { id: "findings", label: "Temuan", icon: <ShieldAlert className="size-3.5" />, count: findings.length },
    {
      id: "compare",
      label: "Bandingkan",
      icon: <ClipboardList className="size-3.5" />,
      count: demo?.discrepancies.length ?? item.priority_reasons.length,
    },
    { id: "sbar", label: "SBAR", icon: <Stethoscope className="size-3.5" /> },
    { id: "review", label: "Telaah", icon: <CheckCircle2 className="size-3.5" /> },
    { id: "history", label: "Riwayat", icon: <FileClock className="size-3.5" /> },
  ]

  return (
    <div className="space-y-5">
      <FeedbackBanner feedback={feedback} onClose={() => setFeedback(null)} />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button variant="ghost" size="sm" onClick={onBack} icon={<ArrowLeft className="size-4" />}>
          Kembali ke worklist
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setCopilotOpen(true)}
          icon={<Sparkles className="size-4" />}
        >
          AI Copilot
        </Button>
      </div>

      <Card padded={false} className="overflow-hidden">
        <div className="border-b border-slate-200 bg-gradient-to-r from-slate-50 via-white to-blue-50/50 p-5">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex min-w-0 items-start gap-4">
              <div
                className="hidden size-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-blue-700 font-display text-lg font-extrabold text-white shadow-md sm:flex"
                aria-hidden="true"
              >
                {initials(item.patient_name ?? item.patient_id)}
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="font-display text-xl font-bold tracking-tight text-slate-900">
                    {cleanText(item.patient_name ?? item.patient_id)}
                  </h1>
                  <PriorityBadge tier={item.latest_tier} score={item.ml_score} compact />
                  <WorkflowStatusBadge status={displayStatus} />
                </div>
                <p className="mt-1 font-clinical-mono text-[11px] text-slate-500">
                  {cleanText(item.patient_id)} · {cleanText(item.encounter_id)}
                </p>
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-slate-600">
                  <span className="inline-flex items-center gap-1.5">
                    <UserRound className="size-3.5 text-slate-400" aria-hidden="true" />
                    {cleanText(item.ward)}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Stethoscope className="size-3.5 text-slate-400" aria-hidden="true" />
                    DPJP: {cleanText(item.dpjp_name)}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="size-3.5 text-slate-400" aria-hidden="true" />
                    Admisi {formatDateTime(item.admitted_at)}
                  </span>
                </div>
              </div>
            </div>

            <div className="w-full max-w-sm space-y-3">
              <SlaIndicator
                hoursElapsed={item.sla_hours_elapsed}
                tier={item.latest_tier}
                showBar
              />
              <RiskScoreBar score={item.ml_score} />
            </div>
          </div>
        </div>

        <div className="grid divide-y divide-slate-100 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <div className="p-4">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Alasan utama
            </p>
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-800">
              {cleanText(item.priority_reasons[0]?.reason ?? "Belum ada alasan prioritas.")}
            </p>
          </div>
          <div className="p-4">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Kandidat temuan
            </p>
            <p className="mt-1 font-clinical-mono text-lg font-bold text-slate-900">
              {findings.length}
            </p>
          </div>
          <div className="p-4">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              High-alert
            </p>
            <p
              className={cn(
                "mt-1 font-clinical-mono text-lg font-bold",
                highAlerts.length > 0 ? "text-red-700" : "text-emerald-700",
              )}
            >
              {highAlerts.length}
            </p>
          </div>
        </div>
      </Card>

      <AiDraftNotice />

      <Tabs items={tabs} value={tab} onChange={setTab} ariaLabel="Bagian telaah kasus" />

      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="min-h-[240px]"
      >
        {tab === "findings" && <FindingsPanel findings={findings} />}
        {tab === "compare" && <ComparePanel item={item} demo={demo} />}
        {tab === "sbar" && (
          <SbarPanel
            sbar={sbar}
            onChange={setSbar}
            onCopy={() => void copySbar()}
            copied={sbarCopied}
          />
        )}
        {tab === "review" && (
          <ReviewPanel
            completed={completed}
            pendingAction={pendingAction}
            reason={reason}
            note={note}
            submitting={submitting}
            canSubmit={canSubmit}
            highAlerts={highAlerts}
            onOpenAction={openAction}
            onReasonChange={setReason}
            onNoteChange={setNote}
            onSubmit={() => void submitAction()}
            onCancel={() => setPendingAction(null)}
          />
        )}
        {tab === "history" && (
          <HistoryPanel
            live={live}
            loading={historyQuery.isLoading}
            error={historyQuery.isError}
            entries={historyEntries}
            onRetry={() => void historyQuery.refetch()}
          />
        )}
      </div>

      <div className="sticky bottom-0 z-20 -mx-4 border-t border-slate-200 bg-white/95 px-4 py-3 shadow-[0_-8px_24px_-16px_rgba(15,23,42,0.35)] backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <p className="flex items-center gap-2 text-[11px] leading-relaxed text-slate-500">
            <ShieldCheck className="size-3.5 shrink-0 text-slate-400" aria-hidden="true" />
            Setiap keputusan dicatat di jejak audit bersama versi data.
          </p>

          {completed ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="success" dot>
                Kasus sudah selesai
              </Badge>
              <Button variant="secondary" size="sm" onClick={onBack}>
                Kembali ke worklist
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => { openAction("DRAFT_REVIEW"); setTab("review") }}>
                Simpan draf
              </Button>
              <Button variant="warning" size="sm" onClick={() => { openAction("ESCALATE"); setTab("review") }}>
                Eskalasi
              </Button>
              <Button variant="danger" size="sm" onClick={() => { openAction("REJECT"); setTab("review") }}>
                Tolak
              </Button>
              <Button variant="secondary" size="sm" onClick={() => { openAction("EDIT"); setTab("review") }}>
                Edit & setujui
              </Button>
              <Button
                variant="success"
                size="sm"
                onClick={() => { openAction("APPROVE"); setTab("review") }}
                icon={highAlerts.length > 0 ? <ShieldAlert className="size-4" /> : undefined}
              >
                Setujui
              </Button>
            </div>
          )}
        </div>
      </div>

      <Modal
        open={pendingAction !== null}
        onClose={() => {
          if (!submitting) setPendingAction(null)
        }}
        title={activeAction?.title ?? "Keputusan telaah"}
        description={activeAction?.description}
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setPendingAction(null)}
              disabled={submitting}
            >
              Batal
            </Button>
            <Button
              variant={activeAction?.variant ?? "primary"}
              onClick={() => void submitAction()}
              loading={submitting}
              disabled={!canSubmit}
            >
              {activeAction?.label ?? "Simpan"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {activeAction?.requiresReason && (
            <Field
              label="Alasan klinis"
              htmlFor="review-reason"
              required
              hint="Minimal 10 karakter. Alasan ini masuk ke jejak audit dan dibaca DPJP."
              error={
                reason.length > 0 && reason.trim().length < 10
                  ? "Alasan masih terlalu pendek."
                  : undefined
              }
            >
              <Textarea
                id="review-reason"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                invalid={reason.length > 0 && reason.trim().length < 10}
                placeholder="Contoh: Substitusi antihipertensi belum terdokumentasi dan perlu konfirmasi DPJP."
              />
            </Field>
          )}

          <Field
            label="Catatan untuk tim"
            htmlFor="review-note"
            hint="Opsional. Gunakan untuk informasi tindak lanjut atau monitoring."
          >
            <Textarea
              id="review-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Contoh: Pantau tekanan darah 1 jam setelah dosis pertama."
            />
          </Field>

          <InlineAlert tone="info" title="Dasar keputusan">
            Tindakan ini akan disimpan bersama prioritas, skor model, alasan, dan identitas
            apoteker. Sistem tidak mengubah terapi secara otomatis.
          </InlineAlert>
          {/* Task 8.1 Req 6.6: Safety disclaimer */}
          <InlineAlert tone="warning" title="Keputusan final apoteker">
            Keputusan apoteker bersifat final. Output AI bersifat advisori saja.
          </InlineAlert>
          {/* Task 8.1 Req 7.1-7.5: Escalation sub-form */}
          {pendingAction === "ESCALATE" && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-amber-800">Form Eskalasi</p>
              <Field
                label="Alasan eskalasi"
                htmlFor="escalation-reason"
                required
                hint="Jelaskan mengapa kasus ini perlu dieskalasi ke DPJP."
              >
                <Textarea
                  id="escalation-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Contoh: Diperlukan keputusan dokter untuk perubahan terapi antihipertensi."
                />
              </Field>
              <Field
                label="Penerima eskalasi"
                htmlFor="escalation-recipient"
                hint="Opsional. Biarkan kosong untuk eskalasi otomatis ke DPJP."
              >
                <Select id="escalation-recipient">
                  <option value="">DPJP (otomatis)</option>
                  <option value="senior_pharmacist">Apoteker senior</option>
                  <option value="coordinator">Koordinator farmasi</option>
                </Select>
              </Field>
            </div>
          )}
        </div>
      </Modal>

      <HighAlertDialog
        open={highAlertOpen}
        items={highAlerts}
        onCancel={() => setHighAlertOpen(false)}
        onConfirm={confirmHighAlert}
      />

      <CopilotDrawer
        encounterId={item.encounter_id}
        isOpen={copilotOpen}
        onClose={() => setCopilotOpen(false)}
      />
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Panel tab                                                                  */
/* -------------------------------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/* ReviewPanel — tab telaah keputusan (Req 4.1, 6.1–6.7, 7.1–7.5)          */
/* -------------------------------------------------------------------------- */

interface ReviewPanelProps {
  completed: boolean
  pendingAction: ReviewAction | null
  reason: string
  note: string
  submitting: boolean
  canSubmit: boolean
  highAlerts: HighAlertItem[]
  onOpenAction: (action: ReviewAction) => void
  onReasonChange: (value: string) => void
  onNoteChange: (value: string) => void
  onSubmit: () => void
  onCancel: () => void
}

function ReviewPanel({
  completed,
  pendingAction,
  reason,
  note,
  submitting,
  canSubmit,
  highAlerts,
  onOpenAction,
  onReasonChange,
  onNoteChange,
  onSubmit,
  onCancel,
}: ReviewPanelProps) {
  const activeAction = pendingAction ? ACTION_META[pendingAction] : null

  if (completed) {
    return (
      <InlineAlert tone="success" title="Kasus sudah selesai">
        Keputusan telaah telah disimpan dan tercatat di jejak audit.
      </InlineAlert>
    )
  }

  return (
    <div className="space-y-4">
      {/* Req 6.6: Safety disclaimer */}
      <InlineAlert tone="warning" title="Keputusan final apoteker">
        Keputusan apoteker bersifat final. Output AI bersifat advisori saja.
      </InlineAlert>

      {/* Req 6.1: Four decision buttons */}
      {!pendingAction && (
        <Card className="space-y-4">
          <h2 className="font-display text-sm font-bold text-slate-900">Pilih tindakan telaah</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {(["APPROVE", "REJECT", "EDIT", "ESCALATE"] as ReviewAction[]).map((action) => {
              const meta = ACTION_META[action]
              return (
                <button
                  key={action}
                  type="button"
                  onClick={() => onOpenAction(action)}
                  className={cn(
                    "flex flex-col items-start rounded-xl border-2 p-4 text-left transition",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2",
                    "min-h-[44px]",
                    action === "APPROVE" && "border-emerald-200 bg-emerald-50 hover:border-emerald-400 hover:bg-emerald-100",
                    action === "REJECT"  && "border-red-200 bg-red-50 hover:border-red-400 hover:bg-red-100",
                    action === "EDIT"    && "border-blue-200 bg-blue-50 hover:border-blue-400 hover:bg-blue-100",
                    action === "ESCALATE" && "border-amber-200 bg-amber-50 hover:border-amber-400 hover:bg-amber-100",
                  )}
                >
                  <span className="font-display text-sm font-bold text-slate-900">{meta.label}</span>
                  <span className="mt-1 text-[11px] leading-relaxed text-slate-600">{meta.description}</span>
                </button>
              )
            })}
          </div>
        </Card>
      )}

      {/* Selected action form */}
      {pendingAction && activeAction && (
        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-display text-sm font-bold text-slate-900">{activeAction.title}</h2>
            <Button variant="ghost" size="sm" onClick={onCancel} disabled={submitting}>
              Ganti tindakan
            </Button>
          </div>

          {/* Escalation sub-form (Req 7.1–7.5) */}
          {pendingAction === "ESCALATE" && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-amber-800">Form Eskalasi</p>
              <Field
                label="Alasan eskalasi"
                htmlFor="review-escalation-reason"
                required
                hint="Jelaskan mengapa kasus ini perlu dieskalasi ke DPJP."
              >
                <Textarea
                  id="review-escalation-reason"
                  value={reason}
                  onChange={(event) => onReasonChange(event.target.value)}
                  placeholder="Contoh: Diperlukan keputusan dokter untuk perubahan terapi antihipertensi."
                />
              </Field>
              <Field
                label="Penerima eskalasi"
                htmlFor="review-escalation-recipient"
                hint="Opsional. Biarkan kosong untuk eskalasi otomatis ke DPJP."
              >
                <Select id="review-escalation-recipient">
                  <option value="">DPJP (otomatis)</option>
                  <option value="senior_pharmacist">Apoteker senior</option>
                  <option value="coordinator">Koordinator farmasi</option>
                </Select>
              </Field>
            </div>
          )}

          {/* Required reason for REJECT/EDIT/ESCALATE */}
          {activeAction.requiresReason && pendingAction !== "ESCALATE" && (
            <Field
              label="Alasan klinis"
              htmlFor="review-tab-reason"
              required
              hint="Minimal 10 karakter. Alasan ini masuk ke jejak audit dan dibaca DPJP."
              error={
                reason.length > 0 && reason.trim().length < 10
                  ? "Alasan masih terlalu pendek."
                  : undefined
              }
            >
              <Textarea
                id="review-tab-reason"
                value={reason}
                onChange={(event) => onReasonChange(event.target.value)}
                invalid={reason.length > 0 && reason.trim().length < 10}
                placeholder="Contoh: Substitusi antihipertensi belum terdokumentasi dan perlu konfirmasi DPJP."
              />
            </Field>
          )}

          {/* Optional note for all actions */}
          <Field
            label="Catatan untuk tim"
            htmlFor="review-tab-note"
            hint="Opsional. Gunakan untuk informasi tindak lanjut atau monitoring."
          >
            <Textarea
              id="review-tab-note"
              value={note}
              onChange={(event) => onNoteChange(event.target.value)}
              placeholder="Contoh: Pantau tekanan darah 1 jam setelah dosis pertama."
            />
          </Field>

          <InlineAlert tone="info" title="Dasar keputusan">
            Tindakan ini akan disimpan bersama prioritas, skor model, alasan, dan identitas
            apoteker. Sistem tidak mengubah terapi secara otomatis.
          </InlineAlert>

          <div className="flex flex-wrap gap-2">
            <Button
              variant={activeAction.variant}
              onClick={onSubmit}
              loading={submitting}
              disabled={!canSubmit}
              className="min-h-11"
            >
              {activeAction.label}
            </Button>
            <Button variant="secondary" onClick={onCancel} disabled={submitting} className="min-h-11">
              Batal
            </Button>
          </div>
        </Card>
      )}

      {/* High-alert notice */}
      {highAlerts.length > 0 && (
        <InlineAlert tone="critical" title={`${highAlerts.length} obat high-alert teridentifikasi`}>
          Konfirmasi setiap obat high-alert sebelum menyetujui. Klik Setujui untuk memunculkan dialog konfirmasi.
        </InlineAlert>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* FindingsPanel                                                              */
/* -------------------------------------------------------------------------- */

function FindingsPanel({ findings }: { findings: Finding[] }) {
  const [showTier3, setShowTier3] = useState(false)
  const tier1 = findings.filter((finding) => finding.tier === 1)
  const tier2 = findings.filter((finding) => finding.tier === 2)
  const tier3 = findings.filter((finding) => finding.tier === 3)

  if (findings.length === 0) {
    return (
      <EmptyState
        icon={<CheckCircle2 className="size-5" />}
        title="Tidak ada kandidat temuan"
        description="Mesin prioritas tidak menandai diskrepansi obat pada kasus ini. Tetap lakukan verifikasi klinis sesuai kebijakan."
      />
    )
  }

  return (
    <div className="space-y-5">
      {/* Req 17.1: AiDraftNotice for discrepancy flags */}
      <AiDraftNotice detail="Temuan berikut dihasilkan oleh model AI dan aturan klinis. Setiap temuan wajib diverifikasi apoteker sebelum tindakan diambil." />

      {tier1.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-sm font-bold text-slate-900">Perlu perhatian segera</h2>
            <Badge tone="critical">{tier1.length}</Badge>
          </div>
          {tier1.map((finding) => (
            <FindingCard key={finding.id} {...finding} />
          ))}
        </section>
      )}

      {tier2.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-sm font-bold text-slate-900">Perlu verifikasi</h2>
            <Badge tone="warning">{tier2.length}</Badge>
          </div>
          {tier2.map((finding) => (
            <FindingCard key={finding.id} {...finding} />
          ))}
        </section>
      )}

      {tier3.length > 0 && (
        <section className="space-y-3">
          <button
            type="button"
            onClick={() => setShowTier3((current) => !current)}
            className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-3 text-left transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
            aria-expanded={showTier3}
          >
            <span className="flex items-center gap-2">
              <span className="font-display text-sm font-bold text-slate-900">
                Informasi tambahan
              </span>
              <Badge tone="neutral">{tier3.length}</Badge>
            </span>
            <ChevronDown
              className={cn("size-4 text-slate-500 transition", showTier3 && "rotate-180")}
              aria-hidden="true"
            />
          </button>
          {showTier3 && (
            <div className="space-y-3">
              {tier3.map((finding) => (
                <FindingCard key={finding.id} {...finding} />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}

function ComparePanel({ item, demo }: { item: WorklistItemV1; demo: Patient | undefined }) {
  if (demo && demo.discrepancies.length > 0) {
    return (
      <Card padded={false} className="overflow-hidden">
        <div className="border-b border-slate-200 p-4">
          <h2 className="font-display text-sm font-bold text-slate-900">
            Obat rumah vs order admisi
          </h2>
          <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">
            Kandidat diskrepansi dari pencocokan BPMH. Status awal selalu perlu konfirmasi
            apoteker.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3 font-bold">Obat</th>
                <th scope="col" className="px-4 py-3 font-bold">Obat rumah</th>
                <th scope="col" className="px-4 py-3 font-bold">Order admisi</th>
                <th scope="col" className="px-4 py-3 font-bold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {demo.discrepancies.map((discrepancy) => (
                <tr key={discrepancy.id} className="align-top">
                  <td className="px-4 py-3">
                    <p className="text-xs font-semibold text-slate-900">
                      {cleanText(discrepancy.medication)}
                    </p>
                    <p className="mt-0.5 text-[10px] text-slate-500">
                      {DISCREPANCY_LABEL[discrepancy.type]}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-700">{cleanText(discrepancy.home)}</td>
                  <td className="px-4 py-3 text-xs text-slate-700">
                    {cleanText(discrepancy.admission)}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={discrepancy.status === "Terkonfirmasi" ? "success" : "warning"}>
                      {cleanText(discrepancy.status)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="border-t border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-[10px] leading-relaxed text-slate-500">
            Data ini adalah kandidat, bukan keputusan final. Konfirmasi ke DPJP sebelum mengubah
            terapi.
          </p>
        </div>
      </Card>
    )
  }

  if (item.priority_reasons.length === 0) {
    return (
      <EmptyState
        icon={<ClipboardList className="size-5" />}
        title="Belum ada data perbandingan"
        description="Worklist tidak memuat rincian order obat. Buka modul BPMH untuk melengkapi data sebelum membandingkan."
      />
    )
  }

  return (
    <Card padded={false} className="overflow-hidden">
      <div className="border-b border-slate-200 p-4">
        <h2 className="font-display text-sm font-bold text-slate-900">Alasan prioritas</h2>
        <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">
          Rincian order obat tidak tersedia di worklist. Berikut alasan yang dikirim mesin
          prioritas.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
            <tr>
              <th scope="col" className="px-4 py-3 font-bold">Sumber</th>
              <th scope="col" className="px-4 py-3 font-bold">Alasan</th>
              <th scope="col" className="px-4 py-3 font-bold">Tier</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {item.priority_reasons.map((reason, index) => (
              <tr key={`${item.encounter_id}-compare-${index}`} className="align-top">
                <td className="px-4 py-3">
                  <SourceTag source={reason.source} />
                </td>
                <td className="px-4 py-3 text-xs text-slate-700">{cleanText(reason.reason)}</td>
                <td className="px-4 py-3">
                  <Badge
                    tone={
                      reason.tier === "HIGH"
                        ? "critical"
                        : reason.tier === "MEDIUM"
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {reason.tier}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function SbarPanel({
  sbar,
  onChange,
  onCopy,
  copied,
}: {
  sbar: SbarDraft
  onChange: (value: SbarDraft) => void
  onCopy: () => void
  copied: boolean
}) {
  function update(field: keyof SbarDraft, value: string) {
    onChange({ ...sbar, [field]: value })
  }

  return (
    <div className="space-y-4">
      <AiDraftNotice detail="Susun SBAR sebagai bahan komunikasi ke DPJP. Edit dulu agar sesuai kondisi pasien sebelum dikirim." />
      {/* Task 6.1 Req 4.7: SBAR disclaimer about pharmacist verification and DPJP */}
      <InlineAlert tone="warning" title="Wajib diverifikasi">
        Apoteker wajib memverifikasi konten ini. Keputusan terapi akhir tetap berada pada DPJP.
      </InlineAlert>

      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-display text-sm font-bold text-slate-900">SBAR komunikasi klinis</h2>
            <p className="mt-0.5 text-[11px] text-slate-500">
              Situation · Background · Assessment · Recommendation
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={onCopy}
            icon={copied ? <CheckCircle2 className="size-4" /> : <Copy className="size-4" />}
          >
            {copied ? "Tersalin" : "Salin SBAR"}
          </Button>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="S — Situation" htmlFor="sbar-situation" required>
            <Textarea
              id="sbar-situation"
              rows={3}
              value={sbar.situation}
              onChange={(event) => update("situation", event.target.value)}
            />
          </Field>
          <Field label="B — Background" htmlFor="sbar-background" required>
            <Textarea
              id="sbar-background"
              rows={3}
              value={sbar.background}
              onChange={(event) => update("background", event.target.value)}
            />
          </Field>
          <Field label="A — Assessment" htmlFor="sbar-assessment" required>
            <Textarea
              id="sbar-assessment"
              rows={4}
              value={sbar.assessment}
              onChange={(event) => update("assessment", event.target.value)}
            />
          </Field>
          <Field label="R — Recommendation" htmlFor="sbar-recommendation" required>
            <Textarea
              id="sbar-recommendation"
              rows={4}
              value={sbar.recommendation}
              onChange={(event) => update("recommendation", event.target.value)}
            />
          </Field>
        </div>

        <p className="text-[10px] leading-relaxed text-slate-500">
          SBAR tidak dikirim otomatis ke siapa pun. Salin dan komunikasikan melalui kanal resmi
          rumah sakit.
        </p>
      </Card>
    </div>
  )
}

function HistoryPanel({
  live,
  loading,
  error,
  entries,
  onRetry,
}: {
  live: boolean
  loading: boolean
  error: boolean
  entries: AuditTimelineEntry[]
  onRetry: () => void
}) {
  if (!live) {
    return (
      <EmptyState
        icon={<FileClock className="size-5" />}
        title="Riwayat tersedia pada mode data live"
        description="Mode sintetis tidak menyimpan riwayat telaah. Hubungkan aplikasi ke API untuk melihat jejak audit kasus ini."
      />
    )
  }

  if (loading) {
    return (
      <Card className="space-y-4">
        {[0, 1, 2].map((item) => (
          <div key={item} className="flex gap-3">
            <Skeleton className="size-8 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-3 w-64" />
            </div>
          </div>
        ))}
      </Card>
    )
  }

  if (error) {
    return (
      <ErrorState
        title="Riwayat tidak dapat dimuat"
        description="Jejak audit kasus ini belum bisa diambil dari server."
        onRetry={onRetry}
      />
    )
  }

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between gap-2">
        <div>
          <h2 className="font-display text-sm font-bold text-slate-900">Riwayat telaah</h2>
          <p className="mt-0.5 text-[11px] text-slate-500">
            Urutan keputusan dan aktor yang tercatat.
          </p>
        </div>
        <Badge tone="neutral">{entries.length} entri</Badge>
      </div>
      <AuditTimeline entries={entries} />
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/* 404 / halaman tidak ditemukan                                             */
/* -------------------------------------------------------------------------- */

export interface NotFoundStateProps {
  onReturn: () => void
}

/**
 * Keadaan 404 untuk rute halaman yang tidak dikenal. Merender `EmptyState`
 * dari primitives dengan ikon Compass, judul "Halaman tidak ditemukan",
 * deskripsi singkat, dan tombol "Kembali ke Worklist" yang memanggil
 * callback `onReturn`.
 *
 * _Validates: Requirements 9.4_
 */
export function NotFoundState({ onReturn }: NotFoundStateProps) {
  return (
    <EmptyState
      icon={<Compass className="size-5" />}
      title="Halaman tidak ditemukan"
      description="Halaman yang Anda cari tidak tersedia atau telah dipindahkan."
      action={
        <Button variant="secondary" onClick={onReturn}>
          Kembali ke Worklist
        </Button>
      }
    />
  )
}
