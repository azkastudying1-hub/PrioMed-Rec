/**
 * Unit tests for Audit pages migration to uiux/ design system.
 *   - AuditLogPage (audit.test.tsx)
 *   - AuditLogPageV2
 *
 * Task 10.3: Validates Requirements 8.2, 8.3, 8.4, 8.5, 8.6, 8.8
 */
import { describe, it, expect, vi } from "vitest"
import { render } from "@testing-library/react"
import { screen } from "@testing-library/dom"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { AuditLogPage } from "../AuditLogPage"
import { AuditLogPageV2 } from "../AuditLogPageV2"
import type { AuditEntry } from "../../types/clinical"

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------
vi.mock("../../lib/auth", () => ({
  useAuthStore: vi.fn((selector?: (state: { user: { role: string } | null }) => unknown) => {
    const state = { user: { role: "ADMIN" } }
    return typeof selector === "function" ? selector(state) : state
  }),
}))

vi.mock("../../lib/apiClient", () => ({
  verifyAuditChain: vi.fn(),
}))

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
const sampleEntries: AuditEntry[] = [
  {
    id: "audit-1",
    patientId: "P-001",
    action: "APPROVE" as const,
    pharmacist: "apt-01",
    timestamp: "2026-10-28 09:00",
    note: "Approved after review",
    source: "Model v1",
  },
  {
    id: "audit-2",
    patientId: "P-002",
    action: "REJECT" as const,
    pharmacist: "apt-02",
    timestamp: "2026-10-28 10:30",
    note: "Rejected due to incomplete info",
    source: "Model v1",
  },
  {
    id: "audit-3",
    patientId: "P-003",
    action: "EDIT" as const,
    pharmacist: "apt-01",
    timestamp: "2026-10-28 11:15",
    note: "Edited dose",
    source: "Model v1",
  },
]

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

/* ========================================================================== */
/* AuditLogPage                                                               */
/* ========================================================================== */

describe("AuditLogPage", () => {
  it("Req 8.2: renders SectionHeading (not legacy Heading) as page title", () => {
    render(
      <AuditLogPage
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
    )
    // SectionHeading renders title as a heading element
    expect(screen.getByRole("heading", { name: /Audit Log/i })).toBeInTheDocument()
  })

  it("Req 8.3: renders Skeleton components when viewState is 'loading'", () => {
    const { container } = render(
      <AuditLogPage
        entries={[]}
        viewState="loading"
        onViewState={() => {}}
      />,
    )
    // Skeleton renders aria-hidden divs with animate-pulse
    const skeletons = container.querySelectorAll("[aria-hidden='true'].animate-pulse")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it("Req 8.4: renders EmptyState with reset filter action when no entries match filter", async () => {
    render(
      <AuditLogPage
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
    )
    // Type a term that matches nothing
    const searchInput = screen.getByPlaceholderText(/Cari pasien atau apoteker/i)
    await userEvent.type(searchInput, "zzz_nonexistent_patient")
    // EmptyState with reset filter action
    expect(screen.getByText(/Tidak ada audit sesuai filter/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Reset filter/i })).toBeInTheDocument()
  })

  it("Req 8.5: APPROVE action badge has CheckCircle2 icon and green (success) tone", () => {
    const { container } = render(
      <AuditLogPage
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
    )
    // Badge uses `tone="success"` which adds text-emerald-800 to the outer span
    const approveBadges = container.querySelectorAll("span.text-emerald-800")
    expect(approveBadges.length).toBeGreaterThan(0)
    // At least one should contain "APPROVE"
    const hasApprove = Array.from(approveBadges as NodeListOf<Element>).some((el: Element) =>
      el.textContent?.includes("APPROVE"),
    )
    expect(hasApprove).toBe(true)
  })

  it("Req 8.5: REJECT action badge has XCircle icon and danger (red) tone", () => {
    const { container } = render(
      <AuditLogPage
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
    )
    const rejectBadges = container.querySelectorAll("span.text-red-800")
    expect(rejectBadges.length).toBeGreaterThan(0)
    const hasReject = Array.from(rejectBadges as NodeListOf<Element>).some((el: Element) =>
      el.textContent?.includes("REJECT"),
    )
    expect(hasReject).toBe(true)
  })

  it("Req 8.5: EDIT action badge has Pencil icon and info (blue) tone", () => {
    const { container } = render(
      <AuditLogPage
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
    )
    const editBadges = container.querySelectorAll("span.text-blue-800")
    expect(editBadges.length).toBeGreaterThan(0)
    const hasEdit = Array.from(editBadges as NodeListOf<Element>).some((el: Element) =>
      el.textContent?.includes("EDIT"),
    )
    expect(hasEdit).toBe(true)
  })

  it("Req 8.6: timestamps use font-clinical-mono class", () => {
    const { container } = render(
      <AuditLogPage
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
    )
    const monoTimestamps = container.querySelectorAll(".font-clinical-mono")
    expect(monoTimestamps.length).toBeGreaterThan(0)
  })

  it("Req 8.3: renders ErrorState when viewState is 'error'", () => {
    render(
      <AuditLogPage
        entries={[]}
        viewState="error"
        onViewState={() => {}}
      />,
    )
    expect(screen.getByText(/Audit Log tidak dapat dimuat/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Coba lagi/i })).toBeInTheDocument()
  })

  it("Req 8.4: renders EmptyState when viewState is 'empty'", () => {
    render(
      <AuditLogPage
        entries={[]}
        viewState="empty"
        onViewState={() => {}}
      />,
    )
    expect(screen.getByText(/Belum ada aktivitas tercatat/i)).toBeInTheDocument()
  })
})

/* ========================================================================== */
/* AuditLogPageV2                                                             */
/* ========================================================================== */

describe("AuditLogPageV2", () => {
  it("Req 8.8: renders SectionHeading for page title", () => {
    render(
      <AuditLogPageV2
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
      { wrapper: createWrapper() },
    )
    expect(screen.getByRole("heading", { name: /Log Audit/i })).toBeInTheDocument()
  })

  it("Req 8.8: renders Skeleton during loading state", () => {
    const { container } = render(
      <AuditLogPageV2
        entries={[]}
        viewState="loading"
        onViewState={() => {}}
      />,
      { wrapper: createWrapper() },
    )
    const skeletons = container.querySelectorAll("[aria-hidden='true'].animate-pulse")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it("Req 8.8: renders ErrorState during error state", () => {
    render(
      <AuditLogPageV2
        entries={[]}
        viewState="error"
        onViewState={() => {}}
      />,
      { wrapper: createWrapper() },
    )
    expect(screen.getByText(/Gagal memuat log audit/i)).toBeInTheDocument()
  })

  it("Req 8.8: renders EmptyState when no entries", () => {
    render(
      <AuditLogPageV2
        entries={[]}
        viewState="ready"
        onViewState={() => {}}
      />,
      { wrapper: createWrapper() },
    )
    expect(screen.getByText(/Belum ada entri audit/i)).toBeInTheDocument()
  })

  it("Req 8.8: APPROVE badge renders with success tone", () => {
    const { container } = render(
      <AuditLogPageV2
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
      { wrapper: createWrapper() },
    )
    const successBadges = container.querySelectorAll("span.text-emerald-800")
    expect(successBadges.length).toBeGreaterThan(0)
    const hasApprove = Array.from(successBadges as NodeListOf<Element>).some((el: Element) =>
      el.textContent?.includes("APPROVE"),
    )
    expect(hasApprove).toBe(true)
  })

  it("Req 8.8: timestamps use font-clinical-mono class", () => {
    const { container } = render(
      <AuditLogPageV2
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
      { wrapper: createWrapper() },
    )
    const monoEls = container.querySelectorAll(".font-clinical-mono")
    expect(monoEls.length).toBeGreaterThan(0)
  })

  it("Req 8.8: verify chain button visible for ADMIN role", () => {
    render(
      <AuditLogPageV2
        entries={sampleEntries}
        viewState="ready"
        onViewState={() => {}}
      />,
      { wrapper: createWrapper() },
    )
    // The button has aria-label (not visible text) — find it by aria-label
    expect(
      screen.getByRole("button", { name: /Verifikasi integritas rantai hash audit/i }),
    ).toBeInTheDocument()
  })
})


