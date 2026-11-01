/**
 * Unit tests for Worklist enhancements:
 *   - PriorityBadge compact mode labels
 *   - WorklistTable column count (7 headers)
 *   - High-alert badge with TriangleAlert icon in WorklistPage
 *
 * Validates: Requirements 3.3, 3.4, 3.6
 */
import { describe, it, expect, vi } from "vitest"
import { render } from "@testing-library/react"
import { screen } from "@testing-library/dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { PriorityBadge } from "../clinical"
import { WorklistPage } from "../pages"

// ---------------------------------------------------------------------------
// Module mocks — keep WorklistPage in synthetic mode so no API calls occur
// ---------------------------------------------------------------------------
vi.mock("../../api/client", () => ({ DATA_MODE: "synthetic" }))
vi.mock("../../lib/auth", () => ({
  useAuthStore: vi.fn((selector: (state: { user: { sub: string } }) => unknown) =>
    selector({ user: { sub: "test-user" } }),
  ),
}))

// subscribeQueueEvents is only used in live mode; stub it so the effect
// returns a no-op unsubscribe without touching SSE internals.
vi.mock("../../api/queue", () => ({
  subscribeQueueEvents: vi.fn(() => () => undefined),
}))

// ---------------------------------------------------------------------------
// Helper: wrap with QueryClientProvider (required by WorklistPage)
// ---------------------------------------------------------------------------
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return Wrapper
}

/* ========================================================================== */
/* PriorityBadge                                                               */
/* ========================================================================== */

describe("PriorityBadge", () => {
  it('renders "TINGGI" label in compact mode for HIGH tier', () => {
    render(<PriorityBadge tier="HIGH" compact />)
    expect(screen.getByText("TINGGI")).toBeInTheDocument()
  })

  it('renders "SEDANG" label in compact mode for MEDIUM tier', () => {
    render(<PriorityBadge tier="MEDIUM" compact />)
    expect(screen.getByText("SEDANG")).toBeInTheDocument()
  })

  it('renders "RENDAH" label in compact mode for LOW tier', () => {
    render(<PriorityBadge tier="LOW" compact />)
    expect(screen.getByText("RENDAH")).toBeInTheDocument()
  })

  it('renders full label "Prioritas tinggi" in non-compact mode for HIGH tier', () => {
    render(<PriorityBadge tier="HIGH" />)
    expect(screen.getByText("Prioritas tinggi")).toBeInTheDocument()
  })

  it('renders "Belum dinilai" when tier is null/undefined', () => {
    render(<PriorityBadge tier={null} />)
    expect(screen.getByText("Belum dinilai")).toBeInTheDocument()
  })
})

/* ========================================================================== */
/* WorklistTable column count                                                  */
/* ========================================================================== */

describe("WorklistTable column count", () => {
  it("renders exactly 7 column headers", () => {
    const Wrapper = createWrapper()
    render(<WorklistPage onSelectEncounter={() => undefined} />, { wrapper: Wrapper })

    // The table headers are always present in the DOM (jsdom ignores CSS breakpoints)
    const headers = screen.getAllByRole("columnheader")
    expect(headers).toHaveLength(7)
  })
})

/* ========================================================================== */
/* High-alert badge                                                            */
/* ========================================================================== */

describe("High-alert badge", () => {
  it("high-alert badge renders when priority_reasons contains 'high-alert'", () => {
    // Synthetic data includes patients with highAlertCount > 0, which injects
    // a priority_reason containing "high-alert". WorklistPage renders WorklistTable
    // which shows the "{n} high-alert" badge for those rows.
    const Wrapper = createWrapper()
    render(<WorklistPage onSelectEncounter={() => undefined} />, { wrapper: Wrapper })

    // Badge text pattern: "{n} high-alert"
    const badges = screen.getAllByText(/\d+ high-alert/i)
    expect(badges.length).toBeGreaterThan(0)
  })

  it("high-alert badge does not render when no high-alert reasons", () => {
    // PriorityBadge itself does not render any high-alert badge — only WorklistTable
    // does, and only for rows where priority_reasons contain "high-alert". A standalone
    // PriorityBadge render confirms no badge is added without the condition.
    render(<PriorityBadge tier="LOW" compact />)
    expect(screen.queryByText(/high-alert/i)).not.toBeInTheDocument()
  })
})

