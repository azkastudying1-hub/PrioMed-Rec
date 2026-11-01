import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  BookOpenCheck,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  FileCheck2,
  MousePointerClick,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { PriorityBadge, SectionHeading } from "../uiux/clinical"
import { Badge, Button, Card, EmptyState, ErrorState, Skeleton } from "../uiux/primitives"
import type { PageId, ViewState } from "../types/clinical"

const steps = [
  {
    number: "01",
    icon: ClipboardList,
    title: "Tinjau Worklist",
    text: "Mulai dari pasien dengan prioritas tertinggi. Baca skor, status alur, dan alasan utama sebelum membuka ringkasan.",
    action: "Buka Worklist",
    page: "worklist" as PageId,
  },
  {
    number: "02",
    icon: ClipboardCheck,
    title: "Lengkapi BPMH",
    text: "Masukkan riwayat obat melalui tabel atau tempel teks. Nama obat wajib; field lain dapat dilengkapi saat verifikasi.",
    action: "Buka Form BPMH",
    page: "bpmh" as PageId,
  },
  {
    number: "03",
    icon: BarChart3,
    title: "Telaah analisis",
    text: "Periksa kontribusi skor, kandidat discrepancy, interaksi, dan sumbernya. Skor bukan keputusan final.",
    action: "Buka Analisis",
    page: "analysis" as PageId,
  },
  {
    number: "04",
    icon: FileCheck2,
    title: "Verifikasi dan putuskan",
    text: "Koreksi draf SBAR, isi rekomendasi apoteker, lalu pilih APPROVE, EDIT, atau REJECT.",
    action: "Lihat Audit Log",
    page: "audit" as PageId,
  },
]

export function TutorialPage({
  viewState,
  onViewState,
  onNavigate,
}: {
  viewState: ViewState
  onViewState: (state: ViewState) => void
  onNavigate: (page: PageId) => void
}) {
  if (viewState === "loading") return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  )
  if (viewState === "error") {
    return <ErrorState description="Tutorial tidak dapat dimuat" onRetry={() => onViewState("ready")} />
  }
  if (viewState === "empty") {
    return (
      <EmptyState
        title="Materi tutorial belum tersedia"
        description="Gunakan data demo untuk melihat panduan penggunaan PrioMed-Rec."
        action={<Button onClick={() => onViewState("ready")}>Tampilkan tutorial</Button>}
      />
    )
  }

  return (
    <div className="space-y-7">
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-[var(--navy)] text-white shadow-sm">
        <div className="grid lg:grid-cols-[1.05fr_0.95fr]">
          <div className="flex flex-col justify-center p-6 md:p-9">
            <Badge tone="teal" className="w-fit">
              <BookOpenCheck className="size-3.5" /> Panduan penggunaan
            </Badge>
            <div role="heading" aria-level={1} className="mt-5 max-w-xl font-['Plus_Jakarta_Sans'] text-3xl font-bold leading-tight tracking-tight md:text-4xl">
              Selesaikan Medication Reconciliation dengan alur yang transparan
            </div>
            <p className="mt-4 max-w-xl text-sm leading-7 text-slate-200 md:text-base">
              Pelajari cara memprioritaskan pasien, menyusun BPMH, memeriksa hasil analisis, dan mendokumentasikan keputusan tanpa menyerahkan keputusan klinis kepada AI.
            </p>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Button
                className="border-cyan-300 bg-cyan-300 text-slate-950 hover:bg-cyan-200"
                icon={<ArrowRight className="size-4" />}
                onClick={() => onNavigate("worklist")}
              >
                Mulai dari Worklist
              </Button>
              <Badge tone="warning">
                <ShieldCheck className="size-3.5" /> Human-in-the-loop wajib
              </Badge>
            </div>
          </div>

          <div className="relative min-h-[24rem] overflow-hidden border-t border-white/10 lg:min-h-full lg:border-l lg:border-t-0">
            <img
              src="/images/tutorial-pharmacy.png"
              loading="lazy"
              width={1200}
              height={800}
              alt="Rak obat yang tertata di area farmasi rumah sakit"
              className="absolute inset-0 size-full origin-top scale-110 object-cover object-center brightness-105 saturate-90 contrast-105"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-[#071A3A]/82 via-[#0A1F44]/18 to-transparent" />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#071A3A]/35" />
            <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-slate-950/70 to-transparent" />

            <div className="absolute left-5 top-5 rounded-xl border border-white/20 bg-[#061A3A]/88 px-4 py-3 shadow-xl shadow-slate-950/25 ring-1 ring-cyan-200/10 backdrop-blur-md md:left-7 md:top-7 md:px-5 md:py-4">
              <div
                role="heading"
                aria-level={2}
                className="font-['Plus_Jakarta_Sans'] text-2xl font-extrabold tracking-tight text-white drop-shadow-md md:text-3xl"
              >
                Prio<span className="text-cyan-300">Med</span>
                <span className="font-semibold text-blue-100">-Rec</span>
              </div>
              <p className="mt-1.5 text-[0.6875rem] font-bold uppercase tracking-[0.18em] text-cyan-100">
                Clinical decision support
              </p>
              <span className="mt-3 block h-0.5 w-12 rounded-full bg-gradient-to-r from-cyan-300 to-blue-400" />
            </div>

            <div className="absolute inset-x-5 bottom-5 rounded-xl border border-white/25 bg-[#071A3A]/88 p-4 text-white shadow-xl backdrop-blur-md md:left-auto md:right-6 md:w-80">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.625rem] font-bold uppercase tracking-[0.14em] text-cyan-200">
                    Pratinjau klinis
                  </p>
                  <p className="mt-1 font-['Plus_Jakarta_Sans'] text-sm font-bold text-white">
                    Ringkasan Pasien #0231
                  </p>
                </div>
                <PriorityBadge tier="HIGH" score={0.87} />
              </div>
              <div className="mt-3 grid grid-cols-3 gap-1.5">
                {[
                  ["Bangsal", "ICU"],
                  ["Usia", "72 th"],
                  ["High-alert", "3 obat"],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-md bg-white/10 p-2 ring-1 ring-white/10">
                    <p className="text-[0.625rem] font-bold uppercase text-blue-100">{label}</p>
                    <p className="mt-1 text-xs font-bold text-white">{value}</p>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center gap-2 border-t border-white/15 pt-3 text-[0.6875rem] font-semibold text-cyan-100">
                <Sparkles className="size-3.5 shrink-0 text-cyan-300" />
                Output sistem wajib diverifikasi apoteker
              </div>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <SectionHeading as="h2" title="Alur penggunaan utama" />
            <p className="mt-1 text-sm text-slate-600">Empat langkah dari antrean pasien hingga dokumentasi keputusan.</p>
          </div>
          <Badge tone="info">Estimasi demo · 5–8 menit per pasien</Badge>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {steps.map((step) => {
            const Icon = step.icon
            return (
              <Card key={step.number} className="flex min-h-72 flex-col border-t-4 border-t-blue-600">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-2xl font-bold text-blue-700">{step.number}</span>
                  <div className="rounded-lg bg-blue-50 p-2.5 text-blue-700"><Icon className="size-5" /></div>
                </div>
                <h3 className="mt-5 text-sm font-bold text-slate-900">{step.title}</h3>
                <p className="mt-2 flex-1 text-sm leading-6 text-slate-600">{step.text}</p>
                <Button className="mt-5 w-full" variant="secondary" icon={<MousePointerClick className="size-4" />} onClick={() => onNavigate(step.page)}>
                  {step.action}
                </Button>
              </Card>
            )
          })}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <h2 className="text-lg font-bold text-slate-900">Cara membaca output sistem</h2>
          <p className="mt-1 text-sm text-slate-600">Tiga jenis output memiliki sumber dan batasan yang berbeda.</p>
          <div className="mt-5 space-y-4">
            {[
              { title: "Skor prioritas", source: "Model ML", text: "Untuk mengurutkan review, bukan menilai kegawatan medis.", kind: "ml" as const },
              { title: "Kandidat ketidaksesuaian", source: "Rule engine", text: "Menunjukkan apa yang perlu dicek, bukan kesalahan pasti.", kind: "rule" as const },
              { title: "Draf SBAR", source: "AI generatif", text: "Meringkas data dan harus diedit sebelum digunakan.", kind: "ai" as const },
            ].map((item) => (
              <div key={item.title} className="grid gap-3 rounded-lg border border-slate-200 p-4 md:grid-cols-[10rem_1fr]">
                <div>
                  <p className="font-bold text-slate-900">{item.title}</p>
                  <p className="mt-1 text-xs text-slate-500">Sumber: {item.source}</p>
                </div>
                <div>
                  <p className="mb-2 text-sm text-slate-600">{item.text}</p>
                  {/* AiDraftNotice instead of legacy VerificationNotice */}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-5">
          <Card className="border-amber-200 bg-amber-50 border">
            <div className="flex gap-3">
              <AlertTriangle className="size-5 shrink-0 text-amber-700" />
              <div>
                <h3 className="text-sm font-bold text-amber-900">Sebelum memilih APPROVE</h3>
                <div className="mt-3 space-y-2">
                  {[
                    "Cocokkan BPMH dengan sumber asli.",
                    "Baca alasan setiap flag dan sitasi.",
                    "Periksa pasangan obat pada referensi institusi.",
                    "Pastikan SBAR sudah dikoreksi apoteker.",
                  ].map((item) => (
                    <div key={item} className="flex items-start gap-2 text-sm text-amber-950">
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> {item}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>

          <Card className="bg-slate-950 text-white">
            <div className="flex items-start gap-3">
              <BadgeCheck className="size-6 shrink-0 text-cyan-300" />
              <div>
                <div role="heading" aria-level={3} className="font-['Plus_Jakarta_Sans'] font-bold">Prinsip utama PrioMed-Rec</div>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  “Kami tidak menggantikan apoteker. Kami membantu mereka mengetahui pasien mana yang diperiksa lebih dulu.”
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
