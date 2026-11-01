/**
 * Unit tests for new UI components:
 *   - ShapContributionList (clinical.tsx)
 *   - DataPlaceholder (clinical.tsx)
 *   - NotFoundState (pages.tsx)
 *   - Button warning variant (primitives.tsx)
 *
 * Validates: Requirements 5.2, 5.4, 9.4, 6.1
 */
import { describe, it, expect, vi } from "vitest"
import { render } from "@testing-library/react"
import { screen } from "@testing-library/dom"
import userEvent from "@testing-library/user-event"

import {
  ShapContributionList,
  DataPlaceholder,
  type ShapContribution,
} from "../clinical"

import { Button } from "../primitives"

// ---------------------------------------------------------------------------
// Minimal stub for NotFoundState – pages.tsx pulls in TanStack Query and
// lots of app-level imports, so we import only the component we need via
// a targeted import to avoid pulling in side-effects.
// ---------------------------------------------------------------------------
import { NotFoundState } from "../pages"

/* ========================================================================== */
/* ShapContributionList                                                        */
/* ========================================================================== */

describe("ShapContributionList", () => {
  const validContributions: ShapContribution[] = [
    { feature: "Umur", shap_value: 0.45 },
    { feature: "Kreatinin", shap_value: -0.3 },
    { feature: "Tekanan Darah", shap_value: 0.2 },
  ]

  it("renders visual bars when contribution data is provided", () => {
    render(<ShapContributionList contributions={validContributions} />)

    // Each contribution creates a listitem
    const items = screen.getAllByRole("listitem")
    expect(items).toHaveLength(3)

    // Feature names are visible
    expect(screen.getByText("Umur")).toBeInTheDocument()
    expect(screen.getByText("Kreatinin")).toBeInTheDocument()
    expect(screen.getByText("Tekanan Darah")).toBeInTheDocument()
  })

  it("renders 'Belum tersedia' when contributions array is empty", () => {
    render(<ShapContributionList contributions={[]} />)
    expect(screen.getByText("Belum tersedia")).toBeInTheDocument()
  })

  it("renders 'Belum tersedia' when contributions is null/undefined", () => {
    // @ts-expect-error – intentionally passing null to test runtime guard
    render(<ShapContributionList contributions={null} />)
    expect(screen.getByText("Belum tersedia")).toBeInTheDocument()
  })

  it("renders 'Perlu verifikasi' when contributions are partial (missing feature/shap_value)", () => {
    const partialContributions: ShapContribution[] = [
      { feature: "Umur", shap_value: 0.45 },
      // shap_value is null → partial
      { feature: "Kreatinin", shap_value: null as unknown as number },
    ]
    render(<ShapContributionList contributions={partialContributions} />)
    expect(screen.getByText("Perlu verifikasi")).toBeInTheDocument()
  })

  it("renders 'Perlu verifikasi' when contributions have empty feature name", () => {
    const partialContributions: ShapContribution[] = [
      { feature: "", shap_value: 0.45 },
    ]
    render(<ShapContributionList contributions={partialContributions} />)
    expect(screen.getByText("Perlu verifikasi")).toBeInTheDocument()
  })

  it("renders model version label when modelVersion prop is provided", () => {
    render(
      <ShapContributionList
        contributions={validContributions}
        modelVersion="v2.1.0"
      />,
    )
    expect(screen.getByText(/Model:.*v2\.1\.0/)).toBeInTheDocument()
  })

  it("renders rule version label when ruleVersion prop is provided", () => {
    render(
      <ShapContributionList
        contributions={validContributions}
        ruleVersion="rules-2024-11"
      />,
    )
    expect(screen.getByText(/Aturan:.*rules-2024-11/)).toBeInTheDocument()
  })

  it("does not render version labels when neither is provided", () => {
    render(<ShapContributionList contributions={validContributions} />)
    expect(screen.queryByText(/Model:/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Aturan:/)).not.toBeInTheDocument()
  })

  it("labels positive contribution bar as 'meningkatkan'", () => {
    render(
      <ShapContributionList
        contributions={[{ feature: "Umur", shap_value: 0.5 }]}
      />,
    )
    expect(screen.getByText("meningkatkan")).toBeInTheDocument()
  })

  it("labels negative contribution bar as 'menurunkan'", () => {
    render(
      <ShapContributionList
        contributions={[{ feature: "Kreatinin", shap_value: -0.3 }]}
      />,
    )
    expect(screen.getByText("menurunkan")).toBeInTheDocument()
  })
})

/* ========================================================================== */
/* DataPlaceholder                                                             */
/* ========================================================================== */

describe("DataPlaceholder", () => {
  it("renders 'Belum tersedia' for availability=\"unavailable\"", () => {
    render(<DataPlaceholder availability="unavailable" />)
    expect(screen.getByText("Belum tersedia")).toBeInTheDocument()
  })

  it("renders 'Perlu verifikasi' for availability=\"needs_verification\"", () => {
    render(<DataPlaceholder availability="needs_verification" />)
    expect(screen.getByText("Perlu verifikasi")).toBeInTheDocument()
  })

  it("renders children for availability=\"available\"", () => {
    render(
      <DataPlaceholder availability="available">
        <span>Data lengkap</span>
      </DataPlaceholder>,
    )
    expect(screen.getByText("Data lengkap")).toBeInTheDocument()
    expect(screen.queryByText("Belum tersedia")).not.toBeInTheDocument()
    expect(screen.queryByText("Perlu verifikasi")).not.toBeInTheDocument()
  })

  it("does not render placeholder when availability is 'available'", () => {
    const { container } = render(
      <DataPlaceholder availability="available">
        <div>content</div>
      </DataPlaceholder>,
    )
    // No status role rendered (no placeholder div)
    const statusEls = container.querySelectorAll("[role='status']")
    expect(statusEls).toHaveLength(0)
  })

  it("applies a custom label when provided", () => {
    render(
      <DataPlaceholder availability="unavailable" label="Data tidak ada" />,
    )
    expect(screen.getByText("Data tidak ada")).toBeInTheDocument()
  })
})

/* ========================================================================== */
/* NotFoundState                                                               */
/* ========================================================================== */

describe("NotFoundState", () => {
  it("renders heading 'Halaman tidak ditemukan'", () => {
    render(<NotFoundState onReturn={() => {}} />)
    expect(screen.getByText("Halaman tidak ditemukan")).toBeInTheDocument()
  })

  it("renders 'Kembali ke Worklist' button", () => {
    render(<NotFoundState onReturn={() => {}} />)
    expect(
      screen.getByRole("button", { name: /Kembali ke Worklist/i }),
    ).toBeInTheDocument()
  })

  it("calls onReturn callback when button is clicked", async () => {
    const onReturn = vi.fn()
    render(<NotFoundState onReturn={onReturn} />)
    await userEvent.click(
      screen.getByRole("button", { name: /Kembali ke Worklist/i }),
    )
    expect(onReturn).toHaveBeenCalledOnce()
  })
})

/* ========================================================================== */
/* Button – warning variant                                                    */
/* ========================================================================== */

describe("Button", () => {
  it("warning variant applies amber background class (bg-amber-600)", () => {
    render(<Button variant="warning">Simpan</Button>)
    const btn = screen.getByRole("button", { name: /Simpan/i })
    expect(btn).toHaveClass("bg-amber-600")
  })

  it("warning variant applies white text", () => {
    render(<Button variant="warning">Test</Button>)
    const btn = screen.getByRole("button", { name: /Test/i })
    expect(btn).toHaveClass("text-white")
  })
})

