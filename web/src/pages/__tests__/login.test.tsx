/**
 * web/src/pages/__tests__/login.test.tsx
 * ----------------------------------------
 * Unit tests for LoginPage migration to uiux/ design system primitives.
 * Requirements: 1.2, 1.5, 1.6, 1.7
 */

import { render } from "@testing-library/react"
import { screen, fireEvent, waitFor } from "@testing-library/dom"
import userEvent from "@testing-library/user-event"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { LoginPage } from "../LoginPage"
import { loginApi } from "../../lib/apiClient"

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../lib/apiClient", () => ({
  loginApi: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(msg: string) {
      super(msg)
      this.name = "ApiError"
    }
  },
}))

vi.mock("../../lib/auth", () => ({
  useAuthStore: vi.fn((selector: (s: { login: () => void }) => unknown) =>
    selector({ login: vi.fn() }),
  ),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLogin(onSuccess = vi.fn()) {
  return render(<LoginPage onSuccess={onSuccess} />)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("renders SkipLink (anchor with text 'Lewati ke konten utama')", () => {
    renderLogin()
    const skipLink = screen.getByRole("link", { name: /lewati ke konten utama/i })
    expect(skipLink).toBeInTheDocument()
    expect(skipLink).toHaveAttribute("href", "#pmr-main")
  })

  it("renders HeartPulse icon (svg element present, no emoji 💊 text)", () => {
    const { container } = renderLogin()
    // HeartPulse from lucide-react renders as an <svg>
    const svgs = container.querySelectorAll("svg")
    expect(svgs.length).toBeGreaterThan(0)
    // No pill emoji should appear anywhere in the page
    expect(container.textContent).not.toContain("💊")
  })

  it("renders username Input with id='login-username'", () => {
    renderLogin()
    const usernameInput = screen.getByRole("textbox", { name: /username/i })
    expect(usernameInput).toBeInTheDocument()
    expect(usernameInput).toHaveAttribute("id", "login-username")
    // Must be an <input>, not plain HTML without id
    expect(usernameInput.tagName).toBe("INPUT")
  })

  it("renders password Input with type='password' and id='login-password'", () => {
    renderLogin()
    // password inputs don't have implicit role, query by label
    const passwordInput = document.getElementById("login-password")
    expect(passwordInput).toBeInTheDocument()
    expect(passwordInput).toHaveAttribute("type", "password")
    expect(passwordInput).toHaveAttribute("id", "login-password")
    expect(passwordInput!.tagName).toBe("INPUT")
  })

  it("renders Masuk submit button", () => {
    renderLogin()
    const submitBtn = screen.getByRole("button", { name: /masuk/i })
    expect(submitBtn).toBeInTheDocument()
    expect(submitBtn).toHaveAttribute("type", "submit")
  })

  it("renders SafetyBanner ('Keputusan klinis tetap di tangan apoteker')", () => {
    renderLogin()
    expect(
      screen.getByText(/keputusan klinis tetap di tangan apoteker/i),
    ).toBeInTheDocument()
  })

  it("shows InlineAlert tone='danger' with title 'Gagal masuk' when loginApi throws", async () => {
    vi.mocked(loginApi).mockRejectedValueOnce(new Error("401 Unauthorized"))

    renderLogin()

    await userEvent.type(screen.getByRole("textbox", { name: /username/i }), "apt-01")
    await userEvent.type(document.getElementById("login-password")!, "wrongpass")

    fireEvent.submit(screen.getByRole("button", { name: /masuk/i }).closest("form")!)

    // InlineAlert with tone="danger" renders role="alert"
    const alert = await screen.findByRole("alert")
    expect(alert).toBeInTheDocument()
    expect(screen.getByText(/gagal masuk/i)).toBeInTheDocument()
  })

  it("submit button shows loading spinner (LoaderCircle) while submitting", async () => {
    // Never-resolving promise so we can inspect the loading state
    vi.mocked(loginApi).mockReturnValueOnce(new Promise(() => {}))

    const { container } = renderLogin()

    await userEvent.type(screen.getByRole("textbox", { name: /username/i }), "apt-01")
    await userEvent.type(document.getElementById("login-password")!, "demo1234")

    fireEvent.submit(screen.getByRole("button", { name: /masuk/i }).closest("form")!)

    // Wait for the loading state to appear
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /masuk/i })
      expect(btn).toBeDisabled()
    })

    // LoaderCircle renders as an SVG inside the button
    const submitBtn = screen.getByRole("button", { name: /masuk/i })
    const spinnerSvg = submitBtn.querySelector("svg")
    expect(spinnerSvg).toBeInTheDocument()
  })
})

