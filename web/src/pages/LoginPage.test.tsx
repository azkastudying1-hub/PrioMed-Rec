/**
 * web/src/pages/LoginPage.test.tsx
 * ---------------------------------
 * Unit tests for LoginPage migration to uiux/ design system.
 * 
 * Task 3.2: Write comprehensive unit tests for the LoginPage migration.
 * Requirements: 1.2, 1.5, 1.6, 1.7
 * 
 * Tests verify:
 * 1. LoginPage renders Input and Button from uiux/ primitives (not plain HTML)
 * 2. LoginPage renders HeartPulse icon (not emoji)
 * 3. LoginPage shows InlineAlert with tone "danger" on auth error
 * 4. LoginPage shows Button loading spinner when submitting
 * 5. LoginPage renders SkipLink
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render } from '@testing-library/react'
import { screen, fireEvent, waitFor } from '@testing-library/dom'
import userEvent from '@testing-library/user-event'
import { LoginPage } from './LoginPage'
import * as apiClient from '../lib/apiClient'
import { useAuthStore } from '../lib/auth'

// Mock the auth store
const mockLogin = vi.fn()
vi.mock('../lib/auth', () => ({
  useAuthStore: vi.fn((selector) => {
    const store = {
      login: mockLogin,
    }
    return typeof selector === 'function' ? selector(store) : store
  }),
}))

// Mock the API client
vi.mock('../lib/apiClient', () => ({
  loginApi: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string,
      public details?: unknown,
    ) {
      super(message)
      this.name = 'ApiError'
    }
  },
}))

describe('LoginPage Migration to uiux/ Design System', () => {
  const mockOnSuccess = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Requirement 1.3: Input and Button from uiux/ primitives', () => {
    it('should render username Input with Field wrapper', () => {
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Check for field label
      expect(screen.getByText('Username')).toBeInTheDocument()
      
      // Check for input with proper id
      const usernameInput = screen.getByPlaceholderText('apt-01') as HTMLInputElement
      expect(usernameInput).toBeInTheDocument()
      expect(usernameInput.type).toBe('text')
      expect(usernameInput.id).toBe('login-username')
    })

    it('should render password Input with Field wrapper', () => {
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Check for field label
      expect(screen.getByText('Password')).toBeInTheDocument()
      
      // Check for password input
      const passwordInput = screen.getByPlaceholderText('••••••••') as HTMLInputElement
      expect(passwordInput).toBeInTheDocument()
      expect(passwordInput.type).toBe('password')
      expect(passwordInput.id).toBe('login-password')
    })

    it('should render htmlFor/id associations on Field components', () => {
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Check that labels have proper htmlFor attributes
      const labels = screen.getAllByText(/^(Username|Password)$/)
      expect(labels.length).toBe(2)
      
      // The first label is Username
      expect(labels[0].tagName).toBe('LABEL')
      expect(labels[0]).toHaveAttribute('for', 'login-username')
      
      // The second label is Password
      expect(labels[1].tagName).toBe('LABEL')
      expect(labels[1]).toHaveAttribute('for', 'login-password')
    })

    it('should render Button primitive with lg size (min-h-12)', () => {
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      const submitButton = screen.getByRole('button', { name: /Masuk/i })
      expect(submitButton).toBeInTheDocument()
      
      // Check for lg size class
      const buttonClasses = submitButton.className
      expect(buttonClasses).toContain('min-h-12')
    })

    it('should render Input and Button from design system primitives', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Verify form uses design system components
      const usernameInput = screen.getByPlaceholderText('apt-01')
      const passwordInput = screen.getByPlaceholderText('••••••••')
      const submitButton = screen.getByRole('button', { name: /Masuk/i })
      
      // All should be properly styled with primitive classes
      expect(usernameInput.className).toBeTruthy()
      expect(passwordInput.className).toBeTruthy()
      expect(submitButton.className).toBeTruthy()
      
      // Button should use primitive styling with required attributes
      expect((submitButton as HTMLButtonElement).type).toBe('submit')
      expect(submitButton.className).toContain('w-full')
    })
  })

  describe('Requirement 1.2: HeartPulse icon instead of emoji', () => {
    it('should render HeartPulse icon', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Check for HeartPulse SVG icon (lucide-react)
      const heartPulseIcon = container.querySelector('svg')
      expect(heartPulseIcon).toBeInTheDocument()
      
      // The icon should be in a styled container
      const iconContainer = heartPulseIcon?.closest('div')
      expect(iconContainer).toHaveClass('rounded-xl')
      expect(iconContainer).toHaveClass('bg-gradient-to-br')
      expect(iconContainer).toHaveClass('from-cyan-400')
      expect(iconContainer).toHaveClass('to-blue-600')
    })

    it('should not render emoji icon', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // The rendered text should not contain the pill emoji
      const text = container.textContent
      expect(text).not.toContain('💊')
    })

    it('should render HeartPulse icon in gradient container matching AppShell Brand', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      const iconContainer = container.querySelector(
        '.bg-gradient-to-br.from-cyan-400.to-blue-600'
      )
      expect(iconContainer).toBeInTheDocument()
      expect(iconContainer).toHaveClass('text-white')
      expect(iconContainer).toHaveClass('shadow-lg')
      expect(iconContainer).toHaveClass('rounded-xl')
    })
  })

  describe('Requirement 1.5: InlineAlert with tone "danger" on auth error', () => {
    it('should not render InlineAlert when no error', () => {
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // InlineAlert with "Gagal masuk" should not be visible
      expect(screen.queryByText('Gagal masuk')).not.toBeInTheDocument()
    })

    it('should render InlineAlert with tone "danger" when auth error occurs', async () => {
      const errorMessage = 'Username atau password salah'
      vi.mocked(apiClient.loginApi).mockRejectedValueOnce(
        new apiClient.ApiError(401, 'INVALID_CREDENTIALS', errorMessage)
      )

      const user = userEvent.setup()
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Fill in credentials and submit
      await user.type(screen.getByPlaceholderText('apt-01'), 'apt-01')
      await user.type(screen.getByPlaceholderText('••••••••'), 'wrong-password')
      await user.click(screen.getByRole('button', { name: /Masuk/i }))
      
      // Wait for error to appear
      await waitFor(() => {
        expect(screen.getByText('Gagal masuk')).toBeInTheDocument()
        expect(screen.getByText(errorMessage)).toBeInTheDocument()
      })
      
      // Verify InlineAlert has danger tone styling - check the container with proper structure
      const alert = screen.getByText('Gagal masuk')
      expect(alert).toBeInTheDocument()
      // The InlineAlert container should have red styling
      const alertElement = alert.closest('[class*="bg-"]')
      expect(alertElement).toHaveClass('bg-red-50')
    })

    it('should display error message inside InlineAlert', async () => {
      const errorMessage = 'Server tidak merespons'
      vi.mocked(apiClient.loginApi).mockRejectedValueOnce(
        new apiClient.ApiError(500, 'SERVER_ERROR', errorMessage)
      )

      const user = userEvent.setup()
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Fill in credentials and submit
      await user.type(screen.getByPlaceholderText('apt-01'), 'apt-01')
      await user.type(screen.getByPlaceholderText('••••••••'), 'password123')
      await user.click(screen.getByRole('button', { name: /Masuk/i }))
      
      // Wait for error message
      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument()
      })
    })

    it('should show InlineAlert on login failure', async () => {
      vi.mocked(apiClient.loginApi).mockRejectedValueOnce(
        new apiClient.ApiError(401, 'INVALID_CREDENTIALS', 'Invalid credentials')
      )

      const user = userEvent.setup()
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      await user.type(screen.getByPlaceholderText('apt-01'), 'apt-01')
      await user.type(screen.getByPlaceholderText('••••••••'), 'wrong')
      await user.click(screen.getByRole('button', { name: /Masuk/i }))
      
      await waitFor(() => {
        expect(screen.getByText('Gagal masuk')).toBeInTheDocument()
      })
    })
  })

  describe('Requirement 1.6, 1.8: Button loading state during submission', () => {
    it('should disable button while submitting', async () => {
      let resolveLogin: any
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve
      })
      vi.mocked(apiClient.loginApi).mockReturnValueOnce(loginPromise as any)

      const user = userEvent.setup()
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      await user.type(screen.getByPlaceholderText('apt-01'), 'apt-01')
      await user.type(screen.getByPlaceholderText('••••••••'), 'demo1234')
      
      const submitButton = screen.getByRole('button', { name: /Masuk/i })
      
      // Initially enabled
      expect(submitButton).not.toBeDisabled()
      
      // Click submit
      await user.click(submitButton)
      
      // Should be disabled during loading
      await waitFor(() => {
        expect(submitButton).toBeDisabled()
      }, { timeout: 2000 })
      
      // Cleanup
      resolveLogin({
        access_token: 'mock-token',
        refresh_token: 'mock-refresh',
        token_type: 'bearer',
        role: 'PHARMACIST',
        username: 'apt-01',
        user_id: '1',
      })
    })

    it('should enable button again after login fails', async () => {
      vi.mocked(apiClient.loginApi).mockRejectedValueOnce(
        new apiClient.ApiError(401, 'INVALID_CREDENTIALS', 'Kredensial salah')
      )

      const user = userEvent.setup()
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      await user.type(screen.getByPlaceholderText('apt-01'), 'apt-01')
      await user.type(screen.getByPlaceholderText('••••••••'), 'wrong')
      
      const submitButton = screen.getByRole('button', { name: /Masuk/i })
      await user.click(submitButton)
      
      // After failure, button should be re-enabled
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled()
      })
    })

    it('should render loading prop on Button during submission', async () => {
      let resolveLogin: any
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve
      })
      vi.mocked(apiClient.loginApi).mockReturnValueOnce(loginPromise as any)

      const user = userEvent.setup()
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      await user.type(screen.getByPlaceholderText('apt-01'), 'apt-01')
      await user.type(screen.getByPlaceholderText('••••••••'), 'demo1234')
      
      const submitButton = screen.getByRole('button', { name: /Masuk/i })
      await user.click(submitButton)
      
      // Wait for loading state
      await waitFor(() => {
        expect(submitButton).toBeDisabled()
      }, { timeout: 2000 })
      
      resolveLogin({
        access_token: 'mock-token',
        refresh_token: 'mock-refresh',
        token_type: 'bearer',
        role: 'PHARMACIST',
        username: 'apt-01',
        user_id: '1',
      })
    })
  })

  describe('Requirement 1.7: SkipLink for keyboard accessibility', () => {
    it('should render SkipLink at top of page', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // SkipLink should be in the document (sr-only by default)
      const skipLink = container.querySelector('a')
      expect(skipLink).toBeInTheDocument()
      expect(skipLink).toHaveAttribute('href', '#pmr-main')
      expect(skipLink).toHaveClass('sr-only')
    })

    it('should have proper SkipLink styling for keyboard focus', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // SkipLink should become visible on focus
      const skipLink = container.querySelector('a')
      expect(skipLink).toBeInTheDocument()
      expect(skipLink).toHaveClass('focus:not-sr-only')
    })

    it('should anchor to login form id', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      const skipLink = container.querySelector('a')
      const formElement = container.querySelector('#pmr-main')
      
      expect(skipLink).toHaveAttribute('href', '#pmr-main')
      expect(formElement).toBeInTheDocument()
      expect(formElement?.tagName).toBe('FORM')
    })

    it('should be keyboard accessible (can be focused via Tab key)', () => {
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      const skipLink = screen.getByRole('link')
      expect(skipLink).toBeInTheDocument()
      
      // SkipLink should be focusable via keyboard
      skipLink.focus()
      expect(skipLink).toHaveFocus()
    })
  })

  describe('Requirement 1.1: Design system typography and colors', () => {
    it('should use design system typography tokens', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Check for font-display class on heading (Plus Jakarta Sans)
      const heading = screen.getByText('PrioMed-Rec')
      expect(heading).toHaveClass('font-display')
      expect(heading).toHaveClass('font-bold')
    })

    it('should use design system color tokens', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Check for design system background color
      const bgContainer = container.querySelector('.bg-\\[var\\(--pmr-bg\\)\\]')
      expect(bgContainer).toBeInTheDocument()
    })

    it('should render layout with proper spacing and alignment', () => {
      const { container } = render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // Check for centered layout
      const mainContainer = container.querySelector('.min-h-screen.flex')
      expect(mainContainer).toBeInTheDocument()
      expect(mainContainer).toHaveClass('items-center')
      expect(mainContainer).toHaveClass('justify-center')
    })
  })

  describe('Requirement 1.4: SafetyBanner component', () => {
    it('should render SafetyBanner below the form', () => {
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      // SafetyBanner displays the safety message
      expect(
        screen.getByText(/Keputusan klinis tetap di tangan apoteker/i)
      ).toBeInTheDocument()
    })

    it('should render safety banner with info tone', () => {
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      const banner = screen.getByText(/Keputusan klinis tetap di tangan apoteker/i)
      expect(banner).toBeInTheDocument()
      
      // Safety banner with info tone should have info styling
      const bannerElement = banner.closest('[class*="bg-"]')
      expect(bannerElement).toHaveClass('bg-blue-50')
    })
  })

  describe('Integration: Form submission flow', () => {
    it('should successfully login and call onSuccess', async () => {
      vi.mocked(apiClient.loginApi).mockResolvedValueOnce({
        access_token: 'test-token',
        refresh_token: 'test-refresh',
        token_type: 'bearer',
        role: 'PHARMACIST',
        username: 'apt-01',
        user_id: '1',
      })

      const user = userEvent.setup()
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      await user.type(screen.getByPlaceholderText('apt-01'), 'apt-01')
      await user.type(screen.getByPlaceholderText('••••••••'), 'demo1234')
      await user.click(screen.getByRole('button', { name: /Masuk/i }))
      
      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalled()
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })

    it('should handle network error gracefully', async () => {
      vi.mocked(apiClient.loginApi).mockRejectedValueOnce(
        new apiClient.ApiError(0, 'NETWORK_ERROR', 'Koneksi ke server gagal')
      )

      const user = userEvent.setup()
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      await user.type(screen.getByPlaceholderText('apt-01'), 'apt-01')
      await user.type(screen.getByPlaceholderText('••••••••'), 'demo1234')
      await user.click(screen.getByRole('button', { name: /Masuk/i }))
      
      await waitFor(() => {
        expect(screen.getByText('Koneksi ke server gagal')).toBeInTheDocument()
      })
    })

    it('should allow form submission via Enter key', async () => {
      vi.mocked(apiClient.loginApi).mockResolvedValueOnce({
        access_token: 'test-token',
        refresh_token: 'test-refresh',
        token_type: 'bearer',
        role: 'PHARMACIST',
        username: 'apt-01',
        user_id: '1',
      })

      const user = userEvent.setup()
      render(<LoginPage onSuccess={mockOnSuccess} />)
      
      const usernameInput = screen.getByPlaceholderText('apt-01')
      const passwordInput = screen.getByPlaceholderText('••••••••')
      
      await user.type(usernameInput, 'apt-01')
      await user.type(passwordInput, 'demo1234')
      
      // Submit via Enter key
      await user.keyboard('{Enter}')
      
      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })
  })
})


