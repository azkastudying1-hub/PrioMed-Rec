/*
 * web/src/uiux/clinical.tsx
 * ---------------------------------------------------------------------------
 * Komponen khusus domain klinis: prioritas, SLA, identitas pasien, temuan,
 * label draf AI, jejak audit, dan hard-stop high-alert.
 *
 * Aturan yang dijaga di sini:
 *  - HIGH / MEDIUM / LOW selalu tampil sebagai ikon + teks, bukan warna saja.
 *  - Target SLA mengikuti keputusan proyek: HIGH 4 jam, MEDIUM 12 jam,
 *    LOW 24 jam (warning 2 / 6 / 12 jam).
 *  - Teks AI selalu membawa label "Draf AI - wajib diverifikasi apoteker".
 *  - High-alert tidak bisa disetujui tanpa centang eksplisit per temuan.
 */

import { useEffect, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  CircleAlert,
  CircleCheck,
  Clock,
  FileClock,
  FileText,
  Info,
  Pencil,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  UserRound,
  XCircle,
} from "lucide-react"
import type { RiskLevel } from "../types/clinical"
import {
  Badge,
  Button,
  Card,
  InlineAlert,
  Modal,
  cn,
  cleanText,
  type Tone,
} from "./primitives"

/* -------------------------------------------------------------------------- */
/* SLA                                                                        */
/* -------------------------------------------------------------------------- */

export const SLA_TARGETS: Record<RiskLevel, { targetHours: number; warningHours: number }> = {
  HIGH: { targetHours: 4, warningHours: 2 },
  MEDIUM: { targetHours: 12, warningHours: 6 },
  LOW: { targetHours: 24, warningHours: 12 },
}

export function slaTargetHours(tier: RiskLevel | null | undefined): number | null {
  return tier ? SLA_TARGETS[tier].targetHours : null
}

export function isSlaBreached(
  hoursElapsed: number | null | undefined,
  tier: RiskLevel | null | undefined,
): boolean {
  if (hoursElapsed == null || !tier) return false
  return hoursElapsed >= SLA_TARGETS[tier].targetHours
}

export function formatDuration(hours: number): string {
  const totalMinutes = Math.max(0, Math.round(hours * 60))
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  if (h <= 0) return `${m} mnt`
  return `${h} j ${m} mnt`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return cleanText(value)
  return new Intl.DateTimeFormat("id-ID", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}

export interface SlaIndicatorProps {
  hoursElapsed: number | null | undefined
  tier: RiskLevel | null | undefined
  compact?: boolean
  showBar?: boolean
  className?: string
}

export function SlaIndicator({
  hoursElapsed,
  tier,
  compact = false,
  showBar = false,
  className,
}: SlaIndicatorProps) {
  if (hoursElapsed == null || !tier) {
    return <span className="text-xs text-slate-500">SLA belum tersedia</span>
  }

  const { targetHours, warningHours } = SLA_TARGETS[tier]
  const remaining = targetHours - hoursElapsed
  const breached = remaining <= 0
  const warning = !breached && hoursElapsed >= warningHours
  const ratio = Math.min(Math.max(hoursElapsed / targetHours, 0), 1)

  const tone = breached
    ? "border-red-200 bg-red-50 text-red-900"
    : warning
      ? "border-amber-200 bg-amber-50 text-amber-900"
      : "border-slate-200 bg-slate-50 text-slate-700"
  const barTone = breached ? "bg-red-600" : warning ? "bg-amber-500" : "bg-teal-600"
  const Icon = breached ? TriangleAlert : warning ? Clock : CheckCircle2
  const label = breached
    ? `Lewat SLA ${formatDuration(-remaining)}`
    : `Sisa ${formatDuration(remaining)}`

  return (
    <div className={cn("min-w-0", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-clinical-mono text-[11px] font-semibold",
          tone,
        )}
        title={`Target SLA ${targetHours} jam. Warning pada ${warningHours} jam.`}
      >
        <Icon className="size-3.5 shrink-0" aria-hidden="true" />
        {label}
      </span>
      {showBar && (
        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-200" aria-hidden="true">
          <div
            className={cn("h-full rounded-full transition-all", barTone)}
            style={{ width: `${Math.max(ratio * 100, 4)}%` }}
          />
        </div>
      )}
      {!compact && (
        <p className="mt-1 text-[11px] text-slate-500">
          Target {targetHours} jam · {formatDuration(hoursElapsed)} berjalan
        </p>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Prioritas & status                                                         */
/* -------------------------------------------------------------------------- */

const tierMeta: Record<
  RiskLevel,
  { label: string; shortLabel: string; tone: Tone; Icon: typeof AlertTriangle }
> = {
  HIGH: { label: "Prioritas tinggi", shortLabel: "TINGGI", tone: "critical", Icon: AlertTriangle },
  MEDIUM: { label: "Prioritas sedang", shortLabel: "SEDANG", tone: "warning", Icon: CircleAlert },
  LOW: { label: "Prioritas rendah", shortLabel: "RENDAH", tone: "success", Icon: CircleCheck },
}

export interface PriorityBadgeProps {
  tier: RiskLevel | null | undefined
  score?: number | null
  compact?: boolean
  className?: string
}

export function PriorityBadge({ tier, score, compact = false, className }: PriorityBadgeProps) {
  if (!tier) {
    return (
      <Badge tone="neutral" dot className={className}>
        Belum dinilai
      </Badge>
    )
  }

  const meta = tierMeta[tier]
  const Icon = meta.Icon
  const percent =
    score == null ? null : Math.round((score <= 1 ? score * 100 : score) * 10) / 10

  return (
    <div className={cn("flex flex-col items-start gap-1", className)}>
      <Badge tone={meta.tone} icon={<Icon className="size-3.5" aria-hidden="true" />}>
        {/* Task 5.1 Req 3.3: Explicit short labels in compact mode */}
        {compact ? meta.shortLabel : meta.label}
      </Badge>
      {percent != null && (
        <span
          className="font-clinical-mono text-[10px] text-slate-500"
          title="Probabilitas diskrepansi dari model ML. Bukan diagnosis."
        >
          ML {percent}%
        </span>
      )}
    </div>
  )
}

const workflowMeta: Record<string, { label: string; tone: Tone }> = {
  MENUNGGU_BPMH: { label: "Menunggu BPMH", tone: "neutral" },
  BPMH_LENGKAP: { label: "BPMH lengkap", tone: "info" },
  DALAM_ANALISIS: { label: "Dalam analisis", tone: "info" },
  MENUNGGU_TELAAH: { label: "Menunggu telaah", tone: "warning" },
  DRAFT_TELAAH: { label: "Draf telaah", tone: "neutral" },
  DRAFT_REVIEW: { label: "Draf telaah", tone: "neutral" },
  SELESAI_DISETUJUI: { label: "Disetujui", tone: "success" },
  SELESAI_DIEDIT: { label: "Diedit & disetujui", tone: "success" },
  SELESAI_APPROVE: { label: "Disetujui", tone: "success" },
  SELESAI_EDIT: { label: "Diedit & disetujui", tone: "success" },
  APPROVED: { label: "Disetujui", tone: "success" },
  DISETUJUI: { label: "Disetujui", tone: "success" },
  DITOLAK: { label: "Ditolak", tone: "danger" },
  REJECTED: { label: "Ditolak", tone: "danger" },
  ESKALASI: { label: "Eskalasi", tone: "warning" },
  RETRIAGE: { label: "Retriage", tone: "neutral" },
  SIAP_DIANALISIS: { label: "Siap dianalisis", tone: "info" },
  PERLU_VERIFIKASI: { label: "Perlu verifikasi", tone: "warning" },
}

function normalizeStatus(status: string) {
  return status.trim().toUpperCase().replace(/[\s-]+/g, "_")
}

export function WorkflowStatusBadge({
  status,
  className,
}: {
  status: string
  className?: string
}) {
  const key = normalizeStatus(status)
  const meta = workflowMeta[key] ?? { label: cleanText(status), tone: "neutral" as Tone }
  return (
    <Badge tone={meta.tone} dot className={className}>
      {meta.label}
    </Badge>
  )
}

export function isTerminalStatus(status: string): boolean {
  const key = normalizeStatus(status)
  return ["SELESAI_APPROVE", "SELESAI_EDIT", "APPROVED", "DISETUJUI", "DITOLAK", "REJECTED"].includes(key)
}

/* -------------------------------------------------------------------------- */
/* Identitas pasien                                                           */
/* -------------------------------------------------------------------------- */

export function initials(value: string | null | undefined): string {
  const cleaned = (value ?? "").replace(/pasien\s*#?/i, "").trim()
  if (!cleaned) return "?"
  const parts = cleaned.split(/\s+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

export interface PatientIdentityProps {
  name: string | null | undefined
  patientId: string
  encounterId?: string | null
  ward?: string | null
  dpjp?: string | null
  admittedAt?: string | null
  compact?: boolean
  className?: string
}

export function PatientIdentity({
  name,
  patientId,
  encounterId,
  ward,
  dpjp,
  admittedAt,
  compact = false,
  className,
}: PatientIdentityProps) {
  const displayName = cleanText(name ?? patientId)

  return (
    <div className={cn("flex min-w-0 items-start gap-3", className)}>
      <div
        className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-teal-500 to-blue-700 font-display text-[11px] font-extrabold text-white shadow-sm"
        aria-hidden="true"
      >
        {initials(displayName)}
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-slate-900">{displayName}</p>
        <p className="truncate font-clinical-mono text-[10px] text-slate-500">
          {cleanText(patientId)}
          {encounterId ? ` · ${cleanText(encounterId)}` : ""}
        </p>
        {!compact && (ward || dpjp || admittedAt) && (
          <div className="mt-2 grid gap-1 text-[11px] text-slate-600">
            {ward && (
              <span className="inline-flex items-center gap-1.5">
                <UserRound className="size-3 text-slate-400" aria-hidden="true" />
                {cleanText(ward)}
              </span>
            )}
            {dpjp && <span>DPJP: {cleanText(dpjp)}</span>}
            {admittedAt && (
              <span className="inline-flex items-center gap-1.5">
                <Clock className="size-3 text-slate-400" aria-hidden="true" />
                Admisi {formatDateTime(admittedAt)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* KPI                                                                        */
/* -------------------------------------------------------------------------- */

const kpiTones: Record<Tone, { border: string; icon: string; value: string }> = {
  neutral: { border: "border-l-slate-300", icon: "text-slate-400", value: "text-slate-900" },
  info: { border: "border-l-blue-500", icon: "text-blue-500", value: "text-blue-900" },
  success: { border: "border-l-emerald-500", icon: "text-emerald-500", value: "text-emerald-900" },
  warning: { border: "border-l-amber-500", icon: "text-amber-500", value: "text-amber-900" },
  danger: { border: "border-l-red-500", icon: "text-red-500", value: "text-red-900" },
  critical: { border: "border-l-red-600", icon: "text-red-600", value: "text-red-900" },
  teal: { border: "border-l-teal-500", icon: "text-teal-500", value: "text-teal-900" },
}

export interface KpiCardProps {
  label: string
  value: string | number
  hint?: string
  tone?: Tone
  icon?: ReactNode
}

export function KpiCard({ label, value, hint, tone = "neutral", icon }: KpiCardProps) {
  const styles = kpiTones[tone]
  return (
    <Card padded={false} className={cn("border-l-4 p-4", styles.border)}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</p>
        {icon && (
          <span className={cn("shrink-0", styles.icon)} aria-hidden="true">
            {icon}
          </span>
        )}
      </div>
      <p className={cn("mt-1 font-clinical-mono text-2xl font-bold leading-tight", styles.value)}>
        {value}
      </p>
      {hint && <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{hint}</p>}
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/* Alasan & temuan                                                           */
/* -------------------------------------------------------------------------- */

function sourceMeta(source: string | null | undefined) {
  const key = (source ?? "").trim().toUpperCase()
  if (key === "ML") return { label: "ML", text: "text-blue-700" }
  if (key === "SLA") return { label: "SLA", text: "text-teal-700" }
  if (key === "RULE" || key === "RULES" || key === "ATURAN") {
    return { label: "Aturan", text: "text-amber-700" }
  }
  return { label: key || "SISTEM", text: "text-slate-500" }
}

export function SourceTag({
  source,
  className,
}: {
  source: string | null | undefined
  className?: string
}) {
  const meta = sourceMeta(source)
  return (
    <span
      className={cn(
        "shrink-0 font-clinical-mono text-[9px] font-bold uppercase tracking-wider",
        meta.text,
        className,
      )}
      title={`Sumber alasan: ${meta.label}`}
    >
      {meta.label}
    </span>
  )
}

export interface ReasonChipProps {
  reason: string
  source?: string | null
  tier?: RiskLevel | null
  className?: string
}

export function ReasonChip({ reason, source, tier, className }: ReasonChipProps) {
  const tone =
    tier === "HIGH"
      ? "border-red-200 bg-red-50 text-red-900"
      : tier === "MEDIUM"
        ? "border-amber-200 bg-amber-50 text-amber-900"
        : "border-slate-200 bg-slate-50 text-slate-700"

  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 text-[11px]",
        tone,
        className,
      )}
      title={cleanText(reason)}
    >
      <SourceTag source={source} />
      <span className="truncate">{cleanText(reason)}</span>
    </span>
  )
}

export type FindingTier = 1 | 2 | 3

const findingTones: Record<
  FindingTier,
  { card: string; icon: string; label: string; badge: Tone; Icon: typeof AlertTriangle }
> = {
  1: {
    card: "border-red-200 bg-red-50/50",
    icon: "text-red-600",
    label: "Perlu perhatian segera",
    badge: "critical",
    Icon: ShieldAlert,
  },
  2: {
    card: "border-amber-200 bg-amber-50/50",
    icon: "text-amber-600",
    label: "Perlu verifikasi",
    badge: "warning",
    Icon: AlertTriangle,
  },
  3: {
    card: "border-slate-200 bg-slate-50/60",
    icon: "text-slate-500",
    label: "Informasi tambahan",
    badge: "neutral",
    Icon: Info,
  },
}

export interface FindingCardProps {
  tier: FindingTier
  title: string
  source?: string | null
  why: string
  action: string
  home?: string
  admission?: string
}

export function FindingCard({
  tier,
  title,
  source,
  why,
  action,
  home,
  admission,
}: FindingCardProps) {
  const meta = findingTones[tier]
  const Icon = meta.Icon

  return (
    <Card padded={false} className={cn("overflow-hidden border", meta.card)}>
      <div className="flex items-start gap-3 p-4">
        <span className={cn("mt-0.5 shrink-0", meta.icon)} aria-hidden="true">
          <Icon className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900">{cleanText(title)}</h3>
            <Badge tone={meta.badge}>Tier {tier}</Badge>
            <SourceTag source={source} />
          </div>
          <p className="mt-0.5 text-[11px] font-medium text-slate-500">{meta.label}</p>

          {(home || admission) && (
            <div className="mt-3 grid gap-2 rounded-lg border border-white/70 bg-white/80 p-3 text-xs sm:grid-cols-2">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Obat rumah
                </p>
                <p className="mt-0.5 text-slate-800">{cleanText(home)}</p>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Order admisi
                </p>
                <p className="mt-0.5 text-slate-800">{cleanText(admission)}</p>
              </div>
            </div>
          )}

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Mengapa ditandai
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-slate-700">{cleanText(why)}</p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                Yang perlu dilakukan
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-slate-700">{cleanText(action)}</p>
            </div>
          </div>
        </div>
      </div>
    </Card>
  )
}

/* -------------------------------------------------------------------------- */
/* Label AI & keselamatan                                                     */
/* -------------------------------------------------------------------------- */

export function AiDraftNotice({
  source = "template",
  detail,
}: {
  source?: string
  detail?: string
}) {
  const sourceLabel =
    source === "template"
      ? "Draf otomatis (template)"
      : source === "langflow" || source === "llm"
        ? "Draf AI (LLM)"
        : "Draf AI"

  return (
    <InlineAlert
      tone="warning"
      icon={<Sparkles className="size-4" />}
      title={`${sourceLabel} — wajib diverifikasi apoteker`}
    >
      {detail ??
        "Teks ini disusun sistem sebagai bahan telaah. Keputusan akhir, termasuk menambah atau mengubah terapi, tetap milik apoteker dan DPJP."}
    </InlineAlert>
  )
}

export function SafetyBanner({ compact = false }: { compact?: boolean }) {
  return (
    <InlineAlert
      tone="info"
      icon={<ShieldCheck className="size-4" />}
      title="Keputusan klinis tetap di tangan apoteker"
      className={compact ? "py-2.5" : undefined}
    >
      Sistem memprioritaskan kasus dan menandai kandidat diskrepansi. Sistem tidak mendiagnosis
      dan tidak menggantikan penilaian profesional.
    </InlineAlert>
  )
}

/* -------------------------------------------------------------------------- */
/* Skor ML                                                                    */
/* -------------------------------------------------------------------------- */

export interface RiskScoreBarProps {
  score: number | null | undefined
  showCaption?: boolean
  className?: string
}

export function RiskScoreBar({ score, showCaption = true, className }: RiskScoreBarProps) {
  if (score == null) {
    return <p className="text-[11px] text-slate-500">Skor ML belum tersedia.</p>
  }

  const percent = Math.min(Math.max(score <= 1 ? score * 100 : score, 0), 100)

  return (
    <div className={cn("min-w-0", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
          Probabilitas diskrepansi
        </span>
        <span className="font-clinical-mono text-xs font-bold text-slate-800">
          {Math.round(percent)}%
        </span>
      </div>
      <div
        className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-200"
        role="meter"
        aria-label="Probabilitas diskrepansi dari model ML"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-teal-500 to-blue-700"
          style={{ width: `${Math.max(percent, 4)}%` }}
        />
      </div>
      {showCaption && (
        <p className="mt-1 text-[10px] leading-relaxed text-slate-500">
          Skor model untuk membantu urutan telaah, bukan diagnosis.
        </p>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Jejak audit                                                                */
/* -------------------------------------------------------------------------- */

export interface AuditTimelineEntry {
  id: string
  action: string
  actor?: string | null
  actorType?: string | null
  timestamp?: string | null
  note?: string | null
}

const auditMeta: Record<string, { label: string; Icon: typeof CheckCircle2; className: string }> = {
  APPROVE: { label: "Disetujui", Icon: CheckCircle2, className: "bg-emerald-100 text-emerald-700" },
  EDIT: { label: "Diedit & disetujui", Icon: Pencil, className: "bg-blue-100 text-blue-700" },
  REJECT: { label: "Ditolak", Icon: XCircle, className: "bg-red-100 text-red-700" },
  ESCALATE: { label: "Dieskalasi", Icon: TriangleAlert, className: "bg-amber-100 text-amber-700" },
  DRAFT_REVIEW: { label: "Draf disimpan", Icon: FileText, className: "bg-slate-100 text-slate-600" },
  DRAFT: { label: "Draf disimpan", Icon: FileText, className: "bg-slate-100 text-slate-600" },
}

export function AuditTimeline({ entries }: { entries: AuditTimelineEntry[] }) {
  if (entries.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
        <FileClock className="mx-auto size-6 text-slate-400" aria-hidden="true" />
        <p className="mt-2 text-sm font-semibold text-slate-800">Belum ada riwayat telaah</p>
        <p className="mt-1 text-xs text-slate-500">
          Setiap keputusan yang disimpan akan muncul di sini dan di jejak audit.
        </p>
      </div>
    )
  }

  return (
    <ol className="space-y-0">
      {entries.map((entry, index) => {
        const key = (entry.action ?? "").toUpperCase()
        const meta =
          auditMeta[key] ?? {
            label: cleanText(entry.action),
            Icon: FileText,
            className: "bg-slate-100 text-slate-600",
          }
        const Icon = meta.Icon
        return (
          <li key={entry.id} className="relative flex gap-3 pb-5 last:pb-0">
            {index < entries.length - 1 && (
              <span
                className="absolute left-[15px] top-8 h-[calc(100%-1.5rem)] w-px bg-slate-200"
                aria-hidden="true"
              />
            )}
            <span
              className={cn(
                "relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full",
                meta.className,
              )}
              aria-hidden="true"
            >
              <Icon className="size-4" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <p className="text-sm font-semibold text-slate-900">{meta.label}</p>
                <span className="font-clinical-mono text-[10px] text-slate-500">
                  {formatDateTime(entry.timestamp)}
                </span>
              </div>
              <p className="text-[11px] text-slate-500">
                {cleanText(entry.actor ?? "Sistem")}
                {entry.actorType ? ` · ${cleanText(entry.actorType)}` : ""}
              </p>
              {entry.note && (
                <p className="mt-1 rounded-md bg-slate-50 px-2 py-1 text-xs text-slate-700">
                  {cleanText(entry.note)}
                </p>
              )}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

/* -------------------------------------------------------------------------- */
/* Judul bagian                                                               */
/* -------------------------------------------------------------------------- */

export interface SectionHeadingProps {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
  as?: "h1" | "h2"
  className?: string
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  actions,
  as = "h1",
  className,
}: SectionHeadingProps) {
  const Heading = as
  return (
    <div
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow && (
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-700">
            {eyebrow}
          </p>
        )}
        <Heading
          className={cn(
            "font-display font-bold tracking-tight text-slate-900",
            as === "h1" ? "text-xl sm:text-2xl" : "text-lg",
          )}
        >
          {title}
        </Heading>
        {description && (
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-500 sm:text-sm">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Hard stop high-alert                                                       */
/* -------------------------------------------------------------------------- */

export interface HighAlertItem {
  id: string
  label: string
  detail?: string
}

export interface HighAlertDialogProps {
  open: boolean
  items: HighAlertItem[]
  onCancel: () => void
  onConfirm: () => void
}

export function HighAlertDialog({ open, items, onCancel, onConfirm }: HighAlertDialogProps) {
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  useEffect(() => {
    if (open) setChecked({})
  }, [open])

  const allChecked = items.length > 0 && items.every((item) => checked[item.id])

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title="Konfirmasi obat high-alert"
      description="Persetujuan diblokir sampai setiap temuan high-alert diperiksa secara eksplisit."
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            Batal
          </Button>
          <Button variant="danger" disabled={!allChecked} onClick={onConfirm}>
            Saya sudah memeriksa semua
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <InlineAlert
          tone="critical"
          icon={<ShieldAlert className="size-4" />}
          title={`${items.length} temuan high-alert memerlukan konfirmasi`}
        >
          Periksa dosis, rute, frekuensi, interaksi, dan rencana monitoring sebelum menyetujui.
        </InlineAlert>

        <ul className="space-y-2">
          {items.map((item) => {
            const id = `high-alert-${item.id}`
            return (
              <li key={item.id}>
                <label
                  htmlFor={id}
                  className="flex cursor-pointer items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-3 transition hover:bg-red-100/70"
                >
                  <input
                    id={id}
                    type="checkbox"
                    checked={Boolean(checked[item.id])}
                    onChange={(event) =>
                      setChecked((current) => ({ ...current, [item.id]: event.target.checked }))
                    }
                    className="mt-0.5 size-4 shrink-0 rounded border-slate-300 text-red-700 focus:ring-red-500"
                  />
                  <span className="min-w-0">
                    <span className="block text-xs font-bold text-red-900">
                      {cleanText(item.label)}
                    </span>
                    {item.detail && (
                      <span className="mt-0.5 block text-[11px] leading-relaxed text-red-800/80">
                        {cleanText(item.detail)}
                      </span>
                    )}
                  </span>
                </label>
              </li>
            )
          })}
        </ul>

        <p className="text-[11px] leading-relaxed text-slate-500">
          Konfirmasi ini dicatat di jejak audit bersama identitas apoteker, waktu, dan versi data.
        </p>
      </div>
    </Modal>
  )
}

/* -------------------------------------------------------------------------- */
/* Placeholder data klinis                                                    */
/* -------------------------------------------------------------------------- */

/**
 * Tiga kemungkinan ketersediaan data klinis:
 *  - "unavailable"        → data belum pernah diambil ("Belum tersedia")
 *  - "needs_verification"  → data ada tapi perlu konfirmasi apoteker ("Perlu verifikasi")
 *  - "available"           → data lengkap, tampilkan children
 */
export type DataAvailability = "unavailable" | "needs_verification" | "available"

export interface DataPlaceholderProps {
  availability: DataAvailability
  label?: string
  className?: string
  children?: ReactNode
}

/**
 * Placeholder terstandar untuk data klinis yang hilang atau belum lengkap.
 *
 * Aturan:
 *  - "unavailable"       → teks "Belum tersedia" + ikon Info, latar slate-50
 *  - "needs_verification" → teks "Perlu verifikasi" + ikon TriangleAlert, latar amber-50
 *  - "available"         → tampilkan children (tidak ada placeholder)
 *
 * Tidak pernah merender ruang kosong atau container kosong.
 */
export function DataPlaceholder({
  availability,
  label,
  className,
  children,
}: DataPlaceholderProps) {
  // Data tersedia → tampilkan children apa adanya
  if (availability === "available") {
    return <>{children}</>
  }

  const isUnavailable = availability === "unavailable"
  const Icon = isUnavailable ? Info : TriangleAlert
  const text = label ?? (isUnavailable ? "Belum tersedia" : "Perlu verifikasi")

  return (
    <div
      role="status"
      className={cn(
        "flex items-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-medium",
        isUnavailable
          ? "border-slate-200 bg-slate-50 text-slate-600"
          : "border-amber-200 bg-amber-50 text-amber-800",
        className,
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span>{text}</span>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Kontribusi SHAP                                                            */
/* -------------------------------------------------------------------------- */

export interface ShapContribution {
  feature: string
  /** Nilai SHAP: positif = meningkatkan risiko, negatif = menurunkan */
  shap_value: number
  /** Nilai asli fitur (opsional) */
  value?: string
  /** Arah kontribusi: "positive" | "negative" (opsional, diambil dari shap_value jika tidak ada) */
  direction?: string
}

export interface ShapContributionListProps {
  contributions: ShapContribution[]
  modelVersion?: string | null
  ruleVersion?: string | null
  className?: string
}

/**
 * Daftar kontribusi SHAP yang diurutkan dengan batang visual menunjukkan
 * magnitudo dan arah kontribusi terhadap skor risiko.
 *
 * - Nilai positif → batang biru memanjang ke kanan (meningkatkan risiko)
 * - Nilai negatif → batang teal memanjang ke kiri (menurunkan risiko)
 * - Nilai numerik ditampilkan dengan font-clinical-mono
 * - Arah ditunjukkan dengan warna DAN label teks ("meningkatkan"/"menurunkan")
 * - AiDraftNotice ditampilkan di atas daftar
 * - Data kosong/null → DataPlaceholder "Belum tersedia"
 * - Data parsial (ada nilai hilang) → DataPlaceholder "Perlu verifikasi"
 * - Versi model dan aturan ditampilkan sebagai label di bawah daftar
 */
export function ShapContributionList({
  contributions,
  modelVersion,
  ruleVersion,
  className,
}: ShapContributionListProps) {
  // Data kosong atau null → belum tersedia
  if (!contributions || contributions.length === 0) {
    return <DataPlaceholder availability="unavailable" />
  }

  // Data parsial (ada entri dengan nilai wajib hilang) → perlu verifikasi
  const hasPartial = contributions.some(
    (c) => c.shap_value == null || !c.feature || c.feature.trim() === "",
  )
  if (hasPartial) {
    return <DataPlaceholder availability="needs_verification" />
  }

  const maxAbsValue = Math.max(...contributions.map((c) => Math.abs(c.shap_value)), 0)
  // Hindari pembagian dengan nol
  const safeMax = maxAbsValue > 0 ? maxAbsValue : 1

  return (
    <div className={cn("space-y-3", className)}>
      <AiDraftNotice />

      <div role="list" aria-label="Daftar kontribusi SHAP">
        {contributions.map((contribution, index) => {
          const isPositive =
            contribution.direction === "negative"
              ? false
              : contribution.direction === "positive"
                ? true
                : contribution.shap_value >= 0
          const directionLabel = isPositive ? "meningkatkan" : "menurunkan"
          const barWidth = Math.min(Math.abs(contribution.shap_value) / safeMax, 1) * 48
          const formattedValue = contribution.shap_value.toFixed(3)

          return (
            <div
              key={`${contribution.feature}-${index}`}
              role="listitem"
              className="flex items-center gap-3 py-1"
            >
              {/* Nama fitur (kiri) */}
              <span className="w-28 shrink-0 truncate text-xs font-medium text-slate-700 sm:w-40">
                {cleanText(contribution.feature)}
              </span>

              {/* Area batang (terpusat di nol) */}
              <div className="relative h-5 flex-1">
                {/* Garis tengah */}
                <div
                  className="absolute left-1/2 top-0 h-full w-px bg-slate-200"
                  aria-hidden="true"
                />
                {/* Batang kontribusi */}
                <div
                  className={cn(
                    "absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full",
                    isPositive ? "bg-blue-600" : "bg-teal-600",
                  )}
                  style={
                    isPositive
                      ? { left: "50%", width: `${barWidth}%` }
                      : { right: "50%", width: `${barWidth}%` }
                  }
                  role="img"
                  aria-label={`${contribution.feature}: ${directionLabel} risiko, nilai ${formattedValue}`}
                />
              </div>

              {/* Nilai numerik (kanan) */}
              <div className="flex w-28 shrink-0 items-center justify-end gap-2 sm:w-36">
                <span className="text-[10px] font-medium text-slate-500">{directionLabel}</span>
                <span className="font-clinical-mono text-xs font-semibold text-slate-800">
                  {formattedValue}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Label versi model dan aturan */}
      {(modelVersion || ruleVersion) && (
        <div className="flex flex-wrap gap-3 pt-1 text-[10px] text-slate-500">
          {modelVersion && (
            <span className="font-clinical-mono">Model: {cleanText(modelVersion)}</span>
          )}
          {ruleVersion && (
            <span className="font-clinical-mono">Aturan: {cleanText(ruleVersion)}</span>
          )}
        </div>
      )}
    </div>
  )
}
